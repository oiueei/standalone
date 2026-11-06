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

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Collection, Thing
from core.models.booking import DATE_BASED_TYPES, RETURNABLE_TYPES
from core.serializers.booking import (
    ReservationRequestSerializer,
    ThingRequestWithDatesSerializer,
)
from core.services.booking_service import (
    BookingRequestError,
    request_date_based_booking,
    request_reservation,
    request_standard_booking,
    resolve_rental_collection,
)
from core.services.team import managers_ready_collections
from core.views._helpers import body_dict, deny_if_cannot_view, refusal_body


def _asks_for_several(request):
    """Whether the body names a ``quantity`` other than 1."""
    data = body_dict(request)
    if "quantity" not in data or data["quantity"] is None:
        return False
    return data["quantity"] != 1 and str(data["quantity"]).strip() != "1"


class ThingRequestView(APIView):
    """
    POST /api/v1/things/{thing_code}/request/
    Request a reservation/booking for a thing.

    All thing types now use BookingPeriod:
    - LEND/RENT: requires start_date and end_date
    - GIFT/SELL: no extra fields required
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="10/h", method="POST", block=True))
    def post(self, request, thing_code):
        # Collections prefetched manager-ready so the reservation notice's
        # `managers()` fan-out (every curator of the reservations collection)
        # never costs a query per collection — `get_viewable_thing` inlined for
        # the prefetch, same guard.
        thing = get_object_or_404(
            Thing.objects.prefetch_related(
                Prefetch("collections", queryset=managers_ready_collections())
            ),
            code=thing_code,
        )
        denied = deny_if_cannot_view(
            thing, request.user.code, "Not authorized to request this thing"
        )
        if denied:
            return denied

        # Owner cannot request their own thing
        if thing.is_owner(request.user.code):
            return Response(
                refusal_body("Cannot request your own thing", code="cannot_request_own_thing"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if thing is available
        if thing.status != Thing.Status.ACTIVE:
            return Response(
                refusal_body("Thing is not available for reservation", code="thing_unavailable"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if all collections containing this thing are INACTIVE
        thing_collections = thing.collections.all()
        if (
            thing_collections.exists()
            and not thing_collections.filter(status=Collection.Status.ACTIVE).exists()
        ):
            return Response(
                refusal_body("This collection is currently inactive", code="collection_inactive"),
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
                refusal_body("This collection is currently paused", code="collection_paused"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check owner email early (avoids duplicating this check in each handler).
        # Only RESERVE_THING reads it afterwards: the other verbs mail each
        # manager at their own address.
        owner_email = thing.owner.email
        if not owner_email:
            return Response(
                refusal_body("Thing owner not found", code="thing_owner_missing"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Route based on thing type. Serializer validation stays here (HTTP-layer
        # parsing); the create + side effects live in booking_service.
        # The collection the requester was looking at when they asked (the SPA sends
        # it whenever it has one). It picks the collection the owner's notification
        # deep-links to and shows up on — a thing can live in several.
        collection_code = body_dict(request).get("collection_code")

        try:
            if thing.type not in RETURNABLE_TYPES and _asks_for_several(request):
                # Only a loan or a rental can hold several units: a reservation takes
                # one space and a gift or a sale one thing.
                raise BookingRequestError(
                    "Ask for between 1 and 1.", code="quantity_invalid", params={"max": 1}
                )
            if thing.type == Thing.Type.RESERVE_THING:
                return self._request_reservation(request, thing, owner_email, collection_code)
            if thing.type in DATE_BASED_TYPES:
                return self._request_date_based(request, thing, collection_code)
            else:
                booking = request_standard_booking(thing, request.user, collection_code)
                return Response(
                    {"message": "Booking request sent", "booking_code": booking.code},
                    status=status.HTTP_201_CREATED,
                )
        except BookingRequestError as exc:
            return Response(exc.as_body(), status=exc.status_code)

    def _request_reservation(self, request, thing, owner_email, collection_code):
        """RESERVE_THING — validate the request's shape, then delegate.

        The shape is a pickup date plus either a length in days or a start/end
        time (``ReservationRequestSerializer``); which one the collection wants
        is the service's call. It creates the booking already ACCEPTED
        (auto-confirmed) and emails both parties. Membership, the day or hour
        rules, the active-reservations cap and the clash are all checked there
        and come back as BookingRequestError.
        """
        serializer = ReservationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        booking = request_reservation(
            thing,
            request.user,
            owner_email,
            serializer.validated_data["start_date"],
            serializer.validated_data.get("duration_days"),
            serializer.validated_data.get("project_note", ""),
            collection_code,
            start_time=serializer.validated_data.get("start_time"),
            end_time=serializer.validated_data.get("end_time"),
            contact_phone=serializer.validated_data.get("contact_phone", ""),
        )
        return Response(
            {
                "message": "Reservation confirmed",
                "booking_code": booking.code,
                "start_date": str(booking.start_date),
                "end_date": str(booking.end_date),
                "start_time": str(booking.start_time) if booking.start_time else None,
                "end_time": str(booking.end_time) if booking.end_time else None,
            },
            status=status.HTTP_201_CREATED,
        )

    def _request_date_based(self, request, thing, collection_code):
        """Validate LEND/RENT dates then delegate to the service."""
        serializer = ThingRequestWithDatesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        rental_collection = resolve_rental_collection(thing, collection_code, request.user)

        booking = request_date_based_booking(
            thing,
            request.user,
            start_date,
            end_date,
            rental_collection,
            collection_code,
            quantity=serializer.validated_data["quantity"],
        )
        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "quantity": booking.quantity,
            },
            status=status.HTTP_201_CREATED,
        )
