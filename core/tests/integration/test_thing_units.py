"""A space with several identical units: up to ``Thing.units`` reservations at once.

One rule of "full" (``saturated_periods``) is what a request is judged by, what the
calendar serves the browser and what the live availability reads. With one unit all
of it is what it always was; the rest of the suite is that proof, so these tests are
about what changes with more than one: who gets in, what is served, and that the
server and the page cannot disagree about a start.
"""

import random
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.models.booking import saturated_periods
from core.serializers.booking import BookingPeriodCalendarSerializer
from core.services.booking_service import BookingRequestError, request_reservation

pytestmark = pytest.mark.django_db

THING_URL = "/api/v1/things/{}/"
CALENDAR_URL = "/api/v1/things/{}/calendar/"


def _as(api_client, who):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(who).access_token}")
    return api_client


def _members(collection, count, first=1):
    people = [
        User.objects.create(code=f"UN{n:04d}", email=f"un{n}@your-domain.test")
        for n in range(first, first + count)
    ]
    collection.invites.add(*people)
    return people


@pytest.fixture
def shed(db, user):
    """A DAY-unit shed holding one space with four identical units."""
    collection = Collection.objects.create(
        code="UNSH01",
        owner=user,
        headline="Shed",
        status="ACTIVE",
        mode=Collection.Mode.PROPRIETARY,
        kind="SHED",
        allowed_thing_types=["RESERVE_THING"],
        reservation_max_days=3,
        reservation_max_active_per_member=50,
    )
    thing = Thing.objects.create(
        code="UNTH01", type=Thing.Type.RESERVE_THING, owner=user, headline="Lathe", units=4
    )
    collection.things.add(thing)
    return collection, thing


def _book(collection, thing, who, day, days=1):
    return request_reservation(
        thing,
        who,
        collection.owner.email,
        day,
        days,
        collection_code=collection.code,
    )


def _refusal(collection, thing, who, day, days=1):
    with pytest.raises(BookingRequestError) as caught:
        _book(collection, thing, who, day, days)
    return caught.value


def _row(start, end, start_time=None, end_time=None):
    """The five attributes of a booking that the calendar readers look at."""
    return SimpleNamespace(
        start_date=start, end_date=end, start_time=start_time, end_time=end_time, status="ACCEPTED"
    )


DAY = date(2026, 6, 1)


def _d(n):
    return DAY + timedelta(days=n)


class TestSaturatedPeriods:
    def test_with_one_unit_it_is_the_same_list(self):
        rows = [_row(_d(0), _d(2)), _row(_d(1), _d(3))]

        assert saturated_periods(rows, 1) is rows

    def test_with_no_units_to_speak_of_it_is_still_the_same_list(self):
        rows = [_row(_d(0), _d(2))]

        assert saturated_periods(rows, 0) is rows

    def test_nothing_booked_is_nothing_full(self):
        assert saturated_periods([], 3) == []

    def test_whole_days_are_counted_day_by_day_and_the_full_ones_join(self):
        # 0-4 and 2-6 with two units: both are on during days 2 and 3.
        rows = [_row(_d(0), _d(4)), _row(_d(2), _d(6))]

        full = saturated_periods(rows, 2)

        assert [(p.start_date, p.end_date, p.start_time) for p in full] == [(_d(2), _d(4), None)]

    def test_days_that_are_full_but_not_next_to_each_other_stay_apart(self):
        rows = [_row(_d(0), _d(2)), _row(_d(0), _d(2)), _row(_d(4), _d(5)), _row(_d(4), _d(5))]

        full = saturated_periods(rows, 2)

        assert [(p.start_date, p.end_date) for p in full] == [(_d(0), _d(2)), (_d(4), _d(5))]

    def test_a_booking_that_only_touches_at_the_end_does_not_overlap(self):
        rows = [_row(_d(0), _d(2)), _row(_d(2), _d(4))]

        assert saturated_periods(rows, 2) == []

    def test_hourly_stretches_are_swept_inside_their_day(self):
        rows = [
            _row(_d(0), _d(1), time(10), time(12)),
            _row(_d(0), _d(1), time(11), time(13)),
        ]

        full = saturated_periods(rows, 2)

        assert [(p.start_date, p.end_date, p.start_time, p.end_time) for p in full] == [
            (_d(0), _d(1), time(11), time(12))
        ]

    def test_hourly_stretches_that_touch_come_out_as_one(self):
        rows = [
            _row(_d(0), _d(1), time(10), time(12)),
            _row(_d(0), _d(1), time(11), time(14)),
            _row(_d(0), _d(1), time(12), time(13)),
        ]

        full = saturated_periods(rows, 2)

        assert [(p.start_time, p.end_time) for p in full] == [(time(11), time(13))]

    def test_hourly_bookings_of_different_days_never_meet(self):
        rows = [
            _row(_d(0), _d(1), time(10), time(12)),
            _row(_d(1), _d(2), time(10), time(12)),
        ]

        assert saturated_periods(rows, 2) == []

    def test_a_whole_day_booking_counts_against_every_hour(self):
        rows = [_row(_d(0), _d(1)), _row(_d(0), _d(1), time(11), time(12))]

        full = saturated_periods(rows, 2)

        assert [(p.start_time, p.end_time) for p in full] == [(time(11), time(12))]

    def test_enough_whole_day_bookings_make_the_day_full_whatever_the_hours(self):
        rows = [_row(_d(0), _d(1)), _row(_d(0), _d(1)), _row(_d(0), _d(1), time(11), time(12))]

        full = saturated_periods(rows, 2)

        assert [(p.start_date, p.end_date, p.start_time) for p in full] == [(_d(0), _d(1), None)]

    def test_the_rows_it_makes_serve_through_the_calendar_serializer(self):
        full = saturated_periods(
            [_row(_d(0), _d(1), time(10), time(12)), _row(_d(0), _d(1), time(11), time(13))], 2
        )

        data = BookingPeriodCalendarSerializer(full, many=True).data

        assert data == [
            {
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
                "start_time": "11:00:00",
                "end_time": "12:00:00",
                "status": "ACCEPTED",
            }
        ]

    def test_it_leaves_the_bookings_it_was_given_alone(self):
        rows = [_row(_d(0), _d(2)), _row(_d(1), _d(3))]
        before = [(r.start_date, r.end_date) for r in rows]

        saturated_periods(rows, 2)

        assert [(r.start_date, r.end_date) for r in rows] == before


class TestWhoGetsIn:
    def test_with_one_unit_a_second_overlapping_reservation_is_refused(self, shed):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=1)
        thing.refresh_from_db()
        first, second = _members(collection, 2)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, first, day)

        refusal = _refusal(collection, thing, second, day)

        assert (refusal.status_code, refusal.code) == (409, "dates_taken")

    def test_with_four_units_the_fourth_at_once_gets_in_and_the_fifth_does_not(self, shed):
        collection, thing = shed
        people = _members(collection, 5)
        day = date.today() + timedelta(days=2)
        for person in people[:4]:
            _book(collection, thing, person, day)

        refusal = _refusal(collection, thing, people[4], day)

        assert (refusal.status_code, refusal.code) == (409, "dates_taken")
        assert BookingPeriod.objects.filter(thing_code=thing).count() == 4

    def test_a_reservation_that_only_touches_the_end_of_a_full_stretch_gets_in(self, shed):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=2)
        thing.refresh_from_db()
        a, b, c = _members(collection, 3)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day, 2)
        _book(collection, thing, b, day, 2)

        # The two end on day + 2, the day it is free again.
        booking = _book(collection, thing, c, day + timedelta(days=2))

        assert booking.start_date == day + timedelta(days=2)

    def test_a_day_with_booked_neighbours_but_still_a_free_unit_is_not_refused(self, shed):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=2)
        thing.refresh_from_db()
        a, b, c = _members(collection, 3)
        day = date.today() + timedelta(days=2)
        # Two are on the first two days, one alone on the third: both of the first
        # two share days with a request for the third, but it is not full there.
        _book(collection, thing, a, day, 3)
        _book(collection, thing, b, day, 2)

        booking = _book(collection, thing, c, day + timedelta(days=2))

        assert booking.start_date == day + timedelta(days=2)

    def test_a_reservation_that_overlaps_a_full_stretch_by_one_day_does_not(self, shed):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=2)
        thing.refresh_from_db()
        a, b, c = _members(collection, 3)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day, 2)
        _book(collection, thing, b, day, 2)

        refusal = _refusal(collection, thing, c, day + timedelta(days=1), 2)

        assert refusal.status_code == 409

    def test_the_same_person_cannot_hold_two_at_once(self, shed):
        collection, thing = shed
        (person,) = _members(collection, 1)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, person, day, 2)

        refusal = _refusal(collection, thing, person, day + timedelta(days=1))

        assert (refusal.status_code, refusal.code) == (409, "reservation_one_per_person")
        assert BookingPeriod.objects.filter(thing_code=thing).count() == 1

    def test_the_same_person_can_hold_two_one_after_the_other(self, shed):
        collection, thing = shed
        (person,) = _members(collection, 1)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, person, day, 2)

        second = _book(collection, thing, person, day + timedelta(days=2))

        assert second.start_date == day + timedelta(days=2)

    def test_somebody_elses_overlapping_reservation_does_not_count_as_theirs(self, shed):
        collection, thing = shed
        a, b = _members(collection, 2)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day)

        assert _book(collection, thing, b, day).requester_code == b

    def test_a_cancelled_reservation_frees_the_person_and_the_unit(self, shed):
        collection, thing = shed
        (person,) = _members(collection, 1)
        day = date.today() + timedelta(days=2)
        booking = _book(collection, thing, person, day)
        BookingPeriod.objects.filter(pk=booking.pk).update(status=BookingPeriod.Status.CANCELLED)

        assert _book(collection, thing, person, day).start_date == day

    def test_lowering_the_units_cancels_nothing_and_refuses_the_next_one(
        self, shed, authenticated_client
    ):
        collection, thing = shed
        a, b, c, d = _members(collection, 4)
        day = date.today() + timedelta(days=2)
        for person in (a, b, c):
            _book(collection, thing, person, day)

        res = authenticated_client.patch(THING_URL.format(thing.code), {"units": 2}, format="json")

        assert res.status_code == status.HTTP_200_OK, res.data
        assert (
            BookingPeriod.objects.filter(
                thing_code=thing, status=BookingPeriod.Status.ACCEPTED
            ).count()
            == 3
        )
        assert _refusal(collection, thing, d, day).status_code == 409

    def test_with_more_units_than_reservations_a_booking_is_never_refused_for_being_full(
        self, shed
    ):
        collection, thing = shed
        people = _members(collection, 3)
        day = date.today() + timedelta(days=2)

        for person in people:
            _book(collection, thing, person, day, 3)

        assert BookingPeriod.objects.filter(thing_code=thing).count() == 3


class TestWhatIsServed:
    def _fill(self, collection, thing, people, day):
        for person in people:
            _book(collection, thing, person, day)

    def test_somebody_who_does_not_manage_it_is_served_only_the_full_stretches(
        self, shed, api_client
    ):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=2)
        a, b, c = _members(collection, 3)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day, 2)
        _book(collection, thing, b, day + timedelta(days=1), 2)
        _book(collection, thing, c, day + timedelta(days=5))

        res = _as(api_client, c).get(CALENDAR_URL.format(thing.code))

        assert res.status_code == status.HTTP_200_OK
        # Only day + 1 has both. Nobody's name is in it.
        assert [(row["start_date"], row["end_date"]) for row in res.data] == [
            (str(day + timedelta(days=1)), str(day + timedelta(days=2)))
        ]
        assert all(set(row) == set(BookingPeriodCalendarSerializer().fields) for row in res.data)

    def test_with_one_unit_a_member_is_served_every_booking_as_before(self, shed, api_client):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=1)
        a, b = _members(collection, 2)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day)
        _book(collection, thing, b, day + timedelta(days=3))

        res = _as(api_client, b).get(CALENDAR_URL.format(thing.code))

        assert len(res.data) == 2

    def test_whoever_manages_it_is_served_the_real_bookings_with_names(
        self, shed, authenticated_client
    ):
        collection, thing = shed
        a, b = _members(collection, 2)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day)
        _book(collection, thing, b, day)

        res = authenticated_client.get(CALENDAR_URL.format(thing.code))

        assert len(res.data) == 2
        assert {row["requester_code"] for row in res.data} == {a.code, b.code}

    def test_whoever_manages_it_is_served_what_a_member_would_with_for_request(
        self, shed, authenticated_client
    ):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=2)
        a, b = _members(collection, 2)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day, 2)
        _book(collection, thing, b, day + timedelta(days=1), 2)

        res = authenticated_client.get(CALENDAR_URL.format(thing.code) + "?for=request")

        assert [(row["start_date"], row["end_date"]) for row in res.data] == [
            (str(day + timedelta(days=1)), str(day + timedelta(days=2)))
        ]
        assert all("requester_code" not in row for row in res.data)

    def test_the_owners_own_list_on_the_thing_keeps_the_real_bookings(
        self, shed, authenticated_client
    ):
        collection, thing = shed
        a, b = _members(collection, 2)
        day = date.today() + timedelta(days=2)
        _book(collection, thing, a, day)
        _book(collection, thing, b, day)

        res = authenticated_client.get(
            THING_URL.format(thing.code) + f"?collection={collection.code}"
        )

        assert len(res.data["bookings"]) == 2

    def test_available_today_is_true_with_three_of_four_taken(self, shed):
        collection, thing = shed
        people = _members(collection, 3)
        self._fill(collection, thing, people, date.today())

        assert Thing.objects.get(pk=thing.pk).availability_window()["available_today"] is True

    def test_available_today_is_false_with_all_four_taken(self, shed):
        collection, thing = shed
        people = _members(collection, 4)
        self._fill(collection, thing, people, date.today())

        window = Thing.objects.get(pk=thing.pk).availability_window()

        assert window["available_today"] is False
        assert window["next_available"] == date.today() + timedelta(days=1)

    def test_the_thing_says_how_many_units_it_has(self, shed, api_client):
        collection, thing = shed
        (person,) = _members(collection, 1)

        res = _as(api_client, person).get(THING_URL.format(thing.code))

        assert res.data["units"] == 4


class TestTheNumberOfUnits:
    def _create(self, client, collection, **extra):
        return client.post(
            "/api/v1/things/",
            {"headline": "Lathe", "collection_code": collection.code, **extra},
            format="json",
        )

    def test_a_space_can_be_created_with_several_units(self, shed, authenticated_client):
        collection, _ = shed

        res = self._create(authenticated_client, collection, units=3)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert Thing.objects.get(code=res.data["code"]).units == 3

    def test_a_space_created_without_saying_has_one(self, shed, authenticated_client):
        collection, _ = shed

        res = self._create(authenticated_client, collection)

        assert res.data["units"] == 1

    @pytest.mark.parametrize("units", [0, 21, -1])
    def test_zero_and_more_than_twenty_are_refused(self, shed, authenticated_client, units):
        collection, _ = shed

        res = self._create(authenticated_client, collection, units=units)

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "units" in res.data

    def test_twenty_is_allowed(self, shed, authenticated_client):
        collection, _ = shed

        assert self._create(authenticated_client, collection, units=20).status_code == 201

    def test_a_loan_can_have_several_units(self, authenticated_client, user):
        library = Collection.objects.create(
            code="UNLB01",
            owner=user,
            headline="Library",
            kind="LIBRARY",
            allowed_thing_types=["LEND_THING", "RENT_THING"],
        )

        res = self._create(authenticated_client, library, units=6)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert Thing.objects.get(code=res.data["code"]).units == 6

    def test_a_gift_cannot_have_several_units(self, authenticated_client, user):
        stall = Collection.objects.create(code="UNST01", owner=user, headline="Stall")

        res = self._create(authenticated_client, stall, units=2)

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "units" in res.data

    def test_a_loan_can_be_created_naming_one_unit(self, authenticated_client, user):
        library = Collection.objects.create(
            code="UNLB02",
            owner=user,
            headline="Library",
            kind="LIBRARY",
            allowed_thing_types=["LEND_THING", "RENT_THING"],
        )

        res = self._create(authenticated_client, library, units=1)

        assert res.status_code == status.HTTP_201_CREATED, res.data

    def test_a_space_can_be_edited_to_a_different_number(self, shed, authenticated_client):
        _, thing = shed

        res = authenticated_client.patch(THING_URL.format(thing.code), {"units": 7}, format="json")

        assert res.status_code == status.HTTP_200_OK, res.data
        thing.refresh_from_db()
        assert thing.units == 7

    def test_editing_a_loan_to_several_units_is_allowed(self, authenticated_client, user):
        library = Collection.objects.create(
            code="UNLB03",
            owner=user,
            headline="Library",
            kind="LIBRARY",
            allowed_thing_types=["LEND_THING", "RENT_THING"],
        )
        loan = Thing.objects.create(code="UNLN01", type=Thing.Type.LEND_THING, owner=user)
        library.things.add(loan)

        res = authenticated_client.patch(THING_URL.format(loan.code), {"units": 2}, format="json")

        assert res.status_code == status.HTTP_200_OK, res.data
        loan.refresh_from_db()
        assert loan.units == 2

    def test_a_loan_keeps_its_units_when_saved_for_something_else(self, authenticated_client, user):
        library = Collection.objects.create(
            code="UNLB05",
            owner=user,
            headline="Library",
            kind="LIBRARY",
            allowed_thing_types=["LEND_THING", "RENT_THING"],
        )
        loan = Thing.objects.create(
            code="UNLN03", type=Thing.Type.LEND_THING, owner=user, headline="Drill", units=3
        )
        library.things.add(loan)

        res = authenticated_client.patch(
            THING_URL.format(loan.code), {"headline": "Drill 2"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        loan.refresh_from_db()
        assert loan.units == 3

    def test_a_thing_that_is_neither_a_reservation_nor_a_loan_goes_back_to_one_unit(
        self, authenticated_client, user
    ):
        stall = Collection.objects.create(code="UNST04", owner=user, headline="Stall")
        # What a row left behind by a thing that used to be a reservation looks like.
        gift = Thing.objects.create(
            code="UNGF02", type=Thing.Type.GIFT_THING, owner=user, headline="Drill", units=3
        )
        stall.things.add(gift)

        res = authenticated_client.patch(
            THING_URL.format(gift.code), {"headline": "Drill 2"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        gift.refresh_from_db()
        assert gift.units == 1


# ── The cross-check: what is served as free is what the request accepts ──────────────


def _slot_free_in(served, day, start, end):
    """Whether ``[start, end)`` on ``day`` touches none of the stretches served as taken."""
    for row in served:
        if row.start_date > day or row.end_date <= day:
            continue
        if row.start_time is None:
            return False
        if row.start_time < end and row.end_time > start:
            return False
    return True


def _mins(minutes):
    return time(minutes // 60, minutes % 60)


@pytest.fixture
def hourly_shed(db, user):
    collection = Collection.objects.create(
        code="UNHR01",
        owner=user,
        headline="Hourly shed",
        status="ACTIVE",
        mode=Collection.Mode.PROPRIETARY,
        kind="SHED",
        allowed_thing_types=["RESERVE_THING"],
        reservation_unit=Collection.ReservationUnit.HOUR,
        reservation_min_minutes=30,
        reservation_max_minutes=240,
        reservation_max_active_per_member=50,
        reservation_horizon_days=365,
        opening_hours={str(n): [["09:00", "21:00"]] for n in range(7)},
    )
    thing = Thing.objects.create(
        code="UNTH02", type=Thing.Type.RESERVE_THING, owner=user, headline="Press", units=3
    )
    collection.things.add(thing)
    return collection, thing


class TestWhatIsServedFreeIsWhatIsAccepted:
    """The most important test of units: for bookings put down at random (a fixed seed),
    every start that the stretches served to the page leave free is a start that
    ``request_reservation`` accepts, and every start they leave taken is one it
    refuses for being taken. The page and the server run one rule or they disagree."""

    def _probe(self, collection, thing, who, day, start, end):
        try:
            booking = request_reservation(
                thing,
                who,
                collection.owner.email,
                day,
                collection_code=collection.code,
                start_time=start,
                end_time=end,
            )
        except BookingRequestError as exc:
            assert exc.code == "time_taken", (day, start, end, exc.code)
            return False
        BookingPeriod.objects.filter(pk=booking.pk).delete()
        return True

    @pytest.mark.parametrize("seed", range(8))
    def test_hourly_starts(self, hourly_shed, seed):
        collection, thing = hourly_shed
        rng = random.Random(20261103 + seed)
        day = date.today() + timedelta(days=3)
        people = _members(collection, 30)
        # Random hourly bookings on the half-hour grid, 30 to 180 minutes, and now and
        # then a whole-day one (a loan or a day-booking of the same thing).
        for number in range(rng.randint(6, 14)):
            if rng.random() < 0.1:
                start, end = None, None
            else:
                from_minute = 540 + 30 * rng.randint(0, 17)
                length = 30 * rng.randint(1, 6)
                start, end = _mins(from_minute), _mins(min(from_minute + length, 21 * 60))
            BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=people[number],
                requester_email=people[number].email,
                owner_code=thing.owner,
                start_date=day,
                end_date=day + timedelta(days=1),
                start_time=start,
                end_time=end,
                status=BookingPeriod.Status.ACCEPTED,
            )
        served = saturated_periods(list(BookingPeriod.objects.filter(thing_code=thing)), 3)
        probes = people[-1]  # nobody who booked above: the one-per-person rule is its own test

        checked = 0
        for duration in (30, 60, 120):
            for from_minute in range(540, 21 * 60 - duration + 1, 30):
                start, end = _mins(from_minute), _mins(from_minute + duration)
                expected = _slot_free_in(served, day, start, end)
                assert self._probe(collection, thing, probes, day, start, end) is expected, (
                    seed,
                    start,
                    end,
                )
                checked += 1
        assert checked > 30

    @pytest.mark.parametrize("seed", range(4))
    def test_day_starts(self, shed, seed):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=3)
        thing.refresh_from_db()
        rng = random.Random(20261103 + 100 + seed)
        first = date.today() + timedelta(days=2)
        people = _members(collection, 30)
        for number in range(rng.randint(5, 10)):
            start = first + timedelta(days=rng.randint(0, 9))
            BookingPeriod.objects.create(
                thing_code=thing,
                thing_type=thing.type,
                requester_code=people[number],
                requester_email=people[number].email,
                owner_code=thing.owner,
                start_date=start,
                end_date=start + timedelta(days=rng.randint(1, 3)),
                status=BookingPeriod.Status.ACCEPTED,
            )
        served = saturated_periods(list(BookingPeriod.objects.filter(thing_code=thing)), 3)

        for offset in range(0, 10):
            for days in (1, 2, 3):
                start = first + timedelta(days=offset)
                expected = all(
                    not (row.start_date < start + timedelta(days=days) and row.end_date > start)
                    for row in served
                )
                try:
                    booking = _book(collection, thing, people[-1], start, days)
                except BookingRequestError as exc:
                    assert exc.code == "dates_taken", (seed, start, days, exc.code)
                    accepted = False
                else:
                    BookingPeriod.objects.filter(pk=booking.pk).delete()
                    accepted = True
                assert accepted is expected, (seed, start, days)


def test_the_demo_has_one_space_with_three_units_and_the_rest_with_one():
    from django.core.management import call_command

    call_command("seed_demo", lang="en", verbosity=0)

    assert Thing.objects.get(code="1u1uRa").units == 3
    assert set(Thing.objects.exclude(code="1u1uRa").values_list("units", flat=True)) == {1}
