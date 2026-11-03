"""Pausing a thing with a calendar between two days.

A pause is a blocked stretch, not a closure day: it stops anything that overlaps it
(even a booking that starts before and ends after), however many units the thing has.
It is served to whoever asks to book and checked when they do, from one place
(``Thing.pause_period``); it takes nothing back from bookings already made; and it ends
on its own once its last day has passed.
"""

from datetime import date, time, timedelta

import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.serializers.booking import BookingPeriodCalendarSerializer
from core.services.booking_service import (
    BookingRequestError,
    request_date_based_booking,
    request_reservation,
)

pytestmark = pytest.mark.django_db

THING_URL = "/api/v1/things/{}/"
CALENDAR_URL = "/api/v1/things/{}/calendar/"
REQUEST_URL = "/api/v1/things/{}/request/"
TODAY = date.today()


def _d(n):
    return TODAY + timedelta(days=n)


def _as(api_client, who):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(who).access_token}")
    return api_client


def _members(collection, count, first=1):
    people = [
        User.objects.create(code=f"PA{n:04d}", email=f"pa{n}@your-domain.test")
        for n in range(first, first + count)
    ]
    collection.invites.add(*people)
    return people


@pytest.fixture
def library(db, user):
    collection = Collection.objects.create(
        code="PALB01",
        owner=user,
        headline="Library",
        status="ACTIVE",
        kind="LIBRARY",
        allowed_thing_types=["LEND_THING", "RENT_THING"],
    )
    thing = Thing.objects.create(
        code="PATH01", type=Thing.Type.LEND_THING, owner=user, headline="Drill"
    )
    collection.things.add(thing)
    return collection, thing


@pytest.fixture
def shed(db, user):
    collection = Collection.objects.create(
        code="PASH01",
        owner=user,
        headline="Shed",
        status="ACTIVE",
        mode=Collection.Mode.PROPRIETARY,
        kind="SHED",
        allowed_thing_types=["RESERVE_THING"],
        reservation_max_days=7,
        reservation_max_active_per_member=50,
    )
    thing = Thing.objects.create(
        code="PATH02", type=Thing.Type.RESERVE_THING, owner=user, headline="Lathe"
    )
    collection.things.add(thing)
    return collection, thing


@pytest.fixture
def hourly_shed(db, user):
    collection = Collection.objects.create(
        code="PAHR01",
        owner=user,
        headline="Hourly shed",
        status="ACTIVE",
        mode=Collection.Mode.PROPRIETARY,
        kind="SHED",
        allowed_thing_types=["RESERVE_THING"],
        reservation_unit=Collection.ReservationUnit.HOUR,
        reservation_min_minutes=60,
        reservation_max_minutes=240,
        reservation_horizon_days=365,
        reservation_max_active_per_member=50,
        opening_hours={str(n): [["09:00", "21:00"]] for n in range(7)},
    )
    thing = Thing.objects.create(
        code="PATH03", type=Thing.Type.RESERVE_THING, owner=user, headline="Press"
    )
    collection.things.add(thing)
    return collection, thing


def _pause(thing, start, end):
    Thing.objects.filter(pk=thing.pk).update(paused_from=start, paused_until=end)
    thing.refresh_from_db()


def _loan(thing, who, start, end):
    return request_date_based_booking(thing, who, start, end, collection_code=None)


def _reserve(collection, thing, who, day, days=1, **hours):
    return request_reservation(
        thing, who, collection.owner.email, day, days, collection_code=collection.code, **hours
    )


def _refusal(fn, *args, **kwargs):
    with pytest.raises(BookingRequestError) as caught:
        fn(*args, **kwargs)
    return caught.value


class TestThePauseIsOneStretch:
    def test_without_a_pause_there_is_no_stretch(self, library):
        _, thing = library

        assert thing.pause_period() is None

    def test_it_runs_from_the_first_day_to_the_day_after_the_last(self, library):
        _, thing = library
        _pause(thing, _d(10), _d(12))

        pause = thing.pause_period()

        assert (pause.start_date, pause.end_date) == (_d(10), _d(13))
        assert pause.start_time is None and pause.end_time is None

    def test_a_pause_that_has_ended_is_no_stretch(self, library):
        _, thing = library
        _pause(thing, _d(-5), _d(-1))

        assert thing.pause_period() is None

    def test_a_pause_whose_last_day_is_today_still_is(self, library):
        _, thing = library
        _pause(thing, _d(-2), _d(0))

        assert thing.pause_period() is not None

    def test_it_is_a_stretch_the_calendar_serializer_can_serve(self, library):
        _, thing = library
        _pause(thing, _d(10), _d(10))

        data = BookingPeriodCalendarSerializer([thing.pause_period()], many=True).data

        assert data == [
            {
                "start_date": str(_d(10)),
                "end_date": str(_d(11)),
                "start_time": None,
                "end_time": None,
                "status": "ACCEPTED",
            }
        ]


class TestWhatIsRefused:
    def test_a_loan_that_starts_before_and_ends_after_the_pause_is_refused(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        refusal = _refusal(_loan, thing, person, _d(8), _d(15))

        assert (refusal.status_code, refusal.code) == (409, "thing_paused")
        assert not BookingPeriod.objects.filter(thing_code=thing).exists()

    def test_a_loan_inside_the_pause_is_refused(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        assert _refusal(_loan, thing, person, _d(11), _d(12)).code == "thing_paused"

    def test_a_loan_that_is_back_on_the_first_day_of_the_pause_gets_in(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        booking = _loan(thing, person, _d(7), _d(10))

        assert booking.end_date == _d(10)

    def test_a_loan_that_starts_the_day_after_the_pause_gets_in(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        assert _loan(thing, person, _d(13), _d(15)).start_date == _d(13)

    def test_a_loan_that_starts_on_the_last_day_of_the_pause_is_refused(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        assert _refusal(_loan, thing, person, _d(12), _d(14)).code == "thing_paused"

    def test_the_refusal_comes_over_the_api_with_its_code(self, library, api_client):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        res = _as(api_client, person).post(
            REQUEST_URL.format(thing.code),
            {
                "start_date": str(_d(11)),
                "end_date": str(_d(13)),
                "collection_code": collection.code,
            },
            format="json",
        )

        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["code"] == "thing_paused"
        assert res.data["error"] == "This thing is paused on those dates."

    def test_a_day_reservation_that_spans_the_pause_is_refused(self, shed):
        collection, thing = shed
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(10))

        refusal = _refusal(_reserve, collection, thing, person, _d(9), 3)

        assert (refusal.status_code, refusal.code) == (409, "thing_paused")

    def test_a_reservation_by_the_hour_on_a_paused_day_is_refused(self, hourly_shed):
        collection, thing = hourly_shed
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(10))

        refusal = _refusal(
            _reserve, collection, thing, person, _d(10), start_time=time(10), end_time=time(11)
        )

        assert (refusal.status_code, refusal.code) == (409, "thing_paused")

    def test_a_reservation_by_the_hour_the_day_after_gets_in(self, hourly_shed):
        collection, thing = hourly_shed
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(10))

        booking = _reserve(
            collection, thing, person, _d(11), start_time=time(10), end_time=time(11)
        )

        assert booking.start_date == _d(11)

    def test_with_four_units_and_nothing_booked_the_pause_blocks_all_the_same(self, shed):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=4)
        thing.refresh_from_db()
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        assert _refusal(_reserve, collection, thing, person, _d(11)).code == "thing_paused"

    def test_a_pause_that_has_ended_blocks_nothing(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(-5), _d(-1))

        assert _loan(thing, person, _d(2), _d(4)).start_date == _d(2)

    def test_the_day_the_pause_ends_it_blocks_that_day_and_not_the_next(self, library):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(-3), _d(0))

        assert _refusal(_loan, thing, person, _d(0), _d(2)).code == "thing_paused"
        assert _loan(thing, person, _d(1), _d(2)).start_date == _d(1)


class TestWhatIsLeftAlone:
    def test_bookings_already_made_are_not_touched_by_a_pause(self, library, authenticated_client):
        collection, thing = library
        a, b = _members(collection, 2)
        _loan(thing, a, _d(10), _d(12))
        pending = _loan(thing, b, _d(20), _d(22))
        BookingPeriod.objects.filter(pk=pending.pk).update(status=BookingPeriod.Status.ACCEPTED)

        res = authenticated_client.patch(
            THING_URL.format(thing.code),
            {"paused_from": str(_d(9)), "paused_until": str(_d(25))},
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        assert BookingPeriod.objects.filter(thing_code=thing).count() == 2
        assert set(BookingPeriod.objects.values_list("status", flat=True)) == {
            BookingPeriod.Status.PENDING,
            BookingPeriod.Status.ACCEPTED,
        }

    def test_the_owners_list_on_the_thing_does_not_carry_the_pause(
        self, shed, authenticated_client
    ):
        collection, thing = shed
        (person,) = _members(collection, 1)
        _reserve(collection, thing, person, _d(3))
        _pause(thing, _d(10), _d(12))

        res = authenticated_client.get(
            THING_URL.format(thing.code) + f"?collection={collection.code}"
        )

        assert len(res.data["bookings"]) == 1

    def test_whoever_manages_it_is_served_the_real_bookings_without_the_pause(
        self, library, authenticated_client
    ):
        collection, thing = library
        (person,) = _members(collection, 1)
        _loan(thing, person, _d(3), _d(5))
        _pause(thing, _d(10), _d(12))

        res = authenticated_client.get(CALENDAR_URL.format(thing.code))

        assert [row["requester_code"] for row in res.data] == [person.code]


class TestWhatIsServed:
    def test_somebody_who_does_not_manage_it_is_served_the_pause_as_a_stretch(
        self, library, api_client
    ):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        res = _as(api_client, person).get(CALENDAR_URL.format(thing.code))

        assert [(row["start_date"], row["end_date"]) for row in res.data] == [
            (str(_d(10)), str(_d(13)))
        ]
        assert all("requester_code" not in row for row in res.data)

    def test_whoever_manages_it_is_served_it_when_they_ask_to_book(
        self, library, authenticated_client
    ):
        _, thing = library
        _pause(thing, _d(10), _d(12))

        res = authenticated_client.get(CALENDAR_URL.format(thing.code) + "?for=request")

        assert [(row["start_date"], row["end_date"]) for row in res.data] == [
            (str(_d(10)), str(_d(13)))
        ]

    def test_it_comes_with_the_bookings_a_member_is_served(self, shed, api_client):
        collection, thing = shed
        Thing.objects.filter(pk=thing.pk).update(units=2)
        a, b = _members(collection, 2)
        _reserve(collection, thing, a, _d(3), 2)
        _reserve(collection, thing, b, _d(3), 2)
        _pause(thing, _d(10), _d(10))

        res = _as(api_client, a).get(CALENDAR_URL.format(thing.code))

        assert sorted((row["start_date"], row["end_date"]) for row in res.data) == [
            (str(_d(3)), str(_d(5))),
            (str(_d(10)), str(_d(11))),
        ]

    def test_a_pause_that_has_ended_is_not_served(self, library, api_client):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(-5), _d(-1))

        res = _as(api_client, person).get(CALENDAR_URL.format(thing.code))

        assert res.data == []

    def test_the_thing_reads_back_a_pause_that_is_in_force(self, library, api_client):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(10), _d(12))

        res = _as(api_client, person).get(THING_URL.format(thing.code))

        assert (res.data["paused_from"], res.data["paused_until"]) == (str(_d(10)), str(_d(12)))

    def test_the_thing_reads_back_no_dates_when_the_pause_has_ended(self, library, api_client):
        collection, thing = library
        (person,) = _members(collection, 1)
        _pause(thing, _d(-5), _d(-1))

        res = _as(api_client, person).get(THING_URL.format(thing.code))

        assert (res.data["paused_from"], res.data["paused_until"]) == (None, None)
        # The stored days are still there; only the reading hides them.
        thing.refresh_from_db()
        assert thing.paused_until == _d(-1)

    def test_a_thing_never_paused_reads_back_none(self, library, api_client):
        collection, thing = library
        (person,) = _members(collection, 1)

        res = _as(api_client, person).get(THING_URL.format(thing.code))

        assert (res.data["paused_from"], res.data["paused_until"]) == (None, None)

    def test_available_today_is_false_during_the_pause_and_the_next_day_is_the_day_after(
        self, library
    ):
        _, thing = library
        _pause(thing, _d(-1), _d(3))

        window = Thing.objects.get(pk=thing.pk).availability_window()

        assert window["available_today"] is False
        assert window["next_available"] == _d(4)

    def test_a_reservation_space_is_not_available_today_during_the_pause(self, shed):
        _, thing = shed
        _pause(thing, _d(0), _d(0))

        window = Thing.objects.get(pk=thing.pk).availability_window()

        assert window["available_today"] is False
        assert window["next_available"] == _d(1)

    def test_an_hourly_space_is_not_available_on_a_paused_day(self, hourly_shed):
        _, thing = hourly_shed
        _pause(thing, _d(1), _d(2))

        window = Thing.objects.get(pk=thing.pk).availability_window()

        assert window["next_available"] not in (_d(1), _d(2))

    def test_a_pause_that_has_ended_leaves_availability_as_it_was(self, library):
        _, thing = library
        _pause(thing, _d(-5), _d(-1))

        assert Thing.objects.get(pk=thing.pk).availability_window()["available_today"] is True


class TestSettingThePause:
    def _patch(self, client, thing, **body):
        return client.patch(THING_URL.format(thing.code), body, format="json")

    def test_whoever_manages_the_thing_can_set_and_remove_it(self, library, authenticated_client):
        _, thing = library

        res = self._patch(
            authenticated_client, thing, paused_from=str(_d(10)), paused_until=str(_d(12))
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        thing.refresh_from_db()
        assert (thing.paused_from, thing.paused_until) == (_d(10), _d(12))

        res = self._patch(authenticated_client, thing, paused_from=None, paused_until=None)

        assert res.status_code == status.HTTP_200_OK, res.data
        thing.refresh_from_db()
        assert (thing.paused_from, thing.paused_until) == (None, None)

    def test_a_pause_of_one_day_is_allowed(self, library, authenticated_client):
        _, thing = library

        res = self._patch(
            authenticated_client, thing, paused_from=str(_d(10)), paused_until=str(_d(10))
        )

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_a_pause_that_starts_today_is_allowed(self, library, authenticated_client):
        _, thing = library

        res = self._patch(
            authenticated_client, thing, paused_from=str(_d(0)), paused_until=str(_d(3))
        )

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_somebody_who_does_not_manage_it_cannot_set_one(self, library, api_client):
        collection, thing = library
        (person,) = _members(collection, 1)

        res = self._patch(
            _as(api_client, person), thing, paused_from=str(_d(10)), paused_until=str(_d(12))
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN
        thing.refresh_from_db()
        assert thing.paused_from is None

    @pytest.mark.parametrize("only", ["paused_from", "paused_until"])
    def test_only_one_of_the_two_days_is_refused(self, library, authenticated_client, only):
        _, thing = library

        res = self._patch(authenticated_client, thing, **{only: str(_d(10))})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert set(res.data) & {"paused_from", "paused_until"}
        thing.refresh_from_db()
        assert thing.paused_from is None and thing.paused_until is None

    def test_clearing_only_one_of_two_stored_days_is_refused(self, library, authenticated_client):
        _, thing = library
        _pause(thing, _d(10), _d(12))

        res = self._patch(authenticated_client, thing, paused_from=None)

        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_pause_that_ends_before_it_starts_is_refused_in_its_field(
        self, library, authenticated_client
    ):
        _, thing = library

        res = self._patch(
            authenticated_client, thing, paused_from=str(_d(12)), paused_until=str(_d(10))
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "paused_until" in res.data

    def test_a_pause_that_ends_in_the_past_is_refused(self, library, authenticated_client):
        _, thing = library

        res = self._patch(
            authenticated_client, thing, paused_from=str(_d(-5)), paused_until=str(_d(-1))
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "paused_until" in res.data

    def test_a_year_is_allowed_and_a_day_more_is_not(self, library, authenticated_client):
        _, thing = library

        a_year = self._patch(
            authenticated_client, thing, paused_from=str(_d(1)), paused_until=str(_d(365))
        )
        too_long = self._patch(
            authenticated_client, thing, paused_from=str(_d(1)), paused_until=str(_d(366))
        )

        assert a_year.status_code == status.HTTP_200_OK, a_year.data
        assert too_long.status_code == status.HTTP_400_BAD_REQUEST
        assert "paused_until" in too_long.data

    def test_a_gift_cannot_be_paused(self, authenticated_client, user):
        stall = Collection.objects.create(code="PAST01", owner=user, headline="Stall")
        gift = Thing.objects.create(code="PATH04", type=Thing.Type.GIFT_THING, owner=user)
        stall.things.add(gift)

        res = self._patch(
            authenticated_client, gift, paused_from=str(_d(10)), paused_until=str(_d(12))
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "paused_from" in res.data
        gift.refresh_from_db()
        assert gift.paused_from is None

    def test_taking_the_pause_off_a_gift_is_always_allowed(self, authenticated_client, user):
        stall = Collection.objects.create(code="PAST02", owner=user, headline="Stall")
        gift = Thing.objects.create(code="PATH05", type=Thing.Type.GIFT_THING, owner=user)
        stall.things.add(gift)

        res = self._patch(authenticated_client, gift, paused_from=None, paused_until=None)

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_a_pause_that_has_ended_does_not_stop_an_unrelated_edit(
        self, library, authenticated_client
    ):
        _, thing = library
        _pause(thing, _d(-5), _d(-1))

        res = self._patch(authenticated_client, thing, headline="Drill 2")

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_a_space_can_be_paused(self, shed, authenticated_client):
        _, thing = shed

        res = self._patch(
            authenticated_client, thing, paused_from=str(_d(10)), paused_until=str(_d(12))
        )

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_creating_a_thing_cannot_set_it(self, library, authenticated_client):
        collection, _ = library

        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Saw",
                "collection_code": collection.code,
                "paused_from": str(_d(10)),
                "paused_until": str(_d(12)),
            },
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        thing = Thing.objects.get(code=res.data["code"])
        assert thing.paused_from is None
