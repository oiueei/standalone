"""
Unit tests for community collection mode.
"""

import pytest

from core.models import Collection


@pytest.mark.django_db
class TestCollectionMode:
    """Tests for Collection.mode field and helpers."""

    def test_default_mode_is_proprietary(self, user):
        """New collections should default to PROPRIETARY mode."""
        coll = Collection.objects.create(owner=user, headline="Test")
        assert coll.mode == "PROPRIETARY"

    def test_create_community_collection(self, user):
        """Should create a collection with COMMUNITY mode."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        assert coll.mode == "COMMUNITY"
        assert coll.is_community()

    def test_is_community_false_for_proprietary(self, collection):
        """Proprietary collections should return False."""
        assert not collection.is_community()

    def test_can_add_thing_owner_proprietary(self, user, collection):
        """Owner can always add things to proprietary collections."""
        assert collection.can_add_thing(user.code)

    def test_can_add_thing_invitee_proprietary(self, user, user2, collection):
        """Invitees cannot add things to proprietary collections."""
        collection.invites.add(user2)
        assert not collection.can_add_thing(user2.code)

    def test_can_add_thing_owner_community(self, user):
        """Owner can add things to community collections."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        assert coll.can_add_thing(user.code)

    def test_can_add_thing_invitee_community(self, user, user2):
        """Invitees can add things to community collections."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        coll.invites.add(user2)
        assert coll.can_add_thing(user2.code)

    def test_can_add_thing_stranger_community(self, user, user2):
        """Non-invited users cannot add things to community collections."""
        coll = Collection.objects.create(owner=user, headline="Market", mode="COMMUNITY")
        assert not coll.can_add_thing(user2.code)
