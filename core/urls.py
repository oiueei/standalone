"""
URL configuration for core app.

IMPORTANT: All email action links use RSVP codes as intermediaries.
Never expose real codes (booking_code, reservation_code, etc.) in URLs.
"""

from django.http import JsonResponse
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views.auth import (
    LogoutView,
    MeView,
    PopInView,
    RequestLinkView,
    TokenRefreshView,
    VerifyLinkView,
)
from .views.booking import (
    BookingActionView,
    BookingCancelView,
    MyBookingsView,
    OwnerBookingsView,
    ThingCalendarView,
)
from .views.collections import (
    CollectionBroadcastView,
    CollectionInviteView,
    CollectionViewSet,
    InvitedCollectionsView,
    MyPendingInvitationsView,
)
from .views.events import EventAttendeesView, EventAttendView
from .views.faq import FAQAnswerView, FAQDetailView, FAQVisibilityView, ThingFAQListView
from .views.inbox import InboxView
from .views.notifications import NotificationsByTokenView
from .views.reservations import ThingRequestView
from .views.slots import ThingSlotsView
from .views.stats import ThingStatsView
from .views.theeemes import TheeemeListView
from .views.things import InvitedThingsView, ThingViewSet
from .views.transfers import ThingTransferView
from .views.upload import CloudinarySignatureView
from .views.users import UserDetailView
from .views.wishes import WishHelpersView, WishOfferHelpView


def health_check(request):
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register(r"things", ThingViewSet, basename="thing")
router.register(r"collections", CollectionViewSet, basename="collection")

urlpatterns = [
    # Health check
    path("health/", health_check, name="health-check"),
    # Auth & RSVP Actions
    path("auth/request-link/", RequestLinkView.as_view(), name="request-link"),
    path("auth/pop-in/", PopInView.as_view(), name="pop-in"),
    path("auth/verify/<str:rsvp_code>/", VerifyLinkView.as_view(), name="verify-link"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # RSVP action endpoint (unified handler for all email-based actions)
    # Handles: MAGIC_LINK, COLLECTION_INVITE, BOOKING_ACCEPT/REJECT
    path("rsvp/<str:rsvp_code>/", VerifyLinkView.as_view(), name="rsvp-action"),
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
        "collections/<str:collection_code>/broadcast/",
        CollectionBroadcastView.as_view(),
        name="collection-broadcast",
    ),
    # Upload
    path("upload/signature/", CloudinarySignatureView.as_view(), name="upload-signature"),
    # Theeemes
    path("theeemes/", TheeemeListView.as_view(), name="theeeme-list"),
    # Things (non-viewset)
    path("invited-things/", InvitedThingsView.as_view(), name="invited-things"),
    path("things/<str:thing_code>/request/", ThingRequestView.as_view(), name="thing-request"),
    path(
        "things/<str:thing_code>/calendar/",
        ThingCalendarView.as_view(),
        name="thing-calendar",
    ),
    path(
        "things/<str:thing_code>/slots/",
        ThingSlotsView.as_view(),
        name="thing-slots",
    ),
    path(
        "things/<str:thing_code>/transfers/",
        ThingTransferView.as_view(),
        name="thing-transfers",
    ),
    path(
        "things/<str:thing_code>/stats/",
        ThingStatsView.as_view(),
        name="thing-stats",
    ),
    path(
        "things/<str:thing_code>/attend/",
        EventAttendView.as_view(),
        name="event-attend",
    ),
    path(
        "things/<str:thing_code>/attendees/",
        EventAttendeesView.as_view(),
        name="event-attendees",
    ),
    path(
        "things/<str:thing_code>/offer-help/",
        WishOfferHelpView.as_view(),
        name="wish-offer-help",
    ),
    path(
        "things/<str:thing_code>/helpers/",
        WishHelpersView.as_view(),
        name="wish-helpers",
    ),
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
