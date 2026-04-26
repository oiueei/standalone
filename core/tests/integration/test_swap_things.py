"""
Integration tests for SWAP_THING item swapping feature.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.transfer import ThingTransfer
from core.services.booking_service import accept_booking, reject_booking


@pytest.fixture
def swap_collection(db, user):
    """Create a COMMUNITY swap collection owned by user."""
    return Collection.objects.create(
        code="SWAP01",
        owner=user,
        headline="Swap Collection",
        mode="COMMUNITY",
        is_swap=True,
    )


@pytest.fixture
def owner_swap_thing(db, user, swap_collection):
    """Create a SWAP_THING owned by user in the swap collection."""
    t = Thing.objects.create(
        code="SWTH01",
        type="SWAP_THING",
        owner=user,
        headline="Owner Swap Item",
    )
    swap_collection.things.add(t)
    return t


@pytest.fixture
def guest_swap_thing(db, user2, swap_collection):
    """Create a SWAP_THING owned by user2 in the swap collection."""
    t = Thing.objects.create(
        code="SWTH02",
        type="SWAP_THING",
        owner=user2,
        headline="Guest Swap Item",
    )
    swap_collection.things.add(t)
    return t


@pytest.fixture
def guest_swap_thing2(db, user2, swap_collection):
    """Create a second SWAP_THING owned by user2."""
    t = Thing.objects.create(
        code="SWTH03",
        type="SWAP_THING",
        owner=user2,
        headline="Guest Swap Item 2",
    )
    swap_collection.things.add(t)
    return t


@pytest.fixture
def auth_client_user(api_client, user):
    """Authenticated client for user (collection owner)."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def auth_client_user2(user2):
    """Authenticated client for user2 (guest)."""
    client = APIClient()
    refresh = RefreshToken.for_user(user2)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


# --- Collection-level tests ---


class TestSwapCollectionCreation:
    def test_create_swap_collection(self, auth_client_user):
        res = auth_client_user.post(
            "/api/v1/collections/",
            {"headline": "My Swap", "mode": "COMMUNITY", "is_swap": True},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["is_swap"] is True

    def test_swap_requires_community_mode(self, auth_client_user):
        """is_swap with PROPRIETARY mode should be rejected."""
        res = auth_client_user.post(
            "/api/v1/collections/",
            {"headline": "Prop Swap", "mode": "PROPRIETARY", "is_swap": True},
            format="json",
        )
        assert res.status_code == 400


# --- Thing type restriction tests ---


class TestSwapThingRestrictions:
    def test_create_swap_thing_in_swap_collection(self, auth_client_user, swap_collection):
        res = auth_client_user.post(
            "/api/v1/things/",
            {
                "headline": "Swap It",
                "type": "SWAP_THING",
                "collection_code": swap_collection.code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["type"] == "SWAP_THING"

    def test_cannot_create_non_swap_in_swap_collection(self, auth_client_user, swap_collection):
        res = auth_client_user.post(
            "/api/v1/things/",
            {
                "headline": "Gift In Swap",
                "type": "GIFT_THING",
                "collection_code": swap_collection.code,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_cannot_create_swap_in_non_swap_collection(self, auth_client_user):
        coll = Collection.objects.create(
            code="NOSWP1",
            owner=User.objects.get(code="TEST01"),
            headline="Normal Collection",
            mode="COMMUNITY",
        )
        res = auth_client_user.post(
            "/api/v1/things/",
            {
                "headline": "Swap Fail",
                "type": "SWAP_THING",
                "collection_code": coll.code,
            },
            format="json",
        )
        assert res.status_code == 400


# --- Swap request tests ---


class TestSwapRequest:
    def test_swap_request_success(
        self,
        auth_client_user2,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user2,
    ):
        swap_collection.invites.add(user2)
        res = auth_client_user2.post(
            f"/api/v1/things/{owner_swap_thing.code}/request/",
            {"offered_thing_codes": [guest_swap_thing.code]},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["message"] == "Swap request sent"
        assert guest_swap_thing.code in res.data["offered_thing_codes"]

    def test_swap_request_multiple_offerings(
        self,
        auth_client_user2,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        guest_swap_thing2,
        user2,
    ):
        swap_collection.invites.add(user2)
        res = auth_client_user2.post(
            f"/api/v1/things/{owner_swap_thing.code}/request/",
            {
                "offered_thing_codes": [
                    guest_swap_thing.code,
                    guest_swap_thing2.code,
                ]
            },
            format="json",
        )
        assert res.status_code == 200
        assert len(res.data["offered_thing_codes"]) == 2

    def test_swap_request_no_offerings(
        self, auth_client_user2, swap_collection, owner_swap_thing, user2
    ):
        swap_collection.invites.add(user2)
        res = auth_client_user2.post(
            f"/api/v1/things/{owner_swap_thing.code}/request/",
            {"offered_thing_codes": []},
            format="json",
        )
        assert res.status_code == 400

    def test_swap_request_unowned_thing(
        self,
        auth_client_user2,
        swap_collection,
        owner_swap_thing,
        user2,
    ):
        """Cannot offer a thing you don't own."""
        swap_collection.invites.add(user2)
        res = auth_client_user2.post(
            f"/api/v1/things/{owner_swap_thing.code}/request/",
            {"offered_thing_codes": [owner_swap_thing.code]},
            format="json",
        )
        assert res.status_code == 400

    def test_swap_request_inactive_thing(
        self,
        auth_client_user2,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user2,
    ):
        """Cannot offer an inactive thing."""
        swap_collection.invites.add(user2)
        guest_swap_thing.status = "INACTIVE"
        guest_swap_thing.save()
        res = auth_client_user2.post(
            f"/api/v1/things/{owner_swap_thing.code}/request/",
            {"offered_thing_codes": [guest_swap_thing.code]},
            format="json",
        )
        assert res.status_code == 400

    def test_swap_request_wrong_collection(
        self, auth_client_user2, swap_collection, owner_swap_thing, user2
    ):
        """Cannot offer a thing from a different collection."""
        swap_collection.invites.add(user2)
        other_coll = Collection.objects.create(
            code="OTHER1",
            owner=User.objects.get(code="TEST01"),
            headline="Other Swap",
            mode="COMMUNITY",
            is_swap=True,
        )
        other_thing = Thing.objects.create(
            code="OTHR01",
            type="SWAP_THING",
            owner=user2,
            headline="Other Thing",
        )
        other_coll.things.add(other_thing)
        res = auth_client_user2.post(
            f"/api/v1/things/{owner_swap_thing.code}/request/",
            {"offered_thing_codes": [other_thing.code]},
            format="json",
        )
        assert res.status_code == 400


# --- Swap acceptance tests ---


class TestSwapAcceptance:
    def test_accept_swap_transfers_ownership(
        self,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user,
        user2,
    ):
        """Accepting a swap transfers ownership in both directions."""
        swap_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=owner_swap_thing,
            thing_type="SWAP_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        booking.offered_things.set([guest_swap_thing])

        accept_booking(booking)

        owner_swap_thing.refresh_from_db()
        guest_swap_thing.refresh_from_db()
        assert owner_swap_thing.owner == user2
        assert guest_swap_thing.owner == user

    def test_accept_swap_creates_transfers(
        self,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user,
        user2,
    ):
        """Accepting creates ThingTransfer records for all things involved."""
        swap_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=owner_swap_thing,
            thing_type="SWAP_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        booking.offered_things.set([guest_swap_thing])

        accept_booking(booking)

        # Transfer for requested thing
        assert ThingTransfer.objects.filter(
            thing=owner_swap_thing, from_user=user, to_user=user2
        ).exists()
        # Transfer for offered thing
        assert ThingTransfer.objects.filter(
            thing=guest_swap_thing, from_user=user2, to_user=user
        ).exists()

    def test_accept_swap_things_stay_active(
        self,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user,
        user2,
    ):
        """All things remain ACTIVE after a swap."""
        swap_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=owner_swap_thing,
            thing_type="SWAP_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        booking.offered_things.set([guest_swap_thing])

        accept_booking(booking)

        owner_swap_thing.refresh_from_db()
        guest_swap_thing.refresh_from_db()
        assert owner_swap_thing.status == "ACTIVE"
        assert guest_swap_thing.status == "ACTIVE"

    def test_accept_swap_multiple_offerings(
        self,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        guest_swap_thing2,
        user,
        user2,
    ):
        """All offered things transfer to the original owner."""
        swap_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=owner_swap_thing,
            thing_type="SWAP_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        booking.offered_things.set([guest_swap_thing, guest_swap_thing2])

        accept_booking(booking)

        owner_swap_thing.refresh_from_db()
        guest_swap_thing.refresh_from_db()
        guest_swap_thing2.refresh_from_db()
        assert owner_swap_thing.owner == user2
        assert guest_swap_thing.owner == user
        assert guest_swap_thing2.owner == user
        assert (
            ThingTransfer.objects.filter(
                thing__in=[owner_swap_thing, guest_swap_thing, guest_swap_thing2]
            ).count()
            == 3
        )  # 1 requested + 2 offered

    def test_reject_swap_no_changes(
        self,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user,
        user2,
    ):
        """Rejecting a swap leaves ownership unchanged."""
        swap_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=owner_swap_thing,
            thing_type="SWAP_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        booking.offered_things.set([guest_swap_thing])

        reject_booking(booking)

        owner_swap_thing.refresh_from_db()
        guest_swap_thing.refresh_from_db()
        assert owner_swap_thing.owner == user
        assert guest_swap_thing.owner == user2
        assert (
            ThingTransfer.objects.filter(thing__in=[owner_swap_thing, guest_swap_thing]).count()
            == 0
        )


# --- Serializer tests ---


class TestSwapSerializer:
    def test_collection_serializer_includes_is_swap(self, auth_client_user, swap_collection):
        res = auth_client_user.get(f"/api/v1/collections/{swap_collection.code}/")
        assert res.status_code == 200
        assert res.data["is_swap"] is True

    def test_booking_serializer_includes_offered_things(
        self,
        auth_client_user,
        swap_collection,
        owner_swap_thing,
        guest_swap_thing,
        user,
        user2,
    ):
        swap_collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=owner_swap_thing,
            thing_type="SWAP_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        booking.offered_things.set([guest_swap_thing])

        res = auth_client_user.get(f"/api/v1/things/{owner_swap_thing.code}/calendar/")
        assert res.status_code == 200
        assert len(res.data) == 1
        assert guest_swap_thing.code in res.data[0]["offered_thing_codes"]
        assert "Guest Swap Item" in res.data[0]["offered_thing_headlines"]
