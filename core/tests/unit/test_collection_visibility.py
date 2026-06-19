"""Unit tests for per-collection PUBLIC/PRIVATE visibility (#5, phase 1).

Cover the model authorisation helpers (``Collection.can_view`` / ``Thing.can_view``
made anonymous-safe with a PUBLIC branch) and the create serializer's
default-by-mode behaviour. The view-level anonymous read and the auto-join flow
are exercised in their own integration suites.
"""

import pytest

from core.models import Collection, Thing
from core.serializers import CollectionCreateSerializer
from core.tests.factories import CollectionFactory, ThingFactory, UserFactory

pytestmark = pytest.mark.django_db


# --- Collection.is_public / can_view -------------------------------------


def test_is_public_reflects_visibility():
    assert CollectionFactory(visibility=Collection.Visibility.PUBLIC).is_public() is True
    assert CollectionFactory(visibility=Collection.Visibility.PRIVATE).is_public() is False


def test_owner_can_view_own_private_and_inactive_collection():
    owner = UserFactory()
    private = CollectionFactory(owner=owner, visibility=Collection.Visibility.PRIVATE)
    inactive = CollectionFactory(
        owner=owner,
        visibility=Collection.Visibility.PRIVATE,
        status=Collection.Status.INACTIVE,
    )
    assert private.can_view(owner.code) is True
    assert inactive.can_view(owner.code) is True


def test_anonymous_can_view_public_active_collection():
    public = CollectionFactory(visibility=Collection.Visibility.PUBLIC)
    # An anonymous visitor is passed user_code=None.
    assert public.can_view(None) is True


def test_anonymous_cannot_view_private_collection():
    private = CollectionFactory(visibility=Collection.Visibility.PRIVATE)
    assert private.can_view(None) is False


def test_anonymous_cannot_view_public_but_inactive_collection():
    hidden = CollectionFactory(
        visibility=Collection.Visibility.PUBLIC,
        status=Collection.Status.INACTIVE,
    )
    assert hidden.can_view(None) is False


def test_invited_member_can_view_private_collection_but_stranger_cannot():
    member = UserFactory()
    stranger = UserFactory()
    private = CollectionFactory(visibility=Collection.Visibility.PRIVATE)
    private.invites.add(member)
    assert private.can_view(member.code) is True
    assert private.can_view(stranger.code) is False


def test_stranger_can_view_public_collection():
    stranger = UserFactory()
    public = CollectionFactory(visibility=Collection.Visibility.PUBLIC)
    assert public.can_view(stranger.code) is True


# --- Thing.can_view through a PUBLIC collection ---------------------------


def test_anonymous_can_view_active_thing_in_public_collection():
    public = CollectionFactory(visibility=Collection.Visibility.PUBLIC)
    thing = ThingFactory(status=Thing.Status.ACTIVE)
    public.things.add(thing)
    assert thing.can_view(None) is True


def test_anonymous_cannot_view_thing_in_private_collection():
    private = CollectionFactory(visibility=Collection.Visibility.PRIVATE)
    thing = ThingFactory(status=Thing.Status.ACTIVE)
    private.things.add(thing)
    assert thing.can_view(None) is False


def test_anonymous_cannot_view_inactive_thing_even_in_public_collection():
    public = CollectionFactory(visibility=Collection.Visibility.PUBLIC)
    thing = ThingFactory(status=Thing.Status.INACTIVE)
    public.things.add(thing)
    assert thing.can_view(None) is False


def test_anonymous_cannot_view_thing_in_public_but_inactive_collection():
    hidden = CollectionFactory(
        visibility=Collection.Visibility.PUBLIC,
        status=Collection.Status.INACTIVE,
    )
    thing = ThingFactory(status=Thing.Status.ACTIVE)
    hidden.things.add(thing)
    assert thing.can_view(None) is False


def test_invited_member_can_view_thing_in_private_collection():
    member = UserFactory()
    private = CollectionFactory(visibility=Collection.Visibility.PRIVATE)
    private.invites.add(member)
    thing = ThingFactory(status=Thing.Status.ACTIVE)
    private.things.add(thing)
    assert thing.can_view(member.code) is True


# --- CollectionCreateSerializer default-by-mode ---------------------------


def _validated(data):
    serializer = CollectionCreateSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    return serializer.validated_data


def test_community_collection_defaults_to_public():
    data = _validated({"headline": "Neighbourhood share", "mode": "COMMUNITY"})
    assert data["visibility"] == Collection.Visibility.PUBLIC


def test_proprietary_collection_defaults_to_private():
    data = _validated({"headline": "My shelf"})  # mode defaults to PROPRIETARY
    assert data["visibility"] == Collection.Visibility.PRIVATE


def test_explicit_visibility_overrides_the_mode_default():
    # A proprietary owner may open their collection to the public.
    data = _validated({"headline": "Open shelf", "mode": "PROPRIETARY", "visibility": "PUBLIC"})
    assert data["visibility"] == Collection.Visibility.PUBLIC
    # A community owner may close theirs.
    data = _validated({"headline": "Closed group", "mode": "COMMUNITY", "visibility": "PRIVATE"})
    assert data["visibility"] == Collection.Visibility.PRIVATE
