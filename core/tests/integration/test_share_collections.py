"""
Integration tests for COMMUNITY collections with exclusive SHARE mode (is_share).
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing


@pytest.fixture
def community_collection(db, user):
    """Create a COMMUNITY collection owned by user."""
    return Collection.objects.create(
        code="SHCO01",
        owner=user,
        headline="Share Collection",
        mode="COMMUNITY",
        is_share=True,
    )


@pytest.fixture
def guest_client(db, user2, community_collection):
    """Return an authenticated client for user2, invited to the collection."""
    community_collection.invites.add(user2)
    client = APIClient()
    refresh = RefreshToken.for_user(user2)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
class TestShareCollectionCreation:
    """Test creating and validating share collections."""

    def test_create_share_collection(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "My Share Collection",
                "mode": "COMMUNITY",
                "is_share": True,
            },
            format="json",
        )
        assert res.status_code == 201
        data = res.json()
        assert data["is_share"] is True
        assert data["is_swap"] is False

    def test_share_and_swap_mutually_exclusive(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Both",
                "mode": "COMMUNITY",
                "is_share": True,
                "is_swap": True,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_share_requires_community_mode(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Proprietary Share",
                "mode": "PROPRIETARY",
                "is_share": True,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_update_to_share_and_swap_rejected(self, authenticated_client, community_collection):
        res = authenticated_client.patch(
            f"/api/v1/collections/{community_collection.code}/",
            {"is_swap": True, "is_share": True},
            format="json",
        )
        assert res.status_code == 400


@pytest.mark.django_db
class TestShareCollectionTypeRestrictions:
    """Test that share collections only accept SHARE_THING."""

    def test_share_collection_accepts_share_thing(self, authenticated_client, community_collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SHARE_THING",
                "headline": "A Shared Item",
                "collection_code": community_collection.code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["type"] == "SHARE_THING"

    def test_share_collection_rejects_gift_thing(self, authenticated_client, community_collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "A Gift",
                "collection_code": community_collection.code,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_share_collection_rejects_swap_thing(self, authenticated_client, community_collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SWAP_THING",
                "headline": "A Swap",
                "collection_code": community_collection.code,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_guest_can_add_share_thing(self, guest_client, community_collection):
        res = guest_client.post(
            "/api/v1/things/",
            {
                "type": "SHARE_THING",
                "headline": "Guest Share",
                "collection_code": community_collection.code,
            },
            format="json",
        )
        assert res.status_code == 201

    def test_guest_cannot_add_gift_thing(self, guest_client, community_collection):
        res = guest_client.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "Guest Gift",
                "collection_code": community_collection.code,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_share_flag_visible_in_collection_detail(
        self, authenticated_client, community_collection
    ):
        res = authenticated_client.get(f"/api/v1/collections/{community_collection.code}/")
        assert res.status_code == 200
        assert res.json()["is_share"] is True
