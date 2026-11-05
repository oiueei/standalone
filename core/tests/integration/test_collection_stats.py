"""
Integration tests for the owner-only usage-stats CSV.

Covers the owner gate (any collection mode), and that the CSV carries the
expected snapshot counts and the aggregate age/postal breakdown.
"""

import csv as csvlib

import pytest
from rest_framework.test import APIClient

from core.models import Collection, NetworkPoint, Thing, User
from core.services.export_service import build_collection_export
from core.tests.factories import (
    BookingPeriodFactory,
    CollectionFactory,
    ThingFactory,
    ThingTransferFactory,
    UserFactory,
)

URL = "/api/v1/collections/{code}/stats/"


def _csv_dict(res):
    reader = csvlib.reader(res.content.decode().splitlines())
    return {row[0]: row[1] for row in reader if len(row) >= 2}


class TestCollectionStats:
    def _community(self, owner, code="COMM01"):
        return Collection.objects.create(
            code=code, owner=owner, headline="C", mode=Collection.Mode.COMMUNITY
        )

    def test_non_owner_forbidden(self, authenticated_client2, user):
        coll = self._community(user)
        res = authenticated_client2.get(URL.format(code=coll.code))
        assert res.status_code == 403

    def test_proprietary_collection_allowed(self, authenticated_client, user, user2):
        # Stats are available to the owner of ANY collection, not just COMMUNITY.
        coll = Collection.objects.create(
            code="PROP01", owner=user, headline="P", mode=Collection.Mode.PROPRIETARY
        )
        user2.age_range = "GEN_Z"
        user2.postal_code = "48001"
        user2.save()
        coll.invites.add(user2)

        res = authenticated_client.get(URL.format(code=coll.code))
        assert res.status_code == 200
        assert f"{coll.code}-stats.csv" in res["Content-Disposition"]
        data = _csv_dict(res)
        assert data["Members"] == "1"
        # One member: naming their bracket or their code would be naming them.
        assert "Born 1997-2012 (Gen Z)" not in data
        assert "Postal 48001" not in data
        assert data["Birth year shared by fewer than 3"] == "1"
        assert data["Postal, other codes"] == "1"

    def test_csv_counts_and_demographics(self, authenticated_client, user, user2):
        coll = self._community(user)
        user2.age_range = "GEN_Z"
        user2.postal_code = "48001"
        user2.save()
        m2 = User.objects.create(code="MEM002", email="lala@your-domain.test")  # no demographics
        coll.invites.add(user2, m2)

        t1 = Thing.objects.create(
            code="TT0001", type="GIFT_THING", owner=user, headline="a", status="ACTIVE"
        )
        t2 = Thing.objects.create(
            code="TT0002", type="GIFT_THING", owner=user, headline="b", status="TAKEN"
        )
        coll.things.add(t1, t2)

        res = authenticated_client.get(URL.format(code=coll.code))
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert "attachment" in res["Content-Disposition"]
        assert f"{coll.code}-stats.csv" in res["Content-Disposition"]

        data = _csv_dict(res)
        assert data["Members"] == "2"
        assert data["Things total"] == "2"
        assert data["Things active"] == "1"
        assert data["Things reserved"] == "1"
        assert "Born 1997-2012 (Gen Z)" not in data
        assert data["Birth year shared by fewer than 3"] == "1"
        assert data["Birth year not specified"] == "1"
        assert "Postal 48001" not in data
        assert data["Postal, other codes"] == "1"
        assert data["Postal not specified"] == "1"

    def _members(self, coll, people):
        """Add one member per ``(age_range, postal_code)`` pair."""
        coll.invites.add(
            *User.objects.bulk_create(
                User(
                    code=f"MIN{i:03d}",
                    email=f"lele{i}@your-domain.test",
                    age_range=age,
                    postal_code=p,
                )
                for i, (age, p) in enumerate(people)
            )
        )

    def test_a_bracket_or_a_code_is_named_from_three_members_up(self, authenticated_client, user):
        """Below three the figure is about a person; from three it is about a group.
        Two members sharing a bracket and a code is the case the rule exists for: in a
        group of two, "Postal 08001: 2" names both of them. A bracket nobody is in is
        left out too, or the missing rows would name the small ones."""
        coll = self._community(user)
        self._members(
            coll,
            [("GEN_Z", "48001")] * 3 + [("GEN_X", "08001")] * 2 + [("BOOMER", "28001")],
        )

        data = _csv_dict(authenticated_client.get(URL.format(code=coll.code)))

        assert data["Born 1997-2012 (Gen Z)"] == "3"
        assert data["Postal 48001"] == "3"
        # The pair and the one are summed, never named.
        assert "Born 1965-1980 (Gen X)" not in data
        assert "Postal 08001" not in data
        assert "Born 1946-1964 (Boomers)" not in data
        assert "Postal 28001" not in data
        assert data["Birth year shared by fewer than 3"] == "3"
        assert data["Postal, other codes"] == "3"
        assert "Born 1981-1996 (Millennials)" not in data

    def test_only_the_ten_most_common_codes_are_named(self, authenticated_client, user):
        """Ten named codes at most; an eleventh, even one held by three members, is
        counted with the others rather than growing the file without end."""
        coll = self._community(user)
        common = [("", f"0800{n}" if n < 10 else "08010") for n in range(10) for _ in range(4)]
        self._members(coll, common + [("", "48001")] * 3)

        data = _csv_dict(authenticated_client.get(URL.format(code=coll.code)))

        named = sorted(label for label in data if label.startswith("Postal 0"))
        assert len(named) == 10
        assert all(data[label] == "4" for label in named)
        assert "Postal 48001" not in data
        assert data["Postal, other codes"] == "3"


class TestNetworkStatsAreTheEntitys:
    """In a network a dinamizador gets the figures of their own things; the founder, all."""

    @pytest.fixture
    def world(self, db):
        founder = UserFactory(code="FOUN01", email="lala@your-domain.test", name="Lala")
        lele = UserFactory(code="ENTA01", email="lele@your-domain.test", name="Lele")
        lili = UserFactory(code="ENTB01", email="lili@your-domain.test", name="Lili")
        member = UserFactory(code="MEMB01", email="lolo@your-domain.test", name="Lolo")
        network = CollectionFactory(
            owner=founder, mode=Collection.Mode.NETWORK, allowed_thing_types=["LEND_THING"]
        )
        network.invites.add(lele, lili, member)
        network.co_owners.add(lele, lili)
        NetworkPoint.objects.create(collection=network, user=lele, entity_name="Coop Lele")
        # Lele runs 3 things (one taken), Lili runs 1.
        leles = [ThingFactory(owner=lele, type="LEND_THING", status="ACTIVE") for _ in range(2)]
        leles.append(ThingFactory(owner=lele, type="LEND_THING", status="TAKEN"))
        lilis = [ThingFactory(owner=lili, type="LEND_THING", status="ACTIVE")]
        network.things.add(*leles, *lilis)
        # Bookings: 2 on Lele's things, 1 on Lili's. Handovers: 1 and 2.
        for thing in (leles[0], leles[1], lilis[0]):
            BookingPeriodFactory(thing_code=thing, requester_code=member)
        ThingTransferFactory(thing=leles[0], from_user=lele, to_user=member)
        ThingTransferFactory(thing=lilis[0], from_user=lili, to_user=member)
        ThingTransferFactory(thing=lilis[0], from_user=lili, to_user=member)
        return {"network": network, "founder": founder, "lele": lele, "lili": lili}

    def _stats(self, world, who):
        client = APIClient()
        client.force_authenticate(world[who])
        res = client.get(URL.format(code=world["network"].code))
        assert res.status_code == 200
        rows = list(csvlib.reader(res.content.decode().splitlines()))
        return rows, {row[0]: row[1] for row in rows if len(row) >= 2}

    def test_dinamizador_sees_only_their_things_in_the_six_rows(self, world):
        rows, data = self._stats(world, "lele")
        assert data["Things total"] == "3"
        assert data["Things active"] == "2"
        assert data["Things reserved"] == "1"
        assert data["Things added (90d)"] == "3"
        assert data["Bookings (90d)"] == "2"
        assert data["Handovers (90d)"] == "1"
        assert rows[1] == ["Pickup point", "Coop Lele"]

    def test_members_and_invitations_stay_the_networks(self, world):
        _, data = self._stats(world, "lele")
        assert data["Members"] == "3"
        assert data["Pending invitations"] == "0"
        assert "Invitations sent (90d)" in data
        assert "Active members (90d)" in data

    def test_another_dinamizador_has_their_own_figures(self, world):
        rows, data = self._stats(world, "lili")
        assert data["Things total"] == "1"
        assert data["Bookings (90d)"] == "1"
        assert data["Handovers (90d)"] == "2"
        # No point set up: the dinamizador's own name stands for the entity.
        assert rows[1] == ["Pickup point", "Lili"]

    def test_founder_gets_the_whole_network_and_no_pickup_row(self, world):
        rows, data = self._stats(world, "founder")
        assert data["Things total"] == "4"
        assert data["Bookings (90d)"] == "3"
        assert data["Handovers (90d)"] == "3"
        assert "Pickup point" not in data
        assert rows[1][0] == "Members"

    def test_entity_name_that_looks_like_a_formula_is_quoted(self, world):
        NetworkPoint.objects.filter(user=world["lele"]).update(entity_name="=SUM(A1)")
        rows, _ = self._stats(world, "lele")
        assert rows[1] == ["Pickup point", "'=SUM(A1)"]

    def test_group_copy_stats_match_the_csv(self, world):
        _, data = self._stats(world, "lele")
        data.pop("metric")
        payload = build_collection_export(world["network"], world["lele"])
        stats = payload["stats"]
        assert stats["Pickup point"] == "Coop Lele"
        assert {k: str(v) for k, v in stats.items()} == data
        assert stats["Things total"] == len(payload["things"]) == 3

    def test_proprietary_co_curator_still_gets_the_totals(self, db):
        owner = UserFactory(code="OWNR01", email="o@your-domain.test")
        co = UserFactory(code="COCU01", email="c@your-domain.test")
        coll = CollectionFactory(owner=owner, mode=Collection.Mode.PROPRIETARY)
        coll.co_owners.add(co)
        coll.things.add(ThingFactory(owner=owner), ThingFactory(owner=owner))
        client = APIClient()
        client.force_authenticate(co)
        res = client.get(URL.format(code=coll.code))
        data = {r[0]: r[1] for r in csvlib.reader(res.content.decode().splitlines()) if len(r) > 1}
        assert data["Things total"] == "2"
        assert "Pickup point" not in data
