"""
Reservation views for OIUEEI.

All reservations now use the unified BookingPeriod model.
Email links use RSVP codes as intermediaries to avoid exposing
real codes (booking_code, thing_code) in URLs.
"""

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import RSVP, Thing
from core.models.booking import DATE_BASED_TYPES, REPEATABLE_TYPES, BookingPeriod
from core.serializers.booking import (
    ThingOrderSerializer,
    ThingRequestWithDatesSerializer,
    ThingRequestWithTimesSerializer,
)
from core.services.email_service import send_booking_confirmation_email, send_booking_request_email


class ThingRequestView(APIView):
    """
    POST /api/v1/things/{thing_code}/request/
    Request a reservation/booking for a thing.

    All thing types now use BookingPeriod:
    - LEND/RENT/SHARE: requires start_date and end_date
    - ORDER: requires delivery_date and quantity
    - GIFT/SELL: no extra fields required
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="10/h", method="POST", block=True))
    def post(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        # Check if user can view this thing (is invited to collection)
        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to request this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Owner cannot request their own thing
        if thing.is_owner(request.user.code):
            return Response(
                {"error": "Cannot request your own thing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # EVENT_THING and WISH_THING bypass BookingPeriod — use attend/offer endpoints
        if thing.type in ("EVENT_THING", "WISH_THING"):
            return Response(
                {"error": "This thing type does not support reservations"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if thing is available
        if thing.status != "ACTIVE":
            return Response(
                {"error": "Thing is not available for reservation"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if all collections containing this thing are INACTIVE
        thing_collections = thing.collections.all()
        if thing_collections.exists() and not thing_collections.filter(status="ACTIVE").exists():
            return Response(
                {"error": "This collection is currently inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check owner email early (avoids duplicating this check in each handler)
        owner_email = thing.owner.email
        if not owner_email:
            return Response(
                {"error": "Thing owner not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Route based on thing type
        if thing.type == "ASSET_THING" and thing.booking_unit == "HOUR":
            return self._handle_hourly_request(request, thing, owner_email)
        elif thing.type in DATE_BASED_TYPES:
            return self._handle_date_based_request(request, thing, owner_email)
        elif thing.type in REPEATABLE_TYPES:
            return self._handle_order_request(request, thing, owner_email)
        else:
            return self._handle_standard_request(request, thing, owner_email)

    def _handle_date_based_request(self, request, thing, owner_email):
        """Handle LEND/RENT/SHARE requests with date-based booking."""
        serializer = ThingRequestWithDatesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]

        with transaction.atomic():
            Thing.objects.select_for_update().get(code=thing.code)

            if BookingPeriod.has_overlap(thing.code, start_date, end_date):
                return Response(
                    {"error": "Selected dates overlap with existing booking"},
                    status=status.HTTP_409_CONFLICT,
                )

            booking = BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=request.user,
                requester_email=request.user.email,
                owner_code=thing.owner,
                start_date=start_date,
                end_date=end_date,
            )

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
                "start_date": str(start_date),
                "end_date": str(end_date),
            },
            status=status.HTTP_200_OK,
        )

    def _handle_hourly_request(self, request, thing, owner_email):
        """Handle ASSET_THING hourly requests (single day + time range)."""
        serializer = ThingRequestWithTimesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_date = serializer.validated_data["start_date"]
        start_time = serializer.validated_data["start_time"]
        end_time = serializer.validated_data["end_time"]

        with transaction.atomic():
            Thing.objects.select_for_update().get(code=thing.code)

            if BookingPeriod.has_overlap(
                thing.code,
                start_date,
                start_date,
                start_time=start_time,
                end_time=end_time,
            ):
                return Response(
                    {"error": "Selected time overlaps with existing booking"},
                    status=status.HTTP_409_CONFLICT,
                )

            booking = BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=request.user,
                requester_email=request.user.email,
                owner_code=thing.owner,
                start_date=start_date,
                end_date=start_date,
                start_time=start_time,
                end_time=end_time,
            )

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
                "start_date": str(start_date),
                "start_time": str(start_time),
                "end_time": str(end_time),
            },
            status=status.HTTP_200_OK,
        )

    def _handle_order_request(self, request, thing, owner_email):
        """Handle ORDER_THING requests (delivery_date + quantity)."""
        serializer = ThingOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        delivery_date = serializer.validated_data["delivery_date"]
        quantity = serializer.validated_data["quantity"]

        with transaction.atomic():
            Thing.objects.select_for_update().get(code=thing.code)

            booking = BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=request.user,
                requester_email=request.user.email,
                owner_code=thing.owner,
                delivery_date=delivery_date,
                quantity=quantity,
            )

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {
                "message": "Order request sent",
                "booking_code": booking.code,
                "delivery_date": str(delivery_date),
                "quantity": quantity,
            },
            status=status.HTTP_200_OK,
        )

    def _handle_standard_request(self, request, thing, owner_email):
        """Handle GIFT/SELL requests (no dates)."""
        with transaction.atomic():
            thing = Thing.objects.select_for_update().get(code=thing.code)

            if thing.status != "ACTIVE":
                return Response(
                    {"error": "Thing is not available for reservation"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            existing = BookingPeriod.objects.filter(
                thing_code=thing,
                requester_code=request.user,
                status="PENDING",
            ).first()
            if existing:
                return Response(
                    {"error": "You already have a pending request for this thing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            booking = BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=request.user,
                requester_email=request.user.email,
                owner_code=thing.owner,
            )

            thing.status = "TAKEN"
            thing.save(update_fields=["status"])

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
            },
            status=status.HTTP_200_OK,
        )

    def _send_booking_email(self, requester, thing, booking, owner_email):
        """Send booking request email to owner with RSVP-protected links."""
        # Create RSVP tokens for accept/reject links
        rsvp_accept = RSVP.create_for_booking("BOOKING_ACCEPT", booking, owner_email)
        rsvp_reject = RSVP.create_for_booking("BOOKING_REJECT", booking, owner_email)

        # Build links
        base_url = settings.RSVP_BASE_URL
        accept_link = f"{base_url}/{rsvp_accept.code}"
        reject_link = f"{base_url}/{rsvp_reject.code}"

        send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link)
        send_booking_confirmation_email(requester, thing, booking)
