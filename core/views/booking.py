"""
Booking views for OIUEEI lending calendar.

All email action links use RSVP codes as intermediaries.
Accept/reject can also be done by the owner via authenticated API endpoints.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.booking import BookingPeriod
from core.models.rsvp import RSVP
from core.pagination import StandardResultsPagination
from core.serializers.booking import (
    BookingPeriodCalendarSerializer,
    BookingPeriodOwnerCalendarSerializer,
    BookingPeriodSerializer,
    MyBookingSerializer,
)
from core.services.booking_service import cancel_booking, finalize_booking_decision
from core.views._helpers import get_viewable_thing, viewer_code


class ThingCalendarView(APIView):
    """
    GET /api/v1/things/{thing_code}/calendar/
    Get blocked periods for a thing's calendar.
    Owner sees full details, guests see only dates and status.
    """

    permission_classes = [AllowAny]

    def get(self, request, thing_code):
        thing, denied = get_viewable_thing(
            thing_code, viewer_code(request), "Not authorized to view this thing"
        )
        if denied:
            return denied

        # Get blocked periods
        blocked_periods = BookingPeriod.get_blocked_periods(thing_code)

        # Owner sees full details; guests see only dates and status.
        if thing.is_owner(viewer_code(request)):
            # The owner serializer reads requester_code.name and the swap offers
            # per period — pull both in up front so the calendar stays a fixed
            # number of queries regardless of how many bookings it lists.
            blocked_periods = blocked_periods.select_related("requester_code").prefetch_related(
                "offered_things"
            )
            serializer = BookingPeriodOwnerCalendarSerializer(blocked_periods, many=True)
        else:
            serializer = BookingPeriodCalendarSerializer(blocked_periods, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class MyBookingsView(ListAPIView):
    """
    GET /api/v1/my-bookings/
    List all booking requests made by the current user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MyBookingSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return (
            BookingPeriod.objects.filter(requester_code=self.request.user)
            .select_related("thing_code", "owner_code")
            .prefetch_related("offered_things")
            .order_by("-created")
        )


class OwnerBookingsView(ListAPIView):
    """
    GET /api/v1/owner-bookings/
    List all booking requests for things owned by the current user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BookingPeriodSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return (
            BookingPeriod.objects.filter(owner_code=self.request.user)
            .select_related("thing_code", "requester_code")
            .prefetch_related("offered_things")
            .order_by("-created")
        )


class BookingCancelView(APIView):
    """
    POST /api/v1/bookings/{booking_code}/cancel/

    Allows the requester to cancel their own pending booking.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, booking_code):
        booking = get_object_or_404(BookingPeriod, code=booking_code)

        # Only the requester can cancel
        if booking.requester_code_id != request.user.code:
            return Response(
                {"error": "Not authorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not booking.is_valid():
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thing = cancel_booking(booking)

        # A concurrent transition already processed this booking — no-op.
        if thing is None:
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate any outstanding RSVP links for this booking
        RSVP.objects.filter(
            target_code=booking_code,
            action__in=[RSVP.Action.BOOKING_ACCEPT, RSVP.Action.BOOKING_REJECT],
        ).delete()

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class BookingActionView(APIView):
    """
    POST /api/v1/bookings/{booking_code}/accept/
    POST /api/v1/bookings/{booking_code}/reject/

    Allows the thing owner to accept or reject a pending booking
    via an authenticated API call (as an alternative to email RSVP links).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, booking_code, action):
        booking = get_object_or_404(BookingPeriod, code=booking_code)

        # Only the thing owner can accept/reject
        if booking.owner_code_id != request.user.code:
            return Response(
                {"error": "Not authorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not booking.is_valid():
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        accepted = action == "accept"
        thing = finalize_booking_decision(booking, accepted=accepted)

        # A concurrent request (double-click, or email link racing this call)
        # already transitioned this booking — the service no-ops and returns None.
        if thing is None:
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
