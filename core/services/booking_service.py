"""
Booking business logic for OIUEEI.

Extracts accept/reject logic from views into reusable service functions.
Uses transaction.atomic to ensure BookingPeriod and Thing updates are consistent.
"""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import RSVP, Collection, Thing
from core.models.booking import SINGLE_USE_TYPES, BookingPeriod
from core.models.event import Event
from core.models.notification import InAppNotification
from core.models.transfer import ThingTransfer
from core.services.team import load_team

DEFAULT_AVAILABILITY_HORIZON_DAYS = 90


class BookingRequestError(Exception):
    """A reservation request failed a business rule.

    Carries the HTTP status the view should return so the request handlers can
    live in this service layer without importing DRF. The view translates it to
    ``Response({"error": message}, status=status_code)`` — preserving the exact
    response shape the API had when these handlers lived on ``ThingRequestView``.

    ``code`` is an optional machine-readable marker, added on top of that shape
    rather than replacing it — most callers still get a bare ``{"error": ...}``.
    It exists so a client can act on *which* rule failed without pattern-matching
    English prose (or worse, any 403 at all): ``RequestThingPage``'s auto-join
    checks for ``code == "not_a_member"`` specifically, so a *different* 403 on
    this endpoint — e.g. the thing going INACTIVE out from under an open form —
    can't be mistaken for a membership gap and silently join the reader to a
    group over an unrelated error.

    A rule refusal from the model (``core.utils.Refusal``) brings its own
    ``code`` and ``params`` along, so ``raise BookingRequestError(violation)``
    carries them without restating them. ``as_body()`` is the response body:
    ``{"error": ...}`` plus ``code``/``params`` when there are any — what lets
    the request page say the refusal in the reader's language rather than the
    English sentence.
    """

    def __init__(self, message, status_code=400, code=None, params=None):
        super().__init__(message)
        self.message = str(message)
        self.status_code = status_code
        self.code = code if code is not None else getattr(message, "code", None)
        self.params = params if params is not None else getattr(message, "params", None) or {}

    def as_body(self):
        body = {"error": self.message}
        if self.code:
            body["code"] = self.code
        if self.params:
            body["params"] = self.params
        return body


def _pickup_blocked(day, ranges):
    """Is ``day`` inside any booking's ``[start, end)``? (The return day is free.)"""
    return any(start <= day < end for start, end in ranges)


def _range_conflicts(start, end, ranges):
    """Does ``[start, end]`` strictly overlap any booking? Mirrors
    ``BookingPeriod.has_overlap()`` — touching at a boundary is allowed."""
    return any(start < e and s < end for s, e in ranges)


def _pickup_available(day, ranges, weekdays, durations, closed=frozenset()):
    """Can a rental be picked up on ``day`` under the collection's rental rules?

    Mirrors the frontend picker (``frontend/src/utils/rental.js::isPickupDisabled``)
    so the card's availability indicator and the date picker can never contradict
    each other: the weekday must be allowed, the day must be free for pickup and
    not a closure day, and — once the collection fixes the rental lengths — at
    least one of those lengths must land its return day on an allowed, open
    weekday and fit without overlapping a booking.
    """
    if weekdays and day.weekday() not in weekdays:
        return False
    if day in closed:
        return False
    if _pickup_blocked(day, ranges):
        return False
    if not durations:
        return True
    return any(
        (not weekdays or (day + timedelta(days=n)).weekday() in weekdays)
        and (day + timedelta(days=n)) not in closed
        and not _range_conflicts(day, day + timedelta(days=n), ranges)
        for n in durations
    )


def compute_availability(
    blocked_periods,
    today=None,
    horizon_days=DEFAULT_AVAILABILITY_HORIZON_DAYS,
    allowed_weekdays=None,
    durations=None,
    closed_dates=None,
):
    """Compute live availability for a date-based thing from its blocked periods.

    Pure, side-effect-free helper (easy to unit test). Given an iterable of
    PENDING/ACCEPTED bookings (objects exposing ``start_date``/``end_date``),
    returns a ``(available_today, next_available)`` tuple:

    - ``available_today`` (bool): True when *today* is free for a fresh pickup.
    - ``next_available`` (date | None): the earliest day a pickup could start on
      or after today, or None when no day within ``horizon_days`` qualifies.

    Range semantics match ``BookingPeriod.has_overlap()``'s strict overlap: a
    booking ``[s, e]`` blocks pickup on ``[s, e)`` but **not** on its return day
    ``e`` — that day is free for the next pickup (back-to-back handovers). So a
    booking ending today leaves today available. Rows with a null
    ``start_date``/``end_date`` (non-date-based bookings) are skipped defensively.

    ``allowed_weekdays`` (Python weekdays, 0=Mon…6=Sun), ``durations`` (rental
    lengths in days) and ``closed_dates`` (an iterable of ``date`` objects —
    ``Collection.closed_date_set()``, the collection's holidays/closures) are the
    governing collection's rental rules (#7). With them, a day only counts as
    available if a real booking could actually start there: its weekday must be
    allowed, it (and, when the lengths are fixed, the return day) must not be a
    closure day, and at least one length must fit — otherwise a Wednesdays-only
    collection reported "available today" on a Monday while the picker offered no
    selectable day (the card and the picker disagreed). Any rule may be passed
    alone; with none (all ``None``/empty) the result is byte-identical to the
    unrestricted walk. Mirrors ``frontend/src/utils/rental.js::isPickupDisabled``.
    """
    if today is None:
        today = timezone.localdate()

    ranges = sorted(
        (b.start_date, b.end_date) for b in blocked_periods if b.start_date and b.end_date
    )
    weekdays = set(allowed_weekdays or ())
    lengths = sorted({int(d) for d in (durations or ())})
    closed = set(closed_dates or ())

    horizon = today + timedelta(days=horizon_days)

    if not weekdays and not lengths and not closed:
        cursor = today
        while cursor <= horizon:
            # A day is blocked for pickup only on [start, end) — the return day
            # (end) is free again, so jump straight to it rather than end + 1.
            covering = next((r for r in ranges if r[0] <= cursor < r[1]), None)
            if covering is None:
                return (cursor == today, cursor)
            cursor = covering[1]
        return (False, None)

    # With rules in play a blocked span can't be skipped wholesale (the next legal
    # pickup depends on the weekday, which lengths still fit, and closure days),
    # so walk day by day — at most horizon_days iterations.
    cursor = today
    while cursor <= horizon:
        if _pickup_available(cursor, ranges, weekdays, lengths, closed):
            return (cursor == today, cursor)
        cursor += timedelta(days=1)
    return (False, None)


def _day_has_a_free_hour(day, collection, blocked_periods, *, closed=None, earliest=0):
    """Does ``day`` have at least one free slot — of the collection's own
    ``reservation_min_minutes``, not a fixed hour — within an HOUR-unit
    collection's opening blocks, given the thing's booked periods?

    A booking counts as occupying ``day`` when ``start_date <= day < end_date``
    — the same half-open day range every other date-based check uses. A
    whole-day booking (``start_time`` NULL — a LEND/RENT or a DAY-unit RESERVE
    sharing the thing) closes the whole day outright. Existing HOUR-unit
    bookings on the day are swept, in order, against each opening block to find
    a gap with room for the minimum **at a start on the step grid** — every
    ``reservation_min_minutes`` from the block's opening, the same starts
    ``RequestThingPage`` offers and ``Collection.reservation_hour_violation``
    accepts (2026-09-18). A 60-minute gap from 10:30 to 11:30 on a 60-minute
    grid is not a free slot: no reservation may start at 10:30. Overlapping
    sub-ranges can't occur between two ACCEPTED/PENDING bookings
    (``has_overlap`` already refuses that).

    Named for the hour-only shape 0150 replaced — kept rather than renamed so
    this diff stays legible next to the tests it already had; what changed is
    only the threshold, from a hardcoded 60 to ``collection.reservation_min_
    minutes``. Before 0150 the two were always the same number, which is
    exactly how a collection with a sub-hour minimum (the feature's whole
    point) ended up reported as having no free slot on a day that plainly had
    one — this function was never told the minimum had become configurable.

    ``closed`` is ``collection.closed_date_set()`` precomputed by a caller that
    asks about many days in a row (``compute_hourly_availability``) — the set
    is rebuilt from the stored ISO strings on every call otherwise.

    ``earliest`` (minutes since midnight) skips grid starts before it — for
    today, the current minute, so a gap that has already slipped into the past
    doesn't make a day "available" nobody can book any more.
    """
    if day in (collection.closed_date_set() if closed is None else closed):
        return False
    blocks = collection.day_opening_blocks(day)
    if not blocks:
        return False
    step = collection.reservation_min_minutes

    def minutes(t):
        return t.hour * 60 + t.minute

    occupied = []
    for b in blocked_periods:
        if not (b.start_date and b.end_date and b.start_date <= day < b.end_date):
            continue
        if b.start_time is None:
            return False  # a whole-day booking blocks everything
        occupied.append((minutes(b.start_time), minutes(b.end_time)))
    occupied.sort()

    for block_start_time, block_end_time in blocks:
        block_start, block_end = minutes(block_start_time), minutes(block_end_time)

        def fits(gap_start, gap_end):
            # The first grid start at or after the gap opens (and not before
            # `earliest`) — the grid runs every `step` minutes from the block's
            # opening, as the picker's does.
            opens = max(gap_start, earliest)
            first = block_start + -(-(opens - block_start) // step) * step
            return first + step <= gap_end

        cursor = block_start
        for occ_start, occ_end in occupied:
            if occ_end <= cursor or occ_start >= block_end:
                continue  # outside this block
            if fits(cursor, occ_start):
                return True
            cursor = max(cursor, occ_end)
        if fits(cursor, block_end):
            return True
    return False


def compute_hourly_availability(blocked_periods, collection, today=None, now=None):
    """The HOUR-unit twin of ``compute_availability``: same
    ``(available_today, next_available)`` shape, so ``Thing.availability_window``
    treats both units alike, but "available" means *some* opening block that
    day still has a gap of at least ``collection.reservation_min_minutes`` —
    never mind whether a specific duration/start-time combination is offered;
    ``RequestThingPage`` works that out from ``opening_hours`` + the calendar
    once a day is picked. Walks ``collection.reservation_horizon_days`` ahead,
    at most, like the day-based walk above does with its own horizon.
    """
    now = now or timezone.localtime()
    today = today or now.date()
    horizon = today + timedelta(days=collection.reservation_horizon_days)
    # Today's starts count only from the current minute — the same floor
    # `reservation_hour_violation` refuses below. Only for the real today: a
    # caller passing another `today` is asking about that day, not the clock.
    now_minutes = now.hour * 60 + now.minute if today == now.date() else 0
    # Parsed once for the whole walk, not once per day: this runs per thing on
    # every listing that shows availability, and a collection just switched to
    # HOUR (opening_hours still {}, every day closed) walks the full horizon —
    # up to 366 days, each re-parsing up to 60 closure dates.
    closed = collection.closed_date_set()
    cursor = today
    while cursor <= horizon:
        earliest = now_minutes if cursor == today else 0
        if _day_has_a_free_hour(
            cursor, collection, blocked_periods, closed=closed, earliest=earliest
        ):
            return (cursor == today, cursor)
        cursor += timedelta(days=1)
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
    _clear_request_notifications(booking)
    return thing


def accept_booking(booking):
    """Accept a booking and update the Thing if it's single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.

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
        booking.accept()
        if booking.thing_type in SINGLE_USE_TYPES:
            if not thing.is_endless:
                thing.status = Thing.Status.INACTIVE
                thing.save(update_fields=["status"])
                thing.deal.add(booking.requester_code)

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


def receives_booking_requests(user):
    """Whether anything of this person's can be asked for, so that "Requests to
    me" has something to show them.

    True when they **own a thing** — a member of a COMMUNITY collection who has
    contributed one gets requests on it — or when they **run a PROPRIETARY
    collection**, as its founder or a co-curator, whose curators answer for every
    thing in it — or when they **founded a NETWORK**, whose founder can reject a
    pending request on any entity's thing before having uploaded one (a network's
    co-curators receive only their own things, which the first case covers).

    It is the reach of ``OwnerBookingsView`` read as a yes/no, and it is asked of
    the server because the browser cannot know it: someone who only joined a
    group has nothing to receive, and the account menu used to offer the page to
    everybody. Two ``EXISTS`` queries, nothing loaded.
    """
    if Thing.objects.filter(owner=user).exists():
        return True
    return Collection.objects.filter(
        Q(mode=Collection.Mode.PROPRIETARY, owner=user)
        | Q(mode=Collection.Mode.PROPRIETARY, co_owners=user)
        | Q(mode=Collection.Mode.NETWORK, owner=user)
    ).exists()


def _clear_request_notifications(booking):
    """Drop every copy of the "someone asked for this" notification once the request is settled.

    A BOOKING_REQUESTED notification is a question put to the whole team that
    manages the thing (see ``send_booking_request_notifications``): accept or
    reject? Accept, reject and requester-cancel all answer it (a request that
    lapses is cleared by ``BookingPeriod.expire_old_pending``), so leaving any
    copy in an inbox asks for a decision that no longer exists — the reader takes
    it as still pending and can't tell the stale ones from the live ones.
    Deliberately **not** scoped to ``booking.owner_code``: the co-curators'
    copies go too, whoever settled it.

    Matched by ``payload__booking_code``, so notifications created before that key
    existed simply don't match — they stay until dismissed by hand.
    """
    InAppNotification.objects.filter(
        type=InAppNotification.Type.BOOKING_REQUESTED,
        payload__booking_code=booking.code,
    ).delete()


def _notify_team_of_decision(booking, thing, collection, decider, accepted):
    """Leave a BOOKING_DECIDED record with the rest of the team that runs the thing.

    A hold request is a question put to the whole team that manages it, so its
    answer has to reach them all: every manager (``thing.managers()`` — the
    thing's owner plus a PROPRIETARY collection's curators) **except the requester
    and whoever decided**. The requester gets their own BOOKING_ACCEPTED/REJECTED,
    and a "so-and-so decided" line about their own request would be noise in their
    inbox. The decider just did it: a card telling them "You confirmed the request"
    was the reader being told what they had pressed a moment ago (three of five
    cards in one inbox). Without this record at all, a
    co-curator's inbox kept a request the founder had already settled; with it,
    that co-curator hears the decision once.

    Runs after ``_clear_request_notifications``, which is type-scoped to
    BOOKING_REQUESTED: the decision record carries the same ``booking_code``
    but a different type, so the clear leaves it standing. Records written
    before 2026-10-02 may carry ``by_you: true`` (the decider's own); the inbox
    still reads them, nothing writes new ones.
    """
    audience = {}
    for manager in thing.managers():
        if manager.code in (booking.requester_code_id, decider.code):
            continue
        audience.setdefault(manager.code, manager)

    for manager in audience.values():
        payload = {
            "thing_headline": thing.headline,
            # The requester is named the way the request that asked about them
            # named them (`send_booking_request_notifications`): the name, or their
            # email when they set none. Every reader here manages the thing, and the
            # request already showed them that address — a bare name here made the
            # same person "a member" in one card and an email in the next. The
            # decider is a co-member, so theirs stays the bare name.
            "requester_name": booking.requester_code.display_name,
            "decider_name": decider.name,
            "accepted": accepted,
            "booking_code": booking.code,
            "thing_code": thing.code,
            "collection_code": collection.code if collection else "",
        }
        if booking.quantity > 1:
            payload["quantity"] = booking.quantity
        if booking.start_date and booking.end_date:
            payload["start_date"] = str(booking.start_date)
            payload["end_date"] = str(booking.end_date)
        InAppNotification.objects.create(
            user=manager,
            type=InAppNotification.Type.BOOKING_DECIDED,
            payload=payload,
        )


def finalize_booking_decision(booking, accepted, decided_by=None):
    """Apply an owner's accept/reject decision and run the shared side-effects.

    Wraps accept_booking()/reject_booking() (which perform the locked, race-safe
    status transition) and, on success, notifies the requester (in-app + email)
    and invalidates the booking's outstanding accept/reject RSVP links. Shared by
    the email/RSVP path (VerifyLinkView) and the in-app API path
    (BookingActionView) so this money/ownership-sensitive sequence lives in one
    place.

    ``decided_by`` is the account that made the call, and it is who the
    requester's notice names — a decision may be a co-curator's since 2026-09,
    and "the founder confirmed your request" would be false in their mouth.
    ``None`` (and the emailed RSVP path, which passes the owner explicitly)
    falls back to ``booking.owner_code``, the thing's owner.

    Returns the updated Thing, or None when the booking was no longer PENDING (a
    concurrent transition already handled it) — each caller turns None into its
    own "expired or already processed" response.
    """
    from core.services.email_service import send_booking_decision_email

    thing = accept_booking(booking) if accepted else reject_booking(booking)
    if thing is None:
        return None

    # ``thing`` is the row the transition just locked, and a fresh row has no
    # collections loaded: walking them for the requester's collection and the
    # team's notice would cost a few queries per collection. The booking's own
    # thing is the same row as the caller loaded it — with its collections
    # prefetched by the views that decide — so the team is read from there, and
    # ``load_team`` covers a caller that did not (a no-op when it did).
    team = load_team(booking.thing_code)

    # Bare name, matching `MyBookingSerializer.get_owner_name`: the reader is
    # the requester, a co-member, and the API withholds the owner's address from
    # them everywhere else.
    decider = decided_by if decided_by is not None else booking.owner_code
    owner_name = decider.name
    # The booking doesn't record which collection it was made through, so the
    # requester-side notification deep-links through the same approximation the
    # request-side one used.
    # Only collections the requester may read: this one also picks the email
    # note the accepted decision carries to them.
    collection = resolve_request_collection(team, requester=booking.requester_code)
    payload = {
        "thing_headline": thing.headline,
        "owner_name": owner_name,
        # The codes let the inbox deep-link the request the way the request-side
        # notice does.
        "booking_code": booking.code,
        "thing_code": thing.code,
        "collection_code": collection.code if collection else "",
    }
    if booking.quantity > 1:
        payload["quantity"] = booking.quantity
    if booking.start_date and booking.end_date:
        # A loan or rental ran for dates: the requester's notice says which,
        # under the body, the way their request told the owner (2026-09-29).
        # GIFT/SELL carry none, and neither does a decision on one.
        payload["start_date"] = str(booking.start_date)
        payload["end_date"] = str(booking.end_date)
    InAppNotification.objects.create(
        user=booking.requester_code,
        type=(
            InAppNotification.Type.BOOKING_ACCEPTED
            if accepted
            else InAppNotification.Type.BOOKING_REJECTED
        ),
        payload=payload,
    )
    send_booking_decision_email(
        booking, thing, accepted=accepted, collection=collection, decided_by=decider
    )
    _clear_request_notifications(booking)
    _notify_team_of_decision(booking, team, collection, decider, accepted)
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

    return thing


# ── Reservation requests ──────────────────────────────────────────────────
# Business logic for creating a booking, one function per thing-type family.
# Each mirrors the old ThingRequestView._handle_* method: it performs the
# locked create + status transition and then fans out the request emails /
# in-app notification / event via the shared *_notifications helpers. Rule
# violations raise BookingRequestError so the view maps them to the exact
# {"error": ...} response + status they used to return inline.


def _readable_collections(collections, requester):
    """The ``collections`` ``requester`` may read — all of them when there is no
    requester to ask about. Their membership is settled in **one** query for the
    whole list instead of an ``is_invited`` per collection, which is what made a
    request's notices cost more the more groups the thing sits in; the rules
    themselves are still ``Collection.can_view``'s, not a copy of them."""
    if requester is None:
        return list(collections)
    invited_to = set(
        requester.invited_to_collections.filter(
            code__in=[collection.code for collection in collections]
        ).values_list("code", flat=True)
    )
    return [c for c in collections if c.can_view(requester.code, invited_to=invited_to)]


def _readable_by(collection, requester):
    """Whether ``requester`` may read ``collection`` — ``True`` when there is no
    requester to ask about (internal callers, the availability indicator).

    A request's ``collection_code`` is whatever the client sent, and a thing can
    sit in a PRIVATE group and a PUBLIC one at once. Nothing a requester is told
    about their request — a group's email note, a notification filed under it —
    may come from a collection they could not have opened themselves.
    """
    return requester is None or collection.can_view(requester.code)


def resolve_rental_collection(thing, collection_code=None, requester=None):
    """Resolve which collection's rental rules (#7) apply to a LEND/RENT request.

    Prefers the collection the request was made through (``collection_code`` —
    the SPA passes the collection context) **when the requester may read it**;
    a code naming any other collection is ignored, so it can't be used to pick
    the rules of a group the requester was never in. Otherwise the thing's first
    collection that actually defines rental rules. Returns ``None`` when no
    collection constrains the dates (legacy free-range behaviour).
    """
    collections = list(thing.collections.all())
    code = (collection_code or "").strip()
    if code:
        for collection in collections:
            if collection.code == code and _readable_by(collection, requester):
                return collection
    for collection in collections:
        # A network may set no rules of its own and still have them: its
        # dinamizadores' pickup points carry theirs.
        if collection.has_rental_rules() or collection.is_network():
            return collection
    return None


def resolve_request_collection(thing, collection_code=None, requester=None):
    """Resolve which collection a booking request was made through.

    Feeds the notification payload (it deep-links there and the collection's own
    inbox filters by it) and the requester's emails, which carry that
    collection's ``email_note``. A thing lives in one collection, but a row from
    before that rule can sit in more, so the request's own context wins —
    ``collection_code`` is the collection the requester was actually looking at
    when they asked. Without it (a request from
    the standalone /things/<code> page) this is an approximation: the collection
    whose rental rules govern the thing, else its first ACTIVE one.

    With a ``requester``, only collections **they may read** are candidates, for
    the named one and both fallbacks alike: the code is the client's to send, and
    the first collection with rules may be a PRIVATE group they are not in — whose
    note would then reach them by email.
    Returns None when no candidate is left — the notification then carries no
    collection and the emails no note.
    """
    collections = _readable_collections(thing.collections.all(), requester)
    code = (collection_code or "").strip()
    if code:
        for collection in collections:
            if collection.code == code:
                return collection
    with_rules = next((c for c in collections if c.has_rental_rules()), None)
    if with_rules:
        return with_rules
    # Lowest code first, which is what `.first()` on the unordered M2M returned.
    active = [c for c in collections if c.status == Collection.Status.ACTIVE]
    return min(active, key=lambda c: c.code, default=None)


def require_a_seat(thing, requester):
    """Asking for a thing is being part of the group that lists it.

    Raises the same ``not_a_member`` 403 a reservation does when ``requester``
    has no place in **any ACTIVE collection** of ``thing``. A place is being in
    ``invites`` or being a curator: whoever founds a group is not in ``invites``
    and, in COMMUNITY, may ask for a member's thing. One collection is enough.
    Without this a signed-in reader of a PUBLIC group could ask for things
    without being a member — so the person who runs the thing could not open
    their profile and they never received the group's summary — whereas anyone
    who arrived without a session ends up a member.
    """
    active = [c for c in thing.collections.all() if c.status == Collection.Status.ACTIVE]
    invited_to = set(
        requester.invited_to_collections.filter(code__in=[c.code for c in active]).values_list(
            "code", flat=True
        )
    )
    if any(c.code in invited_to or c.is_curator(requester.code) for c in active):
        return
    raise BookingRequestError(
        "You need to be a member of this group to ask for this.",
        status_code=403,
        code="not_a_member",
    )


def _thing_paused():
    """The refusal of a request that overlaps the thing's pause."""
    return BookingRequestError(
        "This thing is paused on those dates.", status_code=409, code="thing_paused"
    )


def request_date_based_booking(
    thing,
    requester,
    start_date,
    end_date,
    rental_collection=None,
    collection_code=None,
    quantity=1,
):
    """LEND/RENT — date-based booking with rental-rules + overlap enforcement.

    ``quantity`` is how many of a thing's identical units the request holds (1 to
    ``thing.units``). With several units: one live request per person on the same
    dates, and the request must fit among the units still free.
    """
    require_a_seat(thing, requester)
    # Enforce the collection's rental rules (fixed durations + allowed pickup/
    # return weekdays). The frontend already prevents these — server-side backstop.
    if rental_collection:
        violation = rental_collection.rental_violation(
            start_date, end_date, owner_code=thing.owner_id
        )
        if violation:
            raise BookingRequestError(violation)

    with transaction.atomic():
        locked = Thing.objects.select_for_update().get(code=thing.code)

        if locked.pause_overlaps(start_date, end_date):
            raise _thing_paused()

        if quantity is None or not 1 <= quantity <= locked.units:
            raise BookingRequestError(
                f"Ask for between 1 and {locked.units}.",
                code="quantity_invalid",
                params={"max": locked.units},
            )

        if locked.units > 1:
            # One live request per person and thing on the same dates: to change how
            # many, cancel the pending one and ask again.
            if BookingPeriod.has_overlap(
                thing.code, start_date, end_date, requester_code=requester.code
            ):
                raise BookingRequestError(
                    "You already have a request for this on those dates.",
                    status_code=409,
                    code="loan_one_per_person",
                )
            if BookingPeriod.has_overlap(
                thing.code, start_date, end_date, units=locked.units, quantity=quantity
            ):
                raise BookingRequestError(
                    f"There aren't {quantity} free on those dates.",
                    status_code=409,
                    code="not_enough_units",
                    params={"count": quantity},
                )
        elif BookingPeriod.has_overlap(thing.code, start_date, end_date):
            raise BookingRequestError(
                "Selected dates overlap with existing booking",
                status_code=409,
                code="dates_taken",
            )

        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            deposit_amount=thing.deposit,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
            start_date=start_date,
            end_date=end_date,
            quantity=quantity,
        )

    send_booking_request_notifications(requester, thing, booking, collection_code)
    return booking


def request_standard_booking(thing, requester, collection_code=None):
    """GIFT/SELL — no dates; single-use things flip to TAKEN to block other requests."""
    # ``locked`` is the row read under ``select_for_update`` — fresh, but with no
    # collections prefetched. The caller's ``thing`` is kept for the notices: the
    # view loaded it with its collections manager-ready, so fanning the request
    # out to the whole team (``thing.managers()``) costs no query per collection.
    require_a_seat(thing, requester)
    with transaction.atomic():
        locked = Thing.objects.select_for_update().get(code=thing.code)

        if not locked.is_endless and locked.status != Thing.Status.ACTIVE:
            raise BookingRequestError(
                "Thing is not available for reservation", code="not_available"
            )

        if BookingPeriod.objects.filter(
            thing_code=locked,
            requester_code=requester,
            status=BookingPeriod.Status.PENDING,
        ).exists():
            raise BookingRequestError(
                "You already have a pending request for this thing", code="already_requested"
            )

        booking = BookingPeriod.objects.create(
            thing_code=locked,
            thing_type=locked.type,
            deposit_amount=locked.deposit,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=locked.owner,
        )

        if not locked.is_endless:
            locked.status = Thing.Status.TAKEN
            locked.save(update_fields=["status"])

    send_booking_request_notifications(requester, thing, booking, collection_code)
    return booking


def send_booking_request_notifications(requester, thing, booking, collection_code=None):
    """Fan out a hold request: to each manager an email with their own
    accept/reject links and an in-app notification, the requester's
    confirmation, and a HOLD_REQUESTED event.

    A hold request is a question put to the whole team that can answer it —
    ``thing.managers()``: the thing's owner plus the curators of every
    PROPRIETARY collection it sits in, all of whom may decide (``can_manage``).
    Each gets a BOOKING_REQUESTED notice and an email, **except the requester**:
    a co-curator who asks for a thing is not warned about their own request.
    ``thing`` should be the caller's prefetched instance
    (``managers_ready_collections``), not a freshly locked one, or the fan-out
    pays a query per collection.

    **Every manager's email carries their own RSVP pair**, minted to them
    (``RSVP.create_booking_pair(booking, manager)``): using the link signs the
    decision as whoever it was minted to (``VerifyLinkView``), and the RSVPs
    are all deleted once anyone decides. A shared pair would make the decision
    the founder's whoever pressed it."""
    from core.services.email_service import (
        send_booking_confirmation_email,
        send_booking_request_email,
    )

    managers = [manager for manager in thing.managers() if manager.code != requester.code]
    for manager in managers:
        if not manager.email:
            continue
        rsvp_accept, rsvp_reject = RSVP.create_booking_pair(booking, manager)
        send_booking_request_email(
            requester,
            thing,
            booking,
            manager.email,
            rsvp_accept.action_link(),
            rsvp_reject.action_link(),
        )
    # Resolved before the requester's confirmation so that email can carry the
    # owner's email_note for the group the request was actually made through —
    # the one the member was browsing is the one whose note the request page
    # showed them.
    collection = resolve_request_collection(thing, collection_code, requester)
    send_booking_confirmation_email(requester, thing, booking, collection, informed=len(managers))
    payload = {
        "thing_headline": thing.headline,
        "requester_name": requester.display_name,
        # The codes let the inbox deep-link the request, show it on its own
        # collection's page, and drop it once the owner has decided.
        "booking_code": booking.code,
        "thing_code": thing.code,
        "collection_code": collection.code if collection else "",
    }
    if booking.quantity > 1:
        payload["quantity"] = booking.quantity
    if booking.start_date and booking.end_date:
        # A loan or rental asks for dates: the inbox says which, under the
        # body, the way a reservation notice does. GIFT/SELL carry none.
        payload["start_date"] = str(booking.start_date)
        payload["end_date"] = str(booking.end_date)
    for manager in managers:
        InAppNotification.objects.create(
            user=manager,
            type=InAppNotification.Type.BOOKING_REQUESTED,
            payload=payload,
        )
    Event.log(
        Event.Kind.HOLD_REQUESTED,
        actor=requester,
        thing=thing,
        thing_type=booking.thing_type,
    )


# ── On-site reservations (RESERVE_THING) ──────────────────────────────────
# A different shape from every other booking: **auto-confirmed**. There is no
# owner accept/reject step, so the booking is created straight to ACCEPTED, no
# RSVP pair is minted, and no ThingTransfer is written (the thing is used on the
# owner's premises and never leaves). Both parties are emailed at once. Either
# of them may later cancel a reservation that has not started.


def resolve_reservations_collection(thing, collection_code=None):
    """The reservations collection a RESERVE request is made through.

    Prefers the collection named in the request (``collection_code`` — the SPA
    passes it); otherwise the thing's first reservations collection. Every
    collection a RESERVE thing lives in is a reservations collection (the
    allowlist rule), so the fallback is just "the first one". Returns ``None``
    only for a RESERVE thing that sits in no reservations collection at all — a
    misconfiguration the caller turns into a refusal.
    """
    collections = list(thing.collections.all())
    code = (collection_code or "").strip()
    if code:
        for collection in collections:
            if collection.code == code and collection.is_reservations_collection():
                return collection
    for collection in collections:
        if collection.is_reservations_collection():
            return collection
    return None


def request_reservation(
    thing,
    requester,
    owner_email,
    start_date,
    duration_days=None,
    project_note="",
    collection_code=None,
    *,
    start_time=None,
    end_time=None,
    contact_phone="",
):
    """RESERVE_THING — create an auto-confirmed on-site reservation.

    Two shapes, chosen by ``rc.is_hourly_reservations()`` — never both at once:
    a **DAY**-unit collection takes ``duration_days`` (the original shape,
    unchanged); an **HOUR**-unit one takes ``start_time``/``end_time`` instead,
    and the stored booking still gets ``end_date = start_date + 1`` — never a
    date range — so every date-only consumer downstream (reminders,
    ``close_transfers``, the calendar export's date filter) keeps working
    without change; only ``has_overlap`` is told about the hours.

    Raises ``BookingRequestError`` on any rule failure (403 not a member, 400 a
    reservation-rule violation, 409 a clash). On success the booking is already
    ``ACCEPTED``; both the requester and the owner are emailed and the owner
    gets an in-app notice.
    """
    rc = resolve_reservations_collection(thing, collection_code)
    if rc is None:
        raise BookingRequestError("This thing is not in a reservations collection.")

    if not rc.is_invited(requester.code):
        raise BookingRequestError(
            "You need to be a member of this group to reserve.",
            status_code=403,
            code="not_a_member",
        )

    if rc.is_hourly_reservations():
        if start_time is None or end_time is None:
            raise BookingRequestError(
                "This space is booked by the hour — pick a start and end time.",
                code="reservation_needs_times",
            )
        violation = rc.reservation_hour_violation(start_date, start_time, end_time)
        if violation:
            raise BookingRequestError(violation)
        end_date = start_date + timedelta(days=1)
    else:
        if duration_days is None:
            raise BookingRequestError(
                "This space is booked by the day — pick a length in days.",
                code="reservation_needs_days",
            )
        # reservation_violation covers duration, the every-day-open-weekday rule
        # AND the collection's "how far ahead" horizon — one backstop.
        violation = rc.reservation_violation(start_date, duration_days)
        if violation:
            raise BookingRequestError(violation)
        end_date = start_date + timedelta(days=duration_days)
        start_time = None
        end_time = None

    with transaction.atomic():
        locked = Thing.objects.select_for_update().get(code=thing.code)
        if locked.pause_overlaps(start_date, end_date):
            raise _thing_paused()
        if rc.active_reservation_count(requester.code) >= rc.reservation_max_active_per_member:
            raise BookingRequestError(
                "You've reached the maximum number of active reservations for this space.",
                code="reservation_max_active",
                params={"max": rc.reservation_max_active_per_member},
            )
        if locked.units > 1 and BookingPeriod.has_overlap(
            thing.code,
            start_date,
            end_date,
            start_time=start_time,
            end_time=end_time,
            requester_code=requester.code,
        ):
            # A person takes one unit at a time: otherwise one of them could hold all.
            raise BookingRequestError(
                "You already have a booking of this at that time.",
                status_code=409,
                code="reservation_one_per_person",
            )
        if BookingPeriod.has_overlap(
            thing.code,
            start_date,
            end_date,
            start_time=start_time,
            end_time=end_time,
            units=locked.units,
        ):
            clash_message = (
                "That time is already taken." if start_time else "Those dates are already taken."
            )
            raise BookingRequestError(
                clash_message,
                status_code=409,
                code="time_taken" if start_time else "dates_taken",
            )
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            project_note=project_note or "",
            # Kept only when the group asked for it: a number nobody was told would
            # be stored is not stored.
            contact_phone=(contact_phone or "") if rc.reservation_asks_phone else "",
            status=BookingPeriod.Status.ACCEPTED,
        )

    _send_reservation_notifications(requester, thing, booking, owner_email, rc)
    return booking


def _send_reservation_notifications(requester, thing, booking, owner_email, collection):
    """Fan out a confirmed reservation: the requester's confirmation, and — to
    **every manager** of the thing (owner + the reservations collection's
    co-curators, ``Thing.managers``), minus the requester if they are one — the
    notice email + in-app record. Plus the request→accept event pair (the
    funnel is instant here).

    ``owner_email`` is the view's pre-validated ``thing.owner`` address; the
    owner is one of the managers below and is reached there at their own.
    """
    from core.services.email_service import (
        send_reservation_confirmed_email,
        send_reservation_notice_email,
    )

    send_reservation_confirmed_email(requester, thing, booking, collection)

    payload = {
        "thing_headline": thing.headline,
        "requester_name": requester.display_name,
        "start_date": str(booking.start_date),
        "end_date": str(booking.end_date),
        "start_time": booking.start_time.strftime("%H:%M") if booking.start_time else None,
        "end_time": booking.end_time.strftime("%H:%M") if booking.end_time else None,
        "booking_code": booking.code,
        "thing_code": thing.code,
        "collection_code": collection.code if collection else "",
    }
    for curator in thing.managers():
        if curator.code == requester.code:
            continue
        if curator.email:
            send_reservation_notice_email(curator.email, requester, thing, booking, collection)
        InAppNotification.objects.create(
            user=curator,
            type=InAppNotification.Type.RESERVATION_MADE,
            payload=payload,
        )

    Event.log(
        Event.Kind.HOLD_REQUESTED, actor=requester, thing=thing, thing_type=booking.thing_type
    )
    Event.log(Event.Kind.HOLD_ACCEPTED, actor=requester, thing=thing, thing_type=booking.thing_type)


def cancel_reservation(booking, by_user):
    """Cancel a not-yet-started reservation — allowed to the **requester, or
    any curator** of the reservations collection (owner or co-curator, rule 4;
    2026-09). Frees the slot and tells everyone who wasn't the one to cancel.

    Raises ``BookingRequestError`` (403 wrong person, 400 nothing to cancel /
    already started / not a reservation). Returns the booking on success.
    """
    thing = booking.thing_code
    if booking.thing_type != Thing.Type.RESERVE_THING:
        raise BookingRequestError("Not a reservation.")
    if by_user.code != booking.requester_code_id and not thing.can_manage(by_user.code):
        raise BookingRequestError(
            "You can't cancel this reservation.", status_code=403, code="cancel_forbidden"
        )
    now = timezone.localtime()
    if booking.start_date and booking.start_date < now.date():
        raise BookingRequestError(
            "This reservation has already started.", code="reservation_started"
        )
    # An HOUR-unit reservation starts at its time, not at midnight: cancelling
    # this morning's slot this afternoon would free, and announce, something
    # that already happened. Same "current minute has not begun" rule as a
    # request (`reservation_hour_violation`).
    if (
        booking.start_time is not None
        and booking.start_date == now.date()
        and booking.start_time.hour * 60 + booking.start_time.minute < now.hour * 60 + now.minute
    ):
        raise BookingRequestError(
            "This reservation has already started.", code="reservation_started"
        )

    with transaction.atomic():
        locked = BookingPeriod.objects.select_for_update().get(code=booking.code)
        if locked.status != BookingPeriod.Status.ACCEPTED:
            raise BookingRequestError(
                "This reservation is no longer active.", code="reservation_inactive"
            )
        locked.status = BookingPeriod.Status.CANCELLED
        locked.save(update_fields=["status"])

    _notify_reservation_cancelled(booking, thing, by_user)
    return locked


def _notify_reservation_cancelled(booking, thing, by_user):
    """Tell the member (unless they cancelled) and every curator (bar whoever
    cancelled) that the slot is free again. `other_name` is always the person
    who actually cancelled, so the copy — "{other} cancelled a reservation of
    {thing}" — is true for every reader.

    Whoever cancelled gets their own confirmation too — an email and, since
    2026-09-29, an in-app record of their own: the reservation's whole story
    lives in the inbox, and theirs stopped at the confirmation, with no trace
    that they were the one who ended it."""
    from core.services.email_service import (
        send_reservation_cancel_confirmation_email,
        send_reservation_cancelled_email,
    )

    requester_id = booking.requester_code_id

    recipients = {}  # code -> (User, email)
    if by_user.code != requester_id:
        recipients[requester_id] = (booking.requester_code, booking.requester_email)
    for curator in thing.managers():
        if curator.code != by_user.code:
            recipients.setdefault(curator.code, (curator, curator.email))

    # Bare name: the email's `_member_name` and the frontend's
    # `common.aMember` cover an unset name.
    payload = {
        "thing_headline": thing.headline,
        "other_name": by_user.name,
        "start_date": str(booking.start_date),
        "end_date": str(booking.end_date),
        "start_time": booking.start_time.strftime("%H:%M") if booking.start_time else None,
        "end_time": booking.end_time.strftime("%H:%M") if booking.end_time else None,
        "thing_code": thing.code,
    }
    for code, (user, email) in recipients.items():
        to_the_member = code == requester_id
        InAppNotification.objects.create(
            user=user,
            type=InAppNotification.Type.RESERVATION_CANCELLED,
            payload={**payload, "cancelled_by_owner": to_the_member},
        )
        if email:
            send_reservation_cancelled_email(
                email, by_user.name, thing, booking, cancelled_by_owner=to_the_member
            )

    # The one recipient the loop above never reaches, by construction — a
    # confirmation, not the "somebody else acted" notice the others get. The
    # record says so in its own words (`by_you`), and names whose reservation
    # it was when the canceller is a curator, not the member.
    is_own_reservation = by_user.code == requester_id
    self_payload = {**payload, "by_you": True}
    if not is_own_reservation:
        self_payload["member_name"] = booking.requester_code.name
    InAppNotification.objects.create(
        user=by_user,
        type=InAppNotification.Type.RESERVATION_CANCELLED,
        payload=self_payload,
    )
    if by_user.email:
        send_reservation_cancel_confirmation_email(
            by_user.email,
            thing,
            booking,
            is_own_reservation=is_own_reservation,
            member_name=None if is_own_reservation else booking.requester_code.name,
        )
