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
        for community_type in ("WISH_THING", "SHARE_THING", "ASSET_THING", "SWAP_THING"):
            response = authenticated_client.post(
                "/api/v1/collections/",
                {"headline": "Bad", "allowed_thing_types": ["GIFT_THING", community_type]},
                format="json",
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST, community_type

    def test_create_album_must_be_exactly_gift(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Album",
                "is_minimalist": True,
                "allowed_thing_types": ["GIFT_THING", "SELL_THING"],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_album_with_only_gift_succeeds(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Album",
                "is_minimalist": True,
                "allowed_thing_types": ["GIFT_THING"],
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
