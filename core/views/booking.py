"""
Booking views for OIUEEI lending calendar.

All email action links use RSVP codes as intermediaries.
BookingAcceptView and BookingRejectView have been removed -
all accept/reject actions now go through the unified RSVP endpoint.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing
from core.models.booking import BookingPeriod
from core.pagination import StandardResultsPagination
from core.serializers.booking import (
    BookingPeriodCalendarSerializer,
    BookingPeriodOwnerCalendarSerializer,
    BookingPeriodSerializer,
    MyBookingSerializer,
)


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

        # Owner sees full details, guests see limited info
        if thing.is_owner(request.user.code):
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
        return BookingPeriod.objects.filter(requester_code=self.request.user).order_by("-created")


class OwnerBookingsView(ListAPIView):
    """
    GET /api/v1/owner-bookings/
    List all booking requests for things owned by the current user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BookingPeriodSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return BookingPeriod.objects.filter(owner_code=self.request.user).order_by("-created")
