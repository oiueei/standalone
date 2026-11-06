"""Who may open whose profile: whoever is inside the same group.

Founder, co-curators and members open each other's public profile; someone outside
the group opens none of them, even when the group is public, and a person of another
group is just as closed.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from core.models import Collection
from core.tests.factories import CollectionFactory, UserFactory

PUBLIC, PRIVATE = Collection.Visibility.PUBLIC, Collection.Visibility.PRIVATE


def get_profile(viewer, target):
    client = APIClient()
    client.force_authenticate(viewer)
    return client.get(f"/api/v1/users/{target.code}/")


def shared_codes(res):
    return {c["code"] for c in res.data["shared_collections"]}


@pytest.fixture
def team(db):
    return {
        "founder": UserFactory(code="FOUN01", email="lala@your-domain.test", name="Lala"),
        "curator": UserFactory(code="CURA01", email="lele@your-domain.test", name="Lele"),
        "member": UserFactory(code="MEMB01", email="lili@your-domain.test", name="Lili"),
        "member2": UserFactory(code="MEMB02", email="lolo@your-domain.test", name="Lolo"),
        "reader": UserFactory(code="READ01", email="lulu@your-domain.test", name="Lulu"),
    }


def group(team, visibility=PUBLIC, status=Collection.Status.ACTIVE):
    collection = CollectionFactory(owner=team["founder"], visibility=visibility, status=status)
    collection.invites.add(team["curator"], team["member"], team["member2"])
    collection.co_owners.add(team["curator"])
    return collection


class TestReaderOfAPublicGroup:
    """Reading a public group does not open its team's general profiles."""

    def test_sees_nobody_of_the_team_not_even_the_founder(self, team):
        group(team)
        for target in ("founder", "curator", "member"):
            assert get_profile(team["reader"], team[target]).status_code == 403

    def test_private_group_opens_nobody_to_a_reader(self, team):
        group(team, visibility=PRIVATE)
        for target in ("founder", "curator", "member"):
            assert get_profile(team["reader"], team[target]).status_code == 403

    def test_inactive_group_opens_nobody_to_a_reader(self, team):
        group(team, status=Collection.Status.INACTIVE)
        for target in ("founder", "curator", "member"):
            assert get_profile(team["reader"], team[target]).status_code == 403


class TestInsideAGroup:
    def test_member_sees_the_co_curator_and_shares_the_group(self, team):
        collection = group(team, visibility=PRIVATE)
        res = get_profile(team["member"], team["curator"])
        assert res.status_code == 200
        assert shared_codes(res) == {collection.code}

    def test_member_sees_another_member_of_the_same_group(self, team):
        collection = group(team, visibility=PRIVATE)
        res = get_profile(team["member"], team["member2"])
        assert res.status_code == 200
        assert shared_codes(res) == {collection.code}

    def test_member_does_not_see_a_member_of_another_group(self, team):
        group(team, visibility=PRIVATE)
        other = CollectionFactory(owner=team["curator"], visibility=PRIVATE)
        other.invites.add(team["reader"])
        assert get_profile(team["member"], team["reader"]).status_code == 403

    def test_two_groups_each_with_one_of_them_do_not_make_them_share_one(self, team):
        # The joins must not mix collections: one in A, the other in B, never together.
        CollectionFactory(owner=team["founder"]).invites.add(team["member"])
        CollectionFactory(owner=team["curator"]).invites.add(team["member2"])
        assert get_profile(team["member"], team["member2"]).status_code == 403

    def test_answer_has_exactly_the_public_keys(self, team):
        group(team, visibility=PRIVATE)
        res = get_profile(team["member"], team["member2"])
        assert set(res.data) == {
            "code",
            "name",
            "headline",
            "about",
            "photo_url",
            "created",
            "shared_collections",
        }

    def test_co_curator_sees_a_member_and_shares_the_group(self, team):
        collection = group(team, visibility=PRIVATE)
        res = get_profile(team["curator"], team["member"])
        assert res.status_code == 200
        assert shared_codes(res) == {collection.code}

    def test_founder_sees_a_member(self, team):
        group(team, visibility=PRIVATE)
        assert get_profile(team["founder"], team["member"]).status_code == 200


class TestSharedCollectionsAreOnlyThoseBothAreIn:
    def test_a_group_the_target_runs_and_the_viewer_is_not_in_never_shows(self, team):
        shared = group(team, visibility=PUBLIC)
        shared.invites.add(team["reader"])
        hidden = CollectionFactory(owner=team["curator"], visibility=PRIVATE)
        res = get_profile(team["reader"], team["curator"])
        assert res.status_code == 200
        assert shared_codes(res) == {shared.code}
        assert hidden.code not in shared_codes(res)

    def test_a_group_is_listed_once(self, team):
        collection = group(team, visibility=PRIVATE)
        res = get_profile(team["member"], team["curator"])
        assert len(res.data["shared_collections"]) == 1
        assert res.data["shared_collections"][0]["code"] == collection.code


class TestQueryCount:
    def test_does_not_grow_with_the_number_of_groups(self, team):
        # A member who shares every group with the co-curator: the shared list grows.
        def queries():
            with CaptureQueriesContext(connection) as ctx:
                assert get_profile(team["member"], team["curator"]).status_code == 200
            return len(ctx)

        group(team, visibility=PRIVATE)
        queries()  # warm the caches the first request fills
        few = queries()
        for _ in range(8):
            group(team, visibility=PRIVATE)
        assert queries() == few
