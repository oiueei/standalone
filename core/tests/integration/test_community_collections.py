"""
Integration tests for community collection endpoints.
"""

import pytest

from core.models import Collection, Thing


@pytest.mark.django_db
class TestCommunityCollectionCreate:
    """Tests for creating community collections."""

    def test_create_proprietary_by_default(self, authenticated_client):
        """Creating a collection without mode should default to PROPRIETARY."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "My Collection"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["mode"] == "PROPRIETARY"

    def test_create_community_collection(self, authenticated_client):
        """Should create a community collection."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Mercadillo", "mode": "COMMUNITY"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["mode"] == "COMMUNITY"

    def test_mode_in_collection_detail(self, authenticated_client, collection):
        """Collection detail should include mode field."""
        response = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert response.status_code == 200
        assert response.json()["mode"] == "PROPRIETARY"


@pytest.mark.django_db
class TestCommunityCollectionUpdate:
    """Tests for updating collection mode."""

    def test_change_to_community(self, authenticated_client, collection):
        """Owner should be able to change mode to COMMUNITY."""
        response = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/",
            {"mode": "COMMUNITY"},
            format="json",
        )
        assert response.status_code == 200
        collection.refresh_from_db()
        assert collection.mode == "COMMUNITY"

    def test_change_to_proprietary(self, authenticated_client, user):
        """Owner should be able to change mode back to PROPRIETARY."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        response = authenticated_client.patch(
            f"/api/v1/collections/{coll.code}/",
            {"mode": "PROPRIETARY"},
            format="json",
        )
        assert response.status_code == 200
        coll.refresh_from_db()
        assert coll.mode == "PROPRIETARY"


@pytest.mark.django_db
class TestCommunityAddThing:
    """Tests for adding things to community collections."""

    def test_invitee_can_add_thing_community(self, authenticated_client2, user, user2):
        """Invited user should be able to add their own thing to a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        coll.invites.add(user2)
        thing = Thing.objects.create(owner=user2, headline="My Item", type="SELL_THING")

        response = authenticated_client2.post(
            f"/api/v1/collections/{coll.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 200
        assert coll.things.filter(code=thing.code).exists()

    def test_invitee_cannot_add_thing_proprietary(
        self, authenticated_client2, user, user2, collection
    ):
        """Invited user should NOT be able to add things to a proprietary collection."""
        collection.invites.add(user2)
        thing = Thing.objects.create(owner=user2, headline="My Item", type="SELL_THING")

        response = authenticated_client2.post(
            f"/api/v1/collections/{collection.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 403

    def test_invitee_cannot_add_others_thing_community(self, authenticated_client2, user, user2):
        """Invited user cannot add someone else's thing to a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        coll.invites.add(user2)
        thing = Thing.objects.create(owner=user, headline="Owner Item", type="GIFT_THING")

        response = authenticated_client2.post(
            f"/api/v1/collections/{coll.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 403

    def test_stranger_cannot_add_thing_community(self, authenticated_client2, user):
        """Non-invited user should NOT be able to add things to a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        thing = Thing.objects.create(owner=user, headline="Item", type="GIFT_THING")

        response = authenticated_client2.post(
            f"/api/v1/collections/{coll.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 403

    def test_create_thing_with_community_collection(self, authenticated_client2, user, user2):
        """Invited user should create a thing directly into a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        coll.invites.add(user2)

        response = authenticated_client2.post(
            "/api/v1/things/",
            {
                "type": "SELL_THING",
                "headline": "My Book",
                "fee": "5.00",
                "collection_code": coll.code,
            },
            format="json",
        )
        assert response.status_code == 201
        assert coll.things.filter(headline="My Book").exists()

    def test_create_thing_with_proprietary_collection_denied(
        self, authenticated_client2, user, user2, collection
    ):
        """Invited user should NOT create a thing into a proprietary collection."""
        collection.invites.add(user2)

        response = authenticated_client2.post(
            "/api/v1/things/",
            {
                "type": "GIFT_THING",
                "headline": "My Gift",
                "collection_code": collection.code,
            },
            format="json",
        )
        # Not permitted to add to someone else's proprietary collection → 403.
        assert response.status_code == 403

    def test_create_thing_with_unknown_collection_is_404(self, authenticated_client):
        """A collection_code that resolves to nothing → 404, not a generic 400."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {"type": "GIFT_THING", "headline": "My Gift", "collection_code": "NOPE99"},
            format="json",
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestCommunityRemoveThing:
    """Tests for removing things from community collections."""

    def test_owner_can_remove_any_thing(self, authenticated_client, user, user2):
        """Collection owner can remove any thing from a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        thing = Thing.objects.create(owner=user2, headline="Guest Item", type="SELL_THING")
        coll.things.add(thing)

        response = authenticated_client.post(
            f"/api/v1/collections/{coll.code}/remove-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 200
        assert not coll.things.filter(code=thing.code).exists()

    def test_thing_owner_can_remove_own_thing_community(self, authenticated_client2, user, user2):
        """Thing owner can remove their own thing from a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        coll.invites.add(user2)
        thing = Thing.objects.create(owner=user2, headline="My Item", type="SELL_THING")
        coll.things.add(thing)

        response = authenticated_client2.post(
            f"/api/v1/collections/{coll.code}/remove-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 200
        assert not coll.things.filter(code=thing.code).exists()

    def test_invitee_cannot_remove_others_thing_community(self, authenticated_client2, user, user2):
        """Invitee cannot remove someone else's thing from a community collection."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        coll.invites.add(user2)
        thing = Thing.objects.create(owner=user, headline="Owner Item", type="GIFT_THING")
        coll.things.add(thing)

        response = authenticated_client2.post(
            f"/api/v1/collections/{coll.code}/remove-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 403
        # remove_thing's authz is the inline check, not IsCollectionOwner (which is
        # inert here — the I3 footgun). Lock the inline {"error": ...} body so a
        # naive switch to the permission class (which returns {"detail": ...} and
        # would also wrongly deny community thing-owners) is caught.
        assert response.json() == {"error": "You do not have permission to remove this thing"}

    def test_invitee_cannot_remove_thing_proprietary(
        self, authenticated_client2, user, user2, collection, thing
    ):
        """Invitee cannot remove things from a proprietary collection."""
        collection.invites.add(user2)

        response = authenticated_client2.post(
            f"/api/v1/collections/{collection.code}/remove-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == 403
