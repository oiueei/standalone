"""
URL configuration for core app.

IMPORTANT: All email action links use RSVP codes as intermediaries.
Never expose real codes (booking_code, reservation_code, etc.) in URLs.
"""

from django.http import JsonResponse
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views.auth import LogoutView, MeView, RequestLinkView, VerifyLinkView
from .views.booking import BookingActionView, MyBookingsView, OwnerBookingsView, ThingCalendarView
from .views.collections import CollectionInviteView, CollectionViewSet, InvitedCollectionsView
from .views.faq import FAQAnswerView, FAQDetailView, FAQVisibilityView, ThingFAQListView
from .views.reservations import ThingRequestView
from .views.theeemes import TheeemeListView
from .views.things import InvitedThingsView, ThingViewSet
from .views.users import UserDetailView


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
    path("auth/verify/<str:rsvp_code>/", VerifyLinkView.as_view(), name="verify-link"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    # RSVP action endpoint (unified handler for all email-based actions)
    # Handles: MAGIC_LINK, COLLECTION_INVITE, BOOKING_ACCEPT/REJECT
    path("rsvp/<str:rsvp_code>/", VerifyLinkView.as_view(), name="rsvp-action"),
    # Users
    path("users/<str:user_code>/", UserDetailView.as_view(), name="user-detail"),
    # Collections (non-viewset)
    path(
        "invited-collections/",
        InvitedCollectionsView.as_view(),
        name="invited-collections",
    ),
    path(
        "collections/<str:collection_code>/invite/",
        CollectionInviteView.as_view(),
        name="collection-invite",
    ),
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
