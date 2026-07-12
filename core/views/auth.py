"""
Authentication views for OIUEEI.

Handles magic link authentication and RSVP-based actions.
RSVP serves as an intermediary for ALL email communications to avoid
exposing real codes (booking_code, thing_code, etc.) in URLs.
"""

import logging
import threading

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, User
from core.models.booking import BookingPeriod
from core.models.event import Event
from core.models.notification import InAppNotification
from core.serializers import RequestLinkSerializer, UserSerializer
from core.services.booking_service import finalize_booking_decision
from core.services.email_service import send_invite_rejected_email, send_magic_link_email
from core.utils import get_client_ip, redact_email

security_logger = logging.getLogger("security")

# The refresh cookie is scoped to the auth namespace (not just /refresh/) so it
# also reaches /auth/logout/ — otherwise logout never receives the refresh token
# and can't blacklist it. Set, refreshed and cleared at this exact path.
REFRESH_COOKIE_PATH = "/api/v1/auth/"


def _set_auth_cookies(response, refresh):
    """Set HttpOnly JWT cookies on the response."""
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    is_secure = not settings.DEBUG

    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        max_age=3600,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        max_age=7 * 86400,
        path=REFRESH_COOKIE_PATH,
    )


def _send_magic_link(email, magic_link, collection_headline=None):
    """Send the magic-link email, off the request thread in production.

    ``collection_headline`` (pop-in / share-link join) is forwarded to
    ``send_magic_link_email`` so the subject can name the joined collection; it
    is ``None`` for ``/login`` and the plain onboarding pop-in, which keep the
    generic welcome subject.

    request-link only sends for a registered email, so a synchronous SMTP round
    trip would make "registered" responses measurably slower than "not
    registered" ones — a timing oracle for email enumeration (L10). When
    ``EMAIL_SEND_ASYNC`` is on (production), dispatch to a daemon thread so the
    response returns in constant time regardless. The send touches no DB
    (magic-link email is Cat. 1 / mandatory) and already swallows its own errors.
    Elsewhere it sends synchronously to keep tests deterministic.
    """
    if getattr(settings, "EMAIL_SEND_ASYNC", False):
        threading.Thread(
            target=send_magic_link_email,
            args=(email, magic_link, collection_headline),
            daemon=True,
        ).start()
    else:
        send_magic_link_email(email, magic_link, collection_headline)


def email_ratelimit_key(group, request):
    """Per-account rate-limit key: the requested email, lowercased.

    Complements the per-IP limit so a single mailbox can't be flooded with
    magic-link emails from rotating IPs. Empty/malformed requests share one
    bucket (they 400 in the body anyway).
    """
    try:
        return (request.data.get("email") or "").strip().lower()
    except Exception:
        return ""


class RequestLinkView(APIView):
    """
    POST /api/v1/auth/request-link/
    Request a magic link for authentication.
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    @method_decorator(ratelimit(key=email_ratelimit_key, rate="5/h", method="POST", block=True))
    def post(self, request):
        serializer = RequestLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        ip = get_client_ip(request)

        unified_message = (
            "If this email is registered, your magic link is on its way — "
            "check your inbox, and your spam folder just in case."
        )

        # INVITE-ONLY: Only existing users can request magic links
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't log the address of a non-registered email (M5) — just the IP.
            security_logger.warning(f"Magic link request for unregistered email from IP {ip}")
            return Response(
                {"message": unified_message},
                status=status.HTTP_200_OK,
            )

        security_logger.info(f"Magic link requested for {redact_email(email)} from IP {ip}")

        # Create RSVP
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=email,
        )

        # Send magic link email
        magic_link_base = getattr(settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/verify")
        magic_link = f"{magic_link_base}/{rsvp.token}"

        _send_magic_link(email, magic_link)

        return Response(
            {"message": unified_message},
            status=status.HTTP_200_OK,
        )


class VerifyLinkView(APIView):
    """
    GET  /api/v1/auth/verify/{token}/ — resolve an RSVP action.
    POST /api/v1/auth/verify/{token}/ — commit a confirm-required action.

    Handles all RSVP-based actions:
    - MAGIC_LINK: Verify magic link and return JWT token
    - COLLECTION_INVITE: Accept collection invitation and return JWT token
    - COLLECTION_REJECT: Decline a collection invitation
    - BOOKING_ACCEPT: Accept a booking (all thing types)
    - BOOKING_REJECT: Reject a booking (all thing types)

    Booking accept/reject are irreversible and authenticate no one, so they must
    never fire from a bare GET — an email link-scanner or a page prefetch/refresh
    could otherwise auto-decide a hold. For those actions GET only *previews*
    (no mutation); the frontend renders a confirmation screen whose button issues
    a POST that commits. The login/invite actions stay on GET (a scanner that
    consumes one only forces a fresh link; it decides nothing on the user's
    behalf).

    Authorisation is the unguessable ~134-bit URL token itself — the bearer
    credential — so the view carries no authenticators: that keeps the POST free
    of DRF's SessionAuthentication CSRF gate (no ambient cookie grants authority
    here) and none of the handlers read ``request.user``.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    # Actions that GET must not commit — only an explicit POST may.
    CONFIRM_ACTIONS = frozenset({RSVP.Action.BOOKING_ACCEPT, RSVP.Action.BOOKING_REJECT})

    def _resolve_rsvp(self, request, token):
        """Look up and expiry-check an RSVP token.

        Returns ``(rsvp, None)`` on success or ``(None, Response)`` on failure.
        """
        ip = get_client_ip(request)
        try:
            rsvp = RSVP.objects.get(token=token)
        except RSVP.DoesNotExist:
            security_logger.warning(f"Invalid RSVP code attempted from IP {ip}")
            return None, Response(
                {"error": "Invalid or expired link"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not rsvp.is_valid():
            security_logger.warning(f"Expired RSVP code used from IP {ip}")
            rsvp.delete()
            return None, Response(
                {"error": "Link expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return rsvp, None

    def _dispatch(self, request, rsvp):
        """Route a validated RSVP to its action handler (commits the action)."""
        action_handlers = {
            "MAGIC_LINK": self._handle_magic_link,
            "COLLECTION_INVITE": self._handle_collection_invite,
            "COLLECTION_REJECT": self._handle_collection_reject,
            "BOOKING_ACCEPT": self._handle_booking_accept,
            "BOOKING_REJECT": self._handle_booking_reject,
        }
        handler = action_handlers.get(rsvp.action)
        if not handler:
            ip = get_client_ip(request)
            security_logger.warning(f"Unknown RSVP action '{rsvp.action}' from IP {ip}")
            rsvp.delete()
            return Response(
                {"error": "Unknown action"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return handler(request, rsvp)

    def _preview(self, rsvp):
        """Non-mutating description of a confirm-required action.

        Lets the frontend render a confirmation screen without touching the
        booking or consuming the RSVP — the commit happens on POST.
        """
        data = {"action": rsvp.action, "requires_confirmation": True}
        booking = BookingPeriod.objects.filter(code=rsvp.target_code).first()
        if booking and booking.thing_code:
            data["thing_headline"] = booking.thing_code.headline
        return Response(data, status=status.HTTP_200_OK)

    @method_decorator(ratelimit(key="ip", rate="10/m", method="GET", block=True))
    def get(self, request, token):
        rsvp, error = self._resolve_rsvp(request, token)
        if error:
            return error
        if rsvp.action in self.CONFIRM_ACTIONS:
            return self._preview(rsvp)
        return self._dispatch(request, rsvp)

    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True))
    def post(self, request, token):
        rsvp, error = self._resolve_rsvp(request, token)
        if error:
            return error
        return self._dispatch(request, rsvp)

    def _authenticate_user(self, request, rsvp):
        """Authenticate a user via RSVP: validate and mint a JWT.

        Returns (user, refresh, user_data) on success, or a Response on failure.
        Auth is JWT-cookie based — we deliberately do NOT open a Django session
        (no ``login()``): nothing in the API relies on it, and the admin site has
        its own session, so a shadow session would only be extra attack surface.
        """
        user = rsvp.user_code
        if not user:
            rsvp.delete()
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user.update_last_activity()

        refresh = RefreshToken.for_user(user)

        user_data = UserSerializer(user).data
        return user, refresh, user_data

    def _handle_magic_link(self, request, rsvp):
        """Handle magic link authentication."""
        ip = get_client_ip(request)

        result = self._authenticate_user(request, rsvp)
        if isinstance(result, Response):
            return result
        user, refresh, user_data = result

        # A pop-in / share-link magic link can carry the collection the visitor
        # came to join (``target_code``, stamped by PopInView). Drop them straight
        # onto it after login instead of the generic /welcome — they were already
        # added to its invites (private share) or it is PUBLIC (login-to-act).
        invited_collection = None
        if rsvp.target_code and Collection.objects.filter(code=rsvp.target_code).exists():
            invited_collection = rsvp.target_code

        rsvp.delete()

        security_logger.info(f"User {user.code} logged in via magic link from IP {ip}")

        response_data = {
            "action": "MAGIC_LINK",
            "user": user_data,
        }
        if invited_collection:
            response_data["invited_collection"] = invited_collection

        response = Response(response_data, status=status.HTTP_200_OK)
        _set_auth_cookies(response, refresh)
        return response

    def _handle_collection_invite(self, request, rsvp):
        """Handle collection invitation acceptance."""
        result = self._authenticate_user(request, rsvp)
        if isinstance(result, Response):
            return result
        user, refresh, user_data = result

        # Process collection invitation
        invited_collection = None
        if rsvp.target_code:
            try:
                collection = Collection.objects.get(code=rsvp.target_code)
                collection.invites.add(user)
                Event.log(Event.Kind.MEMBER_JOINED, actor=user, collection=collection)
                invited_collection = rsvp.target_code
            except Collection.DoesNotExist:
                pass  # Collection was deleted, ignore

        # Delete this RSVP and the sibling reject RSVP (invalidate both links)
        RSVP.objects.filter(
            user_code=user,
            action=RSVP.Action.COLLECTION_REJECT,
            target_code=rsvp.target_code,
        ).delete()
        rsvp.delete()

        response_data = {
            "action": "COLLECTION_INVITE",
            "user": user_data,
        }
        if invited_collection:
            response_data["invited_collection"] = invited_collection

        response = Response(response_data, status=status.HTTP_200_OK)
        _set_auth_cookies(response, refresh)
        return response

    def _handle_collection_reject(self, request, rsvp):
        """Handle collection invitation rejection."""
        user = rsvp.user_code
        if not user:
            rsvp.delete()
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Send rejection notification to collection owner
        if rsvp.target_code:
            try:
                collection = Collection.objects.get(code=rsvp.target_code)
                invitee_name = user.display_name
                send_invite_rejected_email(
                    invitee_name,
                    collection.headline,
                    collection.owner.email,
                )
                InAppNotification.objects.create(
                    user=collection.owner,
                    type=InAppNotification.Type.INVITE_REJECTED,
                    payload={
                        "collection_headline": collection.headline,
                        "invitee_name": invitee_name,
                    },
                )
            except Collection.DoesNotExist:
                pass  # Collection was deleted, ignore

        # Delete both accept and reject RSVPs to invalidate all links
        RSVP.objects.filter(
            user_code=user,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=rsvp.target_code,
        ).delete()
        rsvp.delete()

        return Response(
            {
                "action": "COLLECTION_REJECT",
                "message": "Invitation declined",
            },
            status=status.HTTP_200_OK,
        )

    def _handle_booking_action(self, rsvp, accepted):
        """Shared handler for booking accept/reject via RSVP."""
        booking_code = rsvp.target_code

        try:
            booking = BookingPeriod.objects.get(code=booking_code)
        except BookingPeriod.DoesNotExist:
            rsvp.delete()
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not booking.is_valid():
            rsvp.delete()
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thing = booking.thing_code
        if not thing:
            rsvp.delete()
            return Response(
                {"error": "Thing not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        thing = finalize_booking_decision(booking, accepted=accepted)

        # A concurrent request (this link racing the in-app action, or the
        # sibling link) already transitioned this booking — the service no-ops.
        if thing is None:
            rsvp.delete()
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build response
        action_name = "BOOKING_ACCEPT" if accepted else "BOOKING_REJECT"
        message = "Booking accepted" if accepted else "Booking rejected"
        response_data = {
            "action": action_name,
            "message": message,
            "thing_headline": thing.headline,
        }
        if accepted:
            if booking.start_date:
                response_data["start_date"] = str(booking.start_date)
            if booking.end_date:
                response_data["end_date"] = str(booking.end_date)

        return Response(response_data, status=status.HTTP_200_OK)

    def _handle_booking_accept(self, request, rsvp):
        """Handle booking accept action for all thing types."""
        return self._handle_booking_action(rsvp, accepted=True)

    def _handle_booking_reject(self, request, rsvp):
        """Handle booking reject action for all thing types."""
        return self._handle_booking_action(rsvp, accepted=False)


class PopInView(APIView):
    """
    POST /api/v1/auth/pop-in/
    Open-door onboarding: get_or_create a user, add them to onboarding
    collections, and send a magic link. No prior invitation required.

    Accepts optional `share_token` (string, 22 chars). If present and valid,
    the user is added to that collection's invitees instead of (or in
    addition to) the onboarding collections. Invalid tokens are silently
    ignored — the unified response prevents probing the token space.

    Also accepts optional `collection_code`: a visitor acting on a PUBLIC
    collection joins it by code (the public "link" is the collection URL, not a
    share token). Only PUBLIC, ACTIVE collections qualify — a code can never be
    used to slip into a PRIVATE, invite-only collection — and an unknown or
    non-public code is silently ignored, same as an invalid share token.
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    @method_decorator(ratelimit(key=email_ratelimit_key, rate="5/h", method="POST", block=True))
    def post(self, request):
        serializer = RequestLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        share_token = (request.data.get("share_token") or "").strip() or None
        collection_code = (request.data.get("collection_code") or "").strip() or None
        ip = get_client_ip(request)

        user, created = User.objects.get_or_create(email=email)
        if created:
            Event.log(Event.Kind.USER_JOINED, actor=user)

        # Join the relevant collection (if any), else fall back to the onboarding
        # collections. ``joined`` short-circuits that fallback once we've added
        # the user to a specific collection.
        joined = False
        # When the visitor joins a specific collection (owner's share-token link, or
        # a PUBLIC collection by code) stamp it on the magic-link RSVP so
        # VerifyLinkView drops them straight onto that collection after login,
        # instead of the generic /welcome. Empty for the plain onboarding fallback.
        # ``join_headline`` mirrors that collection's headline so the magic-link
        # subject can name it; it stays None for the plain onboarding fallback.
        target_collection_code = ""
        join_headline = None

        # 1) An owner's share-token link (bearer credential).
        if share_token:
            try:
                shared_collection = Collection.objects.get(
                    share_token=share_token, status=Collection.Status.ACTIVE
                )
            except Collection.DoesNotExist:
                shared_collection = None

            if shared_collection is not None:
                shared_collection.invites.add(user)
                Event.log(Event.Kind.MEMBER_JOINED, actor=user, collection=shared_collection)
                joined = True
                target_collection_code = shared_collection.code
                join_headline = shared_collection.headline

        # 2) Login-to-act on a PUBLIC collection: the visitor joins it by code.
        # Strictly PUBLIC + ACTIVE — a code is never a way into a PRIVATE
        # collection — and an unknown/non-public code is silently ignored so the
        # unified response can't be used to probe which codes exist.
        if not joined and collection_code:
            try:
                public_collection = Collection.objects.get(
                    code=collection_code,
                    status=Collection.Status.ACTIVE,
                    visibility=Collection.Visibility.PUBLIC,
                )
            except Collection.DoesNotExist:
                public_collection = None

            if public_collection is not None:
                public_collection.invites.add(user)
                Event.log(Event.Kind.MEMBER_JOINED, actor=user, collection=public_collection)
                joined = True
                target_collection_code = public_collection.code
                join_headline = public_collection.headline

        # 3) No specific target — add to the open demo/onboarding collections.
        if not joined:
            onboarding_collections = Collection.objects.filter(is_onboarding=True)
            for collection in onboarding_collections:
                collection.invites.add(user)
                Event.log(Event.Kind.MEMBER_JOINED, actor=user, collection=collection)

        rsvp = RSVP.objects.create(
            user_code=user, user_email=email, target_code=target_collection_code
        )
        magic_link_base = getattr(settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/verify")
        magic_link = f"{magic_link_base}/{rsvp.token}"
        _send_magic_link(email, magic_link, collection_headline=join_headline)

        security_logger.info(
            f"Pop-in request for {redact_email(email)} from IP {ip} "
            f"(new_user={created}, joined_collection={joined})"
        )

        return Response(
            {"message": "Check your email — we've sent you a magic link to join OIUEEI."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    GET /api/v1/auth/me/
    Get current authenticated user.
    """

    permission_classes = [IsAuthenticated]

    # Called on every app load; setting the csrftoken cookie here guarantees the
    # SPA has a token to send as X-CSRFToken on subsequent unsafe requests (which
    # CookieJWTAuthentication now enforces). GET is safe, so this is not itself
    # CSRF-checked.
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        user = request.user
        user.update_last_activity()
        serializer = UserSerializer(user)
        return Response(serializer.data)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Logout the current user.

    Optionally accepts a refresh token to blacklist it.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Try to blacklist the refresh token from cookie or body
        refresh_token = request.COOKIES.get("refresh_token") or request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except (AttributeError, TokenError):
                pass  # Blacklist not enabled or token invalid

        # No Django session to clear — auth is JWT-cookie only (login() is never
        # called), so logout just blacklists the refresh token and drops cookies.
        response = Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )
        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path=REFRESH_COOKIE_PATH)
        # Also clear any refresh cookie still stored at the previous narrower path
        # so pre-deploy sessions aren't left with a stranded cookie.
        response.delete_cookie("refresh_token", path="/api/v1/auth/refresh/")
        return response


class TokenRefreshView(APIView):
    """
    POST /api/v1/auth/refresh/
    Refresh JWT tokens using the refresh_token cookie.
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True))
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"error": "No refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            old_refresh = RefreshToken(refresh_token)
            # Rotate: create new refresh token and blacklist old one. is_active=True
            # so a deactivated user's refresh token can't keep minting fresh ones —
            # falls into the same 401 + cookie-clear path as User.DoesNotExist below.
            new_refresh = RefreshToken.for_user(
                User.objects.get(
                    code=old_refresh[settings.SIMPLE_JWT["USER_ID_CLAIM"]], is_active=True
                )
            )
            try:
                old_refresh.blacklist()
            except AttributeError:
                pass  # Blacklist not enabled
        except (TokenError, User.DoesNotExist):
            response = Response(
                {"error": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response.delete_cookie("access_token", path="/")
            response.delete_cookie("refresh_token", path=REFRESH_COOKIE_PATH)
            # Also clear any refresh cookie still stored at the previous narrower
            # path so pre-deploy sessions aren't left with a stranded cookie.
            response.delete_cookie("refresh_token", path="/api/v1/auth/refresh/")
            return response

        response = Response({"message": "Token refreshed"}, status=status.HTTP_200_OK)
        _set_auth_cookies(response, new_refresh)
        return response
