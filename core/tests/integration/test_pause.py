"""
Integration tests for the Collection pause feature.

Covers:
- Collection.is_paused property (True when pause_message is non-empty, False when empty)
- PATCH /api/v1/collections/{code}/ sets and clears pause_message
- POST /api/v1/things/{code}/request/ is blocked when all active collections are paused
- POST /api/v1/things/{code}/request/ succeeds when at least one active collection is not paused
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User


def _make_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def pause_users(db):
    owner = User.objects.create(code="POWN01", email="powner@test.com", name="Pause Owner")
    member = User.objects.create(code="PMEM01", email="pmember@test.com", name="Pause Member")
    return owner, member


@pytest.fixture
def pause_collection(db, pause_users):
    owner, member = pause_users
    collection = Collection.objects.create(
        code="PCOL01", owner=owner, headline="Pauseable Collection", status="ACTIVE"
    )
    collection.invites.add(member)
    return collection


@pytest.fixture
def pause_thing(db, pause_users, pause_collection):
    owner, _ = pause_users
    thing = Thing.objects.create(
        code="PTHG01", owner=owner, headline="Pauseable Thing", type="GIFT_THING"
    )
    pause_collection.things.add(thing)
    return thing


# ---------------------------------------------------------------------------
# Model property tests
# ---------------------------------------------------------------------------


def test_is_paused_false_when_pause_message_empty(db, pause_collection):
    assert pause_collection.pause_message == ""
    assert pause_collection.is_paused is False


def test_is_paused_true_when_pause_message_set(db, pause_collection):
    pause_collection.pause_message = "Taking a break until next week."
    pause_collection.save()
    pause_collection.refresh_from_db()
    assert pause_collection.is_paused is True


def test_is_paused_false_after_clearing_pause_message(db, pause_collection):
    pause_collection.pause_message = "On holiday."
    pause_collection.save()
    pause_collection.pause_message = ""
    pause_collection.save()
    pause_collection.refresh_from_db()
    assert pause_collection.is_paused is False


# ---------------------------------------------------------------------------
# API: setting / clearing pause_message via PATCH
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_set_pause_message(pause_users, pause_collection):
    owner, _ = pause_users
    client = _make_client(owner)

    resp = client.patch(
        f"/api/v1/collections/{pause_collection.code}/",
        {"pause_message": "Closed for maintenance."},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK
    pause_collection.refresh_from_db()
    assert pause_collection.pause_message == "Closed for maintenance."
    assert pause_collection.is_paused is True


@pytest.mark.django_db
def test_owner_can_clear_pause_message_to_resume(pause_users, pause_collection):
    pause_collection.pause_message = "On break."
    pause_collection.save()
    owner, _ = pause_users
    client = _make_client(owner)

    resp = client.patch(
        f"/api/v1/collections/{pause_collection.code}/",
        {"pause_message": ""},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK
    pause_collection.refresh_from_db()
    assert pause_collection.pause_message == ""
    assert pause_collection.is_paused is False


@pytest.mark.django_db
def test_non_owner_cannot_set_pause_message(pause_users, pause_collection):
    _, member = pause_users
    client = _make_client(member)

    resp = client.patch(
        f"/api/v1/collections/{pause_collection.code}/",
        {"pause_message": "Trying to pause someone else's collection."},
        format="json",
    )

    assert resp.status_code == status.HTTP_403_FORBIDDEN
    pause_collection.refresh_from_db()
    assert pause_collection.pause_message == ""


# ---------------------------------------------------------------------------
# Reservation enforcement: blocked when paused
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_request_blocked_when_only_collection_is_paused(pause_users, pause_thing, pause_collection):
    _, member = pause_users
    pause_collection.pause_message = "Not available right now."
    pause_collection.save()
    client = _make_client(member)

    with patch("core.services.email_service.send_booking_request_email"):
        resp = client.post(f"/api/v1/things/{pause_thing.code}/request/")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.data["error"] == "This collection is currently paused"


@pytest.mark.django_db
def test_request_allowed_when_collection_is_not_paused(pause_users, pause_thing):
    _, member = pause_users
    client = _make_client(member)

    with patch("core.services.email_service.send_booking_request_email"):
        resp = client.post(f"/api/v1/things/{pause_thing.code}/request/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["message"] == "Booking request sent"


@pytest.mark.django_db
def test_request_allowed_when_one_of_two_active_collections_is_not_paused(
    db, pause_users, pause_thing, pause_collection
):
    """If the thing is in two active collections and only one is paused, holds must still work."""
    owner, member = pause_users
    pause_collection.pause_message = "On break."
    pause_collection.save()

    # Second active collection — not paused
    second_collection = Collection.objects.create(
        code="PCOL02", owner=owner, headline="Second Collection", status="ACTIVE"
    )
    second_collection.things.add(pause_thing)
    second_collection.invites.add(member)

    client = _make_client(member)
    with patch("core.services.email_service.send_booking_request_email"):
        resp = client.post(f"/api/v1/things/{pause_thing.code}/request/")

    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_request_blocked_when_all_active_collections_are_paused(
    db, pause_users, pause_thing, pause_collection
):
    """If the thing is in two active collections and both are paused, holds must be blocked."""
    owner, member = pause_users
    pause_collection.pause_message = "On break."
    pause_collection.save()

    second_collection = Collection.objects.create(
        code="PCOL02", owner=owner, headline="Second Collection", status="ACTIVE"
    )
    second_collection.things.add(pause_thing)
    second_collection.invites.add(member)
    second_collection.pause_message = "Also on break."
    second_collection.save()

    client = _make_client(member)
    with patch("core.services.email_service.send_booking_request_email"):
        resp = client.post(f"/api/v1/things/{pause_thing.code}/request/")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.data["error"] == "This collection is currently paused"
