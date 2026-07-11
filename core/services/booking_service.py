"""
Booking business logic for OIUEEI.

Extracts accept/reject logic from views into reusable service functions.
Uses transaction.atomic to ensure BookingPeriod and Thing updates are consistent.
"""

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from core.models import RSVP, Thing
from core.models.booking import SINGLE_USE_TYPES, BookingPeriod
from core.models.event import Event
from core.models.notification import InAppNotification
from core.models.transfer import ThingTransfer

DEFAULT_AVAILABILITY_HORIZON_DAYS = 90


class BookingRequestError(Exception):
    """A reservation request failed a business rule.

    Carries the HTTP status the view should return so the request handlers can
    live in this service layer without importing DRF. The view translates it to
    ``Response({"error": message}, status=status_code)`` — preserving the exact
    response shape the API had when these handlers lived on ``ThingRequestView``.
    """

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def compute_availability(
    blocked_periods, today=None, horizon_days=DEFAULT_AVAILABILITY_HORIZON_DAYS
):
    """Compute live availability for a date-based thing from its blocked periods.

    Pure, side-effect-free helper (easy to unit test). Given an iterable of
    PENDING/ACCEPTED bookings (objects exposing ``start_date``/``end_date``),
    returns a ``(available_today, next_available)`` tuple:

    - ``available_today`` (bool): True when *today* is free for a fresh pickup.
    - ``next_available`` (date | None): the earliest free day on or after today,
      or None when every day within ``horizon_days`` is booked.

    Range semantics match ``BookingPeriod.has_overlap()``'s strict overlap: a
    booking ``[s, e]`` blocks pickup on ``[s, e)`` but **not** on its return day
    ``e`` — that day is free for the next pickup (back-to-back handovers). So a
    booking ending today leaves today available. Rows with a null
    ``start_date``/``end_date`` (non-date-based bookings) are skipped defensively.
    """
    if today is None:
        today = timezone.localdate()

    ranges = sorted(
        (b.start_date, b.end_date) for b in blocked_periods if b.start_date and b.end_date
    )

    horizon = today + timedelta(days=horizon_days)
    cursor = today
    while cursor <= horizon:
        # A day is blocked for pickup only on [start, end) — the return day (end)
        # is free again, so jump straight to it rather than end + 1.
        covering = next((r for r in ranges if r[0] <= cursor < r[1]), None)
        if covering is None:
            return (cursor == today, cursor)
        cursor = covering[1]
    return (False, None)


def cancel_booking(booking):
    """Cancel a booking by the requester and restore the Thing if single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.

    The booking row is locked and re-read FIRST, then its PENDING status is
    re-checked under the lock — so two concurrent transitions (e.g. cancel
    racing an owner accept) are serialised: the second one finds the booking
    no longer PENDING and returns None instead of double-processing.

    Returns the Thing on success, or None if the booking was no longer PENDING.
    """
    with transaction.atomic():
        booking = BookingPeriod.objects.select_for_update().get(code=booking.code)
        if booking.status != BookingPeriod.Status.PENDING:
            return None
        booking.cancel()
        thing = Thing.objects.select_for_update().get(code=booking.thing_code_id)
        if booking.thing_type in SINGLE_USE_TYPES and not thing.is_endless:
            thing.status = Thing.Status.ACTIVE
            thing.save(update_fields=["status"])
    return thing


def accept_booking(booking):
    """Accept a booking and update the Thing if it's single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.

    For SHARE_THING: transfers ownership to the requester. The thing stays
    ACTIVE so the new owner can continue sharing it.

    For SWAP_THING: bilateral ownership transfer — requested thing goes to
    requester, all offered things go to the original owner. All things stay
    ACTIVE. ThingTransfer records are created for each transfer.

    The booking row is locked and re-read FIRST, then its PENDING status is
    re-checked under the lock, so a concurrent double-accept (owner double
    click, or email link racing the in-app action) cannot run the transfer /
    ThingTransfer / deal side effects twice. ThingTransfer creation uses
    get_or_create for idempotency, backed by the (booking, thing) unique
    constraint.

    Returns the Thing on success, or None if the booking was no longer PENDING.
    """
    with transaction.atomic():
        booking = BookingPeriod.objects.select_for_update().get(code=booking.code)
        if booking.status != BookingPeriod.Status.PENDING:
            return None
        thing = Thing.objects.select_for_update().get(code=booking.thing_code_id)
        # Ownership re-validation for ownership-transferring types (SHARE/SWAP):
        # the booking snapshots owner_code at request time. If an earlier accepted
        # booking already transferred the thing away, this one is stale — bail out
        # like an already-processed booking so a second accept can never transfer
        # from a no-longer-owner (the row lock above serialises concurrent accepts).
        if (
            booking.thing_type in (Thing.Type.SHARE_THING, Thing.Type.SWAP_THING)
            and thing.owner_id != booking.owner_code_id
        ):
            return None
        # A SWAP snapshots the offered things at request time too. Re-validate them
        # under the lock before any mutation: an offered thing already handed off by
        # an earlier accepted swap (or since deactivated) makes this booking stale —
        # bail out like an already-processed booking so the same item can never be
        # transferred twice (stolen from the recipient it first went to).
        offered_things = None
        if booking.thing_type == Thing.Type.SWAP_THING:
            offered_things = list(booking.offered_things.select_for_update())
            for offered in offered_things:
                if (
                    offered.owner_id != booking.requester_code_id
                    or offered.status != Thing.Status.ACTIVE
                ):
                    return None
        booking.accept()
        if booking.thing_type in SINGLE_USE_TYPES:
            if not thing.is_endless:
                thing.status = Thing.Status.INACTIVE
                thing.save(update_fields=["status"])
                thing.deal.add(booking.requester_code)
        elif booking.thing_type == Thing.Type.SHARE_THING:
            thing.owner = booking.requester_code
            thing.save(update_fields=["owner"])
        elif booking.thing_type == Thing.Type.SWAP_THING:
            # Requested thing → requester
            thing.owner = booking.requester_code
            thing.save(update_fields=["owner"])
            # Offered things → original owner (already locked + validated above)
            for offered in offered_things:
                ThingTransfer.objects.get_or_create(
                    thing=offered,
                    booking=booking,
                    defaults={
                        "from_user": booking.requester_code,
                        "to_user": booking.owner_code,
                        "lent_date": date.today(),
                    },
                )
                offered.owner = booking.owner_code
                offered.save(update_fields=["owner"])

        # Record the transfer (item changing hands) — skip for endless things
        if not thing.is_endless:
            ThingTransfer.objects.get_or_create(
                thing=thing,
                booking=booking,
                defaults={
                    "from_user": booking.owner_code,
                    "to_user": booking.requester_code,
                    "lent_date": booking.start_date or date.today(),
                },
            )

    return thing


def reject_booking(booking):
    """Reject a booking and restore the Thing if it's single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.
    The booking row is locked and re-read FIRST and its PENDING status
    re-checked under the lock (see accept_booking for rationale).

    Returns the Thing on success, or None if the booking was no longer PENDING.
    """
    with transaction.atomic():
        booking = BookingPeriod.objects.select_for_update().get(code=booking.code)
        if booking.status != BookingPeriod.Status.PENDING:
            return None
        booking.reject()
        thing = Thing.objects.select_for_update().get(code=booking.thing_code_id)
        if booking.thing_type in SINGLE_USE_TYPES and not thing.is_endless:
            thing.status = Thing.Status.ACTIVE
            thing.save(update_fields=["status"])
    return thing


def _delete_booking_rsvps(booking_code):
    """Invalidate every accept/reject RSVP link for a booking."""
    RSVP.objects.filter(
        target_code=booking_code,
        action__in=[RSVP.Action.BOOKING_ACCEPT, RSVP.Action.BOOKING_REJECT],
    ).delete()


def _decline_conflicting_siblings(booking):
    """Reject other PENDING bookings for the same, now-transferred, thing.

    Only meaningful for ownership-transferring types (SHARE/SWAP): once the thing
    has changed hands, any other pending request for it can no longer be fulfilled.
    Returns the list of bookings actually declined so the caller can notify each
    requester. Each rejection is race-safe — reject_booking re-checks the PENDING
    status under a row lock and no-ops (returns None) on anything already handled.
    """
    siblings = list(
        BookingPeriod.objects.filter(
            thing_code=booking.thing_code_id,
            status=BookingPeriod.Status.PENDING,
        ).exclude(code=booking.code)
    )
    return [sibling for sibling in siblings if reject_booking(sibling) is not None]


def finalize_booking_decision(booking, accepted):
    """Apply an owner's accept/reject decision and run the shared side-effects.

    Wraps accept_booking()/reject_booking() (which perform the locked, race-safe
    status transition) and, on success, notifies the requester (in-app + email)
    and invalidates the booking's outstanding accept/reject RSVP links. On accept
    of an ownership-transferring type (SHARE/SWAP), every other pending request
    for the same thing can no longer be fulfilled, so each is auto-declined and
    its requester is told warmly (their RSVP links are invalidated too). Shared by
    the email/RSVP path (VerifyLinkView) and the in-app API path
    (BookingActionView) so this money/ownership-sensitive sequence lives in one
    place.

    Returns the updated Thing, or None when the booking was no longer PENDING (a
    concurrent transition already handled it) — each caller turns None into its
    own "expired or already processed" response.
    """
    from core.services.email_service import (
        send_booking_decision_email,
        send_booking_unavailable_email,
    )

    thing = accept_booking(booking) if accepted else reject_booking(booking)
    if thing is None:
        return None

    owner_name = booking.owner_code.display_name
    InAppNotification.objects.create(
        user=booking.requester_code,
        type=(
            InAppNotification.Type.BOOKING_ACCEPTED
            if accepted
            else InAppNotification.Type.BOOKING_REJECTED
        ),
        payload={"thing_headline": thing.headline, "owner_name": owner_name},
    )
    send_booking_decision_email(booking, thing, accepted=accepted)
    if accepted:
        # Anchored to the requester (like HOLD_REQUESTED) so a guest's request→accept
        # funnel and the overall holds success rate are both a plain count by kind.
        Event.log(
            Event.Kind.HOLD_ACCEPTED,
            actor=booking.requester_code,
            thing=thing,
            thing_type=booking.thing_type,
        )
    _delete_booking_rsvps(booking.code)

    if accepted and booking.thing_type in (Thing.Type.SHARE_THING, Thing.Type.SWAP_THING):
        for sibling in _decline_conflicting_siblings(booking):
            InAppNotification.objects.create(
                user=sibling.requester_code,
                type=InAppNotification.Type.BOOKING_UNAVAILABLE,
                payload={"thing_headline": thing.headline},
            )
            send_booking_unavailable_email(sibling, thing)
            _delete_booking_rsvps(sibling.code)

    return thing


# ── Reservation requests ──────────────────────────────────────────────────
# Business logic for creating a booking, one function per thing-type family.
# Each mirrors the old ThingRequestView._handle_* method: it performs the
# locked create + status transition and then fans out the request emails /
# in-app notification / event via the shared *_notifications helpers. Rule
# violations raise BookingRequestError so the view maps them to the exact
# {"error": ...} response + status they used to return inline.


def resolve_rental_collection(thing, collection_code=None):
    """Resolve which collection's rental rules (#7) apply to a LEND/RENT request.

    Prefers the collection the request was made through (``collection_code`` —
    the SPA passes the collection context); otherwise the thing's first
    collection that actually defines rental rules. Returns ``None`` when no
    collection constrains the dates (legacy free-range behaviour).
    """
    collections = list(thing.collections.all())
    code = (collection_code or "").strip()
    if code:
        for collection in collections:
            if collection.code == code:
                return collection
    for collection in collections:
        if collection.has_rental_rules():
            return collection
    return None


def request_share_booking(thing, requester, owner_email):
    """SHARE_THING — no dates, permanent transfer on acceptance, thing stays ACTIVE."""
    with transaction.atomic():
        Thing.objects.select_for_update().get(code=thing.code)

        if BookingPeriod.objects.filter(
            thing_code=thing,
            requester_code=requester,
            status=BookingPeriod.Status.PENDING,
        ).exists():
            raise BookingRequestError("You already have a pending request for this thing")

        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
        )

    send_booking_request_notifications(requester, thing, booking, owner_email)
    return booking


def request_date_based_booking(
    thing, requester, owner_email, start_date, end_date, rental_collection=None
):
    """LEND/RENT — date-based booking with rental-rules + overlap enforcement."""
    # Enforce the collection's rental rules (fixed durations + allowed pickup/
    # return weekdays). The frontend already prevents these — server-side backstop.
    if rental_collection:
        violation = rental_collection.rental_violation(start_date, end_date)
        if violation:
            raise BookingRequestError(violation)

    with transaction.atomic():
        Thing.objects.select_for_update().get(code=thing.code)

        if BookingPeriod.has_overlap(thing.code, start_date, end_date):
            raise BookingRequestError(
                "Selected dates overlap with existing booking", status_code=409
            )

        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
            start_date=start_date,
            end_date=end_date,
        )

    send_booking_request_notifications(requester, thing, booking, owner_email)
    return booking


def request_standard_booking(thing, requester, owner_email):
    """GIFT/SELL — no dates; single-use things flip to TAKEN to block other requests."""
    with transaction.atomic():
        thing = Thing.objects.select_for_update().get(code=thing.code)

        if not thing.is_endless and thing.status != Thing.Status.ACTIVE:
            raise BookingRequestError("Thing is not available for reservation")

        if BookingPeriod.objects.filter(
            thing_code=thing,
            requester_code=requester,
            status=BookingPeriod.Status.PENDING,
        ).exists():
            raise BookingRequestError("You already have a pending request for this thing")

        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
        )

        if not thing.is_endless:
            thing.status = Thing.Status.TAKEN
            thing.save(update_fields=["status"])

    send_booking_request_notifications(requester, thing, booking, owner_email)
    return booking


def request_swap_booking(thing, requester, owner_email, offered_codes):
    """SWAP_THING — requester offers their own things in exchange.

    Returns ``(booking, offered_things)`` so the view can echo the resolved
    offered codes in its response.
    """
    # Find the collection this thing belongs to
    thing_collection = thing.collections.filter(is_swap=True).first()
    if not thing_collection:
        raise BookingRequestError("Thing is not in a swap collection")

    # Enforce per-collection minimum: requester must already have N of their own
    # SWAP_THINGs (ACTIVE/TAKEN) in this collection before they can ask for a
    # swap. Backstops the frontend gating in ThingLinkbox/ThingPage.
    minimum = thing_collection.swap_minimum_items
    if minimum > 0:
        own_count = Thing.objects.filter(
            owner=requester,
            type=Thing.Type.SWAP_THING,
            status__in=(Thing.Status.ACTIVE, Thing.Status.TAKEN),
            collections=thing_collection,
        ).count()
        if own_count < minimum:
            raise BookingRequestError(
                f"You need to upload at least {minimum} item(s) to this collection"
                " before you can propose a swap."
            )

    # Validate all offered things
    offered_things = []
    for code in offered_codes:
        try:
            offered = Thing.objects.get(code=code)
        except Thing.DoesNotExist:
            raise BookingRequestError(f"Offered thing {code} not found") from None
        if offered.type != Thing.Type.SWAP_THING:
            raise BookingRequestError(f"Offered thing {code} is not a swap thing")
        if not offered.is_owner(requester.code):
            raise BookingRequestError(f"You do not own offered thing {code}")
        if offered.status != Thing.Status.ACTIVE:
            raise BookingRequestError(f"Offered thing {code} is not active")
        if not offered.collections.filter(code=thing_collection.code).exists():
            raise BookingRequestError(f"Offered thing {code} is not in the same collection")
        offered_things.append(offered)

    with transaction.atomic():
        Thing.objects.select_for_update().get(code=thing.code)

        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
        )
        booking.offered_things.set(offered_things)

    send_swap_request_notifications(requester, thing, offered_things, booking, owner_email)
    return booking, offered_things


def send_booking_request_notifications(requester, thing, booking, owner_email):
    """Fan out a hold request: owner email (RSVP-protected), requester
    confirmation, in-app notification, and a HOLD_REQUESTED event."""
    from core.services.email_service import (
        send_booking_confirmation_email,
        send_booking_request_email,
    )

    rsvp_accept, rsvp_reject = RSVP.create_booking_pair(booking, owner_email)
    send_booking_request_email(
        requester, thing, booking, owner_email, rsvp_accept.action_link(), rsvp_reject.action_link()
    )
    send_booking_confirmation_email(requester, thing, booking)
    InAppNotification.objects.create(
        user=thing.owner,
        type=InAppNotification.Type.BOOKING_REQUESTED,
        payload={
            "thing_headline": thing.headline,
            "requester_name": requester.display_name,
        },
    )
    Event.log(
        Event.Kind.HOLD_REQUESTED,
        actor=requester,
        thing=thing,
        thing_type=booking.thing_type,
    )


def send_swap_request_notifications(requester, thing, offered_things, booking, owner_email):
    """Fan out a swap request (as send_booking_request_notifications, with the
    offered things listed to the owner)."""
    from core.services.email_service import (
        send_swap_confirmation_email,
        send_swap_request_email,
    )

    rsvp_accept, rsvp_reject = RSVP.create_booking_pair(booking, owner_email)
    send_swap_request_email(
        requester,
        thing,
        offered_things,
        owner_email,
        rsvp_accept.action_link(),
        rsvp_reject.action_link(),
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
    Event.log(
        Event.Kind.HOLD_REQUESTED,
        actor=requester,
        thing=thing,
        thing_type=booking.thing_type,
    )
