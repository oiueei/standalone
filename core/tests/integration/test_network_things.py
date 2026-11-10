"""In a network every entity decides only what is its own; the founder can rescue.

A co-curator of a PROPRIETARY collection runs the whole catalogue. In a NETWORK they
run theirs alone: they cannot edit, hide, activate, delete or decide another entity's
thing, and a notice about it reaches that entity only. The founder is deliberately
outside ``managers()`` and ``can_manage``; what they have instead is the rescue, two
things and nothing more: reject a pending request, and hide a thing.
"""

import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.models.notification import InAppNotification
from core.tests.factories import (
    BookingPeriodFactory,
    CollectionFactory,
    ThingFactory,
    ThingTransferFactory,
)

LEND, RENT = "LEND_THING", "RENT_THING"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


@pytest.fixture
def world(db):
    """A network: founder Lala, entities Lele and Lili (co-curators), member Lolo."""
    founder, lele, lili, lolo = (
        _user("FOUN01", "Lala"),
        _user("ENTA01", "Lele"),
        _user("ENTB01", "Lili"),
        _user("MEMB01", "Lolo"),
    )
    network = CollectionFactory(
        owner=founder, mode=Collection.Mode.NETWORK, allowed_thing_types=[LEND, RENT]
    )
    network.invites.add(lele, lili, lolo)
    network.co_owners.add(lele, lili)
    leles = ThingFactory(owner=lele, type=LEND)
    network.things.add(leles)
    founders = ThingFactory(owner=founder, type=LEND)
    network.things.add(founders)
    return {
        "founder": founder,
        "lele": lele,
        "lili": lili,
        "lolo": lolo,
        "network": network,
        "leles": leles,
        "founders": founders,
    }


def _request(thing, requester):
    return BookingPeriodFactory(
        thing_code=thing,
        requester_code=requester,
        start_date="2030-01-10",
        end_date="2030-01-17",
    )


@pytest.mark.django_db
class TestEachEntityRunsItsOwnThings:
    def test_only_the_thing_owner_can_manage_it(self, world):
        thing = Thing.objects.get(code=world["leles"].code)

        assert thing.can_manage("ENTA01")
        assert not thing.can_manage("ENTB01")
        assert not thing.can_manage("FOUN01")

    def test_the_managers_of_a_thing_are_its_owner_alone(self, world):
        thing = Thing.objects.get(code=world["leles"].code)

        assert [u.code for u in thing.managers()] == ["ENTA01"]

    def test_a_co_curator_cannot_edit_another_entitys_thing(self, world):
        res = client_for(world["lili"]).patch(
            f"/api/v1/things/{world['leles'].code}/", {"headline": "Mine now"}, format="json"
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN
        world["leles"].refresh_from_db()
        assert world["leles"].headline != "Mine now"

    def test_a_co_curator_cannot_hide_another_entitys_thing(self, world):
        res = client_for(world["lili"]).post(f"/api/v1/things/{world['leles'].code}/hide/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        world["leles"].refresh_from_db()
        assert world["leles"].status == Thing.Status.ACTIVE

    def test_a_co_curator_cannot_delete_another_entitys_thing(self, world):
        res = client_for(world["lili"]).delete(f"/api/v1/things/{world['leles'].code}/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert Thing.objects.filter(code=world["leles"].code).exists()

    def test_a_co_curator_cannot_decide_a_request_on_another_entitys_thing(self, world):
        booking = _request(world["leles"], world["lolo"])

        res = client_for(world["lili"]).post(f"/api/v1/bookings/{booking.code}/accept/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.PENDING

    def test_the_owner_decides_their_own_request(self, world):
        booking = _request(world["leles"], world["lolo"])

        res = client_for(world["lele"]).post(f"/api/v1/bookings/{booking.code}/accept/")

        assert res.status_code == status.HTTP_200_OK
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.ACCEPTED

    def test_a_proprietary_co_curator_still_runs_every_thing(self, world):
        shared = CollectionFactory(owner=world["founder"], allowed_thing_types=[LEND, RENT])
        shared.invites.add(world["lili"])
        shared.co_owners.add(world["lili"])
        thing = ThingFactory(owner=world["founder"], type=LEND)
        shared.things.add(thing)

        res = client_for(world["lili"]).post(f"/api/v1/things/{thing.code}/hide/")

        assert res.status_code == status.HTTP_200_OK
        thing.refresh_from_db()
        assert thing.status == Thing.Status.INACTIVE


@pytest.mark.django_db
class TestDeletingAThing:
    """A thing that has been lent has changed hands, and the owner's own right to delete
    it ends there; a network's dinamizador keeps it, as a PROPRIETARY co-curator keeps it
    over the catalogue they run. Another dinamizador's thing was never theirs to delete."""

    def lent(self, thing, borrower):
        ThingTransferFactory(thing=thing, from_user=thing.owner, to_user=borrower)

    def test_a_dinamizador_deletes_their_own_thing_even_after_it_was_lent(self, world):
        self.lent(world["leles"], world["lolo"])

        res = client_for(world["lele"]).delete(f"/api/v1/things/{world['leles'].code}/")

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not Thing.objects.filter(code=world["leles"].code).exists()

    def test_a_dinamizador_cannot_delete_another_dinamizadors_thing(self, world):
        self.lent(world["leles"], world["lolo"])

        res = client_for(world["lili"]).delete(f"/api/v1/things/{world['leles'].code}/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert Thing.objects.filter(code=world["leles"].code).exists()

    def test_a_member_who_is_not_a_dinamizador_cannot_delete_a_thing(self, world):
        res = client_for(world["lolo"]).delete(f"/api/v1/things/{world['leles'].code}/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert Thing.objects.filter(code=world["leles"].code).exists()

    def test_the_founder_still_deletes_any_thing_of_the_network(self, world):
        res = client_for(world["founder"]).delete(f"/api/v1/things/{world['leles'].code}/")

        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not Thing.objects.filter(code=world["leles"].code).exists()

    def test_in_a_community_a_lent_thing_is_still_not_its_owners_to_delete(self, world):
        community = CollectionFactory(
            owner=world["founder"], mode=Collection.Mode.COMMUNITY, allowed_thing_types=[LEND, RENT]
        )
        community.invites.add(world["lele"])
        thing = ThingFactory(owner=world["lele"], type=LEND)
        community.things.add(thing)
        self.lent(thing, world["lolo"])

        res = client_for(world["lele"]).delete(f"/api/v1/things/{thing.code}/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert Thing.objects.filter(code=thing.code).exists()


@pytest.mark.django_db
class TestTheFoundersRescue:
    def test_the_founder_rejects_a_pending_request_on_another_entitys_thing(self, world):
        booking = _request(world["leles"], world["lolo"])

        res = client_for(world["founder"]).post(f"/api/v1/bookings/{booking.code}/reject/")

        assert res.status_code == status.HTTP_200_OK
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.REJECTED

    def test_the_founder_cannot_accept_another_entitys_request(self, world):
        booking = _request(world["leles"], world["lolo"])

        res = client_for(world["founder"]).post(f"/api/v1/bookings/{booking.code}/accept/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.PENDING

    def test_a_co_curator_cannot_reject_another_entitys_request(self, world):
        booking = _request(world["leles"], world["lolo"])

        res = client_for(world["lili"]).post(f"/api/v1/bookings/{booking.code}/reject/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.PENDING

    def test_the_member_is_told_and_so_is_the_owner_when_the_founder_rejects(self, world):
        booking = _request(world["leles"], world["lolo"])
        mail.outbox.clear()

        client_for(world["founder"]).post(f"/api/v1/bookings/{booking.code}/reject/")

        assert [m.to for m in mail.outbox] == [["lolo@your-domain.test"]]
        assert InAppNotification.objects.filter(
            user=world["lolo"], type=InAppNotification.Type.BOOKING_REJECTED
        ).exists()
        decided = InAppNotification.objects.get(type=InAppNotification.Type.BOOKING_DECIDED)
        assert decided.user == world["lele"]
        assert decided.payload["decider_name"] == "Lala"
        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.BOOKING_DECIDED, user__in=[world["founder"], world["lili"]]
        ).exists()

    def test_the_founder_hides_another_entitys_thing_and_its_owner_is_told(self, world):
        mail.outbox.clear()

        res = client_for(world["founder"]).post(f"/api/v1/things/{world['leles'].code}/hide/")

        assert res.status_code == status.HTTP_200_OK
        world["leles"].refresh_from_db()
        assert world["leles"].status == Thing.Status.INACTIVE
        notice = InAppNotification.objects.get(type=InAppNotification.Type.THING_HIDDEN)
        assert notice.user == world["lele"]
        assert notice.payload["thing_code"] == world["leles"].code
        assert notice.payload["founder_name"] == "Lala"
        assert [m.to for m in mail.outbox] == [["lele@your-domain.test"]]

    def test_hiding_your_own_thing_tells_nobody(self, world):
        mail.outbox.clear()

        client_for(world["founder"]).post(f"/api/v1/things/{world['founders'].code}/hide/")

        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.THING_HIDDEN
        ).exists()
        assert mail.outbox == []

    def test_a_co_curator_hiding_the_founders_thing_in_a_proprietary_collection_tells_nobody(
        self, world
    ):
        shared = CollectionFactory(
            owner=world["founder"],
            mode=Collection.Mode.PROPRIETARY,
            allowed_thing_types=[LEND, RENT],
        )
        shared.invites.add(world["lele"])
        shared.co_owners.add(world["lele"])
        thing = ThingFactory(owner=world["founder"], type=LEND)
        shared.things.add(thing)
        mail.outbox.clear()

        res = client_for(world["lele"]).post(f"/api/v1/things/{thing.code}/hide/")

        assert res.status_code == status.HTTP_200_OK
        thing.refresh_from_db()
        assert thing.status == Thing.Status.INACTIVE
        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.THING_HIDDEN
        ).exists()
        assert mail.outbox == []

    def test_the_founder_cannot_edit_another_entitys_thing(self, world):
        res = client_for(world["founder"]).patch(
            f"/api/v1/things/{world['leles'].code}/", {"headline": "Mine now"}, format="json"
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN
        world["leles"].refresh_from_db()
        assert world["leles"].headline != "Mine now"

    def test_the_founder_is_not_one_of_the_managers_who_get_the_daily_mail(self, world):
        assert world["founder"].code not in [
            u.code for u in Thing.objects.get(code=world["leles"].code).managers()
        ]

    def test_the_founder_of_a_community_has_no_rescue_over_a_members_request(self, world):
        shared = CollectionFactory(
            owner=world["founder"], mode=Collection.Mode.COMMUNITY, allowed_thing_types=[LEND, RENT]
        )
        shared.invites.add(world["lili"])
        thing = ThingFactory(owner=world["lili"], type=LEND)
        shared.things.add(thing)
        booking = _request(thing, world["lolo"])

        res = client_for(world["founder"]).post(f"/api/v1/bookings/{booking.code}/reject/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.PENDING
        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.BOOKING_REJECTED
        ).exists()


@pytest.mark.django_db
class TestWhatTheFounderSeesInTheRequests:
    def _rows(self, user):
        res = client_for(user).get("/api/v1/owner-bookings/")
        assert res.status_code == status.HTTP_200_OK
        data = res.data["results"] if "results" in res.data else res.data
        return {row["code"]: row for row in data}

    def test_the_founder_sees_every_entitys_request_but_decides_only_their_own(self, world):
        theirs = _request(world["leles"], world["lolo"])
        own = _request(world["founders"], world["lolo"])

        rows = self._rows(world["founder"])

        assert rows[theirs.code]["can_decide"] is False
        assert rows[own.code]["can_decide"] is True

    def test_a_co_curator_sees_only_the_requests_on_their_own_things(self, world):
        mine = _request(world["leles"], world["lolo"])
        not_mine = _request(world["founders"], world["lolo"])

        rows = self._rows(world["lele"])

        assert mine.code in rows and not_mine.code not in rows
        assert rows[mine.code]["can_decide"] is True
