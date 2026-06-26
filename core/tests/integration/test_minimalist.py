"""
Integration tests for minimalist skin option (F15).
"""

import pytest

from core.models import Collection


@pytest.mark.django_db
class TestMinimalistValidation:
    """Tests for is_minimalist validation on collection serializers."""

    def test_cannot_combine_minimalist_and_swap(self, authenticated_client):
        """Minimalist and swap should be mutually exclusive."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Bad Combo",
                "mode": "COMMUNITY",
                "is_swap": True,
                "is_minimalist": True,
            },
            format="json",
        )
        assert response.status_code == 400

    def test_minimalist_with_share_allowed(self, authenticated_client):
        """Minimalist + share should be allowed."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Album Share",
                "mode": "COMMUNITY",
                "is_share": True,
                "is_minimalist": True,
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_minimalist"] is True
        assert data["is_share"] is True

    def test_minimalist_alone_allowed(self, authenticated_client):
        """Minimalist without swap or share should be allowed."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Simple Album",
                "mode": "PROPRIETARY",
                "is_minimalist": True,
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["is_minimalist"] is True


@pytest.mark.django_db
class TestMinimalistTypeRestrictions:
    """Tests for type restrictions in minimalist collections."""

    @pytest.fixture
    def minimalist_collection(self, db, user):
        return Collection.objects.create(
            code="MINIMA",
            owner=user,
            headline="Album Collection",
            mode="PROPRIETARY",
            is_minimalist=True,
        )

    def test_gift_thing_allowed(self, authenticated_client, minimalist_collection):
        """GIFT_THING should be allowed in minimalist collections."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "Nice Gift",
                "thumbnail": "oiueei/things/test123",
                "collection_code": minimalist_collection.code,
            },
            format="json",
        )
        assert response.status_code == 201

    def test_sell_thing_blocked(self, authenticated_client, minimalist_collection):
        """SELL_THING should be blocked in minimalist collections."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SELL_THING",
                "headline": "For Sale",
                "thumbnail": "oiueei/things/test123",
                "fee": "10.00",
                "collection_code": minimalist_collection.code,
            },
            format="json",
        )
        assert response.status_code == 400
        assert "minimalist" in response.json()["error"].lower()

    def test_wish_blocked_in_community_album(self, authenticated_client, user):
        """An album collection stays offer-only: it rejects wishes even in
        COMMUNITY mode, where a wish would otherwise be a valid type."""
        album = Collection.objects.create(
            code="CMALB1",
            owner=user,
            headline="Community Album",
            mode="COMMUNITY",
            is_minimalist=True,
        )
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Wish In Album",
                "thumbnail": "oiueei/things/test123",
                "collection_code": album.code,
            },
            format="json",
        )
        assert response.status_code == 400
        assert "minimalist" in response.json()["error"].lower()

    def test_thumbnail_required(self, authenticated_client, minimalist_collection):
        """Things in minimalist collections must have a thumbnail."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "No Photo",
                "collection_code": minimalist_collection.code,
            },
            format="json",
        )
        assert response.status_code == 400
        assert "photo" in response.json()["error"].lower()

    def test_update_swap_to_minimalist_blocked(self, authenticated_client, user):
        """Updating to both is_swap and is_minimalist should fail."""
        coll = Collection.objects.create(
            code="UPDMIN",
            owner=user,
            headline="Updatable",
            mode="COMMUNITY",
            is_swap=True,
        )
        response = authenticated_client.patch(
            f"/api/v1/collections/{coll.code}/",
            {"is_minimalist": True},
            format="json",
        )
        assert response.status_code == 400
