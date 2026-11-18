"""Asking a borrower for contact details, and who gets to read them.

A library that turns `lending_asks_contact` on needs all four details (full name, address,
phone, identity document) before a loan or a rental can be requested; one that does not ask
ignores them. They are kept sealed, read opened only by whoever manages the thing and by the
borrower in their own account copy, and appear in no email, calendar file or group export.
"""

import json
from datetime import date, timedelta

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.services.calendar_export_service import build_calendar_export
from core.services.contact_seal import unseal
from core.services.export_service import (
    build_account_export,
    build_collection_export,
    export_bytes,
)

pytestmark = pytest.mark.django_db

DETAILS = {
    "full_name": "Laura Pérez Gómez",
    "address": "C/ de la Fusteria 12, 3r 2a\n08003 Barcelona",
    "phone": "+34 600 000 000",
    "identity_document": "12345678Z",
}
SECRETS = ("12345678Z", "Pérez Gómez", "Fusteria", "600 000 000")


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner():
    return User.objects.create(code="LRQOW1", email="lala9@your-domain.test", name="Lala")


@pytest.fixture
def borrower():
    return User.objects.create(code="LRQBO1", email="lele11@your-domain.test", name="Lele")


@pytest.fixture
def curator():
    return User.objects.create(code="LRQCU1", email="lolo4@your-domain.test", name="Lolo")


@pytest.fixture
def member():
    return User.objects.create(code="LRQME1", email="lili7@your-domain.test", name="Lili")


@pytest.fixture
def library(owner, borrower, curator, member):
    collection = Collection.objects.create(
        code="LRQCL1",
        owner=owner,
        headline="Tool library",
        kind=Collection.Kind.LIBRARY,
        mode=Collection.Mode.PROPRIETARY,
        allowed_thing_types=["LEND_THING", "RENT_THING"],
        lending_asks_contact=True,
    )
    collection.invites.add(borrower, curator, member)
    collection.co_owners.add(curator)
    return collection


@pytest.fixture
def drill(owner, library):
    thing = Thing.objects.create(code="LRQTH1", owner=owner, headline="Drill", type="LEND_THING")
    library.things.add(thing)
    return thing


def dates():
    start = date.today() + timedelta(days=3)
    return {"start_date": str(start), "end_date": str(start + timedelta(days=4))}


def ask(user, thing, body=None, **extra):
    payload = {**dates(), "collection_code": "LRQCL1", **(body or {}), **extra}
    return client_for(user).post(f"/api/v1/things/{thing.code}/request/", payload, format="json")


class TestWhenTheLibraryAsks:
    def test_without_the_details_the_request_is_refused_in_every_field_and_nothing_is_created(
        self, drill, borrower
    ):
        res = ask(borrower, drill)

        assert res.status_code == 400
        assert set(res.data["lending_contact"]) == set(DETAILS)
        assert res.data["code"] == "lending_contact_required"
        assert BookingPeriod.objects.count() == 0
        assert mail.outbox == []

    def test_with_the_four_details_it_goes_through_and_they_are_kept_sealed(self, drill, borrower):
        res = ask(borrower, drill, {"lending_contact": DETAILS})

        assert res.status_code == 201, res.data
        booking = BookingPeriod.objects.get(code=res.data["booking_code"])
        assert unseal(booking.lending_contact) == DETAILS
        for secret in SECRETS:
            assert secret not in booking.lending_contact

    def test_the_details_are_trimmed(self, drill, borrower):
        padded = {k: f"  {v}  " for k, v in DETAILS.items()}

        res = ask(borrower, drill, {"lending_contact": padded})

        assert res.status_code == 201, res.data
        assert unseal(BookingPeriod.objects.get().lending_contact) == DETAILS

    @pytest.mark.parametrize("missing", list(DETAILS))
    def test_each_of_the_four_is_required(self, drill, borrower, missing):
        partial = {k: v for k, v in DETAILS.items() if k != missing}

        res = ask(borrower, drill, {"lending_contact": partial})

        assert res.status_code == 400
        assert list(res.data["lending_contact"]) == [missing]
        assert res.data["code"] == "lending_contact_required"
        assert BookingPeriod.objects.count() == 0

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_an_empty_one_is_the_same_as_a_missing_one(self, drill, borrower, blank):
        res = ask(borrower, drill, {"lending_contact": {**DETAILS, "phone": blank}})

        assert res.status_code == 400
        assert list(res.data["lending_contact"]) == ["phone"]
        assert res.data["code"] == "lending_contact_required"

    @pytest.mark.parametrize("junk", ["Laura", 7, ["a"], None])
    def test_details_that_are_not_a_mapping_are_all_missing(self, drill, borrower, junk):
        res = ask(borrower, drill, {"lending_contact": junk})

        assert res.status_code == 400
        assert set(res.data["lending_contact"]) == set(DETAILS)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("full_name", "Laura <b>Pérez</b>"),
            ("full_name", "L" * 129),
            ("full_name", "Laura\nPérez"),
            ("address", "<script>alert(1)</script>"),
            ("address", "C" * 257),
            ("phone", "call me"),
            ("phone", "12345"),
            ("phone", "6" * 33),
            ("identity_document", "ab"),
            ("identity_document", "12345678Z!"),
            ("identity_document", "1" * 33),
        ],
    )
    def test_a_detail_that_breaks_its_rule_is_refused_in_its_own_field(
        self, drill, borrower, field, value
    ):
        res = ask(borrower, drill, {"lending_contact": {**DETAILS, field: value}})

        assert res.status_code == 400
        assert list(res.data["lending_contact"]) == [field]
        assert res.data["code"] == "lending_contact_invalid"
        assert BookingPeriod.objects.count() == 0

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("full_name", "L" * 128),
            ("address", "C" * 256),
            ("phone", "600123456"),
            ("phone", "(93) 123-45.67"),
            ("phone", "6" * 32),
            ("identity_document", "AB12"),
            ("identity_document", "X-1234.567 Z"),
            ("identity_document", "1" * 32),
        ],
    )
    def test_a_detail_exactly_on_its_limit_is_accepted(self, drill, borrower, field, value):
        res = ask(borrower, drill, {"lending_contact": {**DETAILS, field: value}})

        assert res.status_code == 201, res.data

    def test_a_mix_of_missing_and_invalid_lifts_no_single_code_but_says_each_field(
        self, drill, borrower
    ):
        res = ask(
            borrower,
            drill,
            {"lending_contact": {"full_name": "Laura", "phone": "x", "identity_document": ""}},
        )

        assert res.status_code == 400
        assert set(res.data["lending_contact"]) == {"address", "phone", "identity_document"}
        assert "code" not in res.data

    def test_the_dates_are_still_judged_first(self, drill, borrower):
        res = ask(borrower, drill, {"start_date": "2020-01-01"})

        assert res.status_code == 400
        assert "start_date" in res.data
        assert "lending_contact" not in res.data

    def test_a_rental_asks_the_same(self, owner, library, borrower):
        saw = Thing.objects.create(code="LRQTH2", owner=owner, headline="Saw", type="RENT_THING")
        library.things.add(saw)

        assert ask(borrower, saw).status_code == 400
        assert ask(borrower, saw, {"lending_contact": DETAILS}).status_code == 201


class TestWhenTheLibraryDoesNotAsk:
    @pytest.fixture(autouse=True)
    def _off(self, library):
        Collection.objects.filter(pk=library.pk).update(lending_asks_contact=False)

    def test_a_request_needs_nothing_and_keeps_nothing(self, drill, borrower):
        res = ask(borrower, drill)

        assert res.status_code == 201, res.data
        assert BookingPeriod.objects.get().lending_contact == ""

    def test_details_sent_anyway_are_ignored_without_an_error_and_not_stored(self, drill, borrower):
        res = ask(borrower, drill, {"lending_contact": DETAILS})

        assert res.status_code == 201, res.data
        assert BookingPeriod.objects.get().lending_contact == ""

    def test_even_garbage_is_ignored(self, drill, borrower):
        res = ask(borrower, drill, {"lending_contact": {"phone": "<b>"}})

        assert res.status_code == 201, res.data
        assert BookingPeriod.objects.get().lending_contact == ""


def _requested(drill, borrower):
    res = ask(borrower, drill, {"lending_contact": DETAILS})
    assert res.status_code == 201, res.data
    return BookingPeriod.objects.get(code=res.data["booking_code"])


def _row(user, code):
    rows = client_for(user).get("/api/v1/owner-bookings/").data["results"]
    return next((row for row in rows if row["code"] == code), None)


class TestWhoReadsThem:
    def test_the_owner_of_the_thing_reads_them_opened(self, drill, owner, borrower):
        booking = _requested(drill, borrower)

        assert _row(owner, booking.code)["lending_contact"] == DETAILS

    def test_a_curator_of_a_proprietary_library_reads_them_too(self, drill, curator, borrower):
        booking = _requested(drill, borrower)

        assert _row(curator, booking.code)["lending_contact"] == DETAILS

    def test_a_request_with_none_says_none(self, drill, owner, borrower, library):
        Collection.objects.filter(pk=library.pk).update(lending_asks_contact=False)
        res = ask(borrower, drill)

        assert _row(owner, res.data["booking_code"])["lending_contact"] is None

    def test_the_borrower_does_not_get_them_back_in_my_requests(self, drill, borrower):
        _requested(drill, borrower)

        rows = client_for(borrower).get("/api/v1/my-bookings/").data["results"]

        assert rows
        assert all("lending_contact" not in row for row in rows)
        assert not any(secret in json.dumps(rows) for secret in SECRETS)

    def test_without_a_request_the_serializer_serves_nothing(self, drill, borrower):
        from core.serializers import BookingPeriodSerializer

        booking = _requested(drill, borrower)

        assert BookingPeriodSerializer(booking).data["lending_contact"] is None

    def test_in_a_network_only_the_owner_of_the_thing_reads_them_not_the_founder(
        self, owner, borrower, curator
    ):
        network = Collection.objects.create(
            code="LRQNT1",
            owner=owner,
            headline="Network",
            kind=Collection.Kind.LIBRARY,
            mode=Collection.Mode.NETWORK,
            allowed_thing_types=["LEND_THING", "RENT_THING"],
            lending_asks_contact=True,
        )
        network.invites.add(borrower, curator)
        network.co_owners.add(curator)
        ladder = Thing.objects.create(
            code="LRQTH3", owner=curator, headline="Ladder", type="LEND_THING"
        )
        network.things.add(ladder)
        res = client_for(borrower).post(
            f"/api/v1/things/{ladder.code}/request/",
            {**dates(), "collection_code": "LRQNT1", "lending_contact": DETAILS},
            format="json",
        )
        assert res.status_code == 201, res.data

        assert _row(curator, res.data["booking_code"])["lending_contact"] == DETAILS
        founders_row = _row(owner, res.data["booking_code"])
        assert founders_row is not None  # the founder sees the request, for the rescue
        assert founders_row["lending_contact"] is None

    def test_another_member_does_not_see_the_request_at_all(self, drill, member, borrower):
        booking = _requested(drill, borrower)

        assert _row(member, booking.code) is None


class TestTheyNeverLeaveByAnyOtherDoor:
    def test_no_email_carries_them_not_even_after_the_loan_is_accepted(
        self, drill, owner, borrower
    ):
        booking = _requested(drill, borrower)
        assert client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/").status_code == 200

        assert mail.outbox, "the request and its decision were mailed"
        for message in mail.outbox:
            body = " ".join(
                [message.subject, message.body, *(alt[0] for alt in message.alternatives)]
            )
            for secret in SECRETS:
                assert secret not in body

    def test_the_thing_page_and_the_calendar_do_not_carry_them(self, drill, owner, borrower):
        _requested(drill, borrower)

        thing = client_for(owner).get(f"/api/v1/things/{drill.code}/?collection=LRQCL1")
        calendar = client_for(owner).get(f"/api/v1/things/{drill.code}/calendar/")

        for response in (thing, calendar):
            assert response.status_code == 200
            text = response.content.decode()
            assert "lending_contact" not in text
            assert not any(secret in text for secret in SECRETS)

    def test_the_calendar_file_does_not_carry_them(self, drill, owner, borrower, library):
        booking = _requested(drill, borrower)
        client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/")

        ics, count, _ = build_calendar_export(library, owner)

        assert count == 1
        text = ics.decode()
        assert not any(secret in text for secret in SECRETS)

    def test_the_groups_copy_does_not_carry_them(self, drill, owner, borrower, library):
        booking = _requested(drill, borrower)
        client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/")

        text = export_bytes(build_collection_export(library)).decode()

        assert '"bookings"' in text
        assert "lending_contact" not in text
        assert not any(secret in text for secret in SECRETS)

    def test_the_owners_own_account_copy_does_not_carry_the_borrowers_details(
        self, drill, owner, borrower
    ):
        _requested(drill, borrower)

        copy = build_account_export(owner)
        text = export_bytes(copy).decode()

        assert copy["bookings"]["received_by_me"]
        assert not any(secret in text for secret in SECRETS)
        assert all("lending_contact" not in row for row in copy["bookings"]["received_by_me"])

    def test_the_borrowers_own_account_copy_carries_theirs_opened(self, drill, borrower):
        _requested(drill, borrower)

        copy = build_account_export(borrower)

        (row,) = copy["bookings"]["requested_by_me"]
        assert row["lending_contact"] == DETAILS

    def test_once_the_loan_is_marked_returned_the_borrowers_copy_says_none(
        self, drill, borrower, owner
    ):
        booking = _requested(drill, borrower)
        assert client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/").status_code == 200
        BookingPeriod.objects.filter(pk=booking.pk).update(
            start_date=date.today() - timedelta(days=1)
        )
        assert (
            client_for(owner).post(f"/api/v1/bookings/{booking.code}/returned/").status_code == 200
        )

        (row,) = build_account_export(borrower)["bookings"]["requested_by_me"]

        assert row["lending_contact"] is None
        assert _row(owner, booking.code)["lending_contact"] is None
