"""
Booking views for OIUEEI lending calendar.

All email action links use RSVP codes as intermediaries.
Accept/reject can also be done by the owner via authenticated API endpoints.
"""

from datetime import datetime, time

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.booking import RETURNABLE_TYPES, BookingPeriod
from core.models.collection import Collection
from core.models.rsvp import RSVP
from core.models.thing import Thing
from core.pagination import StandardResultsPagination
from core.serializers.booking import (
    BookingPeriodCalendarSerializer,
    BookingPeriodOwnerCalendarSerializer,
    BookingPeriodSerializer,
    MyBookingSerializer,
)
from core.services.booking_service import (
    BookingRequestError,
    cancel_booking,
    cancel_reservation,
    finalize_booking_decision,
)
from core.services.email_service import send_return_overdue_email
from core.services.team import managers_ready_collections
from core.views._helpers import get_viewable_thing, refusal_body, viewer_code


def _quantity_asked(request, thing):
    """How many units the reader means to ask for (``?quantity=``), for a loan or a
    rental with several: the calendar then greys out the days with fewer free. 1 when
    it is missing, not a number or outside 1 to the thing's units, and always 1 for
    anything that is not a loan or a rental."""
    if thing.type not in RETURNABLE_TYPES or thing.units <= 1:
        return 1
    try:
        asked = int(request.query_params.get("quantity", 1))
    except (TypeError, ValueError):
        return 1
    return asked if 1 <= asked <= thing.units else 1


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

        # Owner (and a PROPRIETARY collection's co-curator, who runs its
        # bookings) sees full details; guests see only dates and status.
        managed = thing.can_manage(viewer_code(request))
        if managed and request.query_params.get("for") != "request":
            # The owner serializer reads requester_code.name per period — pull it
            # in up front so the calendar stays a fixed number of queries
            # regardless of how many bookings it lists.
            blocked_periods = blocked_periods.select_related("requester_code")
            serializer = BookingPeriodOwnerCalendarSerializer(blocked_periods, many=True)
        else:
            # What is taken, for anyone asking to book: with several units only
            # where they are all on (``saturated_periods``), plus the thing's pause
            # (``Thing.pause_period``), the rules the request itself is judged by — a
            # manager too, when they ask for ``?for=request``, so booking looks the
            # same to them as to a member. With one unit and no pause it is every
            # booking, as before.
            serializer = BookingPeriodCalendarSerializer(
                thing.served_periods(list(blocked_periods), need=_quantity_asked(request, thing)),
                many=True,
            )

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
        # Bookings on my own things, plus — since 2026-09 — every booking on a
        # thing in a PROPRIETARY collection I curate (owner or co-curator): its
        # curators run its bookings collectively, and `booking.owner_code` is
        # the thing's owner, who in a shared catalogue may be another curator.
        user = self.request.user
        curated = Q(thing_code__collections__mode=Collection.Mode.PROPRIETARY) & (
            Q(thing_code__collections__owner=user) | Q(thing_code__collections__co_owners=user)
        )
        # The founder of a network sees the requests on every entity's things, to
        # be able to reject one (the rescue); a co-curator sees only their own.
        curated |= Q(
            thing_code__collections__mode=Collection.Mode.NETWORK,
            thing_code__collections__owner=user,
        )
        # "Has this thing been lent again since?" — the question behind the
        # "remind them to return it" action, asked once per row inside the
        # list query so a page of finished loans costs no query per row
        # (`BookingPeriod.can_be_return_reminded` reads the annotation).
        lent_again = BookingPeriod.objects.filter(
            thing_code=OuterRef("thing_code"),
            status=BookingPeriod.Status.ACCEPTED,
            start_date__gt=OuterRef("start_date"),
            start_date__lte=timezone.localdate(),
        )
        return (
            BookingPeriod.objects.filter(Q(owner_code=user) | curated)
            .select_related("thing_code", "requester_code")
            # Manager-ready, because the serializer asks `can_manage` per row:
            # the owner short-circuits, but a co-curator's rows walk every
            # collection's curators.
            .prefetch_related(
                Prefetch("thing_code__collections", queryset=managers_ready_collections())
            )
            .annotate(lent_again=Exists(lent_again))
            .distinct()
            .order_by("-created")
        )


class BookingCancelView(APIView):
    """
    POST /api/v1/bookings/{booking_code}/cancel/

    Allows the requester to cancel their own pending booking. For a confirmed
    on-site reservation (RESERVE_THING) **any curator of its collection may
    cancel too** (rule 4) — and only while it hasn't started; everyone who
    didn't cancel is notified. The non-RESERVE branch stays requester-only: a
    curator kills a hold by rejecting it (`BookingActionView`).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, booking_code):
        # Collections prefetched manager-ready (and the thing select_related,
        # which a cancel reads either way) so the RESERVE cancellation's
        # `managers()` fan-out — the notice to every curator — never costs a
        # query per collection.
        booking = get_object_or_404(
            BookingPeriod.objects.select_related(
                "thing_code", "thing_code__owner"
            ).prefetch_related(
                Prefetch("thing_code__collections", queryset=managers_ready_collections())
            ),
            code=booking_code,
        )

        if booking.thing_type == Thing.Type.RESERVE_THING:
            try:
                cancel_reservation(booking, request.user)
            except BookingRequestError as exc:
                return Response(exc.as_body(), status=exc.status_code)
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        # Only the requester can cancel
        if booking.requester_code_id != request.user.code:
            return Response(
                refusal_body("Not authorized", code="not_allowed"),
                status=status.HTTP_403_FORBIDDEN,
            )

        if not booking.is_valid():
            return Response(
                refusal_body("Booking expired or already processed", code="booking_not_pending"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        thing = cancel_booking(booking)

        # A concurrent transition already processed this booking — no-op.
        if thing is None:
            return Response(
                refusal_body("Booking expired or already processed", code="booking_not_pending"),
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

    Allows a manager of the thing — its owner, or a curator of a PROPRIETARY
    collection it sits in — to accept or reject a pending booking via an
    authenticated API call (as an alternative to email RSVP links).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, booking_code, action):
        # Collections prefetched manager-ready: `can_manage` reads them, and so
        # does the decision's notice to the whole team (`managers()`).
        booking = get_object_or_404(
            BookingPeriod.objects.select_related("thing_code").prefetch_related(
                Prefetch("thing_code__collections", queryset=managers_ready_collections())
            ),
            code=booking_code,
        )

        # The thing owner, or a PROPRIETARY collection's curator, decides. The
        # founder of a network may also reject (never accept) what an entity's
        # thing was asked for: the rescue.
        if not (
            booking.owner_code_id == request.user.code
            or booking.thing_code.can_manage(request.user.code)
            or (action == "reject" and booking.thing_code.can_rescue(request.user.code))
        ):
            return Response(
                refusal_body("Not authorized", code="not_allowed"),
                status=status.HTTP_403_FORBIDDEN,
            )

        if not booking.is_valid():
            return Response(
                refusal_body("Booking expired or already processed", code="booking_not_pending"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        accepted = action == "accept"
        # Whoever presses the button signs the requester's notice — a
        # co-curator's decision must not arrive as the founder's.
        thing = finalize_booking_decision(booking, accepted=accepted, decided_by=request.user)

        # A concurrent request (double-click, or email link racing this call)
        # already transitioned this booking — the service no-ops and returns None.
        if thing is None:
            return Response(
                refusal_body("Booking expired or already processed", code="booking_not_pending"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class BookingRemindReturnView(APIView):
    """
    POST /api/v1/bookings/{booking_code}/remind-return/

    "Remind them to return it": a manager of the thing nudges the borrower of a
    loan or rental whose return date has passed. Only the **last** loan of each
    thing qualifies (`BookingPeriod.can_be_return_reminded` says so, and the
    /owner-bookings/ serializer reads the same method for `can_remind_return`);
    one nudge per booking per day, so the button cannot turn into harassment.

    The day is claimed with one conditional UPDATE before the email goes — two
    presses at once cannot both match the row — and the email names whoever
    pressed, with their address as `Reply-To`.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, booking_code):
        booking = get_object_or_404(
            BookingPeriod.objects.select_related("thing_code", "requester_code").prefetch_related(
                Prefetch("thing_code__collections", queryset=managers_ready_collections())
            ),
            code=booking_code,
        )

        if not booking.thing_code.can_manage(request.user.code):
            return Response(
                refusal_body("Not authorized", code="not_allowed"),
                status=status.HTTP_403_FORBIDDEN,
            )

        if not booking.can_be_return_reminded():
            return Response(
                {
                    "error": "This booking is not waiting to be returned",
                    "code": "not_awaiting_return",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_of_today = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
        claimed = (
            BookingPeriod.objects.filter(code=booking.code)
            .filter(Q(return_reminded_at__isnull=True) | Q(return_reminded_at__lt=start_of_today))
            .update(return_reminded_at=timezone.now())
        )
        if not claimed:
            return Response(
                {"error": "You've already reminded them today", "code": "already_reminded_today"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        send_return_overdue_email(
            request.user,
            booking.thing_code,
            booking.end_date,
            booking.requester_code.email,
            quantity=booking.quantity,
        )
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
