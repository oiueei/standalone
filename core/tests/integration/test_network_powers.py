"""What a co-curator can do to the collection itself, in a network and everywhere else.

In a PROPRIETARY or COMMUNITY collection a co-curator has the founder's whole reach
over the collection. In a NETWORK each dinamizador runs their own things, so what
reaches the others is the founder's: naming the team, editing the settings, taking
people out, and the whole group's calendar and copy. One test per row of that table,
and the same call done in the other two modes to show nothing moved there.
"""

import csv
import io

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.notification import InAppNotification
from core.services.account_service import delete_account
from core.tests.factories import BookingPeriodFactory, CollectionFactory, ThingFactory

LEND, RENT = "LEND_THING", "RENT_THING"
BASE = "/api/v1/collections/{code}/"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


def _group(mode):
    founder, lele, lili, lolo = (
        _user("FOUN01", "Lala"),
        _user("ENTA01", "Lele"),
        _user("ENTB01", "Lili"),
        _user("MEMB01", "Lolo"),
    )
    group = CollectionFactory(owner=founder, mode=mode, allowed_thing_types=[LEND, RENT])
    group.invites.add(lele, lili, lolo)
    group.co_owners.add(lele, lili)
    return group, founder, lele, lili, lolo


@pytest.fixture
def network(db):
    group, founder, lele, lili, lolo = _group(Collection.Mode.NETWORK)
    leles = ThingFactory(owner=lele, type=LEND)
    group.things.add(leles)
    lilis = ThingFactory(owner=lili, type=LEND)
    group.things.add(lilis)
    return {
        "group": group,
        "founder": founder,
        "lele": lele,
        "lili": lili,
        "lolo": lolo,
        "leles": leles,
        "lilis": lilis,
    }


def _loan(thing, requester, *, started=True, status=BookingPeriod.Status.ACCEPTED):
    today = timezone.localdate()
    offset = 0 if started else 5
    return BookingPeriodFactory(
        thing_code=thing,
        requester_code=requester,
        thing_type=LEND,
        status=status,
        start_date=today - timezone.timedelta(days=1) + timezone.timedelta(days=offset)
        if started
        else today + timezone.timedelta(days=offset),
        end_date=today + timezone.timedelta(days=offset + 10),
    )


@pytest.mark.django_db
class TestNamingTheTeam:
    def test_only_the_founder_names_a_dinamizador_in_a_network(self, network):
        g = network["group"]
        g.co_owners.remove(network["lili"])
        url = BASE.format(code=g.code) + "co-owners/"

        denied = client_for(network["lele"]).post(url, {"user_code": "ENTB01"}, format="json")
        allowed = client_for(network["founder"]).post(url, {"user_code": "ENTB01"}, format="json")

        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert denied.data["code"] == "network_founder_only"
        assert allowed.status_code == status.HTTP_200_OK
        assert g.co_owners.filter(code="ENTB01").exists()

    def test_a_promotion_in_a_network_says_so_in_the_notice(self, network):
        network["group"].invites.add(User.objects.create(code="NEWC01", email="n@your-domain.test"))
        url = BASE.format(code=network["group"].code) + "co-owners/"

        client_for(network["founder"]).post(url, {"user_code": "NEWC01"}, format="json")

        notice = InAppNotification.objects.get(
            user_id="NEWC01", type=InAppNotification.Type.PROMOTED_CO_OWNER
        )
        assert notice.payload["network"] is True

    @pytest.mark.parametrize("mode", [Collection.Mode.PROPRIETARY, Collection.Mode.COMMUNITY])
    def test_a_promotion_elsewhere_carries_no_network_flag(self, mode):
        g, founder, _, _, lolo = _group(mode)

        client_for(founder).post(
            BASE.format(code=g.code) + "co-owners/", {"user_code": "MEMB01"}, format="json"
        )

        notice = InAppNotification.objects.get(
            user=lolo, type=InAppNotification.Type.PROMOTED_CO_OWNER
        )
        assert "network" not in notice.payload

    def test_only_the_founder_demotes_a_dinamizador_in_a_network(self, network):
        url = BASE.format(code=network["group"].code) + "co-owners/"

        denied = client_for(network["lele"]).delete(url, {"user_code": "ENTB01"}, format="json")

        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert network["group"].co_owners.filter(code="ENTB01").exists()

    @pytest.mark.parametrize("mode", [Collection.Mode.PROPRIETARY, Collection.Mode.COMMUNITY])
    def test_a_co_curator_still_names_the_team_elsewhere(self, mode):
        g, _, lele, _, lolo = _group(mode)

        res = client_for(lele).post(
            BASE.format(code=g.code) + "co-owners/", {"user_code": "MEMB01"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert g.co_owners.filter(code="MEMB01").exists()


@pytest.mark.django_db
class TestTheSettings:
    def test_only_the_founder_edits_the_settings_of_a_network(self, network):
        url = BASE.format(code=network["group"].code)

        denied = client_for(network["lele"]).patch(url, {"headline": "Mine"}, format="json")
        allowed = client_for(network["founder"]).patch(url, {"headline": "Ours"}, format="json")

        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert allowed.status_code == status.HTTP_200_OK
        network["group"].refresh_from_db()
        assert network["group"].headline == "Ours"

    @pytest.mark.parametrize("mode", [Collection.Mode.PROPRIETARY, Collection.Mode.COMMUNITY])
    def test_a_co_curator_still_edits_the_settings_elsewhere(self, mode):
        g, _, lele, _, _ = _group(mode)

        res = client_for(lele).patch(BASE.format(code=g.code), {"headline": "Mine"}, format="json")

        assert res.status_code == status.HTTP_200_OK
        g.refresh_from_db()
        assert g.headline == "Mine"


@pytest.mark.django_db
class TestInvitingAndRemoving:
    def test_every_dinamizador_invites_members_in_a_network(self, network):
        url = BASE.format(code=network["group"].code) + "invite/"

        res = client_for(network["lele"]).post(
            url, {"email": "lulu@your-domain.test"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        invited = User.objects.get(email="lulu@your-domain.test")
        assert invited.rsvps.filter(target_code=network["group"].code).exists()
        assert [m.to for m in mail.outbox] == [["lulu@your-domain.test"]]

    def test_every_dinamizador_bulk_invites_in_a_network(self, network):
        url = BASE.format(code=network["group"].code) + "invite/bulk/"

        res = client_for(network["lele"]).post(
            url, {"invites": [{"email": "lulu@your-domain.test"}]}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert res.data["invited"] == 1

    def test_only_the_founder_removes_a_member_of_a_network(self, network):
        url = BASE.format(code=network["group"].code) + "invite/"

        denied = client_for(network["lele"]).delete(url, {"user_code": "MEMB01"}, format="json")
        allowed = client_for(network["founder"]).delete(url, {"user_code": "MEMB01"}, format="json")

        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert allowed.status_code == status.HTTP_200_OK
        assert not network["group"].invites.filter(code="MEMB01").exists()

    def test_a_dinamizador_cancels_a_pending_invitation_in_a_network(self, network):
        url = BASE.format(code=network["group"].code) + "invite/"
        invited = client_for(network["lele"]).post(
            url, {"email": "lulu@your-domain.test"}, format="json"
        )
        pending = User.objects.get(email="lulu@your-domain.test")

        res = client_for(network["lele"]).delete(url, {"user_code": pending.code}, format="json")

        assert invited.status_code == status.HTTP_200_OK
        assert res.status_code == status.HTTP_200_OK
        assert not pending.rsvps.filter(target_code=network["group"].code).exists()

    def test_a_member_with_a_loan_in_hand_cannot_be_removed(self, network):
        _loan(network["leles"], network["lolo"])
        url = BASE.format(code=network["group"].code) + "invite/"

        res = client_for(network["founder"]).delete(url, {"user_code": "MEMB01"}, format="json")

        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["code"] == "member_holds_loans"
        assert network["group"].invites.filter(code="MEMB01").exists()

    def test_a_loan_of_another_entity_blocks_the_removal_too(self, network):
        _loan(network["lilis"], network["lolo"])
        url = BASE.format(code=network["group"].code) + "invite/"

        res = client_for(network["founder"]).delete(url, {"user_code": "MEMB01"}, format="json")

        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["code"] == "member_holds_loans"
        assert network["group"].invites.filter(code="MEMB01").exists()

    @pytest.mark.parametrize(
        "case", ["pending", "somebody_elses", "over", "not_returnable", "other_collection"]
    )
    def test_only_a_running_accepted_loan_of_this_network_held_by_the_member_blocks(
        self, network, case
    ):
        today = timezone.localdate()
        day = timezone.timedelta
        thing, who, kind, start, end = network["leles"], network["lolo"], LEND, -1, 10
        status_ = BookingPeriod.Status.ACCEPTED
        if case == "pending":
            status_ = BookingPeriod.Status.PENDING
        elif case == "somebody_elses":
            who = network["lili"]
        elif case == "over":
            start, end = -20, -5
        elif case == "not_returnable":
            kind = "GIFT_THING"
        elif case == "other_collection":
            thing = ThingFactory(owner=network["lele"], type=LEND)
        BookingPeriodFactory(
            thing_code=thing,
            requester_code=who,
            thing_type=kind,
            status=status_,
            start_date=today + day(days=start),
            end_date=today + day(days=end),
        )
        url = BASE.format(code=network["group"].code) + "invite/"

        res = client_for(network["founder"]).delete(url, {"user_code": "MEMB01"}, format="json")

        assert res.status_code == status.HTTP_200_OK, res.data
        assert not network["group"].invites.filter(code="MEMB01").exists()

    def test_a_loan_that_has_not_started_does_not_block_and_falls_with_the_member(self, network):
        loan = _loan(network["leles"], network["lolo"], started=False)
        url = BASE.format(code=network["group"].code) + "invite/"

        res = client_for(network["founder"]).delete(url, {"user_code": "MEMB01"}, format="json")

        assert res.status_code == status.HTTP_200_OK
        loan.refresh_from_db()
        assert loan.status == BookingPeriod.Status.ACCEPTED

    def test_a_dinamizador_whose_thing_is_lent_out_cannot_be_removed(self, network):
        _loan(network["leles"], network["lolo"])
        url = BASE.format(code=network["group"].code) + "invite/"

        res = client_for(network["founder"]).delete(url, {"user_code": "ENTA01"}, format="json")

        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["code"] == "curator_things_lent_out"
        assert Thing.objects.filter(code=network["leles"].code).exists()

    def test_removing_a_dinamizador_without_loans_deletes_their_things_and_tells_requesters(
        self, network, django_capture_on_commit_callbacks
    ):
        _loan(network["leles"], network["lolo"], started=False)
        mail.outbox.clear()
        url = BASE.format(code=network["group"].code) + "invite/"

        with django_capture_on_commit_callbacks(execute=True):
            res = client_for(network["founder"]).delete(url, {"user_code": "ENTA01"}, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert not Thing.objects.filter(code=network["leles"].code).exists()
        assert Thing.objects.filter(code=network["lilis"].code).exists()
        assert "lolo@your-domain.test" in [addr for m in mail.outbox for addr in m.to]

    @pytest.mark.parametrize("mode", [Collection.Mode.PROPRIETARY, Collection.Mode.COMMUNITY])
    def test_a_co_curator_still_removes_members_elsewhere_even_with_a_loan(self, mode):
        g, _, lele, _, lolo = _group(mode)
        thing = ThingFactory(owner=lele, type=LEND)
        g.things.add(thing)
        _loan(thing, lolo)

        res = client_for(lele).delete(
            BASE.format(code=g.code) + "invite/", {"user_code": "MEMB01"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert not g.invites.filter(code="MEMB01").exists()


@pytest.mark.django_db
class TestDemoting:
    def test_demoting_a_dinamizador_deletes_their_things_and_says_so(self, network):
        url = BASE.format(code=network["group"].code) + "co-owners/"

        res = client_for(network["founder"]).delete(url, {"user_code": "ENTA01"}, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert not Thing.objects.filter(code=network["leles"].code).exists()
        assert Thing.objects.filter(code=network["lilis"].code).exists()
        assert network["group"].invites.filter(code="ENTA01").exists()
        notice = InAppNotification.objects.get(type=InAppNotification.Type.DEMOTED_CO_OWNER)
        assert notice.payload["things_deleted"] == 1

    def test_demoting_waits_while_one_of_their_things_is_lent_out(self, network):
        _loan(network["leles"], network["lolo"])
        url = BASE.format(code=network["group"].code) + "co-owners/"

        res = client_for(network["founder"]).delete(url, {"user_code": "ENTA01"}, format="json")

        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["code"] == "curator_things_lent_out"
        assert network["group"].co_owners.filter(code="ENTA01").exists()
        assert Thing.objects.filter(code=network["leles"].code).exists()

    def test_demoting_in_a_proprietary_collection_keeps_their_things(self):
        g, founder, lele, _, _ = _group(Collection.Mode.PROPRIETARY)
        thing = ThingFactory(owner=lele, type=LEND)
        g.things.add(thing)

        res = client_for(founder).delete(
            BASE.format(code=g.code) + "co-owners/", {"user_code": "ENTA01"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert Thing.objects.filter(code=thing.code).exists()
        notice = InAppNotification.objects.get(type=InAppNotification.Type.DEMOTED_CO_OWNER)
        assert "things_deleted" not in notice.payload


@pytest.mark.django_db
class TestTheAccountIsNeverBlocked:
    def test_erasing_the_account_of_a_dinamizador_with_a_loan_out_goes_through(self, network):
        loan = _loan(network["leles"], network["lolo"])

        delete_account(network["lele"])

        assert not User.objects.filter(code="ENTA01").exists()
        assert not Thing.objects.filter(code=network["leles"].code).exists()
        assert not BookingPeriod.objects.filter(code=loan.code).exists()
        assert Thing.objects.filter(code=network["lilis"].code).exists()


def _calendar_summary(client, group):
    res = client.post(BASE.format(code=group.code) + "calendar-export/")
    assert res.status_code == status.HTTP_200_OK
    return res.content.decode()


@pytest.mark.django_db
class TestCalendarAndCopy:
    def test_the_founder_gets_every_reservation_and_a_dinamizador_only_theirs(self, network):
        mine = _loan(network["leles"], network["lolo"])
        theirs = _loan(network["lilis"], network["lolo"])

        for_lele = _calendar_summary(client_for(network["lele"]), network["group"])
        for_founder = _calendar_summary(client_for(network["founder"]), network["group"])

        assert f"{mine.code}@oiueei" in for_lele and f"{theirs.code}@oiueei" not in for_lele
        assert f"{mine.code}@oiueei" in for_founder and f"{theirs.code}@oiueei" in for_founder

    def test_the_founder_copies_every_thing_and_a_dinamizador_only_their_own(self, network):
        url = BASE.format(code=network["group"].code) + "export/"

        lele = client_for(network["lele"]).get(url)
        founder = client_for(network["founder"]).get(url)

        assert lele.status_code == founder.status_code == status.HTTP_200_OK
        import json

        lele_things = {t["code"] for t in json.loads(lele.content)["things"]}
        founder_things = {t["code"] for t in json.loads(founder.content)["things"]}
        assert lele_things == {network["leles"].code}
        assert founder_things == {network["leles"].code, network["lilis"].code}

    def test_a_dinamizador_reads_the_stats_as_before(self, network):
        res = client_for(network["lele"]).get(BASE.format(code=network["group"].code) + "stats/")

        assert res.status_code == status.HTTP_200_OK
        rows = list(csv.reader(io.StringIO(res.content.decode())))
        assert rows[0] == ["metric", "value"]

    def test_a_dinamizador_broadcasts_as_before(self, network):
        res = client_for(network["lele"]).post(
            BASE.format(code=network["group"].code) + "broadcast/",
            {"message": "Hello"},
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK
        assert res.data["recipients"] == len(mail.outbox) > 0
        notified = InAppNotification.objects.filter(type=InAppNotification.Type.BROADCAST)
        assert set(notified.values_list("user_id", flat=True)) == {
            m for m in ("ENTA01", "ENTB01", "MEMB01")
        }


@pytest.mark.django_db
class TestTheShareLink:
    """Generating and reading the link stay every dinamizador's (inviting is theirs);
    taking it back would kill the links and QR codes the others handed out."""

    def _url(self, group):
        return BASE.format(code=group.code) + "share-link/"

    def _with_token(self, network, token="TOKEN-OF-THE-NETWORK"):
        network["group"].share_token = token
        network["group"].save(update_fields=["share_token"])

    def test_a_dinamizador_cannot_rotate_the_link(self, network):
        self._with_token(network)

        res = client_for(network["lele"]).post(
            self._url(network["group"]), {"rotate": True}, format="json"
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert res.data["code"] == "network_founder_only"
        network["group"].refresh_from_db()
        assert network["group"].share_token == "TOKEN-OF-THE-NETWORK"

    def test_a_dinamizador_cannot_revoke_the_link(self, network):
        self._with_token(network)

        res = client_for(network["lele"]).delete(self._url(network["group"]))

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert res.data["code"] == "network_founder_only"
        network["group"].refresh_from_db()
        assert network["group"].share_token == "TOKEN-OF-THE-NETWORK"

    def test_a_dinamizador_generates_the_first_link(self, network):
        res = client_for(network["lele"]).post(self._url(network["group"]), {}, format="json")

        assert res.status_code == status.HTTP_200_OK
        network["group"].refresh_from_db()
        assert network["group"].share_token == res.data["share_token"]

    def test_a_dinamizador_reads_the_existing_link(self, network):
        self._with_token(network)

        res = client_for(network["lele"]).post(self._url(network["group"]), {}, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert res.data["share_token"] == "TOKEN-OF-THE-NETWORK"

    def test_asking_to_rotate_before_there_is_a_link_just_generates_one(self, network):
        res = client_for(network["lele"]).post(
            self._url(network["group"]), {"rotate": True}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert res.data["share_token"]

    def test_the_founder_rotates_and_revokes(self, network):
        self._with_token(network)
        client = client_for(network["founder"])

        rotated = client.post(self._url(network["group"]), {"rotate": True}, format="json")
        revoked = client.delete(self._url(network["group"]))

        assert rotated.status_code == status.HTTP_200_OK
        assert rotated.data["share_token"] != "TOKEN-OF-THE-NETWORK"
        assert revoked.status_code == status.HTTP_200_OK
        network["group"].refresh_from_db()
        assert network["group"].share_token is None

    @pytest.mark.parametrize("mode", [Collection.Mode.PROPRIETARY, Collection.Mode.COMMUNITY])
    def test_a_co_curator_elsewhere_still_rotates_and_revokes(self, mode):
        g, _, lele, _, _ = _group(mode)
        g.share_token = "OLD-TOKEN"
        g.save(update_fields=["share_token"])
        client = client_for(lele)

        rotated = client.post(self._url(g), {"rotate": True}, format="json")
        revoked = client.delete(self._url(g))

        assert rotated.status_code == status.HTTP_200_OK
        assert rotated.data["share_token"] != "OLD-TOKEN"
        assert revoked.status_code == status.HTTP_200_OK
