"""
URL configuration for core app.

IMPORTANT: All email action links use RSVP codes as intermediaries.
Never expose real codes (booking_code, reservation_code, etc.) in URLs.
"""

import logging

from django.db import connection
from django.http import JsonResponse
from django.urls import path
from django_ratelimit.core import is_ratelimited
from rest_framework.routers import DefaultRouter

from .views.auth import (
    AccountDeleteRequestView,
    JoinView,
    LogoutView,
    MeView,
    RequestLinkView,
    TokenRefreshView,
    VerifyLinkView,
)
from .views.booking import (
    BookingActionView,
    BookingCancelView,
    BookingRemindReturnView,
    BookingReturnedView,
    MyBookingsView,
    OwnerBookingsView,
    ThingCalendarView,
)
from .views.collections import (
    CollectionBroadcastView,
    CollectionBulkInviteView,
    CollectionCoOwnerView,
    CollectionDigestPrefView,
    CollectionEmailNoteTestView,
    CollectionInviteView,
    CollectionJoinView,
    CollectionLeaveView,
    CollectionPointView,
    CollectionProposalActionView,
    CollectionProposeInviteView,
    CollectionShareLinkView,
    CollectionStatsView,
    CollectionViewSet,
    InvitedCollectionsView,
    MyPendingInvitationsView,
    ShareJoinView,
    SharePreviewView,
)
from .views.contact import ContactView
from .views.csp import csp_report
from .views.export import (
    AccountDataExportView,
    CollectionCalendarExportView,
    CollectionDataExportView,
)
from .views.faq import FAQAnswerView, FAQDetailView, FAQVisibilityView, ThingFAQListView
from .views.inbox import InboxView
from .views.notifications import DigestMuteByTokenView, NotificationsByTokenView
from .views.report import ThingReportView
from .views.reservations import ThingRequestView
from .views.theeemes import TheeemeListView
from .views.things import (
    ThingBulkCreateView,
    ThingViewSet,
)
from .views.transfers import ThingTransferView
from .views.upload import UploadTicketView
from .views.users import UserDetailView

logger = logging.getLogger(__name__)


def health_check(request):
    """Liveness + database health, for uptime monitors.

    A bare 200 would keep reporting "up" through a database outage — the one
    failure mode a monitor most needs to catch. The check is one SELECT 1, so a
    5-minute polling cadence costs nothing. The body never carries error detail:
    this endpoint is public.

    Rate-limited because it is the one anonymous endpoint that reaches the
    database on every hit: uncapped, it is cheap DB amplification rather than a
    monitor. 60/m per IP sits far above any real monitor (a 5-minute cadence is
    0.2/m) and far below a useful flood. HEAD counts too — monitors prefer it, so
    a limiter scoped to GET alone would leave the flood one verb away. The cap
    spares the connection and the query, not the database itself: the limiter's
    own counter lives in ``CACHES['default']``, which here is ``DatabaseCache``
    (config/settings/base.py) — so a capped flood still costs one indexed cache
    read apiece.

    **The limiter is called by hand, inside a ``try``, rather than through
    ``@ratelimit``**, and that is the whole point of this shape. Its store being
    the database means the one outage this endpoint exists to report is also the
    outage that stops the limiter working: as a decorator it ran *before* the
    body, so a refused Postgres connection surfaced from the limiter as an
    unhandled exception and the monitor got a 500 with a traceback in the error tracker,
    never the 503 below (seen in production as a monitor's HEAD probe during a
    database outage). A limiter that cannot reach its counter must not be able to veto the
    answer; the outage it failed on is the answer. Pinned by
    ``test_health.py::test_degraded_when_the_outage_takes_the_limiter_with_it``.

    An explicit 429 rather than ``block=True``: this is a plain Django view, not
    a DRF one, so the handler that turns django-ratelimit's ``Ratelimited`` into
    a 429 (``core.exceptions.api_exception_handler``) never runs here — blocking
    would answer 403, and "forbidden" is the wrong thing to tell a monitor about
    a throttle.
    """
    try:
        limited = is_ratelimited(
            request=request,
            # The group the @ratelimit decorator derived from this function, kept
            # verbatim so live counters survive the change.
            group="core.urls.health_check",
            key="ip",
            rate="60/m",
            method=("GET", "HEAD"),
            increment=True,
        )
    except Exception as exc:
        # Fail open: a broken limiter must not turn the monitor's probe into an
        # outage, but it must not go unseen either.
        logger.warning("Health check rate limiter failed: %s", type(exc).__name__)
        limited = False
    if limited:
        return JsonResponse({"status": "throttled"}, status=429)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "degraded"}, status=503)
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register(r"things", ThingViewSet, basename="thing")
router.register(r"collections", CollectionViewSet, basename="collection")

urlpatterns = [
    # Health check
    path("health/", health_check, name="health-check"),
    # Where the browser reports a CSP violation (see core/views/csp.py)
    path("csp-report/", csp_report, name="csp-report"),
    # Auth & RSVP Actions
    path("auth/request-link/", RequestLinkView.as_view(), name="request-link"),
    path("auth/join/", JoinView.as_view(), name="join"),
    path("auth/verify/<str:token>/", VerifyLinkView.as_view(), name="verify-link"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/delete-account/", AccountDeleteRequestView.as_view(), name="delete-account"),
    # Its complement: read your copy before you erase it (art. 20)
    path("auth/export/", AccountDataExportView.as_view(), name="account-export"),
    # Support channel — anonymous on purpose (a locked-out user is the main case)
    path("contact/", ContactView.as_view(), name="contact"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # RSVP action endpoint (unified handler for all email-based actions)
    # Handles: MAGIC_LINK, COLLECTION_INVITE, BOOKING_ACCEPT/REJECT
    path("rsvp/<str:token>/", VerifyLinkView.as_view(), name="rsvp-action"),
    # Users
    path("users/<str:user_code>/", UserDetailView.as_view(), name="user-detail"),
    # In-app notification inbox
    path("inbox/", InboxView.as_view(), name="inbox-list"),
    path("inbox/<str:code>/", InboxView.as_view(), name="inbox-dismiss"),
    # Notification preferences (tokenised; no login required)
    path(
        "notifications/token/<str:token>/",
        NotificationsByTokenView.as_view(),
        name="notifications-token",
    ),
    path(
        "digest/mute/<str:token>/",
        DigestMuteByTokenView.as_view(),
        name="digest-mute-token",
    ),
    # Collections (non-viewset)
    path(
        "invited-collections/",
        InvitedCollectionsView.as_view(),
        name="invited-collections",
    ),
    path(
        "my-invitations/",
        MyPendingInvitationsView.as_view(),
        name="my-invitations",
    ),
    path(
        "collections/<str:collection_code>/invite/",
        CollectionInviteView.as_view(),
        name="collection-invite",
    ),
    path(
        "collections/<str:collection_code>/point/",
        CollectionPointView.as_view(),
        name="collection-point",
    ),
    path(
        "collections/<str:collection_code>/co-owners/",
        CollectionCoOwnerView.as_view(),
        name="collection-co-owners",
    ),
    path(
        "collections/<str:collection_code>/join/",
        CollectionJoinView.as_view(),
        name="collection-join",
    ),
    path(
        "collections/<str:collection_code>/leave/",
        CollectionLeaveView.as_view(),
        name="collection-leave",
    ),
    path(
        "collections/<str:collection_code>/invite/propose/",
        CollectionProposeInviteView.as_view(),
        name="collection-invite-propose",
    ),
    path(
        "proposals/<str:proposal_code>/<str:action>/",
        CollectionProposalActionView.as_view(),
        name="collection-proposal-action",
    ),
    path(
        "collections/<str:collection_code>/digest/",
        CollectionDigestPrefView.as_view(),
        name="collection-digest-pref",
    ),
    path(
        "collections/<str:collection_code>/invite/bulk/",
        CollectionBulkInviteView.as_view(),
        name="collection-invite-bulk",
    ),
    path(
        "collections/<str:collection_code>/stats/",
        CollectionStatsView.as_view(),
        name="collection-stats",
    ),
    path(
        "collections/<str:collection_code>/export/",
        CollectionDataExportView.as_view(),
        name="collection-export",
    ),
    path(
        "collections/<str:collection_code>/calendar-export/",
        CollectionCalendarExportView.as_view(),
        name="collection-calendar-export",
    ),
    path(
        "collections/<str:collection_code>/email-note/test/",
        CollectionEmailNoteTestView.as_view(),
        name="collection-email-note-test",
    ),
    path(
        "collections/<str:collection_code>/broadcast/",
        CollectionBroadcastView.as_view(),
        name="collection-broadcast",
    ),
    path(
        "collections/<str:collection_code>/share-link/",
        CollectionShareLinkView.as_view(),
        name="collection-share-link",
    ),
    # Public: name + description of the collection a /share/{token} link opens
    path(
        "share/<str:token>/preview/",
        SharePreviewView.as_view(),
        name="share-preview",
    ),
    # Signed-in: accept a /share/{token} invitation with the session you already have
    path(
        "share/<str:token>/join/",
        ShareJoinView.as_view(),
        name="share-join",
    ),
    path(
        "collections/<str:collection_code>/things/bulk/",
        ThingBulkCreateView.as_view(),
        name="collection-things-bulk",
    ),
    # Upload
    path("upload/ticket/", UploadTicketView.as_view(), name="upload-ticket"),
    # Theeemes
    path("theeemes/", TheeemeListView.as_view(), name="theeeme-list"),
    # Things (non-viewset)
    path("things/<str:thing_code>/request/", ThingRequestView.as_view(), name="thing-request"),
    path(
        "things/<str:thing_code>/calendar/",
        ThingCalendarView.as_view(),
        name="thing-calendar",
    ),
    path(
        "things/<str:thing_code>/transfers/",
        ThingTransferView.as_view(),
        name="thing-transfers",
    ),
    path("things/<str:thing_code>/report/", ThingReportView.as_view(), name="thing-report"),
    # Bookings
    path("my-bookings/", MyBookingsView.as_view(), name="my-bookings"),
    path("owner-bookings/", OwnerBookingsView.as_view(), name="owner-bookings"),
    path(
        "bookings/<str:booking_code>/accept/",
        BookingActionView.as_view(),
        {"action": "accept"},
        name="booking-accept",
    ),
    path(
        "bookings/<str:booking_code>/reject/",
        BookingActionView.as_view(),
        {"action": "reject"},
        name="booking-reject",
    ),
    path(
        "bookings/<str:booking_code>/cancel/",
        BookingCancelView.as_view(),
        name="booking-cancel",
    ),
    path(
        "bookings/<str:booking_code>/returned/",
        BookingReturnedView.as_view(),
        name="booking-returned",
    ),
    path(
        "bookings/<str:booking_code>/remind-return/",
        BookingRemindReturnView.as_view(),
        name="booking-remind-return",
    ),
    # FAQ
    path("things/<str:thing_code>/faq/", ThingFAQListView.as_view(), name="thing-faq-list"),
    path("faq/<str:faq_code>/", FAQDetailView.as_view(), name="faq-detail"),
    path("faq/<str:faq_code>/answer/", FAQAnswerView.as_view(), name="faq-answer"),
    path(
        "faq/<str:faq_code>/hide/",
        FAQVisibilityView.as_view(),
        {"action": "hide"},
        name="faq-hide",
    ),
    path(
        "faq/<str:faq_code>/show/",
        FAQVisibilityView.as_view(),
        {"action": "show"},
        name="faq-show",
    ),
] + router.urls
