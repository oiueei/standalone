"""A PROPRIETARY collection's curators run its catalogue collectively.

Every thing in a PROPRIETARY collection was added by a curator *for* the group,
so its curators (owner + co-curators) may add, edit, hide, activate and delete
any of them — there is no contributing member with a stake to protect. COMMUNITY
is unchanged: a member owns what they contribute, and a curator's reach there
still stops short of editing it.

These tests pin `Thing.can_manage`, the `IsThingManager` permission, the widened
`Thing.can_delete`, and the `can_manage` serializer field the frontend gates on.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner(db):
    return User.objects.create(code="OWNR01", email="lala@your-domain.test", name="Lala")


@pytest.fixture
def co_curator(db):
    return User.objects.create(code="COCU01", email="lala2@your-domain.test", name="Lele")


@pytest.fixture
def outsider(db):
    return User.objects.create(code="OUTS01", email="lolo@your-domain.test", name="Lolo")


@pytest.fixture
def space(db, owner, co_curator):
    """A PROPRIETARY collection with one co-curator, and one thing the founder added."""
    collection = Collection.objects.create(
        code="SPC001",
        owner=owner,
        headline="The workshop",
        kind="LIBRARY",
        mode=Collection.Mode.PROPRIETARY,
    )
    collection.invites.add(co_curator)
    collection.co_owners.add(co_curator)
    return collection


@pytest.fixture
def founders_thing(db, owner, space):
    thing = Thing.objects.create(
        code="THG001", owner=owner, headline="The lathe", type="LEND_THING"
    )
    space.things.add(thing)
    return thing


class TestACoCuratorRunsTheProprietaryCatalogue:
    def test_can_add_a_thing(self, space, co_curator):
        res = client_for(co_curator).post(
            "/api/v1/things/",
            {"type": "LEND_THING", "headline": "A drill", "collection_code": space.code},
            format="json",
        )
        assert res.status_code == 201
        thing = Thing.objects.get(code=res.data["code"])
        assert thing.owner_id == co_curator.code  # the adder owns what they add
        assert space.things.filter(code=thing.code).exists()

    def test_can_edit_the_founders_thing(self, space, co_curator, founders_thing):
        res = client_for(co_curator).patch(
            f"/api/v1/things/{founders_thing.code}/", {"headline": "The good lathe"}, format="json"
        )
        assert res.status_code == 200
        founders_thing.refresh_from_db()
        assert founders_thing.headline == "The good lathe"

    def test_can_hide_and_reactivate_the_founders_thing(self, space, co_curator, founders_thing):
        c = client_for(co_curator)
        assert c.post(f"/api/v1/things/{founders_thing.code}/hide/").status_code == 200
        founders_thing.refresh_from_db()
        assert founders_thing.status == Thing.Status.INACTIVE
        assert c.post(f"/api/v1/things/{founders_thing.code}/activate/").status_code == 200
        founders_thing.refresh_from_db()
        assert founders_thing.status == Thing.Status.ACTIVE

    def test_can_delete_the_founders_thing(self, space, co_curator, founders_thing):
        res = client_for(co_curator).delete(f"/api/v1/things/{founders_thing.code}/")
        assert res.status_code == 204
        assert not Thing.objects.filter(code=founders_thing.code).exists()

    def test_the_founder_can_edit_a_co_curators_thing(self, space, owner, co_curator):
        thing = Thing.objects.create(
            code="THG002", owner=co_curator, headline="Co's jig", type="LEND_THING"
        )
        space.things.add(thing)
        res = client_for(owner).patch(
            f"/api/v1/things/{thing.code}/", {"headline": "The jig"}, format="json"
        )
        assert res.status_code == 200

    def test_the_card_tells_the_co_curator_they_may_manage(self, space, co_curator, founders_thing):
        res = client_for(co_curator).get(f"/api/v1/collections/{space.code}/")
        assert res.status_code == 200
        card = next(t for t in res.data["things"] if t["code"] == founders_thing.code)
        assert card["can_manage"] is True

    def test_the_co_curator_sees_the_owner_booking_list_on_the_thing(
        self, space, co_curator, founders_thing
    ):
        res = client_for(co_curator).get(f"/api/v1/things/{founders_thing.code}/")
        assert res.status_code == 200
        assert res.data["can_manage"] is True
        assert res.data["bookings"] == []  # a list, not None — they may see it


class TestCommunityIsUnchanged:
    def test_a_community_co_curator_still_cannot_edit_a_members_thing(self, db):
        owner = User.objects.create(code="COWN01", email="lala9@your-domain.test", name="Owner")
        co_curator = User.objects.create(
            code="CCUR02", email="lala1@your-domain.test", name="Curator"
        )
        contributor = User.objects.create(
            code="CONTR1", email="lele@your-domain.test", name="Member"
        )
        group = Collection.objects.create(
            code="COM001", owner=owner, headline="The street", mode=Collection.Mode.COMMUNITY
        )
        group.invites.add(co_curator, contributor)
        group.co_owners.add(co_curator)
        members_thing = Thing.objects.create(
            code="THG003", owner=contributor, headline="My ladder", type="LEND_THING"
        )
        group.things.add(members_thing)

        res = client_for(co_curator).patch(
            f"/api/v1/things/{members_thing.code}/", {"headline": "Hijack"}, format="json"
        )
        assert res.status_code == 403
        members_thing.refresh_from_db()
        assert members_thing.headline == "My ladder"

    def test_the_card_does_not_offer_management_of_a_community_members_thing(self, db):
        owner = User.objects.create(code="COWN02", email="lala3@your-domain.test", name="Owner")
        co_curator = User.objects.create(
            code="CCUR03", email="lili@your-domain.test", name="Curator"
        )
        contributor = User.objects.create(
            code="CONTR2", email="lolo1@your-domain.test", name="Member"
        )
        group = Collection.objects.create(
            code="COM002", owner=owner, headline="The block", mode=Collection.Mode.COMMUNITY
        )
        group.invites.add(co_curator, contributor)
        group.co_owners.add(co_curator)
        members_thing = Thing.objects.create(
            code="THG004", owner=contributor, headline="A saw", type="LEND_THING"
        )
        group.things.add(members_thing)

        res = client_for(co_curator).get(f"/api/v1/collections/{group.code}/")
        card = next(t for t in res.data["things"] if t["code"] == members_thing.code)
        assert card["can_manage"] is False


class TestReachDoesNotBleedAcrossCollections:
    def test_a_curator_of_one_space_cannot_manage_a_thing_that_lives_only_in_another(self, db):
        owner_a = User.objects.create(code="OWNA01", email="lala4@your-domain.test", name="A")
        owner_b = User.objects.create(code="OWNB01", email="lala5@your-domain.test", name="B")
        curator_a = User.objects.create(
            code="CURA01", email="lele10@your-domain.test", name="CuratorA"
        )

        space_a = Collection.objects.create(
            code="SPCA01", owner=owner_a, headline="Space A", mode=Collection.Mode.PROPRIETARY
        )
        space_a.invites.add(curator_a)
        space_a.co_owners.add(curator_a)

        space_b = Collection.objects.create(
            code="SPCB01", owner=owner_b, headline="Space B", mode=Collection.Mode.PROPRIETARY
        )
        thing_b = Thing.objects.create(
            code="THGB01", owner=owner_b, headline="B's thing", type="LEND_THING"
        )
        space_b.things.add(thing_b)

        res = client_for(curator_a).patch(
            f"/api/v1/things/{thing_b.code}/", {"headline": "reach"}, format="json"
        )
        assert res.status_code == 403
        thing_b.refresh_from_db()
        assert thing_b.headline == "B's thing"
        # and the card in their own space would never have offered it
        card_res = client_for(curator_a).get(f"/api/v1/collections/{space_a.code}/")
        assert card_res.data["things"] == []


class TestNoNPlusOne:
    def test_the_grid_stays_constant_for_a_co_curator(self, db, owner, co_curator):
        """`can_manage` reads the reading collection's `co_owners` via `.all()`;
        that M2M is prefetched unconditionally, so serialising a curator's grid
        must not gain a query per thing."""
        space = Collection.objects.create(
            code="SPCN01", owner=owner, headline="Big space", mode=Collection.Mode.PROPRIETARY
        )
        space.invites.add(co_curator)
        space.co_owners.add(co_curator)
        url = f"/api/v1/collections/{space.code}/"
        c = client_for(co_curator)
        c.get("/api/v1/auth/me/")  # prime DailyActivityMiddleware's once-a-day write

        def add(n, start):
            for i in range(n):
                t = Thing.objects.create(
                    code=f"TN{start + i:04d}", owner=owner, headline="t", type="LEND_THING"
                )
                space.things.add(t)

        add(2, 0)
        with CaptureQueriesContext(connection) as small:
            assert c.get(url).status_code == 200
        add(6, 2)
        with CaptureQueriesContext(connection) as big:
            r2 = c.get(url)

        assert len(r2.data["things"]) == 8
        assert all(t["can_manage"] for t in r2.data["things"])
        assert len(big) == len(small), f"N+1 on the co-curator grid: {len(small)} vs {len(big)}"
