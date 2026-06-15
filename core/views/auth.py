"""
Authentication views for OIUEEI.

Handles magic link authentication and RSVP-based actions.
RSVP serves as an intermediary for ALL email communications to avoid
exposing real codes (booking_code, thing_code, etc.) in URLs.
"""

import logging

from django.conf import settings
from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, User
from core.models.booking import BookingPeriod
from core.models.notification import InAppNotification
from core.serializers import RequestLinkSerializer, UserSerializer
from core.services.booking_service import finalize_booking_decision
from core.services.email_service import send_invite_rejected_email, send_magic_link_email
from core.utils import get_client_ip

security_logger = logging.getLogger("security")


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
        path="/api/v1/auth/refresh/",
    )


class RequestLinkView(APIView):
    """
    POST /api/v1/auth/request-link/
    Request a magic link for authentication.
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        serializer = RequestLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        ip = get_client_ip(request)

        unified_message = "If this email is registered, a magic link has been sent."

        # INVITE-ONLY: Only existing users can request magic links
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            security_logger.warning(
                f"Magic link request for non-existent user: {email} from IP {ip}"
            )
            return Response(
                {"message": unified_message},
                status=status.HTTP_200_OK,
            )

        security_logger.info(f"Magic link requested for {email} from IP {ip}")

        # Create RSVP
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=email,
        )

        # Send magic link email
        magic_link_base = getattr(settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/verify")
        magic_link = f"{magic_link_base}/{rsvp.code}"

        send_magic_link_email(email, magic_link)

        return Response(
            {"message": unified_message},
            status=status.HTTP_200_OK,
        )


class VerifyLinkView(APIView):
    """
    GET /api/v1/auth/verify/{rsvp_code}/
    Process an RSVP action.

    Handles all RSVP-based actions:
    - MAGIC_LINK: Verify magic link and return JWT token
    - COLLECTION_INVITE: Accept collection invitation and return JWT token
    - BOOKING_ACCEPT: Accept a booking (all thing types)
    - BOOKING_REJECT: Reject a booking (all thing types)
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="10/m", method="GET", block=True))
    def get(self, request, rsvp_code):
        ip = get_client_ip(request)

        try:
            rsvp = RSVP.objects.get(code=rsvp_code)
        except RSVP.DoesNotExist:
            security_logger.warning(f"Invalid RSVP code attempted from IP {ip}")
            return Response(
                {"error": "Invalid or expired link"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not rsvp.is_valid():
            security_logger.warning(f"Expired RSVP code used from IP {ip}")
            rsvp.delete()
            return Response(
                {"error": "Link expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Route to appropriate handler based on action type
        action_handlers = {
            "MAGIC_LINK": self._handle_magic_link,
            "COLLECTION_INVITE": self._handle_collection_invite,
            "COLLECTION_REJECT": self._handle_collection_reject,
            "BOOKING_ACCEPT": self._handle_booking_accept,
            "BOOKING_REJECT": self._handle_booking_reject,
        }

        handler = action_handlers.get(rsvp.action)
        if not handler:
            security_logger.warning(f"Unknown RSVP action '{rsvp.action}' from IP {ip}")
            rsvp.delete()
            return Response(
                {"error": "Unknown action"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return handler(request, rsvp)

    def _authenticate_user(self, request, rsvp):
        """Authenticate a user via RSVP: validate, generate JWT, login, delete RSVP.

        Returns (user, refresh, user_data) on success, or a Response on failure.
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
        login(request, user)

        user_data = UserSerializer(user).data
        return user, refresh, user_data

    def _handle_magic_link(self, request, rsvp):
        """Handle magic link authentication."""
        ip = get_client_ip(request)

        result = self._authenticate_user(request, rsvp)
        if isinstance(result, Response):
            return result
        user, refresh, user_data = result

        rsvp.delete()

        security_logger.info(f"User {user.email} logged in via magic link from IP {ip}")

        response = Response(
            {
                "action": "MAGIC_LINK",
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )
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
                invitee_name = user.name or user.email
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
            if booking.delivery_date:
                response_data["delivery_date"] = str(booking.delivery_date)
            if booking.quantity:
                response_data["quantity"] = booking.quantity

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
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        serializer = RequestLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        share_token = (request.data.get("share_token") or "").strip() or None
        ip = get_client_ip(request)

        user, created = User.objects.get_or_create(email=email)

        # If a valid share_token is provided, join that collection.
        # Otherwise, fall back to onboarding collections.
        joined_via_share = False
        if share_token:
            try:
                shared_collection = Collection.objects.get(
                    share_token=share_token, status=Collection.Status.ACTIVE
                )
            except Collection.DoesNotExist:
                shared_collection = None

            if shared_collection is not None:
                shared_collection.invites.add(user)
                joined_via_share = True

        if not joined_via_share:
            onboarding_collections = Collection.objects.filter(is_onboarding=True)
            for collection in onboarding_collections:
                collection.invites.add(user)

        rsvp = RSVP.objects.create(user_code=user, user_email=email)
        magic_link_base = getattr(settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/verify")
        magic_link = f"{magic_link_base}/{rsvp.code}"
        send_magic_link_email(email, magic_link)

        security_logger.info(
            f"Pop-in request for {email} from IP {ip} "
            f"(new_user={created}, via_share={joined_via_share})"
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

        # Logout from Django session
        logout(request)

        response = Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )
        response.delete_cookie("access_token", path="/")
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
            # Rotate: create new refresh token and blacklist old one
            new_refresh = RefreshToken.for_user(
                User.objects.get(code=old_refresh[settings.SIMPLE_JWT["USER_ID_CLAIM"]])
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
            response.delete_cookie("refresh_token", path="/api/v1/auth/refresh/")
            return response

        response = Response({"message": "Token refreshed"}, status=status.HTTP_200_OK)
        _set_auth_cookies(response, new_refresh)
        return response
