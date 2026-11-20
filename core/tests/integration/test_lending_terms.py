"""A library that asks borrowers to accept its terms, and where the record of it lives.

`Collection.lending_asks_terms` is a library's switch (off everywhere by default, refused on a
stall or a shed, and refused on with no welcome document). The terms are that document. When
the library asks, a request has to say `accepts_terms: true`, and the loan keeps when and
which document; the record is shown in no screen, email or calendar file, only in the two
downloads.
"""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.serializers import BookingPeriodSerializer
from core.services.calendar_export_service import build_calendar_export
from core.services.export_service import (
    build_account_export,
    build_collection_export,
    export_bytes,
)

pytestmark = pytest.mark.django_db

COLLECTIONS_URL = "/api/v1/collections/"
DOC = "oiueei/documents/terms-v1"
NEW_DOC = "oiueei/documents/terms-v2"
NOW = datetime(2026, 10, 7, 12, 30, 45, tzinfo=UTC)
# The acceptance is moved to a moment nothing else in a response shares (the request's own
# `created` is "now"), so finding it in a screen or a message can only mean it leaked there.
STAMP = "2026-09-01T08:15:30"


@pytest.fixture(autouse=True)
def _frozen_now():
    with time_machine.travel(NOW, tick=False):
        yield


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner():
    return User.objects.create(code="LTOWN1", email="lala12@your-domain.test", name="Lala")


@pytest.fixture
def borrower():
    return User.objects.create(code="LTBOR1", email="lele12@your-domain.test", name="Lele")


@pytest.fixture
def library(owner, borrower):
    collection = Collection.objects.create(
        code="LTCOL1",
        owner=owner,
        headline="Tool library",
        kind=Collection.Kind.LIBRARY,
        mode=Collection.Mode.PROPRIETARY,
        allowed_thing_types=["LEND_THING", "RENT_THING"],
        welcome_doc=DOC,
        lending_asks_terms=True,
    )
    collection.invites.add(borrower)
    return collection


@pytest.fixture
def drill(owner, library):
    thing = Thing.objects.create(code="LTTH01", owner=owner, headline="Drill", type="LEND_THING")
    library.things.add(thing)
    return thing


def ask(user, thing, body=None):
    start = date.today() + timedelta(days=3)
    payload = {
        "start_date": str(start),
        "end_date": str(start + timedelta(days=4)),
        "collection_code": "LTCOL1",
        **(body or {}),
    }
    return client_for(user).post(f"/api/v1/things/{thing.code}/request/", payload, format="json")


def _requested(drill, borrower):
    res = ask(borrower, drill, {"accepts_terms": True})
    assert res.status_code == 201, res.data
    return BookingPeriod.objects.get(code=res.data["booking_code"])


def _requested_at_a_distinct_moment(drill, borrower):
    booking = _requested(drill, borrower)
    BookingPeriod.objects.filter(pk=booking.pk).update(
        terms_accepted_at=datetime(2026, 9, 1, 8, 15, 30, tzinfo=UTC)
    )
    return booking


class TestTheSwitch:
    def test_it_is_off_in_a_new_library(self, authenticated_client):
        res = authenticated_client.post(
            COLLECTIONS_URL, {"headline": "Lib", "kind": "LIBRARY"}, format="json"
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["lending_asks_terms"] is False
        assert Collection.objects.get(code=res.data["code"]).lending_asks_terms is False

    def test_a_library_with_a_document_can_turn_it_on_when_it_is_created(
        self, authenticated_client
    ):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Lib", "kind": "LIBRARY", "welcome_doc": DOC, "lending_asks_terms": True},
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["lending_asks_terms"] is True

    def test_a_library_with_a_document_can_change_it_when_it_is_edited(self, owner, library):
        client = client_for(owner)

        off = client.patch(
            f"{COLLECTIONS_URL}{library.code}/", {"lending_asks_terms": False}, format="json"
        )
        on = client.patch(
            f"{COLLECTIONS_URL}{library.code}/", {"lending_asks_terms": True}, format="json"
        )

        assert off.status_code == on.status_code == status.HTTP_200_OK
        assert off.data["lending_asks_terms"] is False
        assert on.data["lending_asks_terms"] is True
        library.refresh_from_db()
        assert library.lending_asks_terms is True

    def test_the_document_can_come_in_the_same_edit(self, owner, library):
        Collection.objects.filter(pk=library.pk).update(welcome_doc="", lending_asks_terms=False)

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{library.code}/",
            {"welcome_doc": DOC, "lending_asks_terms": True},
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        library.refresh_from_db()
        assert library.lending_asks_terms is True

    @pytest.mark.parametrize("kind", ["STALL", "SHED"])
    def test_a_stall_or_a_shed_refuses_it_at_creation(self, authenticated_client, kind):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Group", "kind": kind, "welcome_doc": DOC, "lending_asks_terms": True},
            format="json",
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "lending_asks_terms" in res.data
        assert not Collection.objects.filter(headline="Group").exists()

    @pytest.mark.parametrize("kind", ["STALL", "SHED"])
    def test_a_stall_or_a_shed_refuses_it_when_edited(self, owner, kind):
        group = Collection.objects.create(
            code="LTGRP1",
            owner=owner,
            headline="Group",
            kind=kind,
            mode="PROPRIETARY",
            welcome_doc=DOC,
        )

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{group.code}/", {"lending_asks_terms": True}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "lending_asks_terms" in res.data
        group.refresh_from_db()
        assert group.lending_asks_terms is False

    def test_turning_it_on_without_a_document_is_refused_with_its_code_at_creation(
        self, authenticated_client
    ):
        res = authenticated_client.post(
            COLLECTIONS_URL,
            {"headline": "Lib", "kind": "LIBRARY", "lending_asks_terms": True},
            format="json",
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "terms_need_welcome_doc"
        assert "lending_asks_terms" in res.data
        assert not Collection.objects.filter(headline="Lib").exists()

    def test_turning_it_on_without_a_document_is_refused_with_its_code_when_edited(
        self, owner, library
    ):
        Collection.objects.filter(pk=library.pk).update(welcome_doc="", lending_asks_terms=False)

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{library.code}/", {"lending_asks_terms": True}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "terms_need_welcome_doc"
        library.refresh_from_db()
        assert library.lending_asks_terms is False

    def test_turning_it_on_while_removing_the_document_is_refused(self, owner, library):
        Collection.objects.filter(pk=library.pk).update(lending_asks_terms=False)

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{library.code}/",
            {"welcome_doc": "", "lending_asks_terms": True},
            format="json",
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "terms_need_welcome_doc"

    def test_a_library_already_on_that_lost_its_document_can_still_save_its_settings(
        self, owner, library
    ):
        Collection.objects.filter(pk=library.pk).update(welcome_doc="")

        res = client_for(owner).patch(
            f"{COLLECTIONS_URL}{library.code}/",
            {"lending_asks_terms": True, "headline": "Renamed"},
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_a_library_that_already_existed_is_off(self, owner):
        old = Collection.objects.create(code="LTOLD1", owner=owner, headline="Old", kind="LIBRARY")

        assert old.lending_asks_terms is False
        assert (
            Collection.objects.values_list("lending_asks_terms", flat=True).get(pk=old.pk) is False
        )

    def test_the_demo_does_not_turn_it_on(self, owner):
        from core.management.commands.seed_data import common

        assert "lending_asks_terms" not in json.dumps(common.__dict__, default=str)


class TestWhatTheRequestPageIsTold:
    def test_it_asks_when_the_switch_is_on_and_the_document_is_there(self, drill, borrower):
        res = client_for(borrower).get(f"/api/v1/things/{drill.code}/?collection=LTCOL1")

        assert res.data["collection_lending_asks_terms"] is True
        assert res.data["collection_menu"]["welcome_doc_url"]

    def test_the_switch_without_a_document_does_not_ask(self, drill, library, borrower):
        Collection.objects.filter(pk=library.pk).update(welcome_doc="")

        res = client_for(borrower).get(f"/api/v1/things/{drill.code}/?collection=LTCOL1")

        assert res.data["collection_lending_asks_terms"] is False

    def test_a_document_without_the_switch_does_not_ask(self, drill, library, borrower):
        Collection.objects.filter(pk=library.pk).update(lending_asks_terms=False)

        res = client_for(borrower).get(f"/api/v1/things/{drill.code}/?collection=LTCOL1")

        assert res.data["collection_lending_asks_terms"] is False


class TestWhenTheLibraryAsks:
    @pytest.mark.parametrize("body", [{}, {"accepts_terms": False}, {"accepts_terms": "true"}])
    def test_without_a_true_acceptance_the_request_is_refused_and_nothing_is_created(
        self, drill, borrower, body
    ):
        res = ask(borrower, drill, body)

        assert res.status_code == 400
        assert res.data["code"] == "terms_required"
        assert "accepts_terms" in res.data
        assert BookingPeriod.objects.count() == 0
        assert mail.outbox == []

    def test_with_it_the_loan_is_made_and_keeps_when_and_which_document(self, drill, borrower):
        res = ask(borrower, drill, {"accepts_terms": True})

        assert res.status_code == 201, res.data
        booking = BookingPeriod.objects.get(code=res.data["booking_code"])
        assert booking.terms_accepted_at == NOW
        assert booking.terms_doc == DOC

    def test_a_rental_asks_the_same(self, owner, library, borrower):
        saw = Thing.objects.create(code="LTTH02", owner=owner, headline="Saw", type="RENT_THING")
        library.things.add(saw)

        assert ask(borrower, saw).status_code == 400
        assert ask(borrower, saw, {"accepts_terms": True}).status_code == 201

    def test_the_document_kept_is_the_one_there_when_they_accepted_not_a_later_one(
        self, drill, library, borrower
    ):
        booking = _requested(drill, borrower)
        Collection.objects.filter(pk=library.pk).update(welcome_doc=NEW_DOC)

        booking.refresh_from_db()

        assert booking.terms_doc == DOC

    def test_the_dates_are_still_judged_first(self, drill, borrower):
        res = ask(borrower, drill, {"start_date": "2020-01-01"})

        assert res.status_code == 400
        assert "start_date" in res.data
        assert "accepts_terms" not in res.data

    def test_a_library_that_lost_its_document_stops_asking_and_nothing_breaks(
        self, drill, library, borrower
    ):
        Collection.objects.filter(pk=library.pk).update(welcome_doc="")

        res = ask(borrower, drill)

        assert res.status_code == 201, res.data
        booking = BookingPeriod.objects.get()
        assert booking.terms_accepted_at is None
        assert booking.terms_doc == ""


class TestWhenTheLibraryDoesNotAsk:
    @pytest.fixture(autouse=True)
    def _off(self, library):
        Collection.objects.filter(pk=library.pk).update(lending_asks_terms=False)

    def test_a_request_needs_nothing_and_keeps_nothing(self, drill, borrower):
        res = ask(borrower, drill)

        assert res.status_code == 201, res.data
        booking = BookingPeriod.objects.get()
        assert booking.terms_accepted_at is None
        assert booking.terms_doc == ""

    @pytest.mark.parametrize("body", [{"accepts_terms": True}, {"accepts_terms": "garbage"}])
    def test_an_acceptance_sent_anyway_is_ignored_without_an_error_and_not_stored(
        self, drill, borrower, body
    ):
        res = ask(borrower, drill, body)

        assert res.status_code == 201, res.data
        booking = BookingPeriod.objects.get()
        assert booking.terms_accepted_at is None
        assert booking.terms_doc == ""


class TestItShowsInNoScreenNorMessage:
    def test_the_owner_and_the_borrower_do_not_get_it_back_in_their_lists(
        self, drill, owner, borrower
    ):
        _requested_at_a_distinct_moment(drill, borrower)

        for user, url in ((owner, "/api/v1/owner-bookings/"), (borrower, "/api/v1/my-bookings/")):
            rows = client_for(user).get(url).data["results"]
            assert rows
            text = json.dumps(rows)
            assert "terms" not in text
            assert DOC not in text
            assert STAMP not in text

    def test_the_booking_serializer_has_no_such_field(self, drill, borrower):
        data = BookingPeriodSerializer(_requested_at_a_distinct_moment(drill, borrower)).data

        assert not [name for name in data if "terms" in name]

    def test_no_email_carries_it_not_even_after_the_loan_is_accepted(self, drill, owner, borrower):
        booking = _requested_at_a_distinct_moment(drill, borrower)
        assert client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/").status_code == 200

        assert mail.outbox, "the request and its decision were mailed"
        for message in mail.outbox:
            body = " ".join(
                [message.subject, message.body, *(alt[0] for alt in message.alternatives)]
            )
            assert "terms-v1" not in body
            assert STAMP not in body

    def test_the_thing_page_and_the_calendar_do_not_carry_it(self, drill, owner, borrower):
        _requested_at_a_distinct_moment(drill, borrower)

        thing = client_for(owner).get(f"/api/v1/things/{drill.code}/?collection=LTCOL1")
        calendar = client_for(owner).get(f"/api/v1/things/{drill.code}/calendar/")

        for response in (thing, calendar):
            assert response.status_code == 200
            text = response.content.decode()
            assert "terms_accepted_at" not in text
            assert "terms_doc" not in text
            assert STAMP not in text

    def test_the_calendar_file_does_not_carry_it(self, drill, owner, borrower, library):
        booking = _requested_at_a_distinct_moment(drill, borrower)
        client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/")

        ics, count, _ = build_calendar_export(library, owner)

        assert count == 1
        text = ics.decode()
        assert "terms-v1" not in text
        assert STAMP not in text


class TestWhereItDoesShow:
    def test_the_borrowers_own_account_copy_carries_it(self, drill, borrower):
        _requested(drill, borrower)

        (row,) = build_account_export(borrower)["bookings"]["requested_by_me"]

        assert row["terms_accepted_at"] == NOW.isoformat()
        assert row["terms_doc_url"].endswith(DOC)

    def test_a_loan_the_library_did_not_ask_for_says_none_in_it(self, drill, library, borrower):
        Collection.objects.filter(pk=library.pk).update(lending_asks_terms=False)
        ask(borrower, drill)

        (row,) = build_account_export(borrower)["bookings"]["requested_by_me"]

        assert row["terms_accepted_at"] is None
        assert row["terms_doc_url"] is None

    def test_the_groups_copy_carries_it_on_each_loan(self, drill, owner, borrower, library):
        _requested(drill, borrower)

        copy = build_collection_export(library)

        (row,) = copy["bookings"]
        assert row["terms_accepted_at"] == NOW.isoformat()
        assert row["terms_doc_url"].endswith(DOC)
        assert "terms-v1" in export_bytes(copy).decode()

    def test_the_owners_received_bookings_in_their_account_copy_do_not(
        self, drill, owner, borrower
    ):
        _requested(drill, borrower)

        copy = build_account_export(owner)

        assert copy["bookings"]["received_by_me"]
        assert all("terms_accepted_at" not in row for row in copy["bookings"]["received_by_me"])

    def test_it_survives_the_loan_being_marked_returned(self, drill, owner, borrower):
        booking = _requested(drill, borrower)
        assert client_for(owner).post(f"/api/v1/bookings/{booking.code}/accept/").status_code == 200
        BookingPeriod.objects.filter(pk=booking.pk).update(
            start_date=date.today() - timedelta(days=1)
        )
        assert (
            client_for(owner).post(f"/api/v1/bookings/{booking.code}/returned/").status_code == 200
        )

        (row,) = build_account_export(borrower)["bookings"]["requested_by_me"]

        assert row["terms_accepted_at"] == NOW.isoformat()
