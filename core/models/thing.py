"""
Thing model for OIUEEI.
"""

from datetime import time, timedelta

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class Thing(models.Model):
    """
    An item in a collection (gift, sale, order, rent, lend, or share).

    Reservation status (status):
    - ACTIVE: Visible to owner + invited users, available for reservation
    - TAKEN: Visible to guests, awaiting owner confirmation (not available for new requests)
    - INACTIVE: Hidden from guests, not available for reservation
    """

    class Type(models.TextChoices):
        GIFT_THING = "GIFT_THING", "Gift Thing"
        SELL_THING = "SELL_THING", "Sell Thing"
        RENT_THING = "RENT_THING", "Rent Thing"
        LEND_THING = "LEND_THING", "Lend Thing"
        # An on-site reservation: booked to be *used on the owner's premises* — a
        # room, a machine, a workbench — never carried away. Date-based like a
        # loan (one booking blocks its day and frees the next), but nothing
        # changes hands: no ThingTransfer, no ownership move, no deposit. The
        # booking is auto-confirmed (no owner accept step) and lives only in a
        # PROPRIETARY, reservations-only collection an operator runs. `fee` is
        # optional; a COMMUNITY collection can never hold one.
        RESERVE_THING = "RESERVE_THING", "Reserve Thing"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        TAKEN = "TAKEN", "Taken"

    class Availability(models.TextChoices):
        IMMEDIATE = "IMMEDIATE", "Immediate"
        NEXT_WEEK = "NEXT_WEEK", "Next week"
        END_OF_MONTH = "END_OF_MONTH", "End of month"
        NEXT_MONTH = "NEXT_MONTH", "Next month"

    class Condition(models.TextChoices):
        NEW = "NEW", "New"
        GOOD = "GOOD", "Good condition"
        FAIR = "FAIR", "Fair"
        USED = "USED", "Used"
        WELL_USED = "WELL_USED", "Well used"
        ALMOST_JUNK = "ALMOST_JUNK", "Almost junk"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    # 16, not 13 ("RESERVE_THING" is the longest value): headroom for the next
    # verb, matching the slack `BookingPeriod.thing_type` (17) already carries.
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.GIFT_THING)
    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="owner",
        related_name="owned_things",
    )
    created = models.DateTimeField(default=timezone.now)
    # 256/1024, not the 64/256 an owner sees: the field may hold one text per
    # language as inline JSON (see core.utils.parse_localized), so the column has
    # room for all three plus the JSON scaffolding. The per-language limits are
    # enforced by the serializer (LocalizedHeadlineField / LocalizedTextField).
    headline = models.CharField(max_length=256)
    # TextField, not a capped CharField: a thing's description is long-form
    # Markdown (a space, a machine, a piece of history can need a page), and the
    # real limit is the per-language one the serializer enforces
    # (LocalizedTextField, 2000 visible / language). The column is only a
    # backstop; the serializer is the guard.
    description = models.TextField(blank=True, default="")
    thumbnail = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # What the owner asks to be left as security on a loan or a rental — and
    # **information, nothing else**: OIUEEI never holds it, never moves it, and
    # has no state for "returned" or "kept". It is a number shown next to the
    # price, exactly like `fee`, and the two people settle it between them.
    #
    # Written down because the risk here was never technical: it is that a year
    # from now somebody asks "and while we're at it, couldn't OIUEEI hold the
    # money?". That is a different product — escrow, a payment processor, a
    # licence to run one, a dispute process and a whole new category of personal
    # data — and it deserves to be a decision taken on purpose rather than a
    # place this column quietly arrived at.
    #
    # LEND and RENT only: there is nothing to give back on a gift or a sale. The
    # serializers enforce that, not this column, because the JSON API and the CSV
    # import are two more doors into it.
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(
        max_length=12, choices=Availability.choices, blank=True, default=""
    )
    # 64, not 32: a RESERVE thing's location can be a whole address — "Sala 2,
    # 1a planta, Ateneu del Poblenou" — where a gift's is just a neighbourhood.
    location = models.CharField(max_length=64, blank=True, default="")
    condition = models.CharField(max_length=12, choices=Condition.choices, blank=True, default="")
    gallery = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Additional photos beyond the cover thumbnail: an ordered list of "
            "storage keys. Max 8. Things only (not collections)."
        ),
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Owner-defined tags assigned to this thing — a subset of its "
            "collection's tag vocabulary (Collection.tags). Max 12."
        ),
    )
    is_endless = models.BooleanField(default=False)
    # RESERVE_THING only: how many identical ones the space has, so that many
    # reservations can overlap (``BookingPeriod.saturated_periods``). 1 = the
    # ordinary single thing, and every other type stays at 1. The database default
    # is for the previous release's dynos, which insert without naming the column.
    units = models.PositiveSmallIntegerField(default=1, db_default=1)
    # A thing with a calendar (loan, rental, reservation) can be paused: from
    # ``paused_from`` to ``paused_until``, both days included, nobody can request
    # or book it. Both set or both empty; at most one period per thing; it ends on
    # its own once ``paused_until`` has passed. Bookings already made are not
    # touched. ``pause_period`` is the one reading of it.
    paused_from = models.DateField(null=True, blank=True)
    paused_until = models.DateField(null=True, blank=True)
    deal = models.ManyToManyField(
        "User",
        blank=True,
        related_name="deals",
        db_table="thing_deals",
    )

    class Meta:
        app_label = "core"
        db_table = "things"

    def __str__(self):
        return f"{self.code}: {self.headline}"

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner_id == user_code

    def can_manage(self, user_code):
        """The thing owner, or a curator of a **PROPRIETARY** collection this
        thing sits in — the thing-level twin of ``Collection.is_curator``.

        In a PROPRIETARY collection every thing was added by a curator *for*
        the group, so its curators (owner + co-curators) collectively run the
        catalogue: edit / hide / activate / delete any thing, answer any FAQ,
        decide any booking. COMMUNITY is deliberately excluded — there a member
        owns what they contribute and a curator's reach stops short of
        editing it. A NETWORK is excluded too: each entity runs its own things, so
        a co-curator (and the founder) manages the thing's owner's things only
        through the founder's rescue (``Collection.can_rescue``), never here.

        Iterates ``collections.all()`` (and ``is_curator`` iterates
        ``co_owners.all()``) rather than ``.filter().exists()`` so a view that
        prefetched ``collections__co_owners`` pays no extra query — the same
        reasoning as ``is_curator`` itself.
        """
        if self.is_owner(user_code):
            return True
        from core.models.collection import Collection

        return any(
            c.mode == Collection.Mode.PROPRIETARY and c.is_curator(user_code)
            for c in self.collections.all()
        )

    def collections_in_order(self):
        """The collections this thing sits in, oldest first, then by code.

        ``collections.all()`` has no ``ORDER BY``, so the rows come back in whatever order
        the database picks (and a prefetch can change it). Wherever the code takes "the
        first" collection it takes it from here. A thing lives in one collection, so this
        only matters for a row from before that rule. Sorted in Python over the prefetched
        rows: it costs no query.
        """
        return sorted(self.collections.all(), key=lambda c: (c.created, c.code))

    def can_rescue(self, user_code):
        """The founder of a network this thing sits in (``Collection.can_rescue``):
        may reject a pending request on it and hide it, and nothing else. Apart
        from ``can_manage`` on purpose — rescuing is not managing."""
        return any(c.can_rescue(user_code) for c in self.collections.all())

    def can_delete(self, user_code):
        """Who may delete this thing — the one rule, for the endpoint that does it and the
        page that warns before: the owner of a collection it sits in (any mode); a
        co-curator of a PROPRIETARY one; its owner when they are a dinamizador of the
        NETWORK it sits in (lent or not: they run their things there); or its owner while
        it has never changed hands.

        Reads ``collections.all()`` and the co-owners through ``.all()`` like
        ``can_manage``, so a view that prefetched them pays nothing for the collections.
        """
        from core.models.collection import Collection

        is_owner = self.is_owner(user_code)
        for collection in self.collections.all():
            if collection.is_owner(user_code):
                return True
            if collection.mode == Collection.Mode.PROPRIETARY and collection.is_curator(user_code):
                return True
            if collection.mode == Collection.Mode.NETWORK and is_owner:
                if collection.is_curator(user_code):
                    return True
        return is_owner and not self.transfers.exists()

    def managers(self):
        """Every ``User`` for whom ``can_manage`` is true — the thing owner,
        plus the curators (owner + co-curators) of every PROPRIETARY collection
        it sits in. Deduped by code. Used to fan a notice out to the whole
        team that runs the thing (FAQ questions, reservation notices). In a
        NETWORK it is just the thing's owner: the founder's rescue powers don't
        make them a recipient of the day-to-day mail.
        Prefetch-aware via ``collections`` / ``co_owners`` like ``can_manage``.
        """
        from core.models.collection import Collection

        seen = {self.owner.code: self.owner}
        for c in self.collections.all():
            if c.mode == Collection.Mode.PROPRIETARY:
                for u in [c.owner, *c.co_owners.all()]:
                    seen.setdefault(u.code, u)
        return list(seen.values())

    def reserve(self, user_code):
        """Test-only fixture helper: add a user to the deal M2M.

        The real reservation flow lives in core/services/booking_service.py
        (status transitions, locking, emails); this does none of that, and
        an unknown code is a silent no-op. Not for production code.
        """
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.deal.add(user)
        except User.DoesNotExist:
            pass

    def release(self, user_code):
        """Test-only fixture helper: remove a user from the deal M2M.

        Same caveats as reserve — the booking service owns the real flow.
        Not for production code.
        """
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.deal.remove(user)
        except User.DoesNotExist:
            pass

    def pause_period(self, today=None):
        """The pause as a blocked stretch, ``[paused_from, paused_until + 1)``, shaped
        like the rows the calendar readers take (``SaturatedPeriod``), or ``None`` when
        there is no pause or it is over.

        The one reading of the pause: the calendar serves it, the availability reads
        it and a request is refused against it. It is full whatever ``units`` says,
        and unlike a closure day (which only stops a pickup or a return that day) it
        stops anything that overlaps it, even a booking that starts before and ends
        after.
        """
        if self.paused_from is None or self.paused_until is None:
            return None
        if self.paused_until < (today or timezone.localdate()):
            return None
        from core.models.booking import SaturatedPeriod

        return SaturatedPeriod(self.paused_from, self.paused_until + timedelta(days=1))

    def pause_overlaps(self, start_date, end_date):
        """Whether ``[start_date, end_date)`` shares a day with the pause: the strict
        rule of ``BookingPeriod.has_overlap``, so touching at an end does not count
        (a loan that is back on the first day of the pause is fine)."""
        pause = self.pause_period()
        return pause is not None and start_date < pause.end_date and pause.start_date < end_date

    def served_periods(self, periods):
        """What is taken, as the browser is told and the availability is worked out:
        the stretches in which every unit is booked (``saturated_periods``) plus the
        pause. With one unit and no pause, ``periods`` unchanged."""
        from core.models.booking import saturated_periods

        served = saturated_periods(periods, self.units)
        pause = self.pause_period()
        if pause is None:
            return served
        return sorted(
            [*served, pause],
            key=lambda p: (p.start_date, p.start_time is not None, p.start_time or time.min),
        )

    def availability_window(self, horizon_days=90, collection=None):
        """Live availability for date-based things (LEND/RENT/RESERVE) from the calendar.

        Returns ``{"available_today": bool, "next_available": date|None}`` for
        DATE_BASED_TYPES, or ``None`` for any other type (where a booking calendar
        doesn't apply). Prefetch-aware: reuses ``self._blocked_periods`` when the
        view prefetched it, otherwise issues a single ``get_blocked_periods`` query.
        Result is memoised on the instance so the two serializer fields that read
        it don't recompute.

        The **governing collection's rental rules** (#7) are applied: its
        ``rental_weekdays``/``rental_durations`` decide which days a pickup could
        actually start on, so the indicator agrees with what the date picker
        offers. ``collection`` names that collection when the caller already knows
        it (the collection grid passes the collection being rendered); otherwise it
        is resolved from the thing's collections the same way a booking request
        does. A thing in two rule-setting collections uses the first one — the same
        approximation ``resolve_rental_collection`` already makes.
        """
        if hasattr(self, "_availability_window_cache"):
            return self._availability_window_cache

        from core.models.booking import DATE_BASED_TYPES, BookingPeriod

        if self.type not in DATE_BASED_TYPES:
            self._availability_window_cache = None
            return None

        if hasattr(self, "_blocked_periods"):
            blocked = self._blocked_periods
        else:
            blocked = list(BookingPeriod.get_blocked_periods(self.code))

        from core.services.booking_service import (
            compute_availability,
            compute_hourly_availability,
            resolve_rental_collection,
            resolve_reservations_collection,
        )

        # A RESERVE thing follows its reservations collection: weekdays are
        # reused as "days open", durations don't apply, and the walk stops at
        # that collection's own "how far ahead" horizon rather than the default.
        if self.type == Thing.Type.RESERVE_THING:
            # With several units the thing is unavailable only where they are all on,
            # and never during a pause.
            blocked = self.served_periods(blocked)
            rc = collection or resolve_reservations_collection(self)
            if rc and rc.is_hourly_reservations():
                available_today, next_available = compute_hourly_availability(blocked, rc)
            else:
                available_today, next_available = compute_availability(
                    blocked,
                    horizon_days=rc.reservation_horizon_days if rc else horizon_days,
                    allowed_weekdays=rc.rental_weekdays if rc else None,
                    closed_dates=rc.closed_date_set() if rc else None,
                )
            self._availability_window_cache = {
                "available_today": available_today,
                "next_available": next_available,
            }
            return self._availability_window_cache

        if collection is None:
            collection = resolve_rental_collection(self)
        blocked = self.served_periods(blocked)

        rules = collection.rental_rules_for(self.owner_id) if collection else None
        available_today, next_available = compute_availability(
            blocked,
            horizon_days=horizon_days,
            allowed_weekdays=rules.weekdays if rules else None,
            durations=rules.durations if rules else None,
            closed_dates=rules.closed if rules else None,
        )
        self._availability_window_cache = {
            "available_today": available_today,
            "next_available": next_available,
        }
        return self._availability_window_cache

    def can_view(self, user_code):
        """
        Check if the given user can view this thing.

        Visibility rules:
        - Owner can always view their own things
        - Invited users can only view ACTIVE or TAKEN things (not INACTIVE)
        - Anyone (including anonymous, ``user_code=None``) can view an ACTIVE/TAKEN
          thing that sits in at least one ACTIVE, PUBLIC collection

        Args:
            user_code: The user_code to check (None for an anonymous visitor)

        Returns:
            True if user is owner, or the thing is not INACTIVE and lives in an
            ACTIVE collection the user is invited to (or that is PUBLIC)
        """
        if self.is_owner(user_code):
            return True

        # INACTIVE things are only visible to the owner
        if self.status == self.Status.INACTIVE:
            return False

        # Visible if the thing is in any ACTIVE collection where the user is
        # invited, owns it, or the collection is PUBLIC (anonymous read).
        from core.models.collection import Collection

        # For an anonymous visitor (user_code=None) the membership/ownership
        # terms are dropped entirely: ``invites__code=None`` would otherwise
        # become ``IS NULL`` and, under the OR outer join, spuriously match
        # any collection that simply has no invitees.
        access = models.Q(visibility=Collection.Visibility.PUBLIC)
        if user_code is not None:
            access |= models.Q(invites__code=user_code) | models.Q(owner__code=user_code)

        return self.collections.filter(status=Collection.Status.ACTIVE).filter(access).exists()
