"""The optional contact phone of a reservation.

A shed may ask, when someone books, for a phone number to use if something goes wrong
the same day. The number is optional, lives in the app only (never in an email or the
calendar file), reaches whoever manages the reservation and nobody else, and is gone
from the reading the day after the booking. Deleting it for good is
``purge_expired_data`` (``test_retention.py``).
"""

from datetime import date, timedelta

import pytest
from django.core import mail
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.services.calendar_export_service import build_calendar_export

pytestmark = pytest.mark.django_db

REQUEST_URL = "/api/v1/things/{}/request/"
COLLECTIONS_URL = "/api/v1/collections/"
OWNER_BOOKINGS_URL = "/api/v1/owner-bookings/"
PHONE = "600 123 456"


def _as(api_client, who):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(who).access_token}")
    return api_client


def _next_monday():
    d = date.today() + timedelta(days=1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


@pytest.fixture
def shed(db, user, user2):
    """A shed that asks for the phone, one space in it, and a member (user2)."""
    coll = Collection.objects.create(
        code="PHSH01",
        owner=user,
        headline="Shed",
        status="ACTIVE",
        mode=Collection.Mode.PROPRIETARY,
        kind="SHED",
        allowed_thing_types=["RESERVE_THING"],
        reservation_max_days=3,
        reservation_asks_phone=True,
    )
    coll.invites.add(user2)
    thing = Thing.objects.create(
        code="PHTH01",
        type=Thing.Type.RESERVE_THING,
        owner=user,
        headline="Lathe",
    )
    coll.things.add(thing)
    return {"collection": coll, "thing": thing, "owner": user, "member": user2}


def _book(api_client, shed, **extra):
    return _as(api_client, shed["member"]).post(
        REQUEST_URL.format(shed["thing"].code),
        {
            "start_date": str(_next_monday()),
            "duration_days": 1,
            "collection_code": shed["collection"].code,
            **extra,
        },
        format="json",
    )


def _booking_row(shed, *, start, end, phone=PHONE, status_=BookingPeriod.Status.ACCEPTED):
    return BookingPeriod.objects.create(
        thing_code=shed["thing"],
        thing_type=Thing.Type.RESERVE_THING,
        requester_code=shed["member"],
        requester_email=shed["member"].email,
        owner_code=shed["owner"],
        start_date=start,
        end_date=end,
        contact_phone=phone,
        status=status_,
    )


class TestTheSwitch:
    def test_a_shed_can_turn_the_switch_on_when_it_is_created(self, authenticated_client):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Shed", "kind": "SHED", "reservation_asks_phone": True},
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["reservation_asks_phone"] is True
        assert Collection.objects.get(code=res.data["code"]).reservation_asks_phone is True

    def test_a_shed_can_change_the_switch_when_it_is_edited(self, authenticated_client, shed):
        res = authenticated_client.patch(
            f"{COLLECTIONS_URL}{shed['collection'].code}/",
            {"reservation_asks_phone": False},
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        shed["collection"].refresh_from_db()
        assert shed["collection"].reservation_asks_phone is False

    @pytest.mark.parametrize("kind", ["STALL", "LIBRARY"])
    def test_a_collection_that_is_not_a_shed_refuses_the_switch_at_creation(
        self, authenticated_client, kind
    ):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Group", "kind": kind, "reservation_asks_phone": True},
            format="json",
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "reservation_asks_phone" in res.data
        assert not Collection.objects.filter(headline="Group").exists()

    def test_a_collection_that_is_not_a_shed_refuses_the_switch_when_edited(
        self, authenticated_client, user
    ):
        stall = Collection.objects.create(code="PHST01", owner=user, headline="Stall")

        res = authenticated_client.patch(
            f"{COLLECTIONS_URL}{stall.code}/", {"reservation_asks_phone": True}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        stall.refresh_from_db()
        assert stall.reservation_asks_phone is False

    def test_a_stall_can_still_be_edited_without_naming_the_switch(
        self, authenticated_client, user
    ):
        stall = Collection.objects.create(code="PHST02", owner=user, headline="Stall")

        res = authenticated_client.patch(
            f"{COLLECTIONS_URL}{stall.code}/", {"headline": "Renamed"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK


class TestTheRequestPageIsToldWhetherToAsk:
    def test_the_thing_says_its_collection_asks_for_the_phone(self, api_client, shed):
        res = _as(api_client, shed["member"]).get(
            f"/api/v1/things/{shed['thing'].code}/?collection={shed['collection'].code}"
        )

        assert res.status_code == status.HTTP_200_OK
        assert res.data["collection_reservation_asks_phone"] is True

    def test_the_thing_says_it_does_not_when_the_collection_does_not_ask(self, api_client, shed):
        Collection.objects.filter(pk=shed["collection"].pk).update(reservation_asks_phone=False)

        res = _as(api_client, shed["member"]).get(
            f"/api/v1/things/{shed['thing'].code}/?collection={shed['collection'].code}"
        )

        assert res.data["collection_reservation_asks_phone"] is False


class TestSavingTheNumber:
    def test_it_is_saved_when_the_collection_asks(self, api_client, shed):
        res = _book(api_client, shed, contact_phone=PHONE)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == PHONE

    def test_it_is_dropped_without_an_error_when_the_collection_does_not_ask(
        self, api_client, shed
    ):
        Collection.objects.filter(pk=shed["collection"].pk).update(reservation_asks_phone=False)

        res = _book(api_client, shed, contact_phone=PHONE)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == ""

    def test_leaving_it_out_is_always_allowed(self, api_client, shed):
        res = _book(api_client, shed)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == ""

    def test_an_empty_one_is_the_same_as_none(self, api_client, shed):
        res = _book(api_client, shed, contact_phone="   ")

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == ""

    def test_the_spaces_around_it_are_trimmed(self, api_client, shed):
        res = _book(api_client, shed, contact_phone=f"  {PHONE}  ")

        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == PHONE

    @pytest.mark.parametrize("number", ["+34 600 123 456", "(93) 123-45.67", "600123456", "123456"])
    def test_the_usual_ways_of_writing_a_number_are_accepted(self, api_client, shed, number):
        res = _book(api_client, shed, contact_phone=number)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == number

    @pytest.mark.parametrize(
        "number",
        [
            "12345",  # five digits
            "+ ( ) . - ",  # punctuation only, no digits
            "12 34 5",  # six characters but five digits
            "call me 600123456",  # letters
            "6" * 33,  # one over the column
        ],
    )
    def test_a_value_that_is_not_a_phone_number_is_refused_in_its_field(
        self, api_client, shed, number
    ):
        res = _book(api_client, shed, contact_phone=number)

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "contact_phone" in res.data
        assert not BookingPeriod.objects.exists()

    def test_thirty_two_characters_still_fit(self, api_client, shed):
        number = "6" * 32

        res = _book(api_client, shed, contact_phone=number)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).contact_phone == number


class TestWhoReadsIt:
    def test_whoever_manages_the_reservation_receives_it(self, api_client, shed):
        _booking_row(shed, start=date.today(), end=date.today() + timedelta(days=1))

        res = _as(api_client, shed["owner"]).get(OWNER_BOOKINGS_URL)

        assert res.status_code == status.HTTP_200_OK
        assert [row["contact_phone"] for row in res.data["results"]] == [PHONE]

    def test_a_co_curator_receives_it_like_the_requester_email(self, api_client, shed):
        user3 = User.objects.create(code="PHCO01", email="lili3@your-domain.test", name="Co")
        shed["collection"].invites.add(user3)
        shed["collection"].co_owners.add(user3)
        _booking_row(shed, start=date.today(), end=date.today() + timedelta(days=1))

        res = _as(api_client, user3).get(OWNER_BOOKINGS_URL)

        row = res.data["results"][0]
        assert row["requester_email"] == shed["member"].email
        assert row["contact_phone"] == PHONE

    def test_the_person_who_booked_does_not_receive_it_back_in_their_own_list(
        self, api_client, shed
    ):
        _booking_row(shed, start=date.today(), end=date.today() + timedelta(days=1))

        res = _as(api_client, shed["member"]).get("/api/v1/my-bookings/")

        assert res.status_code == status.HTTP_200_OK
        assert all("contact_phone" not in row for row in res.data["results"])

    def test_the_calendar_a_manager_reads_does_not_carry_it(self, api_client, shed):
        _booking_row(shed, start=date.today(), end=date.today() + timedelta(days=1))

        res = _as(api_client, shed["owner"]).get(f"/api/v1/things/{shed['thing'].code}/calendar/")

        assert res.status_code == status.HTTP_200_OK
        assert all("contact_phone" not in row for row in res.data)


class TestItStopsBeingServedTheDayAfter:
    def test_a_whole_day_reservation_shows_it_through_its_last_day(self, api_client, shed):
        today = date.today()
        _booking_row(shed, start=today, end=today + timedelta(days=1))

        res = _as(api_client, shed["owner"]).get(OWNER_BOOKINGS_URL)

        assert res.data["results"][0]["contact_phone"] == PHONE

    def test_the_day_after_the_reservation_it_comes_back_empty_though_nothing_deleted_it(
        self, api_client, shed
    ):
        today = date.today()
        row = _booking_row(shed, start=today - timedelta(days=1), end=today)

        res = _as(api_client, shed["owner"]).get(OWNER_BOOKINGS_URL)

        assert res.data["results"][0]["contact_phone"] == ""
        row.refresh_from_db()
        assert row.contact_phone == PHONE  # the purge, not the reading, deletes

    def test_an_hourly_reservation_of_today_still_shows_it(self, api_client, shed):
        today = date.today()
        # An hourly booking carries end_date = start_date + 1 and never spans midnight.
        row = _booking_row(shed, start=today, end=today + timedelta(days=1))
        BookingPeriod.objects.filter(pk=row.pk).update(start_time="10:00", end_time="12:00")

        res = _as(api_client, shed["owner"]).get(OWNER_BOOKINGS_URL)

        assert res.data["results"][0]["contact_phone"] == PHONE

    def test_an_hourly_reservation_of_yesterday_no_longer_does(self, api_client, shed):
        today = date.today()
        row = _booking_row(shed, start=today - timedelta(days=1), end=today)
        BookingPeriod.objects.filter(pk=row.pk).update(start_time="10:00", end_time="12:00")

        res = _as(api_client, shed["owner"]).get(OWNER_BOOKINGS_URL)

        assert res.data["results"][0]["contact_phone"] == ""


class TestTheNumberStaysOutOfEveryEmailAndFile:
    def test_the_notice_says_a_number_was_left_but_never_prints_it(self, api_client, shed):
        mail.outbox.clear()

        res = _book(api_client, shed, contact_phone=PHONE)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        notice = next(m for m in mail.outbox if shed["owner"].email in m.to)
        assert "They left a contact phone number" in notice.body
        assert "bookings page" in notice.body
        assert not any(PHONE in m.body or "600123456" in m.body for m in mail.outbox)
        assert not any(PHONE in str(m.alternatives) for m in mail.outbox)

    def test_the_notice_has_no_such_line_when_nobody_left_a_number(self, api_client, shed):
        mail.outbox.clear()

        _book(api_client, shed)

        notice = next(m for m in mail.outbox if shed["owner"].email in m.to)
        assert "contact phone number" not in notice.body

    def test_the_requester_confirmation_carries_neither_the_line_nor_the_number(
        self, api_client, shed
    ):
        mail.outbox.clear()

        _book(api_client, shed, contact_phone=PHONE)

        confirmation = next(m for m in mail.outbox if shed["member"].email in m.to)
        assert "contact phone number" not in confirmation.body
        assert PHONE not in confirmation.body

    def test_the_calendar_file_does_not_carry_it(self, shed):
        _booking_row(
            shed, start=date.today() + timedelta(days=2), end=date.today() + timedelta(days=3)
        )

        ics, count, _ = build_calendar_export(shed["collection"], shed["owner"])

        assert count == 1
        assert b"600 123 456" not in ics
        assert b"600123456" not in ics
