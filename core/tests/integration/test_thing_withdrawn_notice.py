"""Deleting a thing tells whoever had a live request on it.

A thing can always be deleted, whatever hangs from it, and its bookings go with it. What
nobody should be left with is a request for something that is gone, or a thing in their
house nobody told them to return. Everyone who asked, once, except whoever deleted; in a
network, whoever holds it also learns where to return it.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, NetworkPoint, Thing, User
from core.tests.factories import BookingPeriodFactory, CollectionFactory, ThingFactory

LEND, RENT = "LEND_THING", "RENT_THING"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


@pytest.fixture
def world(db):
    owner, lili, lolo, lulu = (
        _user("OWNR01", "Lala"),
        _user("ASK001", "Lili"),
        _user("ASK002", "Lolo"),
        _user("ASK003", "Lulu"),
    )
    group = CollectionFactory(
        owner=owner,
        mode=Collection.Mode.PROPRIETARY,
        headline="The street",
        allowed_thing_types=[LEND, RENT],
    )
    group.invites.add(lili, lolo, lulu)
    thing = ThingFactory(owner=owner, type=LEND, headline="Cordless drill")
    group.things.add(thing)
    return {
        "group": group,
        "owner": owner,
        "thing": thing,
        "lili": lili,
        "lolo": lolo,
        "lulu": lulu,
    }


def ask(world, who, *, start, end, status_=BookingPeriod.Status.PENDING):
    today = timezone.localdate()
    return BookingPeriodFactory(
        thing_code=world["thing"],
        requester_code=world[who],
        owner_code=world["owner"],
        thing_type=LEND,
        status=status_,
        start_date=today + timedelta(days=start),
        end_date=today + timedelta(days=end),
    )


def delete(world, who="owner", thing=None, callbacks=None):
    mail.outbox.clear()
    thing = thing or world["thing"]
    with callbacks(execute=True):
        return client_for(world[who]).delete(f"/api/v1/things/{thing.code}/")


def recipients():
    return sorted(addr for m in mail.outbox for addr in m.to)


@pytest.fixture
def callbacks(django_capture_on_commit_callbacks):
    return django_capture_on_commit_callbacks


class TestWhoIsTold:
    def test_a_pending_request_is_told(self, world, callbacks):
        ask(world, "lili", start=3, end=6)

        res = delete(world, callbacks=callbacks)

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert recipients() == ["lili@your-domain.test"]
        [message] = mail.outbox
        assert message.subject == "“Cordless drill” has been withdrawn from The street"
        assert "your request is cancelled" in message.body

    def test_the_notice_speaks_the_language_of_the_group(self, world, callbacks):
        Collection.objects.filter(pk=world["group"].pk).update(language="ca")
        ask(world, "lili", start=3, end=6)

        delete(world, callbacks=callbacks)

        [message] = mail.outbox
        assert message.subject == "S'ha retirat «Cordless drill» de The street"

    def test_an_accepted_future_request_is_told(self, world, callbacks):
        ask(world, "lili", start=3, end=6, status_=BookingPeriod.Status.ACCEPTED)

        delete(world, callbacks=callbacks)

        assert recipients() == ["lili@your-domain.test"]
        assert "return it to them" not in mail.outbox[0].body

    def test_whoever_has_it_in_hand_is_told_to_return_it(self, world, callbacks):
        ask(world, "lili", start=-2, end=6, status_=BookingPeriod.Status.ACCEPTED)

        res = delete(world, callbacks=callbacks)

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not Thing.objects.filter(code=world["thing"].code).exists()
        assert "return it to them as you agreed" in mail.outbox[0].body

    def test_a_request_that_is_over_or_was_refused_tells_nobody(self, world, callbacks):
        ask(world, "lili", start=-30, end=-20, status_=BookingPeriod.Status.ACCEPTED)
        ask(world, "lolo", start=3, end=6, status_=BookingPeriod.Status.REJECTED)
        ask(world, "lulu", start=3, end=6, status_=BookingPeriod.Status.CANCELLED)

        res = delete(world, callbacks=callbacks)

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert mail.outbox == []

    def test_whoever_deletes_is_not_told(self, world, callbacks):
        world["group"].co_owners.add(world["lili"])
        ask(world, "lili", start=3, end=6)
        ask(world, "lolo", start=3, end=6)

        delete(world, who="lili", callbacks=callbacks)

        assert recipients() == ["lolo@your-domain.test"]

    def test_two_requests_of_one_person_are_one_email(self, world, callbacks):
        ask(world, "lili", start=3, end=6)
        ask(world, "lili", start=10, end=12)

        delete(world, callbacks=callbacks)

        assert recipients() == ["lili@your-domain.test"]

    def test_it_is_deleted_even_with_a_loan_in_hand(self, world, callbacks):
        ask(world, "lili", start=-2, end=6, status_=BookingPeriod.Status.ACCEPTED)

        res = delete(world, callbacks=callbacks)

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not Thing.objects.filter(code=world["thing"].code).exists()
        assert not BookingPeriod.objects.exists()

    def test_nothing_is_sent_if_the_delete_is_refused(self, world, callbacks):
        ask(world, "lili", start=3, end=6)

        res = delete(world, who="lolo", callbacks=callbacks)

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert mail.outbox == []
        assert Thing.objects.filter(code=world["thing"].code).exists()

    def test_the_email_names_nobody_who_deleted_it(self, world, callbacks):
        ask(world, "lili", start=3, end=6)

        delete(world, callbacks=callbacks)

        body = mail.outbox[0].body + mail.outbox[0].alternatives[0][0]
        assert "lala@your-domain.test" not in body
        assert "Lala" not in body

    def test_it_is_the_same_in_a_community_by_its_owner(self, world, callbacks):
        community = CollectionFactory(
            owner=world["owner"], mode=Collection.Mode.COMMUNITY, headline="The courtyard"
        )
        community.invites.add(world["lili"], world["lolo"])
        thing = ThingFactory(owner=world["lolo"], type=LEND, headline="Ladder")
        community.things.add(thing)
        BookingPeriodFactory(
            thing_code=thing,
            requester_code=world["lili"],
            owner_code=world["lolo"],
            thing_type=LEND,
            start_date=timezone.localdate() + timedelta(days=3),
            end_date=timezone.localdate() + timedelta(days=6),
        )

        delete(world, who="lolo", thing=thing, callbacks=callbacks)

        assert recipients() == ["lili@your-domain.test"]
        assert "withdrawn from The courtyard" in mail.outbox[0].subject


class TestInANetwork:
    @pytest.fixture
    def net(self, db):
        founder, lele, lolo = (
            _user("FOUN01", "Lala"),
            _user("ENTA01", "Lele"),
            _user("ASK001", "Lolo"),
        )
        group = CollectionFactory(
            owner=founder,
            mode=Collection.Mode.NETWORK,
            headline="The network",
            allowed_thing_types=[LEND, RENT],
        )
        group.invites.add(lele, lolo)
        group.co_owners.add(lele)
        NetworkPoint.objects.create(
            collection=group,
            user=lele,
            entity_name="Cooperativa La Fusteria",
            address="Carrer Major 4",
            hours_note="martes y jueves de 18 a 20",
        )
        thing = ThingFactory(owner=lele, type=LEND, headline="Cordless drill")
        group.things.add(thing)
        return {"group": group, "thing": thing, "lele": lele, "lolo": lolo, "founder": founder}

    def book(self, net, start, end, status_):
        today = timezone.localdate()
        return BookingPeriodFactory(
            thing_code=net["thing"],
            requester_code=net["lolo"],
            owner_code=net["lele"],
            thing_type=LEND,
            status=status_,
            start_date=today + timedelta(days=start),
            end_date=today + timedelta(days=end),
        )

    def test_whoever_holds_it_learns_where_to_return_it(self, net, callbacks):
        self.book(net, -2, 6, BookingPeriod.Status.ACCEPTED)
        mail.outbox.clear()

        with callbacks(execute=True):
            res = client_for(net["lele"]).delete(f"/api/v1/things/{net['thing'].code}/")

        assert res.status_code == status.HTTP_204_NO_CONTENT
        [message] = mail.outbox
        for text in (message.body, message.alternatives[0][0]):
            assert "Carrer Major 4" in text
            assert "martes y jueves de 18 a 20" in text

    def test_whoever_only_asked_is_not_given_the_place(self, net, callbacks):
        self.book(net, 3, 6, BookingPeriod.Status.PENDING)
        mail.outbox.clear()

        with callbacks(execute=True):
            client_for(net["lele"]).delete(f"/api/v1/things/{net['thing'].code}/")

        [message] = mail.outbox
        assert "Carrer Major 4" not in message.body

    def test_the_founder_deleting_it_is_told_to_nobody_but_the_requester(self, net, callbacks):
        self.book(net, 3, 6, BookingPeriod.Status.PENDING)
        mail.outbox.clear()

        with callbacks(execute=True):
            res = client_for(net["founder"]).delete(f"/api/v1/things/{net['thing'].code}/")

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert [m.to for m in mail.outbox] == [["lolo@your-domain.test"]]
