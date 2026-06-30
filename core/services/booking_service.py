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
from core.models.notification import InAppNotification
from core.models.transfer import ThingTransfer

DEFAULT_AVAILABILITY_HORIZON_DAYS = 90


def compute_availability(
    blocked_periods, today=None, horizon_days=DEFAULT_AVAILABILITY_HORIZON_DAYS
):
    """Compute live availability for a date-based thing from its blocked periods.

    Pure, side-effect-free helper (easy to unit test). Given an iterable of
    PENDING/ACCEPTED bookings (objects exposing ``start_date``/``end_date``),
    returns a ``(available_today, next_available)`` tuple:

    - ``available_today`` (bool): True when *today* falls in no blocked range.
    - ``next_available`` (date | None): the earliest free day on or after today,
      or None when every day within ``horizon_days`` is booked.

    Range semantics are **inclusive** on both ends — identical to
    ``BookingPeriod.has_overlap()`` and the frontend's ``isDateBlocked`` — so a
    booking ending today blocks today and the next free day is ``end_date + 1``.
    Rows with a null ``start_date``/``end_date`` (non-date-based bookings) are
    skipped defensively.
    """
    if today is None:
        today = timezone.localdate()

    ranges = sorted(
        (b.start_date, b.end_date) for b in blocked_periods if b.start_date and b.end_date
    )

    horizon = today + timedelta(days=horizon_days)
    cursor = today
    while cursor <= horizon:
        covering = next((r for r in ranges if r[0] <= cursor <= r[1]), None)
        if covering is None:
            return (cursor == today, cursor)
        cursor = covering[1] + timedelta(days=1)
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
            # Offered things → original owner
            for offered in booking.offered_things.select_for_update():
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
