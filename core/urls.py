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
    CollectionBulkInviteView,
    CollectionInviteView,
    CollectionShareLinkView,
    CollectionStatsView,
    CollectionViewSet,
    InvitedCollectionsView,
    MyPendingInvitationsView,
)
from .views.faq import FAQAnswerView, FAQDetailView, FAQVisibilityView, ThingFAQListView
from .views.inbox import InboxView
from .views.notifications import NotificationsByTokenView
from .views.reservations import ThingRequestView
from .views.theeemes import TheeemeListView
from .views.things import (
    DocumentDownloadView,
    InvitedThingsView,
    ThingBulkCreateView,
    ThingViewSet,
)
from .views.transfers import ThingTransferView
from .views.upload import CloudinarySignatureView
from .views.users import UserDetailView
from .views.wishes import ThingWishResponseView, WishResolveView, WishResponseAcceptView


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
    path("auth/verify/<str:token>/", VerifyLinkView.as_view(), name="verify-link"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
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
        "collections/<str:collection_code>/broadcast/",
        CollectionBroadcastView.as_view(),
        name="collection-broadcast",
    ),
    path(
        "collections/<str:collection_code>/share-link/",
        CollectionShareLinkView.as_view(),
        name="collection-share-link",
    ),
    path(
        "collections/<str:collection_code>/things/bulk/",
        ThingBulkCreateView.as_view(),
        name="collection-things-bulk",
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
        "things/<str:thing_code>/transfers/",
        ThingTransferView.as_view(),
        name="thing-transfers",
    ),
    path(
        "things/<str:thing_code>/documents/<int:index>/download/",
        DocumentDownloadView.as_view(),
        name="thing-document-download",
    ),
    # Wishes (a Thing of type WISH_THING)
    path(
        "things/<str:thing_code>/responses/",
        ThingWishResponseView.as_view(),
        name="wish-responses",
    ),
    path(
        "things/<str:thing_code>/resolve/",
        WishResolveView.as_view(),
        name="wish-resolve",
    ),
    path(
        "wish-responses/<str:code>/accept/",
        WishResponseAcceptView.as_view(),
        name="wish-response-accept",
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
