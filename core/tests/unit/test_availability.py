"""
Tests for live availability (LEND/RENT): the pure `compute_availability` helper,
the `Thing.availability_window()` model method, and the serializer fields.
"""

from datetime import date, timedelta

import pytest

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

    def test_today_blocked_returns_next_free_day(self):
        blocked = [_Block(date(2026, 6, 10), date(2026, 6, 15))]
        assert compute_availability(blocked, today=TODAY) == (False, date(2026, 6, 16))

    def test_contiguous_ranges_skip_to_first_gap(self):
        blocked = [
            _Block(date(2026, 6, 12), date(2026, 6, 14)),
            _Block(date(2026, 6, 15), date(2026, 6, 20)),
        ]
        assert compute_availability(blocked, today=TODAY) == (False, date(2026, 6, 21))

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

    def test_inclusive_end_day(self):
        # A booking ending today blocks today; next free day is tomorrow.
        blocked = [_Block(date(2026, 6, 1), TODAY)]
        assert compute_availability(blocked, today=TODAY) == (False, TODAY + timedelta(days=1))


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
        assert res.data["next_available"] == today + timedelta(days=4)

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
