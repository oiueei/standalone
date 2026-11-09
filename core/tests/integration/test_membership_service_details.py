"""Who is told, in what order, and in whose words when a member's membership ends.

``test_membership_emails.py`` drives this through the leave and remove endpoints;
these tests call the service directly for the parts the endpoints do not make
visible: the order the leaving things are listed in, the requests that must not
be announced, a loan held next to a queued request, and the language of the
email.
"""

import datetime

import pytest
from django.core import mail
from django.utils import timezone

from core.models import BookingPeriod, Collection, Thing, User
from core.services.email_service import T
from core.services.membership_service import (
    _people_to_tell,
    end_membership,
    things_leaving_with,
)


@pytest.fixture
def founder(db):
    return User.objects.create(code="MFOU01", email="lala@your-domain.test", name="Lala")


@pytest.fixture
def member(db):
    return User.objects.create(code="MMEM01", email="lele@your-domain.test", name="Lele")


@pytest.fixture
def asker(db):
    return User.objects.create(code="MASK01", email="lili@your-domain.test", name="Lili")


@pytest.fixture
def group(founder, member, asker):
    collection = Collection.objects.create(
        code="MGRP01",
        owner=founder,
        headline="The street",
        mode=Collection.Mode.COMMUNITY,
        language="es",
    )
    collection.invites.add(member, asker)
    return collection


def thing(group, owner, code, headline="Drill", type_="GIFT_THING"):
    created = Thing.objects.create(code=code, owner=owner, type=type_, headline=headline)
    group.things.add(created)
    return created


def book(of, requester, status=BookingPeriod.Status.PENDING, **extra):
    return BookingPeriod.objects.create(
        thing_code=of,
        thing_type=of.type,
        requester_code=requester,
        requester_email=requester.email,
        owner_code=of.owner,
        status=status,
        **extra,
    )


class TestTheThingsThatLeave:
    def test_they_are_listed_oldest_first(self, group, member):
        newer = thing(group, member, "AAA001")
        older = thing(group, member, "ZZZ001")
        Thing.objects.filter(pk=older.pk).update(
            created=timezone.now() - datetime.timedelta(days=2)
        )

        assert [t.code for t in things_leaving_with(group, member)] == [older.code, newer.code]

    def test_things_made_at_the_same_moment_are_listed_by_code(self, group, member):
        moment = timezone.now()
        later_code = thing(group, member, "BBB001")
        earlier_code = thing(group, member, "AAA001")
        Thing.objects.filter(pk__in=[later_code.pk, earlier_code.pk]).update(created=moment)

        assert [t.code for t in things_leaving_with(group, member)] == ["AAA001", "BBB001"]


class TestWhoMustHearAThingIsGoing:
    def test_a_request_on_a_thing_that_stays_is_not_announced(self, group, member, founder, asker):
        going = thing(group, member, "GOING1", "Going")
        staying = thing(group, founder, "STAY01", "Staying")
        book(going, asker)
        other = User.objects.create(code="MOTH01", email="lolo@your-domain.test", name="Lolo")
        book(staying, other)

        told = _people_to_tell(list(things_leaving_with(group, member)), member)

        assert told == [(asker.email, "Going", False)]

    def test_the_leaving_members_own_requests_do_not_hide_everyone_elses(
        self, group, member, founder, asker
    ):
        mine = [thing(group, founder, f"OWN00{i}", f"Own {i}") for i in range(3)]
        leaving = [thing(group, member, f"OUT00{i}", f"Out {i}") for i in range(3)]
        for item in mine:
            book(item, member)
        for item in leaving:
            book(item, member)  # their own requests on their own things come first
        for item in leaving:
            book(item, asker)

        told = _people_to_tell(leaving, member)

        assert {headline for _, headline, _ in told} == {"Out 0", "Out 1", "Out 2"}
        assert {email for email, _, _ in told} == {asker.email}

    def test_the_list_costs_one_query_however_many_things_are_leaving(
        self, group, member, asker, django_assert_num_queries
    ):
        leaving = [thing(group, member, f"QRY00{i}", f"Thing {i}") for i in range(3)]
        for item in leaving:
            book(item, asker)

        with django_assert_num_queries(1):
            told = _people_to_tell(leaving, member)

        assert len(told) == 3

    def test_a_loan_already_started_keeps_its_holding_mark_next_to_a_later_request(
        self, group, member, asker
    ):
        today = timezone.localdate()
        drill = thing(group, member, "LOAN01", "Drill", type_="LEND_THING")
        book(
            drill,
            asker,
            status=BookingPeriod.Status.ACCEPTED,
            start_date=today - datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=2),
        )
        book(
            drill,
            asker,
            status=BookingPeriod.Status.PENDING,
            start_date=today + datetime.timedelta(days=5),
            end_date=today + datetime.timedelta(days=6),
        )

        told = _people_to_tell([drill], member)

        assert told == [(asker.email, "Drill", True)]


class TestEndingAMembership:
    def test_the_founder_cannot_be_taken_out_and_the_refusal_says_why(self, group, founder):
        with pytest.raises(
            ValueError, match=r"^The owner can't be removed from their own collection\.$"
        ):
            end_membership(group, founder, actor=founder)

    def test_the_requesters_email_speaks_the_groups_language(
        self, group, member, asker, django_capture_on_commit_callbacks
    ):
        drill = thing(group, member, "LANG01", "Drill")
        book(drill, asker)
        mail.outbox.clear()

        with django_capture_on_commit_callbacks(execute=True):
            end_membership(group, member, actor=member)

        (sent,) = mail.outbox
        assert sent.subject == T("thing_left_subject", lang="es").format(
            thing="Drill", group="The street"
        )


class TestDemotingADinamizadorTellsWhoAskedForTheirThings:
    """The notice goes out once the demotion commits, to the people with a live request on
    a thing that went with the role, and to nobody else."""

    @pytest.fixture
    def network(self, founder, member, asker):
        other = User.objects.create(code="MOTH01", email="lolo@your-domain.test", name="Lolo")
        bystander = User.objects.create(code="MBYS01", email="lulu@your-domain.test", name="Lulu")
        collection = Collection.objects.create(
            code="MNET01",
            owner=founder,
            headline="The network",
            mode=Collection.Mode.NETWORK,
            allowed_thing_types=["LEND_THING"],
            language="es",
        )
        collection.invites.add(member, other, asker, bystander)
        collection.co_owners.add(member, other)
        return collection, other, bystander

    def _demote(self, founder, collection, member):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(founder).access_token}"
        )
        return client.delete(
            f"/api/v1/collections/{collection.code}/co-owners/",
            {"user_code": member.code},
            format="json",
        )

    def test_only_the_requester_of_a_demoted_dinamizadors_thing_is_emailed_on_commit(
        self, network, founder, member, asker, django_capture_on_commit_callbacks
    ):
        collection, other, bystander = network
        mine = thing(collection, member, "DEM001", "Ladder", type_="LEND_THING")
        theirs = thing(collection, other, "DEM002", "Saw", type_="LEND_THING")
        book(mine, asker)
        book(theirs, bystander)
        mail.outbox.clear()

        with django_capture_on_commit_callbacks(execute=True):
            res = self._demote(founder, collection, member)

        assert res.status_code == 200
        (sent,) = mail.outbox
        assert sent.to == [asker.email]
        assert sent.subject == T("thing_left_subject", lang="es").format(
            thing="Ladder", group="The network"
        )

    def test_nothing_is_sent_before_the_demotion_commits(
        self, network, founder, member, asker, django_capture_on_commit_callbacks
    ):
        collection, _, _ = network
        book(thing(collection, member, "DEM003", "Ladder", type_="LEND_THING"), asker)
        mail.outbox.clear()

        with django_capture_on_commit_callbacks(execute=False):
            res = self._demote(founder, collection, member)

        assert res.status_code == 200
        assert mail.outbox == []
