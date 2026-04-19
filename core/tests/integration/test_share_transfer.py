"""
Integration tests for SHARE_THING ownership transfer feature.
"""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.transfer import ThingTransfer
from core.services.booking_service import accept_booking, reject_booking


@pytest.fixture
def community_collection(db, user):
    """Create a COMMUNITY collection owned by user."""
    coll = Collection.objects.create(
        code="COMM01",
        owner=user,
        headline="Community Collection",
        mode="COMMUNITY",
    )
    return coll


@pytest.fixture
def share_thing(db, user, community_collection):
    """Create a SHARE_THING in a community collection."""
    t = Thing.objects.create(
        code="SHARE1",
        type="SHARE_THING",
        owner=user,
        headline="Shared Book",
    )
    community_collection.things.add(t)
    return t


@pytest.fixture
def user3(db):
    """Create a third test user."""
    return User.objects.create(
        code="TEST03",
        email="test3@example.com",
        name="Test User 3",
    )


@pytest.fixture
def authenticated_client3(user3):
    """Return an authenticated API client for user3."""
    client = APIClient()
    refresh = RefreshToken.for_user(user3)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
class TestShareThingOwnershipTransfer:
    """Tests for SHARE_THING ownership transfer on booking acceptance."""

    def test_accept_share_booking_transfers_ownership(
        self, user, user2, share_thing, community_collection
    ):
        """Accepting a SHARE_THING booking should transfer ownership to the requester."""
        community_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )

        accept_booking(booking)

        share_thing.refresh_from_db()
        assert share_thing.owner_id == user2.code
        assert share_thing.status == "ACTIVE"

    def test_accept_share_booking_creates_transfer(
        self, user, user2, share_thing, community_collection
    ):
        """Accepting a SHARE_THING booking should create a ThingTransfer record."""
        community_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )

        accept_booking(booking)

        transfer = ThingTransfer.objects.get(thing=share_thing)
        assert transfer.from_user_id == user.code
        assert transfer.to_user_id == user2.code

    def test_new_owner_can_approve_next_booking(
        self, user, user2, user3, share_thing, community_collection
    ):
        """After transfer, new owner should be able to approve the next booking."""
        community_collection.invites.add(user2)
        community_collection.invites.add(user3)

        # First transfer: user -> user2
        booking1 = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )
        accept_booking(booking1)
        share_thing.refresh_from_db()
        assert share_thing.owner_id == user2.code

        # Second transfer: user2 -> user3
        booking2 = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user3,
            requester_email=user3.email,
            owner_code=user2,
            start_date=date.today() + timedelta(days=14),
            end_date=date.today() + timedelta(days=21),
        )
        accept_booking(booking2)
        share_thing.refresh_from_db()
        assert share_thing.owner_id == user3.code

    def test_reject_share_booking_keeps_ownership(
        self, user, user2, share_thing, community_collection
    ):
        """Rejecting a SHARE_THING booking should NOT transfer ownership."""
        community_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )

        reject_booking(booking)

        share_thing.refresh_from_db()
        assert share_thing.owner_id == user.code
        assert share_thing.status == "ACTIVE"


@pytest.mark.django_db
class TestShareThingHideRestriction:
    """Tests for hide restrictions on SHARE_THING after transfer."""

    def test_original_owner_can_hide_before_transfer(self, authenticated_client, share_thing):
        """Before any transfer, the thing owner can hide it."""
        response = authenticated_client.post(
            f"/api/v1/things/{share_thing.code}/hide/", format="json"
        )
        assert response.status_code == 200
        share_thing.refresh_from_db()
        assert share_thing.status == "INACTIVE"

    def test_collection_owner_can_hide_after_transfer(
        self, authenticated_client, user, user2, share_thing, community_collection
    ):
        """After transfer, the collection owner can hide the thing."""
        community_collection.invites.add(user2)
        # Transfer ownership to user2
        booking = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )
        accept_booking(booking)

        # user (collection owner) should still be able to hide
        response = authenticated_client.post(
            f"/api/v1/things/{share_thing.code}/hide/", format="json"
        )
        assert response.status_code == 200

    def test_thing_owner_cannot_hide_after_transfer(
        self, authenticated_client2, user, user2, share_thing, community_collection
    ):
        """After transfer, the new thing owner (non-collection-owner) cannot hide."""
        community_collection.invites.add(user2)
        # Transfer ownership to user2
        booking = BookingPeriod.objects.create(
            thing_code=share_thing,
            thing_type="SHARE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )
        accept_booking(booking)

        # user2 (new thing owner, but NOT collection owner) should get 403
        response = authenticated_client2.post(
            f"/api/v1/things/{share_thing.code}/hide/", format="json"
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestShareThingCommunityRestriction:
    """Tests for SHARE_THING being restricted to COMMUNITY collections."""

    def test_cannot_create_share_thing_in_proprietary_collection(
        self, authenticated_client, collection
    ):
        """SHARE_THING should not be creatable in a PROPRIETARY collection."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SHARE_THING",
                "headline": "Shared Item",
                "thumbnail": "oiueei/things/test123",
                "collection_code": collection.code,
            },
            format="json",
        )
        assert response.status_code == 400
        assert "community" in response.json()["error"].lower()

    def test_can_create_share_thing_in_community_collection(
        self, authenticated_client, community_collection
    ):
        """SHARE_THING should be creatable in a COMMUNITY collection."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SHARE_THING",
                "headline": "Shared Item",
                "thumbnail": "oiueei/things/test123",
                "collection_code": community_collection.code,
            },
            format="json",
        )
        assert response.status_code == 201

    def test_cannot_create_share_thing_without_collection(self, authenticated_client):
        """SHARE_THING should require a COMMUNITY collection."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "SHARE_THING",
                "headline": "Shared Item",
                "thumbnail": "oiueei/things/test123",
            },
            format="json",
        )
        assert response.status_code == 400
        assert "community" in response.json()["error"].lower()


@pytest.mark.django_db
class TestShareThingSerializer:
    """Tests for collection_owner field in ThingSerializer."""

    def test_thing_serializer_includes_collection_owner(
        self, authenticated_client, share_thing, community_collection, user
    ):
        """ThingSerializer should include collection_owner field."""
        response = authenticated_client.get(f"/api/v1/things/{share_thing.code}/")
        assert response.status_code == 200
        data = response.json()
        assert data["collection_owner"] == user.code
