"""
Reservation views for OIUEEI.

All reservations now use the unified BookingPeriod model.
Email links use RSVP codes as intermediaries to avoid exposing
real codes (booking_code, thing_code) in URLs.

This view is deliberately thin: it validates the request (auth, availability,
serializers) and dispatches to the ``request_*`` functions in
``core.services.booking_service`` where the create + status transition + email
fan-out live. Business-rule failures come back as ``BookingRequestError`` and
are mapped to the API's ``{"error": ...}`` responses here.
"""

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Collection, Thing
from core.models.booking import DATE_BASED_TYPES
from core.serializers.booking import (
    ThingRequestWithDatesSerializer,
    ThingSwapRequestSerializer,
)
from core.services.booking_service import (
    BookingRequestError,
    request_date_based_booking,
    request_share_booking,
    request_standard_booking,
    request_swap_booking,
    resolve_rental_collection,
)
from core.views._helpers import get_viewable_thing


class ThingRequestView(APIView):
    """
    POST /api/v1/things/{thing_code}/request/
    Request a reservation/booking for a thing.

    All thing types now use BookingPeriod:
    - LEND/RENT: requires start_date and end_date
    - SHARE: no dates — permanent ownership transfer on acceptance, thing stays ACTIVE
    - GIFT/SELL: no extra fields required
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="10/h", method="POST", block=True))
    def post(self, request, thing_code):
        thing, denied = get_viewable_thing(
            thing_code, request.user.code, "Not authorized to request this thing"
        )
        if denied:
            return denied

        # Owner cannot request their own thing
        if thing.is_owner(request.user.code):
            return Response(
                {"error": "Cannot request your own thing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # WISH_THING bypasses BookingPeriod — answer it via the responses endpoint
        if thing.type == Thing.Type.WISH_THING:
            return Response(
                {"error": "This thing type does not support reservations"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if thing is available
        if thing.status != Thing.Status.ACTIVE:
            return Response(
                {"error": "Thing is not available for reservation"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if all collections containing this thing are INACTIVE
        thing_collections = thing.collections.all()
        if (
            thing_collections.exists()
            and not thing_collections.filter(status=Collection.Status.ACTIVE).exists()
        ):
            return Response(
                {"error": "This collection is currently inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if all active collections are paused (no new holds allowed)
        if (
            thing_collections.filter(status=Collection.Status.ACTIVE).exists()
            and not thing_collections.filter(
                status=Collection.Status.ACTIVE, pause_message=""
            ).exists()
        ):
            return Response(
                {"error": "This collection is currently paused"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check owner email early (avoids duplicating this check in each handler)
        owner_email = thing.owner.email
        if not owner_email:
            return Response(
                {"error": "Thing owner not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Route based on thing type. Serializer validation stays here (HTTP-layer
        # parsing); the create + side effects live in booking_service.
        try:
            if thing.type == Thing.Type.SWAP_THING:
                return self._request_swap(request, thing, owner_email)
            elif thing.type == Thing.Type.SHARE_THING:
                booking = request_share_booking(thing, request.user, owner_email)
                return Response(
                    {"message": "Booking request sent", "booking_code": booking.code},
                    status=status.HTTP_201_CREATED,
                )
            elif thing.type in DATE_BASED_TYPES:
                return self._request_date_based(request, thing, owner_email)
            else:
                booking = request_standard_booking(thing, request.user, owner_email)
                return Response(
                    {"message": "Booking request sent", "booking_code": booking.code},
                    status=status.HTTP_201_CREATED,
                )
        except BookingRequestError as exc:
            return Response({"error": exc.message}, status=exc.status_code)

    def _request_date_based(self, request, thing, owner_email):
        """Validate LEND/RENT dates then delegate to the service."""
        serializer = ThingRequestWithDatesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        rental_collection = resolve_rental_collection(thing, request.data.get("collection_code"))

        booking = request_date_based_booking(
            thing, request.user, owner_email, start_date, end_date, rental_collection
        )
        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
                "start_date": str(start_date),
                "end_date": str(end_date),
            },
            status=status.HTTP_201_CREATED,
        )

    def _request_swap(self, request, thing, owner_email):
        """Validate the offered-things list then delegate to the service."""
        swap_ser = ThingSwapRequestSerializer(data=request.data)
        if not swap_ser.is_valid():
            return Response(
                {"error": "You must offer between 1 and 20 things to swap"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking, offered_things = request_swap_booking(
            thing, request.user, owner_email, swap_ser.validated_data["offered_thing_codes"]
        )
        return Response(
            {
                "message": "Swap request sent",
                "booking_code": booking.code,
                "offered_thing_codes": [t.code for t in offered_things],
            },
            status=status.HTTP_201_CREATED,
        )
