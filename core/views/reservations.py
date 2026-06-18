"""
Reservation views for OIUEEI.

All reservations now use the unified BookingPeriod model.
Email links use RSVP codes as intermediaries to avoid exposing
real codes (booking_code, thing_code) in URLs.
"""

from django.db import transaction
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import RSVP, Collection, Thing
from core.models.booking import DATE_BASED_TYPES, REPEATABLE_TYPES, BookingPeriod
from core.models.notification import InAppNotification
from core.serializers.booking import (
    ThingOrderSerializer,
    ThingRequestWithDatesSerializer,
    ThingSwapRequestSerializer,
)
from core.services.email_service import (
    send_booking_confirmation_email,
    send_booking_request_email,
    send_swap_confirmation_email,
    send_swap_request_email,
)
from core.views._helpers import get_viewable_thing


class ThingRequestView(APIView):
    """
    POST /api/v1/things/{thing_code}/request/
    Request a reservation/booking for a thing.

    All thing types now use BookingPeriod:
    - LEND/RENT: requires start_date and end_date
    - SHARE: no dates — permanent ownership transfer on acceptance, thing stays ACTIVE
    - ORDER: requires delivery_date and quantity
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

        # Route based on thing type
        if thing.type == Thing.Type.SWAP_THING:
            return self._handle_swap_request(request, thing, owner_email)
        elif thing.type == Thing.Type.SHARE_THING:
            return self._handle_share_request(request, thing, owner_email)
        elif thing.type in DATE_BASED_TYPES:
            return self._handle_date_based_request(request, thing, owner_email)
        elif thing.type in REPEATABLE_TYPES:
            return self._handle_order_request(request, thing, owner_email)
        else:
            return self._handle_standard_request(request, thing, owner_email)

    def _handle_share_request(self, request, thing, owner_email):
        """Handle SHARE_THING — no dates, permanent transfer on acceptance, thing stays ACTIVE."""
        with transaction.atomic():
            Thing.objects.select_for_update().get(code=thing.code)

            if BookingPeriod.objects.filter(
                thing_code=thing,
                requester_code=request.user,
                status=BookingPeriod.Status.PENDING,
            ).exists():
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

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {"message": "Booking request sent", "booking_code": booking.code},
            status=status.HTTP_200_OK,
        )

    def _handle_date_based_request(self, request, thing, owner_email):
        """Handle LEND/RENT requests with date-based booking."""
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

            if not thing.is_endless and thing.status != Thing.Status.ACTIVE:
                return Response(
                    {"error": "Thing is not available for reservation"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            existing = BookingPeriod.objects.filter(
                thing_code=thing,
                requester_code=request.user,
                status=BookingPeriod.Status.PENDING,
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

            if not thing.is_endless:
                thing.status = Thing.Status.TAKEN
                thing.save(update_fields=["status"])

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
            },
            status=status.HTTP_200_OK,
        )

    def _handle_swap_request(self, request, thing, owner_email):
        """Handle SWAP_THING requests — requester offers their own things in exchange."""
        swap_ser = ThingSwapRequestSerializer(data=request.data)
        if not swap_ser.is_valid():
            return Response(
                {"error": "You must offer between 1 and 20 things to swap"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        offered_codes = swap_ser.validated_data["offered_thing_codes"]

        # Find the collection this thing belongs to
        thing_collection = thing.collections.filter(is_swap=True).first()
        if not thing_collection:
            return Response(
                {"error": "Thing is not in a swap collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce per-collection minimum: requester must already have N of their
        # own SWAP_THINGs (ACTIVE/TAKEN) in this collection before they can ask
        # for a swap. Backstops the frontend gating in ThingLinkbox/ThingPage.
        minimum = thing_collection.swap_minimum_items
        if minimum > 0:
            own_count = Thing.objects.filter(
                owner=request.user,
                type=Thing.Type.SWAP_THING,
                status__in=(Thing.Status.ACTIVE, Thing.Status.TAKEN),
                collections=thing_collection,
            ).count()
            if own_count < minimum:
                return Response(
                    {
                        "error": (
                            f"You need to upload at least {minimum} item(s) to this collection"
                            " before you can propose a swap."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate all offered things
        offered_things = []
        for code in offered_codes:
            try:
                offered = Thing.objects.get(code=code)
            except Thing.DoesNotExist:
                return Response(
                    {"error": f"Offered thing {code} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if offered.type != Thing.Type.SWAP_THING:
                return Response(
                    {"error": f"Offered thing {code} is not a swap thing"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not offered.is_owner(request.user.code):
                return Response(
                    {"error": f"You do not own offered thing {code}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if offered.status != Thing.Status.ACTIVE:
                return Response(
                    {"error": f"Offered thing {code} is not active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not offered.collections.filter(code=thing_collection.code).exists():
                return Response(
                    {"error": f"Offered thing {code} is not in the same collection"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            offered_things.append(offered)

        with transaction.atomic():
            Thing.objects.select_for_update().get(code=thing.code)

            booking = BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=request.user,
                requester_email=request.user.email,
                owner_code=thing.owner,
            )
            booking.offered_things.set(offered_things)

        self._send_swap_email(request.user, thing, offered_things, booking, owner_email)

        return Response(
            {
                "message": "Swap request sent",
                "booking_code": booking.code,
                "offered_thing_codes": [t.code for t in offered_things],
            },
            status=status.HTTP_200_OK,
        )

    def _send_swap_email(self, requester, thing, offered_things, booking, owner_email):
        """Send swap request email to owner with RSVP-protected links."""
        rsvp_accept, rsvp_reject = RSVP.create_booking_pair(booking, owner_email)
        accept_link = rsvp_accept.action_link()
        reject_link = rsvp_reject.action_link()

        send_swap_request_email(
            requester, thing, offered_things, owner_email, accept_link, reject_link
        )
        send_swap_confirmation_email(requester, thing, offered_things, booking)
        InAppNotification.objects.create(
            user=thing.owner,
            type=InAppNotification.Type.SWAP_REQUESTED,
            payload={
                "thing_headline": thing.headline,
                "requester_name": requester.display_name,
            },
        )

    def _send_booking_email(self, requester, thing, booking, owner_email):
        """Send booking request email to owner with RSVP-protected links."""
        rsvp_accept, rsvp_reject = RSVP.create_booking_pair(booking, owner_email)
        accept_link = rsvp_accept.action_link()
        reject_link = rsvp_reject.action_link()

        send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link)
        send_booking_confirmation_email(requester, thing, booking)
        InAppNotification.objects.create(
            user=thing.owner,
            type=InAppNotification.Type.BOOKING_REQUESTED,
            payload={
                "thing_headline": thing.headline,
                "requester_name": requester.display_name,
            },
        )
