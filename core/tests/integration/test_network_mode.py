"""A network of libraries: a third mode, only for a library, fixed at creation.

Where PROPRIETARY has one team running a shared catalogue and COMMUNITY lets any
member contribute, a NETWORK is a founder plus entities that each lend their own
things. The mode can be born only on a library, never gained or lost by an edit,
and is handed out by the deployment's creator policy like the other two.
"""

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, User
from core.tests.factories import CollectionFactory

URL = "/api/v1/collections/"
RESTRICTED = "core.tests.sample_creator_policy.RestrictedCreatorPolicy"
LEND, RENT = "LEND_THING", "RENT_THING"


def _create(client, **body):
    return client.post(URL, {"headline": "Network", **body}, format="json")


def _client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db
class TestCreatingANetwork:
    def test_a_library_can_be_born_a_network_with_both_of_its_verbs(self, authenticated_client):
        res = _create(authenticated_client, kind="LIBRARY", mode="NETWORK")

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["mode"] == "NETWORK"
        assert res.data["allowed_thing_types"] == [LEND, RENT]
        assert Collection.objects.get(code=res.data["code"]).is_network()

    def test_a_network_ignores_a_free_only_list_like_a_proprietary_one(self, authenticated_client):
        res = _create(
            authenticated_client, kind="LIBRARY", mode="NETWORK", allowed_thing_types=[LEND]
        )

        assert res.data["allowed_thing_types"] == [LEND, RENT]

    @pytest.mark.parametrize("kind", ["STALL", "SHED"])
    def test_a_stall_or_a_shed_cannot_be_a_network(self, authenticated_client, kind):
        res = _create(authenticated_client, kind=kind, mode="NETWORK")

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "library" in str(res.data)
        assert not Collection.objects.filter(headline="Network").exists()

    @override_settings(CREATOR_POLICY=RESTRICTED)
    def test_a_deployment_that_withholds_the_mode_refuses_it_like_community(
        self, authenticated_client
    ):
        res = _create(authenticated_client, kind="LIBRARY", mode="NETWORK")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert not Collection.objects.filter(headline="Network").exists()


@pytest.mark.django_db
class TestTheModeIsFixed:
    def test_a_proprietary_library_cannot_become_a_network(self, authenticated_client, user):
        library = CollectionFactory(owner=user, allowed_thing_types=[LEND, RENT])

        res = authenticated_client.patch(
            f"{URL}{library.code}/", {"mode": "NETWORK"}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        library.refresh_from_db()
        assert library.mode == Collection.Mode.PROPRIETARY

    @pytest.mark.parametrize("to", ["PROPRIETARY", "COMMUNITY"])
    def test_a_network_cannot_leave_its_mode(self, authenticated_client, user, to):
        network = CollectionFactory(
            owner=user, mode=Collection.Mode.NETWORK, allowed_thing_types=[LEND, RENT]
        )

        res = authenticated_client.patch(f"{URL}{network.code}/", {"mode": to}, format="json")

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        network.refresh_from_db()
        assert network.mode == Collection.Mode.NETWORK

    def test_naming_the_mode_it_already_has_is_harmless(self, authenticated_client, user):
        network = CollectionFactory(
            owner=user, mode=Collection.Mode.NETWORK, allowed_thing_types=[LEND, RENT]
        )

        res = authenticated_client.patch(
            f"{URL}{network.code}/", {"mode": "NETWORK", "headline": "Renamed"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        network.refresh_from_db()
        assert (network.mode, network.headline) == (Collection.Mode.NETWORK, "Renamed")

    def test_a_proprietary_collection_still_becomes_community(self, authenticated_client, user):
        stall = CollectionFactory(owner=user)

        res = authenticated_client.patch(
            f"{URL}{stall.code}/", {"mode": "COMMUNITY"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        stall.refresh_from_db()
        assert stall.mode == Collection.Mode.COMMUNITY


@pytest.mark.django_db
class TestWhoPutsThingsIn:
    @pytest.fixture
    def network(self, db):
        owner = User.objects.create(code="OWNR01", email="lala@your-domain.test", name="Lala")
        curator = User.objects.create(code="CURA01", email="lele@your-domain.test", name="Lele")
        member = User.objects.create(code="MEMB01", email="lili@your-domain.test", name="Lili")
        network = CollectionFactory(
            owner=owner, mode=Collection.Mode.NETWORK, allowed_thing_types=[LEND, RENT]
        )
        network.invites.add(curator, member)
        network.co_owners.add(curator)
        return network

    def test_the_founder_and_a_curator_can_add_a_thing(self, network):
        assert network.can_add_thing("OWNR01")
        assert network.can_add_thing("CURA01")

    def test_a_plain_member_cannot_add_to_a_network_unlike_a_community(self, network):
        assert not network.can_add_thing("MEMB01")

    def test_a_member_can_still_add_to_a_community(self, network):
        community = CollectionFactory(owner=network.owner, mode=Collection.Mode.COMMUNITY)
        community.invites.add(User.objects.get(code="MEMB01"))

        assert community.can_add_thing("MEMB01")

    def test_only_the_founder_can_rescue(self, network):
        assert network.can_rescue("OWNR01")
        assert not network.can_rescue("CURA01")
        assert not network.can_rescue("MEMB01")

    def test_nobody_rescues_outside_a_network(self, network):
        proprietary = CollectionFactory(owner=network.owner)

        assert not proprietary.can_rescue("OWNR01")


@pytest.mark.django_db
def test_a_network_holds_up_to_ten_co_curators():
    owner = User.objects.create(code="OWNR01", email="lala@your-domain.test")
    network = CollectionFactory(owner=owner, mode=Collection.Mode.NETWORK)
    people = [
        User.objects.create(code=f"P{i:05d}", email=f"p{i}@your-domain.test") for i in range(11)
    ]
    network.invites.add(*people)

    results = [network.promote_co_owner(p) for p in people]

    assert results[:10] == [Collection.Promotion.ADDED] * 10
    assert results[10] is Collection.Promotion.FULL
