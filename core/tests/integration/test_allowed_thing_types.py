"""
Integration tests for Collection.allowed_thing_types.

Validates the per-collection thing-type allowlist set at creation/edit
time on `/collections/new` and `/collections/{code}/edit`.
"""

import pytest
from rest_framework import status

from core.models import Collection, Thing


@pytest.mark.django_db
class TestCreateWithAllowedTypes:
    """POST /api/v1/collections/ — allowlist is persisted and validated."""

    def test_create_proprietary_with_allowlist(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Books to lend", "allowed_thing_types": ["LEND_THING"]},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_thing_types"] == ["LEND_THING"]

    def test_create_proprietary_without_allowlist_succeeds(self, authenticated_client):
        """Empty list is tolerated by the API — UI enforces 'pick at least one'."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Untyped collection"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_thing_types"] == []

    def test_create_proprietary_rejects_community_only_type(self, authenticated_client):
        for community_type in ("WISH_THING", "SHARE_THING", "SWAP_THING"):
            response = authenticated_client.post(
                "/api/v1/collections/",
                {"headline": "Bad", "allowed_thing_types": ["GIFT_THING", community_type]},
                format="json",
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST, community_type


@pytest.mark.django_db
class TestCommunityWithAllowedTypes:
    """COMMUNITY collections accept the wider type set; flags override the list."""

    def test_create_community_with_share_or_wish_succeeds(self, authenticated_client):
        for community_type in ("WISH_THING", "SHARE_THING"):
            response = authenticated_client.post(
                "/api/v1/collections/",
                {
                    "headline": f"Community {community_type}",
                    "mode": "COMMUNITY",
                    "allowed_thing_types": [community_type],
                },
                format="json",
            )
            assert response.status_code == status.HTTP_201_CREATED, community_type

    def test_create_community_rejects_swap_type_without_is_swap(self, authenticated_client):
        """SWAP_THING needs is_swap=True; listing it on a non-swap COMMUNITY is invalid."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "No-swap community",
                "mode": "COMMUNITY",
                "allowed_thing_types": ["SWAP_THING"],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_is_swap_accepts_matching_swap_thing_list(self, authenticated_client):
        """is_swap forces SWAP_THING; the only consistent allowlist is ['SWAP_THING']."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Swap with matching allowlist",
                "mode": "COMMUNITY",
                "is_swap": True,
                "allowed_thing_types": ["SWAP_THING"],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_thing_types"] == ["SWAP_THING"]

    def test_create_with_is_swap_rejects_non_matching_list(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Swap with wrong allowlist",
                "mode": "COMMUNITY",
                "is_swap": True,
                "allowed_thing_types": ["GIFT_THING"],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_is_share_accepts_matching_share_thing_list(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Share with matching allowlist",
                "mode": "COMMUNITY",
                "is_share": True,
                "allowed_thing_types": ["SHARE_THING"],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_with_is_share_rejects_non_matching_list(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Share with wrong allowlist",
                "mode": "COMMUNITY",
                "is_share": True,
                "allowed_thing_types": ["LEND_THING"],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_is_swap_empty_allowlist_succeeds(self, authenticated_client):
        """Empty allowlist is fine on a swap collection — the flag does the restricting."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Swap clean",
                "mode": "COMMUNITY",
                "is_swap": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestUpdateWithAllowedTypes:
    """PUT /api/v1/collections/{code}/ — narrowing is rejected when it would orphan."""

    def test_update_widens_list(self, authenticated_client, collection):
        response = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/",
            {"allowed_thing_types": ["GIFT_THING", "SELL_THING"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_narrows_orphaning_existing_things_fails(
        self, authenticated_client, user, collection
    ):
        """Cannot drop a type from the allowlist while things of that type sit in the collection."""
        thing = Thing.objects.create(code="THNG10", type="LEND_THING", owner=user, headline="Drill")
        collection.things.add(thing)
        # Restrict to GIFT only — the existing LEND_THING would be orphaned.
        response = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/",
            {"allowed_thing_types": ["GIFT_THING"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Error must name the offending type so the UI can guide the user.
        assert "LEND_THING" in str(response.data)


@pytest.mark.django_db
class TestAddThingRespectsAllowlist:
    """POST /api/v1/things/ with collection_code is gated by allowed_thing_types."""

    def test_add_thing_of_allowed_type(self, authenticated_client, user):
        coll = Collection.objects.create(
            code="COLL11",
            owner=user,
            headline="Sells only",
            allowed_thing_types=["SELL_THING"],
        )
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SELL_THING",
                "headline": "Bike",
                "fee": "50.00",
                "collection_code": coll.code,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_add_thing_of_disallowed_type_rejected(self, authenticated_client, user):
        coll = Collection.objects.create(
            code="COLL12",
            owner=user,
            headline="Sells only",
            allowed_thing_types=["SELL_THING"],
        )
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "Sweater",
                "collection_code": coll.code,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_empty_allowlist_means_no_restriction(self, authenticated_client, user):
        """When allowed_thing_types is empty, any type is accepted (subject to other rules)."""
        coll = Collection.objects.create(
            code="COLL13",
            owner=user,
            headline="Free for all",
            allowed_thing_types=[],
        )
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "Anything goes",
                "collection_code": coll.code,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
