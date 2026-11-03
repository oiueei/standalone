"""
BookingPeriod model - unified reservation/booking model for all thing types.

This model handles all reservation scenarios:
- GIFT_THING, SELL_THING: Single-use reservations (no dates, thing becomes INACTIVE)
- LEND_THING, RENT_THING: Date-based bookings (start/end dates, thing stays ACTIVE on return)
- RESERVE_THING: Date-based **and auto-confirmed** — created straight to ACCEPTED,
  no owner accept/reject step, no RSVP pair, and no ThingTransfer (the thing is
  used on the owner's premises and never leaves). Its create + cancel flow lives
  in ``booking_service.request_reservation`` / ``cancel_reservation``; the
  accept/reject machinery below is never reached for it.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time, timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.utils import generate_id

# Thing types that require dates for booking. RESERVE_THING is date-based too,
# but its booking is auto-confirmed (see the module docstring) — routing it
# through here only gets it the strict-overlap conflict check and the live
# availability window, not the PENDING → accept/reject flow.
DATE_BASED_TYPES = ["LEND_THING", "RENT_THING", "RESERVE_THING"]

# Thing types where the thing becomes INACTIVE after acceptance
SINGLE_USE_TYPES = ["GIFT_THING", "SELL_THING"]

# Thing types booked for on-site use: auto-confirmed, and no ThingTransfer is
# written on the booking (nothing changes hands).
ON_SITE_TYPES = ["RESERVE_THING"]

# Date-based types whose thing is carried away and has to come back: a loan or a
# rental. The ones a return can be due on (and so reminded about).
RETURNABLE_TYPES = [t for t in DATE_BASED_TYPES if t not in ON_SITE_TYPES]


@dataclass(frozen=True)
class SaturatedPeriod:
    """A stretch in which a thing with several units is full, shaped like the rows the
    calendar readers take: ``compute_availability``, ``_day_has_a_free_hour`` and
    ``BookingPeriodCalendarSerializer`` read these five attributes of a booking and
    nothing else (``status`` is only there for the serializer's field, and is always
    a blocking one)."""

    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    status: str = "ACCEPTED"


def saturated_periods(periods, units):
    """The stretches in which ``units`` or more of ``periods`` are on at once.

    The one rule of "full" for a thing with several identical units: the request
    check (``BookingPeriod.has_overlap``), the calendar served to the browser and the
    live availability all read it, so the page greys out exactly what the server
    refuses.

    With ``units <= 1`` it is ``periods`` unchanged: every booking is its own
    stretch, which is what a single thing has always been.

    Whole-day bookings (``start_time`` NULL) count on each day of
    ``[start_date, end_date)``; a day with ``units`` of them is full, and
    consecutive full days come out as one whole-day stretch. An hourly booking
    (``start_time`` and ``end_time``, always on its ``start_date``) counts only
    against the others of its day, on top of the whole-day ones covering it: with
    ``w`` of those, the day's hourly stretches are swept with a threshold of
    ``units - w``. Touching at an end is not an overlap, as in ``has_overlap``, and
    stretches that run into each other come out as one.
    """
    if units <= 1:
        return periods

    whole = defaultdict(int)
    hourly = defaultdict(list)
    for p in periods:
        if not (p.start_date and p.end_date):
            continue
        if p.start_time is None or p.end_time is None:
            day = p.start_date
            while day < p.end_date:
                whole[day] += 1
                day += timedelta(days=1)
        else:
            hourly[p.start_date].append((p.start_time, p.end_time))

    full_days = []
    out = []
    for day in sorted(set(whole) | set(hourly)):
        covering = whole.get(day, 0)
        if covering >= units:
            full_days.append(day)
            continue
        threshold = units - covering
        # Ends sort before starts at the same time (-1 < 1): touching is no overlap.
        events = sorted(
            [(s, 1) for s, _ in hourly[day]] + [(e, -1) for _, e in hourly[day]],
            key=lambda event: (event[0], event[1]),
        )
        count = 0
        opened = None
        spans = []
        for at, delta in events:
            before = count
            count += delta
            if before < threshold <= count:
                opened = at
            elif before >= threshold > count:
                if spans and spans[-1][1] == opened:
                    spans[-1] = (spans[-1][0], at)
                else:
                    spans.append((opened, at))
        out.extend(SaturatedPeriod(day, day + timedelta(days=1), s, e) for s, e in spans)

    run_start = previous = None
    for day in full_days:
        if previous is not None and day == previous + timedelta(days=1):
            previous = day
            continue
        if run_start is not None:
            out.append(SaturatedPeriod(run_start, previous + timedelta(days=1)))
        run_start = previous = day
    if run_start is not None:
        out.append(SaturatedPeriod(run_start, previous + timedelta(days=1)))

    return sorted(
        out, key=lambda p: (p.start_date, p.start_time is not None, p.start_time or time.min)
    )


class BookingPeriod(models.Model):
    """
    Unified reservation/booking model for all thing types.

    For GIFT/SELL: no dates required
    For LEND/RENT/SHARE: start_date and end_date required

    The thing_type field determines behavior on acceptance:
    - GIFT/SELL: thing.status -> INACTIVE
    - LEND/RENT/SHARE: thing stays ACTIVE (date-based availability)
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    created = models.DateTimeField(default=timezone.now)
    thing_code = models.ForeignKey(
        "Thing",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="thing_code",
        related_name="bookings",
    )
    thing_type = models.CharField(max_length=17, default="GIFT_THING")
    # What was agreed when the reservation was made, copied rather than looked
    # up through the thing — the same reason `thing_type` above is a copy and
    # `Report.thing_headline` is a snapshot. An owner who edits the listing in
    # June must not rewrite what a March loan said.
    #
    # One snapshot covers the whole handover: every ThingTransfer is created
    # with its booking attached (`accept_booking`), so a journey reaches the
    # agreed amount through `transfer.booking` and there is no second copy to
    # drift away from this one.
    #
    # Nothing renders it yet — this is the record, not a display field. That is
    # deliberate: the column has to exist from the first reservation that
    # carries a deposit, or the history it is meant to preserve starts with a
    # hole in it.
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # RESERVE_THING only: the requester's optional few lines about what they mean
    # to do with the space ("Explica'ns breument el teu projecte"). Shown to the
    # owner in the reservation-notice email and on their bookings page; blank for
    # every other type, and blank when the requester left it empty.
    project_note = models.CharField(max_length=512, blank=True, default="")
    # RESERVE_THING only, and only when the collection asks for it
    # (``Collection.reservation_asks_phone``): an optional phone number for a
    # same-day problem. Served to whoever manages the reservation, blank from the
    # day after it (``BookingPeriodSerializer``) and emptied for good by
    # ``purge_expired_data``. Never in an email or the calendar export. The
    # database default is for the previous release's dynos, which insert without
    # naming the column.
    contact_phone = models.CharField(max_length=32, blank=True, default="", db_default="")
    requester_code = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="requester_code",
        related_name="booking_requests",
    )
    requester_email = models.CharField(max_length=64)
    owner_code = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="owner_code",
        related_name="booking_owned",
    )
    start_date = models.DateField(null=True, blank=True)  # For LEND/RENT/SHARE
    end_date = models.DateField(null=True, blank=True)  # For LEND/RENT/SHARE
    # HOUR-unit RESERVE_THING only. NULL means "whole day" — true of every
    # booking today (LEND/RENT included) and of a DAY-unit reservation forever.
    # A HOUR-unit reservation still carries `end_date = start_date + 1` (never
    # spans midnight); these two narrow that one day to a slot within it.
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    # When whoever manages the thing last pressed "remind them to return it"
    # (`/bookings/{code}/remind-return/`). Null = never reminded. The action
    # is capped at one nudge a day, so this is the timestamp that answers
    # "was it already today?" — see `can_be_return_reminded`.
    return_reminded_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    class Meta:
        app_label = "core"
        db_table = "booking_periods"
        indexes = [
            # has_overlap()/get_blocked_periods() filter by thing + status on
            # every booking request and calendar view; a thing's booking history
            # grows over time, so a composite turns those into an index seek
            # (status alone is already indexed; thing_code alone is the FK index).
            models.Index(fields=["thing_code", "status"], name="booking_thing_status_idx"),
        ]

    def __str__(self):
        if self.start_date and self.end_date:
            return (
                f"Booking {self.code} for {self.thing_code_id} "
                f"({self.start_date} - {self.end_date})"
            )
        return f"Booking {self.code} for {self.thing_code_id}"

    def is_date_based(self):
        """Check if this booking requires dates (LEND/RENT/SHARE)."""
        return self.thing_type in DATE_BASED_TYPES

    def is_single_use(self):
        """Check if this booking makes the thing unavailable (GIFT/SELL)."""
        return self.thing_type in SINGLE_USE_TYPES

    def is_valid(self):
        """Check if the booking request is still valid (not expired and PENDING)."""
        expiry_hours = getattr(settings, "BOOKING_EXPIRY_HOURS", 72)
        expiry_time = self.created + timedelta(hours=expiry_hours)
        return timezone.now() < expiry_time and self.status == self.Status.PENDING

    def can_be_return_reminded(self, today=None):
        """Whether the "remind them to return it" action may fire for this booking.

        True only for an ACCEPTED loan or rental whose return date has already
        passed — strictly: not on the return day itself, which the day-before
        automatic reminder already covers, but from the day after — and only
        while no **later** ACCEPTED booking of the same thing has started: a
        thing already handed to the next borrower has by definition come back,
        and without that check the button would sit on every old loan of a busy
        thing instead of the latest overdue one. "Later" is what matters: an
        earlier loan that was returned months ago must not veto this one.
        Read by the remind-return endpoint and the /owner-bookings/ serializer
        (`can_remind_return`); the once-a-day cap is answered separately by
        `return_reminded_at`.

        The list view annotates each row with `lent_again` (the same question
        as one subquery) so a page of twenty finished loans costs no query per
        row; anywhere else the question is asked here.
        """
        if self.status != self.Status.ACCEPTED or self.thing_type not in RETURNABLE_TYPES:
            return False
        today = today or timezone.localdate()
        if not self.start_date or not self.end_date or self.end_date >= today:
            return False
        lent_again = getattr(self, "lent_again", None)
        if lent_again is None:
            lent_again = BookingPeriod.objects.filter(
                thing_code=self.thing_code_id,
                status=self.Status.ACCEPTED,
                start_date__gt=self.start_date,
                start_date__lte=today,
            ).exists()
        return not lent_again

    def accept(self):
        """Accept the booking request."""
        self.status = self.Status.ACCEPTED
        self.save(update_fields=["status"])

    def reject(self):
        """Reject the booking request."""
        self.status = self.Status.REJECTED
        self.save(update_fields=["status"])

    def cancel(self):
        """Cancel the booking (by the requester)."""
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status"])

    def expire(self):
        """Mark the booking as expired."""
        self.status = self.Status.EXPIRED
        self.save(update_fields=["status"])

    @classmethod
    def has_overlap(
        cls,
        thing_code,
        start_date,
        end_date,
        exclude_booking_code=None,
        *,
        start_time=None,
        end_time=None,
        units=1,
        requester_code=None,
    ):
        """
        Check if there's a conflict with existing PENDING or ACCEPTED bookings.

        Conflict is **strict overlap**, so a booking's return day may be the next
        booking's pickup day (back-to-back handovers): a requested ``[start, end]``
        conflicts with an existing ``[s, e]`` iff ``start < e AND s < end`` — i.e.
        they share an interior day. Touching at a boundary (``start == e`` or
        ``end == s``) is NOT a conflict.

        existing.start_date < requested.end_date AND existing.end_date > requested.start_date

        ``start_time``/``end_time`` (keyword-only) narrow a same-day clash to a
        time-of-day check, for an HOUR-unit RESERVE_THING request: once the date
        filter above has found bookings sharing that one day, a request for
        ``[start_time, end_time)`` conflicts with an existing row only if that row
        is itself a whole-day booking (``start_time`` NULL — every LEND/RENT and
        every DAY-unit RESERVE booking ever made) or its own time range strictly
        overlaps, by the identical boundary-touching-is-fine rule as the dates.
        Passing neither keyword preserves the exact whole-day check above — this
        is what every existing caller (LEND/RENT, DAY-unit RESERVE) keeps doing.

        ``units`` (keyword-only, RESERVE_THING with several identical units): with
        more than one, "conflict" is "the request overlaps a stretch in which
        ``units`` of the existing bookings are already on" — ``saturated_periods``,
        the same rule the calendar serves to the browser. With 1 the check is the
        one above, unchanged. ``requester_code`` narrows the existing bookings to
        one person's, for "one person, one unit at a time".
        """
        queryset = cls.objects.filter(
            thing_code=thing_code,
            status__in=[cls.Status.PENDING, cls.Status.ACCEPTED],
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if exclude_booking_code:
            queryset = queryset.exclude(code=exclude_booking_code)
        if requester_code is not None:
            queryset = queryset.filter(requester_code=requester_code)

        if units > 1:
            # Only what shares days with the request can matter (the filter above): the
            # count at any instant inside the request involves rows covering that
            # instant, and a full stretch of such rows always touches the request's days,
            # so only the hours of an hourly request still need comparing.
            for full in saturated_periods(list(queryset), units):
                if start_time is None or end_time is None or full.start_time is None:
                    return True
                if full.start_time < end_time and full.end_time > start_time:
                    return True
            return False

        if start_time is None or end_time is None:
            return queryset.exists()

        return queryset.filter(
            models.Q(start_time__isnull=True)
            | models.Q(start_time__lt=end_time, end_time__gt=start_time)
        ).exists()

    @classmethod
    def blocking_filter(cls):
        """The bookings that still shape a thing's calendar: PENDING or ACCEPTED,
        and either undated (a GIFT/SELL hold) or not over before yesterday.

        Every calendar reader — availability, the owner's list, the public
        ``/calendar/`` — only ever used what is still ahead, and the SPA already
        dropped the rest (``useThingBooking``'s ``futureOnly``: no ``end_date``,
        or ``end_date >= today``). Loading it all anyway made every read of a
        thing — anonymous reads of a PUBLIC one included — carry the whole
        booking history, and the hourly availability walk scan it once per day
        of the horizon: a cost that grew with how much a space had been used. One
        day of grace, because the browser's "today" can be the server's yesterday.
        """
        cutoff = timezone.localdate() - timedelta(days=1)
        return models.Q(status__in=[cls.Status.PENDING, cls.Status.ACCEPTED]) & (
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=cutoff)
        )

    @classmethod
    def get_blocked_periods(cls, thing_code):
        """
        The blocked periods of a thing (``blocking_filter``: PENDING and
        ACCEPTED bookings not already over). Returns a queryset.
        """
        return cls.objects.filter(cls.blocking_filter(), thing_code=thing_code).order_by(
            "start_date"
        )

    @classmethod
    def expire_old_pending(cls):
        """
        Expire all PENDING bookings that have passed the expiry time.

        For single-use types (GIFT/SELL), also restores the Thing to ACTIVE —
        the thing was set to TAKEN when the booking was created, and would
        otherwise remain stuck in TAKEN indefinitely after expiry.

        The ``BOOKING_REQUESTED`` notice every manager holds for a request that
        expires is deleted with it.
        """
        # Lazy import to avoid circular dependency (Thing imports BookingPeriod)
        from core.models.notification import InAppNotification  # noqa: PLC0415
        from core.models.thing import Thing  # noqa: PLC0415

        expiry_hours = getattr(settings, "BOOKING_EXPIRY_HOURS", 72)
        cutoff_time = timezone.now() - timedelta(hours=expiry_hours)

        with transaction.atomic():
            # Collect thing codes for single-use bookings that are about to expire
            single_use_thing_codes = list(
                cls.objects.filter(
                    status=cls.Status.PENDING,
                    thing_type__in=SINGLE_USE_TYPES,
                    created__lt=cutoff_time,
                ).values_list("thing_code_id", flat=True)
            )

            if single_use_thing_codes:
                Thing.objects.filter(
                    code__in=single_use_thing_codes,
                    status=Thing.Status.TAKEN,
                    is_endless=False,
                ).update(status=Thing.Status.ACTIVE)

            # A request that lapses is settled, so the "someone asked for this" notice
            # every manager holds has nothing left to ask. Collected first because the
            # `update()` below changes the status the filter reads.
            expiring = cls.objects.filter(status=cls.Status.PENDING, created__lt=cutoff_time)
            expiring_codes = list(expiring.values_list("code", flat=True))

            expired_count = expiring.update(status=cls.Status.EXPIRED)

            if expiring_codes:
                InAppNotification.objects.filter(
                    type=InAppNotification.Type.BOOKING_REQUESTED,
                    payload__booking_code__in=expiring_codes,
                ).delete()

        return expired_count
