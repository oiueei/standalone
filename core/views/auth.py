"""
Authentication views for OIUEEI.

Handles magic link authentication and RSVP-based actions.
RSVP serves as an intermediary for ALL email communications to avoid
exposing real codes (booking_code, thing_code, etc.) in URLs.
"""

import logging
import threading

from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, InvitationProposal, InvitationRecord, Thing, User
from core.models.booking import BookingPeriod
from core.models.event import Event
from core.models.notification import InAppNotification
from core.serializers import RequestLinkSerializer, UserSerializer
from core.services.account_service import delete_account
from core.services.booking_service import finalize_booking_decision, receives_booking_requests
from core.services.creator_policy import capabilities_for
from core.services.email_service import (
    resolve_email_language,
    send_account_delete_email,
    send_collection_welcome_doc_email,
    send_invite_rejected_email,
    send_magic_link_email,
)
from core.services.invitation_service import (
    _ALREADY_ASKED_MESSAGE,
    InvitationAlreadyAsked,
    ProposalAlreadyDecided,
    approve_proposal,
    proposal_approval_blocked,
    reject_proposal,
    resolve_invitation,
)
from core.services.join_quota import consume_join_quota, join_quota_exhausted
from core.services.team import managers_ready_collections
from core.utils import doc_asset_url, get_client_ip, redact_email, safe_next_path
from core.views._helpers import approval_refusal_response, body_dict, refusal_body

security_logger = logging.getLogger("security")

# The refresh cookie is scoped to the auth namespace (not just /refresh/) so it
# also reaches /auth/logout/ — otherwise logout never receives the refresh token
# and can't blacklist it. Set, refreshed and cleared at this exact path.
REFRESH_COOKIE_PATH = "/api/v1/auth/"


def _set_auth_cookies(response, refresh):
    """Set HttpOnly JWT cookies on the response.

    ``Secure`` follows ``SESSION_COOKIE_SECURE`` — the switch Django's own cookies
    already read, which ``production.py`` sets to True alongside
    ``CSRF_COOKIE_SECURE`` and the SSL redirect. It used to be ``not DEBUG``,
    which gives the right answer for both environments this repository ships and
    the wrong one for a shape neither of them is: a deployment running with
    ``DEBUG=True`` behind HTTPS would have served **these two cookies alone**
    without the flag, while the session and CSRF cookies beside them kept it.

    That is worth a line because these are the credentials — an access token and
    a 7-day refresh token — and because the failure is invisible: the app works,
    the cookies are set, and the only difference is that a downgraded request
    would carry them in clear. Reading the same setting as everything else means
    a deployment turns cookie security on in one place, not two.
    """
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    is_secure = getattr(settings, "SESSION_COOKIE_SECURE", False)

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


def _send_magic_link(email, magic_link, collection_headline=None, user=None, collection=None):
    """Send the magic-link email, off the request thread in production.

    ``collection_headline`` (set when this is a join) is forwarded to
    ``send_magic_link_email`` so the subject can name the joined collection; it
    is ``None`` for ``/login`` and the plain onboarding pop-in, which keep the
    generic welcome subject.

    The language is resolved **here**, from the user and (on a join) the collection
    they are joining, and passed down — the email sender must not look the
    recipient up: request-link only sends for a registered email, so a DB round
    trip (or a synchronous SMTP one) would make "registered" responses measurably
    slower than "not registered" ones — a timing oracle for email enumeration.
    When ``EMAIL_SEND_ASYNC`` is on (production), dispatch to a daemon
    thread so the response returns in constant time regardless. The send touches no
    DB (magic-link email is Cat. 1 / mandatory) and already swallows its own
    errors. Elsewhere it sends synchronously to keep tests deterministic.
    """
    lang = resolve_email_language(user=user, collection=collection)
    if getattr(settings, "EMAIL_SEND_ASYNC", False):
        threading.Thread(
            target=send_magic_link_email,
            args=(email, magic_link, collection_headline, lang),
            daemon=True,
        ).start()
    else:
        send_magic_link_email(email, magic_link, collection_headline, lang)


def _tell_the_team_of_a_join(collection, user):
    """One in-app notice per curator (founder and co-curators) for a new member.

    Joining is never blocked or approved, in any mode and through any door; whoever
    runs the group just hears of it. The one joining is left out when they are on
    the team. ``member_name`` is the bare ``name``. Someone who joined by a public
    link has given only an address, so the notice then carries it as ``member_email``
    and names them by it: the team already reads every member's address in the
    members list, and nobody else is ever sent this notice.
    """
    for curator in [collection.owner, *collection.co_owners.all()]:
        if curator.code == user.code:
            continue
        InAppNotification.objects.create(
            user=curator,
            type=InAppNotification.Type.MEMBER_JOINED,
            payload={
                "collection_code": collection.code,
                "collection_headline": collection.headline,
                "member_name": user.name,
                **({} if user.name else {"member_email": user.email}),
            },
        )


def _join_collection(collection, user, source=""):
    """Add ``user`` to ``collection``'s members and run the first-join side effects.

    Every join path funnels through here: accepting an invitation, a share-token
    pop-in, joining a PUBLIC collection to act on it, and the onboarding
    collections. The first time this user becomes a member it logs the
    MEMBER_JOINED event and emails the collection's welcome & rules PDF, if the
    owner set one.

    "First time" is decided **before** the M2M add: the add is idempotent and
    re-runs on every login-to-act pop-in (a share-token re-visit, a public
    collection re-join, repeat onboarding), so an existing member re-entering
    must be a no-op — they must not be sent the document again, and must not log
    a second MEMBER_JOINED, which would count one person as many joins and
    inflate the guest→creator funnel any report over this log measures.

    A member who left is out of ``invites``, so a genuine re-join after a
    MEMBER_LEFT logs again — which is what it is.

    ``source`` records which door this join came through, so a report over the
    Event log can answer "which of these actually brings people in?" — the
    question that decides whether any of them earns its place. Every caller
    passes one; a blank means a row written before this existed.

    The founder is an FK, never an ``invites`` row: when ``user`` is the owner this
    is a no-op (no membership, no event, no counter, no document), and the caller
    still lands them on the collection, which the owner can always read.
    """
    if collection.is_owner(user.code):
        return
    already_member = collection.invites.filter(code=user.code).exists()
    collection.invites.add(user)
    if already_member:
        return

    # Whatever door they came through, an invitation sent to this address is
    # answered now (a no-op when there never was one).
    resolve_invitation(collection, user.email, InvitationRecord.State.ACCEPTED)

    # The member counter only moves on a genuine join, and this is the single
    # funnel every join path goes through (invite acceptance, share token,
    # public login-to-act, onboarding) — so one hook covers all of them. The
    # matching ceiling is enforced earlier, when invitations are *sent*.
    collection.note_capacity("invites")

    Event.log(Event.Kind.MEMBER_JOINED, actor=user, collection=collection, source=source)
    _tell_the_team_of_a_join(collection, user)
    if not collection.welcome_doc:
        return
    send_collection_welcome_doc_email(
        collection.headline,
        doc_asset_url(collection.welcome_doc),
        user.email,
        collection=collection,
    )


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
            # Don't log the address of a non-registered email — just the IP.
            security_logger.warning(f"Magic link request for unregistered email from IP {ip}")
            return Response(
                {"message": unified_message},
                status=status.HTTP_200_OK,
            )

        security_logger.info(f"Magic link requested for {redact_email(email)} from IP {ip}")

        # Where the person was going when the session ran out. Read straight from
        # the body, *not* through ``RequestLinkSerializer``: a bad ``next`` is
        # dropped without a word and the answer does not change, whereas a 400
        # would tell a caller which requests carried a bad one for no reason.
        # ``safe_next_path`` is the only door — the SPA's own check is defence in
        # depth. It rides on the RSVP, not in browser storage, because the link is
        # often opened in another browser (webmail, the phone's mail app).
        next_path = safe_next_path(body_dict(request).get("next"))

        # Create RSVP. ``origin=LOGIN`` tells VerifyLinkView this is a returning
        # user, not a first visit — the new-visitor landing never applies again.
        #
        # This INSERT is the one timing signal that remains: it only runs for a
        # registered address, so those responses are a hair slower than the early
        # return above. Known and accepted, not overlooked. Closing it is not the
        # one-line move it looks like — the delta is everything past the early
        # return, this write *and* the thread spawn, so equalising would mean
        # writing the RSVP from the daemon thread and spawning that thread on both
        # paths: a DB write with no connection cleanup, and a failed INSERT
        # downgraded from a 500 into a silent no-email. The rate limits (5/m per
        # IP, 5/h per email) cap sampling far below what averaging a sub-millisecond
        # difference out of network noise would take, so the trade isn't worth it.
        # Carrying ``next`` adds nothing to that delta: it is the same INSERT, with
        # one more value in a column it already wrote.
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=email,
            origin=RSVP.Origin.LOGIN,
            context={"next": next_path} if next_path else {},
        )

        # Send magic link email
        magic_link_base = getattr(settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/verify")
        magic_link = f"{magic_link_base}/{rsvp.token}"

        _send_magic_link(email, magic_link, user=user)

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

    # Actions that GET must not commit — only an explicit POST may. Account
    # deletion goes further than the bookings: the frontend never auto-commits
    # it from the load effect either — the person must press an explicit
    # on-page button (see VerifyPage).
    CONFIRM_ACTIONS = frozenset(
        {
            RSVP.Action.BOOKING_ACCEPT,
            RSVP.Action.BOOKING_REJECT,
            RSVP.Action.ACCOUNT_DELETE,
            # Approving MAILS a third party who has not been contacted yet, and
            # declining closes a member's request — neither may fire from a bare
            # GET, or a mail client's link scanner would decide who joins the
            # group on the owner's behalf.
            RSVP.Action.PROPOSAL_APPROVE,
            RSVP.Action.PROPOSAL_REJECT,
        }
    )

    # Where the SPA sends the user after a successful login (``landing`` in the
    # response). Server-decided, so it survives a cleared localStorage.
    LANDING_COLLECTION = "collection"
    LANDING_HOME = "home"
    LANDING_PATH = "path"

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
            "ACCOUNT_DELETE": self._handle_account_delete,
            "PROPOSAL_APPROVE": self._handle_proposal_approve,
            "PROPOSAL_REJECT": self._handle_proposal_reject,
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
        if rsvp.action == RSVP.Action.ACCOUNT_DELETE:
            # What the confirmation screen states: whose account, and how much
            # goes with it. The token bearer is the account owner reading their
            # own data — the same trust level as a magic link.
            user = rsvp.user_code
            data["name"] = user.name
            data["email"] = user.email
            data["collections"] = user.owned_collections.count()
            data["things"] = user.owned_things.count()
            return Response(data, status=status.HTTP_200_OK)
        if rsvp.action in (RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT):
            # Nothing but the two keys above. A GET is what a mail client's link
            # scanner issues, and the proposed address, the proposer's private
            # note, and the proposer's own name (whose display fallback is *their*
            # email) are precisely what this flow promises never to expose — the
            # person suggested does not know they were suggested, and if the
            # answer is no they never will. The SPA auto-commits the decision with
            # a POST (real JS a scanner never runs) and reads the invited address
            # from that response, so it never needed any of it here.
            return Response(data, status=status.HTTP_200_OK)
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

    @staticmethod
    def _kind_of(code):
        """A collection's kind, for the response that lands the SPA on it — the app
        builds the address ``/{kind}/{code}`` from it."""
        return Collection.objects.filter(code=code).values_list("kind", flat=True).first()

    def _solo_collection(self, user):
        """``(code, kind)`` of the user's one real ACTIVE collection, or None.

        "Real" leaves out the demonstration collections (``is_onboarding``,
        the ones an open door joins people to): somebody who peeked at the demo
        and then founded or joined a group of their own belongs in that group,
        not on Home, and somebody who only has the demo has no group to be
        taken to. Owned, invited and co-curated all count — a
        co-curator is always in ``invites`` too. A collection that is not ACTIVE
        does not count.

        Two rows are enough to answer "exactly one?", so the query stops there.
        """
        rows = list(
            Collection.objects.filter(
                Q(owner=user) | Q(invites=user),
                status=Collection.Status.ACTIVE,
                is_onboarding=False,
            )
            .distinct()
            .values_list("code", "kind")[:2]
        )
        return rows[0] if len(rows) == 1 else None

    @staticmethod
    def _join_when_pressed(rsvp, user):
        """The collection a magic link takes the person to, or None — joining them first
        when the link was a join and that is still allowed.

        ``JoinView`` no longer joins when the address is typed (it may be somebody
        else's): it writes ``join_source`` — and, for a share link, the
        ``share_token`` it used — on the RSVP, and the click lands here. The join is
        **checked again**, because the world moves between the send and the click:

        * by share link: the collection is still ACTIVE **and its ``share_token`` is
          still the one the link was sent with** — a curator who rotated or revoked it
          in between withdrew exactly this invitation;
        * by public collection: it is still ACTIVE **and** PUBLIC.

        Not allowed → nobody is joined and ``None`` comes back, so the general landing
        rule answers instead of a collection that would 403. Allowed → the join goes
        through ``_join_collection`` like every other door, so the ``MEMBER_JOINED``
        event (with its source) and the welcome document happen now, once.

        A link with a ``target_code`` and **no** ``join_source`` is not a pending join:
        one sent before the join moved to the click (a magic link lives 24 hours), whose
        person was already joined then, or one a deployment's own door stamped. It only
        lands, as it always did.
        """
        if not rsvp.target_code:
            return None
        collection = Collection.objects.filter(
            code=rsvp.target_code, status=Collection.Status.ACTIVE
        ).first()
        if collection is None:
            return None

        context = rsvp.context or {}
        source = context.get("join_source")
        if source is None:
            return collection.code

        if source == Event.Source.SHARE:
            sent_with = context.get("share_token")
            allowed = bool(sent_with) and sent_with == collection.share_token
        elif source == Event.Source.PUBLIC:
            allowed = collection.visibility == Collection.Visibility.PUBLIC
        else:
            allowed = False
        if not allowed:
            return None

        _join_collection(collection, user, source=Event.Source(source))
        return collection.code

    def _handle_magic_link(self, request, rsvp):
        """Handle magic link authentication.

        Decides where the SPA lands the user (``landing``), which used to be a
        client-side ``seenWelcome`` localStorage heuristic — and since logout
        cleared that key, every re-login looked like a first visit and dumped
        returning users on /welcome. The rules, in order:

        1. The link carries a collection (``target_code``: a share-token or
           public-collection join) → that collection. They joined it to get
           there: the join is made **here, at the click**, once checked again
           (``_join_when_pressed``) — not when the address was typed. A link
           whose join is no longer allowed carries no collection, and the rules
           below answer.
        2. Otherwise a link that remembers where the person was going
           (``context["next"]``, stamped by ``RequestLinkView``) → that path
           (``"path"``). It outranks the single-collection rule: the email they
           came from named a page. A link born at an open door (``origin ==
           POPIN``) never follows one: whoever walks in through it has no session
           that ran out on a page, and a ``next`` written there by another route
           must not steer them.
        3. Otherwise → their one real ACTIVE collection when they have exactly
           one (owned, invited or co-curated, **not** a demonstration
           collection), else home. That holds for a link from an open door too:
           somebody who only peeked at the demo goes to Home, and somebody who
           also has a group of their own goes to it.

        There is no ``"welcome"`` landing any more: an open
        door's visitor used to be sent to the deployment's ``aboutPath`` page,
        and now gets the same answer as anyone else, from what they actually
        belong to.
        """
        ip = get_client_ip(request)

        result = self._authenticate_user(request, rsvp)
        if isinstance(result, Response):
            return result
        user, refresh, user_data = result

        # A join magic link carries the collection the visitor came for
        # (``target_code``, stamped by JoinView). The click is what joins them to
        # it — and only if that is still allowed — and then drops them onto it.
        # If the collection went INACTIVE, was made private, or its share link
        # was rotated or revoked between the send and the click, nobody is joined
        # and the rules below take over naturally, instead of landing the user on
        # a page that 403s.
        invited_collection = self._join_when_pressed(rsvp, user)
        origin = rsvp.origin
        # The thing the visitor was trying to act on when they hit the join wall
        # (JoinView stashes it here); resolved to a landing detail below.
        context_thing = (rsvp.context or {}).get("thing_code")
        # Checked again here even though ``RequestLinkView`` already did: the value
        # comes from our own table, but a ``context`` written by another route
        # must not be able to send a session anywhere. Read before the delete.
        next_path = safe_next_path((rsvp.context or {}).get("next"))

        rsvp.delete()

        security_logger.info(f"User {user.code} logged in via magic link from IP {ip}")

        response_data = {
            "action": "MAGIC_LINK",
            "user": user_data,
        }
        if invited_collection:
            response_data["landing"] = self.LANDING_COLLECTION
            response_data["collection"] = invited_collection
            response_data["collection_kind"] = self._kind_of(invited_collection)
            # Kept for compatibility: an older SPA read the landing collection
            # from this field, and it still marks that the link carried a target.
            response_data["invited_collection"] = invited_collection
            # Land on the exact thing, not the collection index, when the join
            # came from an action on one — and it is still a non-hidden thing in
            # that collection (it may have been hidden or moved out meanwhile).
            if (
                context_thing
                and Thing.objects.filter(code=context_thing, collections__code=invited_collection)
                .exclude(status=Thing.Status.INACTIVE)
                .exists()
            ):
                response_data["thing"] = context_thing
        elif next_path and origin != RSVP.Origin.POPIN:
            response_data["landing"] = self.LANDING_PATH
            response_data["path"] = next_path
        else:
            solo = self._solo_collection(user)
            if solo:
                response_data["landing"] = self.LANDING_COLLECTION
                response_data["collection"], response_data["collection_kind"] = solo
            else:
                response_data["landing"] = self.LANDING_HOME

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
                # An invitation the owner sent themselves, or one they approved
                # from a member's recommendation — `deliver_invitation` stamps
                # the RSVP so the two funnels stay distinguishable.
                _join_collection(
                    collection,
                    user,
                    source=(
                        Event.Source.RECOMMENDATION
                        if (rsvp.context or {}).get("via") == "recommendation"
                        else Event.Source.INVITE
                    ),
                )
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
            # Same landing contract as the magic link, for symmetry. An invitation
            # always lands on its collection — unless it was deleted meanwhile.
            "landing": self.LANDING_COLLECTION if invited_collection else self.LANDING_HOME,
        }
        if invited_collection:
            response_data["collection"] = invited_collection
            response_data["collection_kind"] = self._kind_of(invited_collection)
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
                resolve_invitation(collection, user.email, InvitationRecord.State.DECLINED)
                invitee_name = user.display_name
                send_invite_rejected_email(
                    invitee_name,
                    collection.headline,
                    collection.owner.email,
                    collection=collection,
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

    def _handle_booking_action(self, request, rsvp, accepted):
        """Shared handler for booking accept/reject via RSVP.

        The link was minted to **one manager** of the thing (its owner, or a
        curator of a PROPRIETARY collection it sits in — see
        ``send_booking_request_notifications``), so the decision is theirs. But
        it is judged when the link is *used*, not when it was sent: a co-curator
        demoted or removed after the email, a collection turned COMMUNITY, or
        the thing moved out of it, must not be able to decide with the old link.
        """
        booking_code = rsvp.target_code

        # The thing comes with its collections manager-ready: the authority check
        # below and the decision's notice to the whole team both walk them.
        try:
            booking = (
                BookingPeriod.objects.select_related("thing_code")
                .prefetch_related(
                    Prefetch("thing_code__collections", queryset=managers_ready_collections())
                )
                .get(code=booking_code)
            )
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

        # `thing_code` is NOT NULL with CASCADE: a booking whose thing is gone is gone
        # too, so the "Booking not found" above is the only way a missing thing shows.
        thing = booking.thing_code

        # Authority is checked again here, at the click. The link outlives the
        # role that earned it (72h): the owner always may, anyone else only
        # while they still run the thing. A refused link is burnt, so it cannot
        # be tried again.
        if not (rsvp.user_code_id == booking.owner_code_id or thing.can_manage(rsvp.user_code_id)):
            ip = get_client_ip(request)
            security_logger.warning(
                f"Booking {booking.code} decision refused for {rsvp.user_code_id}: "
                f"no longer manages the thing, from IP {ip}"
            )
            rsvp.delete()
            # The code lets the page say why in the reader's language ("you no longer
            # run this thing"), where a bare 403 read as an expired invitation; the
            # English sentence stays the same for a client that does not know it.
            return Response(
                {"error": "Not authorized", "code": "no_longer_manages"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # The decision is signed by whoever the emailed link was minted to —
        # the owner's own, or a co-curator's — passed explicitly rather than
        # left to the service's owner fallback.
        thing = finalize_booking_decision(booking, accepted=accepted, decided_by=rsvp.user_code)

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

    def _handle_account_delete(self, request, rsvp):
        """Commit the right-to-erasure confirmation.

        Reached only via POST (``CONFIRM_ACTIONS``), fired by the explicit
        confirm button on the page the email link lands on — never by a link
        scanner's GET, never auto-committed from a load effect. The RSVP is not
        deleted here: it cascades away with the user row.
        """
        user = rsvp.user_code
        ip = get_client_ip(request)
        user_code = delete_account(user)
        security_logger.info(f"Account {user_code} erased via RSVP confirmation from IP {ip}")
        response = Response(
            {"action": "ACCOUNT_DELETE", "message": "Account deleted"},
            status=status.HTTP_200_OK,
        )
        # The session died with the account — drop the auth cookies so the SPA
        # doesn't keep presenting credentials for a user that no longer exists.
        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path=REFRESH_COOKIE_PATH)
        return response

    def _handle_proposal_action(self, request, rsvp, approve):
        """Commit the owner's answer to a member's suggestion (POST only).

        The RSVP was addressed to the owner, so holding the link *is* the
        authorisation — the same standing an invitation's accept link has. It is
        consumed either way, so a forwarded email can't be replayed.

        The link was minted to **one curator** (``create_proposal`` sends the
        question to the whole team), and it is judged when it is *used*, not when
        it was sent: a co-curator demoted or removed after the email must not
        decide with the old link. A refused link is burnt and the suggestion stays
        pending for whoever still runs the group.
        """
        proposal = InvitationProposal.objects.filter(code=rsvp.target_code).first()
        if not proposal or not proposal.is_valid():
            rsvp.delete()
            return Response(
                refusal_body("This suggestion is no longer pending", code="proposal_not_pending"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not proposal.collection.is_curator(rsvp.user_code_id):
            security_logger.warning(
                f"Proposal {proposal.code} decision refused for {rsvp.user_code_id}: "
                f"no longer runs the collection, from IP {get_client_ip(request)}"
            )
            rsvp.delete()
            return Response(
                {"error": "Not authorized", "code": "no_longer_manages"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if approve:
            # The same two guards the in-app approval applies. Without them the
            # emailed link was a way around the operator's daily invitation cap
            # and the collection's member ceiling — the owner clicking the link
            # in their mail client instead of the button in the app.
            #
            # The RSVP is deliberately left alive: the answer is "not now", so
            # the link has to still work tomorrow. Declining is never blocked —
            # saying no sends the proposer one email and adds nobody.
            blocked = proposal_approval_blocked(proposal)
            if blocked:
                reason, code = blocked
                # ``retryable`` (added by ``approval_refusal_response``) is the
                # difference between a refusal the owner may come back to and
                # every other one this view can give: a 400 here and a 400 for a
                # suggestion that is genuinely gone look identical, and the SPA
                # showed both as "invalid or expired link". An address already
                # invited is the exception: the link is not consumed but waiting
                # changes nothing, so it carries no ``retryable``.
                return approval_refusal_response(reason, code)
            decide, message = approve_proposal, "Invitation sent"
        else:
            decide, message = reject_proposal, "Suggestion declined"
        try:
            decide(proposal)
        except InvitationAlreadyAsked:
            # Another invitation got in between the check above and the send; the
            # reservation of the decision went with the transaction, and the link
            # is left alive like the other refusals of an approval.
            return approval_refusal_response(_ALREADY_ASKED_MESSAGE, 400)
        except ProposalAlreadyDecided:
            # Another curator settled it between the check above and now.
            rsvp.delete()
            return Response(
                refusal_body("This suggestion is no longer pending", code="proposal_not_pending"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Every curator's links and notices went with the decision
        # (``clear_proposal_traces``, called by approve/reject).
        return Response(
            {
                "action": rsvp.action,
                "message": message,
                "email": proposal.email,
                "collection_headline": proposal.collection.headline,
            },
            status=status.HTTP_200_OK,
        )

    def _handle_proposal_approve(self, request, rsvp):
        return self._handle_proposal_action(request, rsvp, approve=True)

    def _handle_proposal_reject(self, request, rsvp):
        return self._handle_proposal_action(request, rsvp, approve=False)

    def _handle_booking_accept(self, request, rsvp):
        """Handle booking accept action for all thing types."""
        return self._handle_booking_action(request, rsvp, accepted=True)

    def _handle_booking_reject(self, request, rsvp):
        """Handle booking reject action for all thing types."""
        return self._handle_booking_action(request, rsvp, accepted=False)


class JoinView(APIView):
    """
    POST /api/v1/auth/join/
    Ask to join a collection you were pointed at, and get a magic link back.

    **Nothing is joined here — the click joins.** The address is only typed, and
    it may be somebody else's: joining on submit put a stranger into a group
    they had never heard of, and sent them its welcome document, because
    someone else typed their email. So this view creates the account (the RSVP
    needs one) with **no membership at all**, stamps the collection on the
    magic-link RSVP and writes into its `context` what the click will need —
    `join_source` and, for a share link, the `share_token` used — and the
    membership is made by `VerifyLinkView` when the link is pressed, after
    checking the join is still allowed. That is what an emailed invitation has
    always done (`_handle_collection_invite`). A signed-in reader's own join
    (`CollectionJoinView`, `ShareJoinView`) stays immediate: there the person
    pressing is the person joining.

    Two doors reach it, and both are the product: an owner's `share_token`
    (the `/share/:token` link they handed out) and a PUBLIC collection's
    `collection_code` (login-to-act — a visitor acting on a collection anyone
    can read joins it on the way in). Without one of those there is nowhere to
    go, and nothing is created; see `_resolve_target`.

    `share_token` (22 chars) is the owner's bearer link. `collection_code` names
    a PUBLIC, ACTIVE collection — never a PRIVATE one, so a code can't be used
    to slip into an invite-only group. Either being unknown, revoked or pointing
    at an INACTIVE collection is silently ignored: the unified response is what
    stops a single answer distinguishing the two cases.

    That guarantee covers the **body**, not the clock — the nothing-to-join path
    creates nothing, so it also returns faster than the one that writes. What
    keeps the spaces unwalkable is their size (22 chars; 36^6 codes) and the two
    rate limits below, not constant time. See `core/views/CLAUDE.md` for why
    padding this is the wrong fix.

    **Neither door is a secret, and that is what `COLLECTION_JOINS_PER_DAY`
    guards.** A PUBLIC collection's code sits in its own URL and a share token is
    passed around by design, so anyone may ask this deployment to mail a magic
    link to any address they type — a relay pointed at the operator's sending
    domain. The two limits below cap one IP and one victim; they say nothing
    about many IPs mailing many strangers once each, which is the actual shape.
    The per-collection daily cap does, and a refusal returns the same unified
    response as everything else here. Off by default; see
    `core/services/join_quota.py`. The cap stops mail to strangers, so an address
    already in the group (its founder, a co-curator, a member) is neither refused
    by it nor charged to it: they are only coming back in, and the 5/h per address
    limit still bounds them. The response is the same for them too.

    **Language is never taken from the request.** This used to accept the
    visitor's current UI language and stamp it onto a newly-created user, so
    their very first magic link would speak it. That stamp was permanent: an
    accidental browser language, never a deliberate choice, then outranked
    the collection's own language for every future email to that member
    (`User.language` always wins over `Collection.language` in
    `resolve_email_language`), with no way back short of them visiting their
    profile. A brand-new user's `language` now
    stays blank, so `_send_magic_link` (already passed `collection=
    join_collection`) resolves this very first email the same way every later
    one is: the collection's own language when the member has none of their
    own set.
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
        thing_code = (request.data.get("thing_code") or "").strip() or None
        ip = get_client_ip(request)

        # Resolve where this address would be joining BEFORE creating anything.
        #
        # `get_or_create` used to run first, so a POST carrying nothing but an
        # email created a real account whatever happened next. On a deployment
        # with no onboarding collections — a fresh install, anyone who never ran
        # `seed_demo` — that account joined nothing and led nowhere: an open
        # registration door into an empty room, on an otherwise invite-only
        # product. Nothing about the response ever said so.
        join_collection, join_source = self._resolve_target(share_token, collection_code)

        if join_collection is None:
            # Nowhere to join: create no user, no RSVP, send no email — and
            # answer exactly as if we had. The response body must stay
            # indistinguishable from the successful one; that it returns sooner
            # is a known and accepted difference (see the class docstring).
            security_logger.info(
                f"Join request for {redact_email(email)} from IP {ip} (no target, nothing created)"
            )
            return self._unified_response()

        # Somebody already in the group is only coming back in, not being
        # admitted: the cap stops mail to strangers, so it neither refuses nor
        # charges them. Looked up without creating anything; the 5/h per address
        # limit still bounds them. Co-curators are in `invites` too.
        already_inside = self._is_inside(join_collection, email)

        if not already_inside and join_quota_exhausted(join_collection.code):
            # This collection has taken its day's joins. Create nothing, send
            # nothing — and answer exactly as if we had, for the same reason the
            # no-target path does: "that collection is over its limit" would
            # confirm that this token or code names a real, joinable collection,
            # which is the one thing the unified response exists to withhold.
            #
            # So the visitor cannot be told, and the operator is told instead —
            # the same shape as the capacity alarms, where the tripwire reports
            # to whoever set it and never to whoever tripped it.
            security_logger.warning(
                f"Join refused for {redact_email(email)} from IP {ip}: "
                f"collection {join_collection.code} is over COLLECTION_JOINS_PER_DAY"
            )
            return self._unified_response()

        user, created = User.objects.get_or_create(email=email)
        if created:
            Event.log(Event.Kind.USER_JOINED, actor=user)

        # Nobody is joined here. The address is only *typed* — it may be somebody
        # else's — so the membership waits for the click on the magic link, which
        # only the mailbox's owner can make (see `VerifyLinkView._join_when_pressed`).
        # What the click needs to decide is written on the RSVP: which door this
        # was and, for a share link, the token that was used, so a link rotated or
        # revoked in between can be told apart from the one still in force.
        join_context = {"join_source": join_source.value}
        if join_source == Event.Source.SHARE:
            join_context["share_token"] = share_token

        # The visitor may have been trying to act on one specific thing (they
        # clicked "Reserve" on a card). Remember it so the magic link lands them
        # back on *that* thing rather than the collection index. Only a
        # non-hidden thing that actually lives in the joined collection
        # qualifies; anything else silently falls back to the collection landing.
        if (
            thing_code
            and join_collection.things.filter(
                code=thing_code,
                status__in=[Thing.Status.ACTIVE, Thing.Status.TAKEN],
            ).exists()
        ):
            join_context["thing_code"] = thing_code

        # The collection is stamped on the magic-link RSVP so VerifyLinkView drops
        # them straight onto it after login. There is always one now: this point
        # is unreachable without a resolved target.
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=email,
            target_code=join_collection.code,
            origin=RSVP.Origin.POPIN,
            context=join_context,
        )
        magic_link_base = getattr(settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/verify")
        magic_link = f"{magic_link_base}/{rsvp.token}"
        _send_magic_link(
            email,
            magic_link,
            collection_headline=join_collection.headline,
            user=user,
            collection=join_collection,
        )
        # Charged after the send is dispatched, so a join that raised before
        # reaching it costs the collection nothing. In production the send is a
        # daemon thread, so "dispatched" is as far as this can honestly count.
        if not already_inside:
            consume_join_quota(join_collection.code)

        security_logger.info(
            f"Join request for {redact_email(email)} from IP {ip} "
            f"(new_user={created}, collection={join_collection.code})"
        )

        return self._unified_response()

    @staticmethod
    def _is_inside(collection, email):
        """Whether this address already belongs to the group: its founder or a member.

        Creates nothing. A co-curator is always in `invites`, so it covers them too.
        """
        existing = User.objects.filter(email=email).first()
        if existing is None:
            return False
        return (
            collection.owner_id == existing.code
            or collection.invites.filter(code=existing.code).exists()
        )

    @staticmethod
    def _resolve_target(share_token, collection_code):
        """The collection this request joins, and where it came from — or `(None, None)`.

        Both lookups are deliberately narrow, and both fail silently: an
        invalid token or an unknown code is answered exactly like a valid one,
        so neither can be used to probe which collections exist.
        """
        # 1) An owner's share-token link (a bearer credential).
        if share_token:
            shared = Collection.objects.filter(
                share_token=share_token, status=Collection.Status.ACTIVE
            ).first()
            if shared is not None:
                return shared, Event.Source.SHARE

        # 2) Login-to-act on a PUBLIC collection: the visitor joins it by code.
        # Strictly PUBLIC + ACTIVE — a code is never a way into a PRIVATE,
        # invite-only collection.
        if collection_code:
            public = Collection.objects.filter(
                code=collection_code,
                status=Collection.Status.ACTIVE,
                visibility=Collection.Visibility.PUBLIC,
            ).first()
            if public is not None:
                return public, Event.Source.PUBLIC

        return None, None

    @staticmethod
    def _unified_response():
        """The one answer this endpoint ever gives.

        Written once, and returned from both the joined and the nothing-to-join
        paths, so the two cannot drift into being distinguishable — which is the
        only thing keeping this endpoint from being an account oracle.
        """
        return Response(
            {"message": "Check your email — we've sent you a magic link to join OIUEEI."},
            status=status.HTTP_200_OK,
        )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """
    GET /api/v1/auth/me/
    Get current authenticated user, and what this deployment lets them create.
    """

    permission_classes = [IsAuthenticated]

    # Called on every app load; setting the csrftoken cookie here guarantees the
    # SPA has a token to send as X-CSRFToken on subsequent unsafe requests (which
    # CookieJWTAuthentication now enforces). GET is safe, so this is not itself
    # CSRF-checked.
    #
    # Decorating `dispatch`, not `get`, is load-bearing. DRF's `APIView.dispatch()`
    # runs `check_permissions()` — which raises before `get()` is ever called — for
    # an unauthenticated request. `ensure_csrf_cookie` only forces the cookie by
    # calling `get_token()` from inside the view it wraps, so decorating `get()`
    # meant that call, and the cookie, never happened for exactly the visitor who
    # needs it most: someone freshly arrived with no session yet, whose first-ever
    # hit here 401s (`App.jsx`'s app-load warm-up fires before the magic-link GET
    # that authenticates them completes). That silently broke every unsafe request
    # from a brand-new visitor's first page — reserving a slot, asking a question —
    # until some *later*, already-authenticated call to this endpoint (e.g. one
    # HomePage happens to make) finally set it. A visitor whose magic link drops
    # them straight onto one thing may never make that later call at all.
    def get(self, request):
        user = request.user
        user.update_last_activity()
        data = UserSerializer(user).data
        # Not a field on UserSerializer: what someone may create is a property of
        # the deployment they are on, not of the person — the same account would
        # get a different answer elsewhere. It rides on this endpoint because the
        # SPA already calls it on every app load, and it comes from the same
        # `capabilities()` the create endpoints refuse with, so the UI can only
        # offer what the API would accept.
        data["capabilities"] = capabilities_for(user).as_dict()
        # Whether "Requests to me" has anything to show this person (something of
        # theirs can be asked for). The account menu reads it when it opens, so the
        # browser keeps nothing new about it.
        data["receives_requests"] = receives_booking_requests(user)
        return Response(data)


class AccountDeleteRequestView(APIView):
    """
    POST /api/v1/auth/delete-account/

    Step one of the right-to-erasure flow: the authenticated user asks to
    delete their account. Nothing is deleted here — this only (re)creates the
    single-use ``ACCOUNT_DELETE`` RSVP (24h expiry) and emails its confirmation
    link (Cat. 1, always delivered). The deletion itself happens in
    ``VerifyLinkView._handle_account_delete``, on an explicit POST from the
    page that link lands on — so a stolen browser session alone can't erase an
    account; the attacker would also need the mailbox.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="3/h", method="POST", block=True))
    def post(self, request):
        user = request.user
        ip = get_client_ip(request)
        # Resend-safe: at most one live confirmation link per account.
        RSVP.objects.filter(user_code=user, action=RSVP.Action.ACCOUNT_DELETE).delete()
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
            action=RSVP.Action.ACCOUNT_DELETE,
        )
        send_account_delete_email(user, rsvp.action_link())
        security_logger.info(
            f"Account deletion requested for {user.code} from IP {ip} (confirmation emailed)"
        )
        return Response(
            {"message": "Confirmation email sent"},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Log the current user out. Unauthenticated by design — best-effort, always 200.

    Optionally accepts a refresh token to blacklist it.
    """

    # Logout must never fail, so it authenticates nothing. Authentication used to
    # break it exactly when it mattered: an expired access token 401'd and left the
    # still-valid (up to 7 days) refresh token unblacklisted, and a cookie-authed
    # POST without an ``X-CSRFToken`` header 403'd in ``CookieJWTAuthentication``,
    # leaving every cookie alive while the SPA navigated to /login anyway — the
    # session then came back to life on the next page load. With no authenticator
    # the view just reads the refresh cookie, blacklists it and drops the cookies.
    # The trade-off is a CSRF-forced logout: it can only end a session, never act
    # inside one.
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # Try to blacklist the refresh token from cookie or body.
        #
        # `body_dict`, not `request.data.get`: this view runs no serializer, so
        # nothing ahead of it rejects a non-object body first — a JSON array
        # reached the `.get` and answered 500 on the one endpoint that
        # authenticates nobody and takes no CSRF token. A non-object body simply
        # carries no `refresh`, which is the same as not sending one.
        refresh_token = request.COOKIES.get("refresh_token") or body_dict(request).get("refresh")
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
