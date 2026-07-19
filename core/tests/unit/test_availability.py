"""
Tests for live availability (LEND/RENT): the pure `compute_availability` helper,
the `Thing.availability_window()` model method, and the serializer fields.
"""

from datetime import date, timedelta

import pytest
import time_machine
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Thing
from core.models.booking import BookingPeriod
from core.services.booking_service import compute_availability

TODAY = date(2026, 6, 12)


class _Block:
    """Minimal stand-in for a BookingPeriod row (start_date/end_date only)."""

    def __init__(self, start, end):
        self.start_date = start
        self.end_date = end


class TestComputeAvailability:
    def test_no_bookings_available_today(self):
        assert compute_availability([], today=TODAY) == (True, TODAY)

    def test_today_blocked_returns_return_day_as_next_free(self):
        # The next free day is the booking's return day (end), not end + 1 —
        # a return day is available for a fresh pickup (back-to-back).
        blocked = [_Block(date(2026, 6, 10), date(2026, 6, 15))]
        assert compute_availability(blocked, today=TODAY) == (False, date(2026, 6, 15))

    def test_back_to_back_ranges_skip_to_final_return_day(self):
        # Two bookings sharing a boundary (first returns 6/15, second picks up
        # 6/15) — 6/15 is a pickup day for the second, so the next free day is
        # only the second booking's return day (6/20).
        blocked = [
            _Block(date(2026, 6, 12), date(2026, 6, 15)),
            _Block(date(2026, 6, 15), date(2026, 6, 20)),
        ]
        assert compute_availability(blocked, today=TODAY) == (False, date(2026, 6, 20))

    def test_return_day_gap_between_non_adjacent_ranges(self):
        # First booking returns 6/14, second picks up 6/15 — 6/14 is free.
        blocked = [
            _Block(date(2026, 6, 12), date(2026, 6, 14)),
            _Block(date(2026, 6, 15), date(2026, 6, 20)),
        ]
        assert compute_availability(blocked, today=TODAY) == (False, date(2026, 6, 14))

    def test_future_booking_leaves_today_free(self):
        blocked = [_Block(date(2026, 7, 1), date(2026, 7, 5))]
        assert compute_availability(blocked, today=TODAY) == (True, TODAY)

    def test_booked_beyond_horizon_returns_none(self):
        blocked = [_Block(TODAY, date(2027, 1, 1))]
        assert compute_availability(blocked, today=TODAY) == (False, None)

    def test_null_dated_rows_are_skipped(self):
        # Non-date-based bookings (GIFT/SELL) have null start/end and must not block.
        assert compute_availability([_Block(None, None)], today=TODAY) == (True, TODAY)

    def test_custom_horizon(self):
        blocked = [_Block(TODAY, TODAY + timedelta(days=5))]
        # within a 3-day horizon the next free day (day 6) is out of range
        assert compute_availability(blocked, today=TODAY, horizon_days=3) == (False, None)

    def test_return_day_is_free_for_pickup(self):
        # A booking ending today leaves today available — today is its return day,
        # free for the next pickup (back-to-back handovers).
        blocked = [_Block(date(2026, 6, 1), TODAY)]
        assert compute_availability(blocked, today=TODAY) == (True, TODAY)


class TestComputeAvailabilityWithRentalRules:
    """Rental rules (#7) constrain which days a pickup can actually start on, so the
    card's indicator agrees with the picker (`rental.js::isPickupDisabled`)."""

    MONDAY = date(2026, 6, 15)
    WED = 2  # Python weekday for Wednesday

    def test_wednesdays_only_with_next_wednesday_booked(self):
        # The reported bug: asked on a Monday, in a Wednesdays-only collection whose
        # next Wednesday (6/17) is already booked for a week, the card said
        # "available today" — while the picker offered no selectable day.
        blocked = [_Block(date(2026, 6, 17), date(2026, 6, 24))]
        assert compute_availability(
            blocked, today=self.MONDAY, allowed_weekdays=[self.WED], durations=[7]
        ) == (False, date(2026, 6, 24))
        # Without the rules the same calendar reads as free today — the old answer.
        assert compute_availability(blocked, today=self.MONDAY) == (True, self.MONDAY)

    def test_pickup_on_a_booking_return_day_is_allowed(self):
        # 6/24 is the previous booking's return day and the next pickup day —
        # back-to-back handovers stay possible under the rules too.
        blocked = [_Block(date(2026, 6, 17), date(2026, 6, 24))]
        assert compute_availability(
            blocked, today=date(2026, 6, 24), allowed_weekdays=[self.WED], durations=[7]
        ) == (True, date(2026, 6, 24))

    def test_duration_that_does_not_fit_before_the_next_booking(self):
        # No weekday rule, one fixed 7-day length: today's rental would run into a
        # booking three days out, so the first day a 7-day rental fits is that
        # booking's return day.
        today = date(2026, 6, 12)
        blocked = [_Block(today + timedelta(days=3), today + timedelta(days=10))]
        assert compute_availability(blocked, today=today, durations=[7]) == (
            False,
            today + timedelta(days=10),
        )

    def test_longer_length_blocked_but_shorter_one_fits(self):
        # Any single allowed length is enough — 14 days would overlap, 7 days fits.
        today = date(2026, 6, 12)
        blocked = [_Block(today + timedelta(days=10), today + timedelta(days=20))]
        assert compute_availability(blocked, today=today, durations=[7, 14]) == (True, today)

    def test_return_weekday_never_allowed_means_never_available(self):
        # Wednesdays only + a 3-day length always returns on a Saturday — no legal
        # pickup exists anywhere in the horizon.
        assert compute_availability(
            [], today=self.MONDAY, allowed_weekdays=[self.WED], durations=[3]
        ) == (False, None)

    def test_weekday_rule_alone(self):
        # Weekdays without fixed lengths: the next allowed weekday, ignoring lengths.
        assert compute_availability([], today=self.MONDAY, allowed_weekdays=[self.WED]) == (
            False,
            date(2026, 6, 17),
        )

    def test_empty_rules_behave_as_no_rules(self):
        # Empty lists (a collection that sets neither) must not change the answer.
        blocked = [_Block(date(2026, 6, 10), date(2026, 6, 15))]
        assert compute_availability(
            blocked, today=TODAY, allowed_weekdays=[], durations=[]
        ) == compute_availability(blocked, today=TODAY)

    def test_horizon_exhausted_under_rules(self):
        assert compute_availability(
            [], today=self.MONDAY, allowed_weekdays=[self.WED], durations=[7], horizon_days=1
        ) == (False, None)


@pytest.mark.django_db
class TestAvailabilityWindowMethod:
    def _lend_thing(self, user):
        return Thing.objects.create(
            code="LEND01", type=Thing.Type.LEND_THING, owner=user, headline="Lendable"
        )

    def test_lend_thing_with_no_bookings(self, user):
        thing = self._lend_thing(user)
        window = thing.availability_window()
        assert window["available_today"] is True
        assert window["next_available"] is not None

    def test_non_date_type_returns_none(self, thing):
        # `thing` fixture is GIFT_THING
        assert thing.availability_window() is None

    @time_machine.travel(date(2026, 6, 15))  # a Monday — fixed, so both branches are pinned
    def test_collection_rental_rules_are_applied(self, user, collection):
        # The collection only lends on Wednesdays, for a week at a time. Asked on
        # a Monday, the thing is not available today and the next available day
        # is that Wednesday. (Unfrozen, this test used to assert a different
        # branch depending on the weekday CI happened to run.)
        collection.rental_weekdays = [2]
        collection.rental_durations = [7]
        collection.save()
        thing = self._lend_thing(user)
        collection.things.add(thing)

        window = thing.availability_window()

        assert window["available_today"] is False
        assert window["next_available"] == date(2026, 6, 17)


@pytest.mark.django_db
class TestAvailabilitySerializerFields:
    def _lend_thing(self, user, collection):
        t = Thing.objects.create(
            code="LEND02", type=Thing.Type.LEND_THING, owner=user, headline="Lendable"
        )
        collection.things.add(t)
        return t

    def test_lend_thing_available_today(self, authenticated_client, user, collection):
        thing = self._lend_thing(user, collection)
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert res.data["available_today"] is True
        assert res.data["next_available"] is not None

    def test_lend_thing_blocked_today_shows_next_available(
        self, authenticated_client, user, user2, collection
    ):
        thing = self._lend_thing(user, collection)
        today = date.today()
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=Thing.Type.LEND_THING,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=today,
            end_date=today + timedelta(days=3),
            status=BookingPeriod.Status.ACCEPTED,
        )
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert res.data["available_today"] is False
        # Return day (end) is free for the next pickup — back-to-back handovers.
        assert res.data["next_available"] == today + timedelta(days=3)

    def test_gift_thing_has_null_availability_fields(self, authenticated_client, thing):
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert res.data["available_today"] is None
        assert res.data["next_available"] is None


@pytest.mark.django_db
class TestCollectionCardAvailability:
    """The same live availability is surfaced on the collection-page cards
    (CollectionThingSummarySerializer), prefetch-aware to avoid N+1."""

    def test_lend_card_shows_availability(self, authenticated_client, user, collection):
        thing = Thing.objects.create(
            code="LEND03", type=Thing.Type.LEND_THING, owner=user, headline="Lendable"
        )
        collection.things.add(thing)
        res = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert res.status_code == 200
        card = next(c for c in res.data["things"] if c["code"] == thing.code)
        assert card["available_today"] is True
        assert card["next_available"] is not None

    def test_gift_card_has_null_availability(self, authenticated_client, thing, collection):
        # `thing` fixture (GIFT) is already in `collection`
        res = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert res.status_code == 200
        card = next(c for c in res.data["things"] if c["code"] == thing.code)
        assert card["available_today"] is None
        assert card["next_available"] is None

    def test_card_honours_the_collection_rental_rules(self, api_client, user, collection):
        # The card reads the rules from the collection it is being rendered in (the
        # grid doesn't prefetch each thing's collections, so it's passed via context).
        collection.rental_weekdays = [2]
        collection.rental_durations = [7]
        collection.save()
        thing = Thing.objects.create(
            code="LEND04", type=Thing.Type.LEND_THING, owner=user, headline="Wednesdays only"
        )
        collection.things.add(thing)

        # Freeze to a fixed Monday so both branches are pinned (unfrozen, this
        # test used to assert a different branch depending on CI's weekday).
        # The JWT must be minted INSIDE the window — a token from real "now"
        # is not yet valid back on the frozen date.
        with time_machine.travel(date(2026, 6, 15)):
            refresh = RefreshToken.for_user(user)
            api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
            res = api_client.get(f"/api/v1/collections/{collection.code}/")

        assert res.status_code == 200
        card = next(c for c in res.data["things"] if c["code"] == thing.code)
        assert card["available_today"] is False
        assert card["next_available"] == date(2026, 6, 17)
