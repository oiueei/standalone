"""
Booking views for OIUEEI lending calendar.

All email action links use RSVP codes as intermediaries.
Accept/reject can also be done by the owner via authenticated API endpoints.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing
from core.models.booking import BookingPeriod
from core.models.notification import InAppNotification
from core.models.rsvp import RSVP
from core.pagination import StandardResultsPagination
from core.serializers.booking import (
    BookingPeriodCalendarSerializer,
    BookingPeriodOwnerCalendarSerializer,
    BookingPeriodSerializer,
    MyBookingSerializer,
)
from core.services.booking_service import accept_booking, cancel_booking, reject_booking
from core.services.email_service import send_booking_decision_email


class ThingCalendarView(APIView):
    """
    GET /api/v1/things/{thing_code}/calendar/
    Get blocked periods for a thing's calendar.
    Owner sees full details, guests see only dates and status.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        # Check if user can view this thing
        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to view this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get blocked periods
        blocked_periods = BookingPeriod.get_blocked_periods(thing_code)

        # For ASSET_THING, all invitees see full details (shared calendar)
        # For other types, owner sees full details, guests see limited info
        if thing.is_owner(request.user.code) or thing.type in ("ASSET_THING", "APPOINTMENT_THING"):
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

        cancel_booking(booking)

        # Invalidate any outstanding RSVP links for this booking
        RSVP.objects.filter(
            target_code=booking_code,
            action__in=["BOOKING_ACCEPT", "BOOKING_REJECT"],
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

        owner_name = request.user.name or request.user.email
        if action == "accept":
            thing = accept_booking(booking)
            send_booking_decision_email(booking, thing, accepted=True)
            InAppNotification.objects.create(
                user=booking.requester_code,
                type=InAppNotification.BOOKING_ACCEPTED,
                payload={"thing_headline": thing.headline, "owner_name": owner_name},
            )
        else:
            thing = reject_booking(booking)
            send_booking_decision_email(booking, thing, accepted=False)
            InAppNotification.objects.create(
                user=booking.requester_code,
                type=InAppNotification.BOOKING_REJECTED,
                payload={"thing_headline": thing.headline, "owner_name": owner_name},
            )

        # Invalidate any outstanding RSVP links for this booking
        RSVP.objects.filter(
            target_code=booking_code,
            action__in=["BOOKING_ACCEPT", "BOOKING_REJECT"],
        ).delete()

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
