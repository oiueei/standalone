"""The borrower's contact details a library may ask for: the switch and how long they live.

`Collection.lending_asks_contact` is a library's switch (off everywhere by default, refused
on a stall or a shed). The details themselves are one sealed column of the booking and go
as soon as nobody needs them: when the loan is marked returned, when the request is refused,
cancelled or expires, and 90 days after the return date at the latest.
"""

from datetime import UTC, date, datetime, timedelta
from io import StringIO

import pytest
import time_machine
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.services.booking_service import cancel_booking, reject_booking
from core.services.contact_seal import seal, unseal

pytestmark = pytest.mark.django_db

COLLECTIONS_URL = "/api/v1/collections/"
TODAY = date(2026, 10, 7)
DETAILS = {
    "full_name": "Laura Pérez Gómez",
    "address": "C/ de la Fusteria 12, 3r 2a",
    "phone": "+34 600 000 000",
    "identity_document": "12345678Z",
}


@pytest.fixture(autouse=True)
def _frozen_today():
    with time_machine.travel(datetime(2026, 10, 7, 12, 0, tzinfo=UTC)):
        yield


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner():
    return User.objects.create(code="LSOWN1", email="lala8@your-domain.test", name="Lala")


@pytest.fixture
def borrower():
    return User.objects.create(code="LSBOR1", email="lele10@your-domain.test", name="Lele")


@pytest.fixture
def library(owner, borrower):
    collection = Collection.objects.create(
        code="LSCOL1",
        owner=owner,
        headline="Tool library",
        kind=Collection.Kind.LIBRARY,
        mode=Collection.Mode.PROPRIETARY,
        allowed_thing_types=["LEND_THING", "RENT_THING"],
        lending_asks_contact=True,
    )
    collection.invites.add(borrower)
    return collection


@pytest.fixture
def drill(owner, library):
    thing = Thing.objects.create(code="LSTHN1", owner=owner, headline="Drill", type="LEND_THING")
    library.things.add(thing)
    return thing


def loan(thing, borrower, *, start, end, status_="ACCEPTED", contact=True, thing_type=None):
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing_type or thing.type,
        requester_code=borrower,
        requester_email=borrower.email,
        owner_code=thing.owner,
        start_date=start,
        end_date=end,
        status=status_,
        lending_contact=seal(DETAILS) if contact else "",
    )


class TestTheSwitch:
    def test_it_is_off_in_a_new_library(self, authenticated_client):
        res = authenticated_client.post(
            COLLECTIONS_URL, {"headline": "Lib", "kind": "LIBRARY"}, format="json"
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["lending_asks_contact"] is False
        assert Collection.objects.get(code=res.data["code"]).lending_asks_contact is False

    def test_a_library_can_turn_it_on_when_it_is_created(self, authenticated_client):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Lib", "kind": "LIBRARY", "lending_asks_contact": True},
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["lending_asks_contact"] is True

    def test_a_library_can_change_it_when_it_is_edited(self, owner, library):
        client = client_for(owner)

        off = client.patch(
            f"{COLLECTIONS_URL}{library.code}/", {"lending_asks_contact": False}, format="json"
        )
        on = client.patch(
            f"{COLLECTIONS_URL}{library.code}/", {"lending_asks_contact": True}, format="json"
        )

        assert off.status_code == on.status_code == status.HTTP_200_OK
        assert off.data["lending_asks_contact"] is False
        assert on.data["lending_asks_contact"] is True
        library.refresh_from_db()
        assert library.lending_asks_contact is True

    @pytest.mark.parametrize("kind", ["STALL", "SHED"])
    def test_a_stall_or_a_shed_refuses_it_at_creation(self, authenticated_client, kind):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Group", "kind": kind, "lending_asks_contact": True},
            format="json",
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "lending_asks_contact" in res.data
        assert not Collection.objects.filter(headline="Group").exists()

    @pytest.mark.parametrize("kind", ["STALL", "SHED"])
    def test_a_stall_or_a_shed_refuses_it_when_edited(self, owner, kind):
        group = Collection.objects.create(
            code="LSGRP1", owner=owner, headline="Group", kind=kind, mode="PROPRIETARY"
        )

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{group.code}/", {"lending_asks_contact": True}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "lending_asks_contact" in res.data
        group.refresh_from_db()
        assert group.lending_asks_contact is False

    def test_a_stall_can_still_be_edited_without_naming_it(self, owner):
        group = Collection.objects.create(
            code="LSGRP2", owner=owner, headline="Group", kind="STALL", mode="PROPRIETARY"
        )

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{group.code}/", {"headline": "Renamed"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK

    def test_a_library_that_already_existed_is_off(self, owner):
        old = Collection.objects.create(code="LSOLD1", owner=owner, headline="Old", kind="LIBRARY")

        assert old.lending_asks_contact is False
        assert (
            Collection.objects.values_list("lending_asks_contact", flat=True).get(pk=old.pk)
            is False
        )

    def test_the_thing_tells_the_request_page_whether_to_ask(self, drill, library, borrower):
        asks = client_for(borrower).get(f"/api/v1/things/{drill.code}/")
        Collection.objects.filter(pk=library.pk).update(lending_asks_contact=False)
        does_not = client_for(borrower).get(f"/api/v1/things/{drill.code}/")

        assert asks.data["collection_lending_asks_contact"] is True
        assert does_not.data["collection_lending_asks_contact"] is False


class TestTheyGoWhenNobodyNeedsThem:
    def test_marking_the_loan_returned_empties_them(self, drill, owner, borrower):
        booking = loan(
            drill, borrower, start=TODAY - timedelta(days=2), end=TODAY + timedelta(days=3)
        )

        res = client_for(owner).post(f"/api/v1/bookings/{booking.code}/returned/")

        assert res.status_code == 200
        booking.refresh_from_db()
        assert booking.lending_contact == ""

    def test_a_refused_request_loses_them(self, drill, borrower):
        booking = loan(
            drill, borrower, start=TODAY, end=TODAY + timedelta(days=3), status_="PENDING"
        )

        assert reject_booking(booking) is not None

        booking.refresh_from_db()
        assert booking.status == "REJECTED"
        assert booking.lending_contact == ""

    def test_a_cancelled_request_loses_them(self, drill, borrower):
        booking = loan(
            drill, borrower, start=TODAY, end=TODAY + timedelta(days=3), status_="PENDING"
        )

        assert cancel_booking(booking) is not None

        booking.refresh_from_db()
        assert booking.status == "CANCELLED"
        assert booking.lending_contact == ""

    def test_a_request_that_expires_loses_them(self, drill, borrower, settings):
        settings.BOOKING_EXPIRY_HOURS = 72
        booking = loan(
            drill, borrower, start=TODAY, end=TODAY + timedelta(days=3), status_="PENDING"
        )
        BookingPeriod.objects.filter(pk=booking.pk).update(
            created=datetime(2026, 10, 1, tzinfo=UTC)
        )

        assert BookingPeriod.expire_old_pending() == 1

        booking.refresh_from_db()
        assert booking.status == "EXPIRED"
        assert booking.lending_contact == ""

    def test_a_request_still_waiting_keeps_them(self, drill, borrower):
        booking = loan(
            drill, borrower, start=TODAY, end=TODAY + timedelta(days=3), status_="PENDING"
        )

        BookingPeriod.expire_old_pending()

        booking.refresh_from_db()
        assert unseal(booking.lending_contact) == DETAILS

    def test_an_accepted_loan_still_out_keeps_them(self, drill, borrower):
        booking = loan(
            drill, borrower, start=TODAY - timedelta(days=2), end=TODAY + timedelta(days=3)
        )

        booking.refresh_from_db()
        assert unseal(booking.lending_contact) == DETAILS


def purge(commit=False):
    out = StringIO()
    call_command("purge_expired_data", *(["--commit"] if commit else []), stdout=out)
    return out.getvalue()


class TestThePurgeBackstop:
    LABEL = "Lending contact details emptied (90 days after return)"

    def test_ninety_days_after_the_return_date_they_are_emptied(self, drill, borrower):
        old = loan(
            drill, borrower, start=TODAY - timedelta(days=100), end=TODAY - timedelta(days=90)
        )

        purge(commit=True)

        old.refresh_from_db()
        assert old.lending_contact == ""

    def test_eighty_nine_days_after_they_stay(self, drill, borrower):
        young = loan(
            drill, borrower, start=TODAY - timedelta(days=99), end=TODAY - timedelta(days=89)
        )

        purge(commit=True)

        young.refresh_from_db()
        assert unseal(young.lending_contact) == DETAILS

    def test_a_cancelled_or_expired_row_that_is_old_is_emptied_too(self, drill, borrower):
        rows = [
            loan(
                drill,
                borrower,
                start=TODAY - timedelta(days=120),
                end=TODAY - timedelta(days=100),
                status_=s,
            )
            for s in ("CANCELLED", "EXPIRED", "REJECTED")
        ]

        purge(commit=True)

        for row in rows:
            row.refresh_from_db()
            assert row.lending_contact == ""

    def test_nothing_but_the_details_is_touched(self, drill, borrower):
        old = loan(
            drill, borrower, start=TODAY - timedelta(days=100), end=TODAY - timedelta(days=95)
        )
        before = BookingPeriod.objects.values().get(pk=old.pk)

        purge(commit=True)

        after = BookingPeriod.objects.values().get(pk=old.pk)
        assert {k: v for k, v in after.items() if k != "lending_contact"} == {
            k: v for k, v in before.items() if k != "lending_contact"
        }

    def test_a_dry_run_counts_it_and_empties_nothing(self, drill, borrower):
        old = loan(
            drill, borrower, start=TODAY - timedelta(days=100), end=TODAY - timedelta(days=95)
        )

        output = purge()

        assert f"{self.LABEL}: 1" in output
        old.refresh_from_db()
        assert unseal(old.lending_contact) == DETAILS

    def test_running_it_again_finds_nothing_more(self, drill, borrower):
        loan(drill, borrower, start=TODAY - timedelta(days=100), end=TODAY - timedelta(days=95))
        purge(commit=True)

        assert f"{self.LABEL}: 0" in purge(commit=True)

    def test_a_row_with_no_details_is_not_counted(self, drill, borrower):
        loan(
            drill,
            borrower,
            start=TODAY - timedelta(days=100),
            end=TODAY - timedelta(days=95),
            contact=False,
        )

        assert f"{self.LABEL}: 0" in purge()

    def test_an_operator_cannot_switch_it_off(self, drill, borrower, settings):
        for name in dir(settings):
            if name.startswith("RETENTION_"):
                setattr(settings, name, 0)
        old = loan(
            drill, borrower, start=TODAY - timedelta(days=100), end=TODAY - timedelta(days=95)
        )

        purge(commit=True)

        old.refresh_from_db()
        assert old.lending_contact == ""
