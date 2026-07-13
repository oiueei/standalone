"""
Integration tests for the per-collection inbox and the request notification's lifecycle.

Two user-reported problems (2026-07-13) shape these tests:

1. A booking-request notification only showed on Home, so an owner sitting on their
   collection's page never saw it. The payload now carries the collection code and
   ``GET /api/v1/inbox/?collection=<code>`` filters by it.
2. Deciding a request (from the email link or the web button) left the notification
   in the inbox, still asking to be decided. Accept, reject, auto-decline and
   requester-cancel now all clear it.
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, BookingPeriod, Collection, Thing, User
from core.models.notification import InAppNotification


def _client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def owner(db):
    return User.objects.create(code="IOWN01", email="ioowner@test.com", name="Owner")


@pytest.fixture
def requester(db):
    return User.objects.create(code="IREQ01", email="ioreq@test.com", name="Requester")


@pytest.fixture
def gift_in_collection(db, owner, requester):
    """A GIFT thing in an ACTIVE collection the requester belongs to."""
    thing = Thing.objects.create(code="IOTH01", owner=owner, headline="A lamp", type="GIFT_THING")
    collection = Collection.objects.create(code="IOCO01", owner=owner, headline="Home stuff")
    collection.things.add(thing)
    collection.invites.add(requester)
    return thing, collection


@pytest.fixture
def quiet_emails():
    """Silence the request/decision fan-out — these tests are about the inbox."""
    with (
        patch("core.services.email_service.send_booking_request_email"),
        patch("core.services.email_service.send_booking_confirmation_email"),
        patch("core.services.email_service.send_booking_decision_email"),
        patch("core.services.email_service.send_booking_unavailable_email"),
        patch("core.services.email_service.send_swap_request_email"),
        patch("core.services.email_service.send_swap_confirmation_email"),
    ):
        yield


def _request_notification(owner):
    return InAppNotification.objects.filter(
        user=owner,
        type__in=[
            InAppNotification.Type.BOOKING_REQUESTED,
            InAppNotification.Type.SWAP_REQUESTED,
        ],
    )


# ── The payload carries the codes ─────────────────────────────────────────


@pytest.mark.django_db
def test_request_notification_carries_booking_thing_and_collection_codes(
    owner, requester, gift_in_collection, quiet_emails
):
    thing, collection = gift_in_collection

    resp = _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")

    assert resp.status_code == status.HTTP_201_CREATED
    notif = _request_notification(owner).get()
    assert notif.payload["booking_code"] == resp.data["booking_code"]
    assert notif.payload["thing_code"] == thing.code
    assert notif.payload["collection_code"] == collection.code


@pytest.mark.django_db
def test_request_notification_uses_the_collection_it_was_made_through(
    owner, requester, gift_in_collection, quiet_emails
):
    """A thing can live in several collections — the one the requester was looking at
    wins over any server-side approximation."""
    thing, first = gift_in_collection
    second = Collection.objects.create(code="IOCO02", owner=owner, headline="Garage")
    second.things.add(thing)
    second.invites.add(requester)

    resp = _client(requester).post(
        f"/api/v1/things/{thing.code}/request/",
        {"collection_code": second.code},
        format="json",
    )

    assert resp.status_code == status.HTTP_201_CREATED
    assert _request_notification(owner).get().payload["collection_code"] == second.code


@pytest.mark.django_db
def test_swap_request_notification_carries_the_codes(db, owner, requester, quiet_emails):
    collection = Collection.objects.create(
        code="IOSW01", owner=owner, headline="Swaps", mode="COMMUNITY", is_swap=True
    )
    wanted = Thing.objects.create(
        code="IOSW02", owner=owner, headline="Owner item", type="SWAP_THING"
    )
    offered = Thing.objects.create(
        code="IOSW03", owner=requester, headline="Guest item", type="SWAP_THING"
    )
    collection.things.add(wanted, offered)
    collection.invites.add(requester)

    resp = _client(requester).post(
        f"/api/v1/things/{wanted.code}/request/",
        {"offered_thing_codes": [offered.code]},
        format="json",
    )

    assert resp.status_code == status.HTTP_201_CREATED
    notif = _request_notification(owner).get()
    assert notif.type == InAppNotification.Type.SWAP_REQUESTED
    assert notif.payload["booking_code"] == resp.data["booking_code"]
    assert notif.payload["thing_code"] == wanted.code
    assert notif.payload["collection_code"] == collection.code


@pytest.mark.django_db
def test_decision_notification_deep_links_the_thing_and_collection(
    owner, requester, gift_in_collection, quiet_emails
):
    thing, collection = gift_in_collection
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    booking = BookingPeriod.objects.get(thing_code=thing)

    _client(owner).post(f"/api/v1/bookings/{booking.code}/accept/")

    notif = InAppNotification.objects.get(
        user=requester, type=InAppNotification.Type.BOOKING_ACCEPTED
    )
    assert notif.payload["thing_code"] == thing.code
    assert notif.payload["collection_code"] == collection.code


# ── The decision clears the owner's notification ──────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["accept", "reject"])
def test_deciding_via_the_api_clears_the_owner_notification(
    owner, requester, gift_in_collection, quiet_emails, action
):
    thing, _ = gift_in_collection
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    booking = BookingPeriod.objects.get(thing_code=thing)
    assert _request_notification(owner).exists()

    resp = _client(owner).post(f"/api/v1/bookings/{booking.code}/{action}/")

    assert resp.status_code == status.HTTP_200_OK
    assert not _request_notification(owner).exists()


@pytest.mark.django_db
def test_deciding_from_the_email_link_clears_the_owner_notification(
    owner, requester, gift_in_collection, quiet_emails
):
    """The RSVP path is how CA hit the bug: accepted by email, notification stayed."""
    thing, _ = gift_in_collection
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    booking = BookingPeriod.objects.get(thing_code=thing)
    rsvp = RSVP.objects.get(target_code=booking.code, action=RSVP.Action.BOOKING_ACCEPT)

    resp = APIClient().post(f"/api/v1/auth/verify/{rsvp.token}/")

    assert resp.status_code == status.HTTP_200_OK
    assert not _request_notification(owner).exists()


@pytest.mark.django_db
def test_requester_cancelling_clears_the_owner_notification(
    owner, requester, gift_in_collection, quiet_emails
):
    thing, _ = gift_in_collection
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    booking = BookingPeriod.objects.get(thing_code=thing)
    assert _request_notification(owner).exists()

    resp = _client(requester).post(f"/api/v1/bookings/{booking.code}/cancel/")

    assert resp.status_code == status.HTTP_200_OK
    assert not _request_notification(owner).exists()


@pytest.mark.django_db
def test_an_ownership_transfer_clears_the_auto_declined_siblings_too(
    db, owner, requester, quiet_emails
):
    """Accepting a SHARE request auto-declines the other pending ones — the owner's
    notifications for those can no longer be acted on either."""
    other = User.objects.create(code="IREQ02", email="ioreq2@test.com", name="Other")
    collection = Collection.objects.create(
        code="IOSH01", owner=owner, headline="Shared", mode="COMMUNITY"
    )
    thing = Thing.objects.create(
        code="IOSH02", owner=owner, headline="The drill", type="SHARE_THING"
    )
    collection.things.add(thing)
    collection.invites.add(requester, other)

    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    _client(other).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    assert _request_notification(owner).count() == 2

    winner = BookingPeriod.objects.get(thing_code=thing, requester_code=requester)
    resp = _client(owner).post(f"/api/v1/bookings/{winner.code}/accept/")

    assert resp.status_code == status.HTTP_200_OK
    assert not _request_notification(owner).exists()
    assert InAppNotification.objects.filter(
        user=other, type=InAppNotification.Type.BOOKING_UNAVAILABLE
    ).exists()


@pytest.mark.django_db
def test_a_notification_without_a_booking_code_survives_a_decision(
    owner, requester, gift_in_collection, quiet_emails
):
    """Rows written before the payload carried codes can't be matched — they stay
    until dismissed by hand rather than clearing someone else's notification."""
    thing, _ = gift_in_collection
    legacy = InAppNotification.objects.create(
        user=owner,
        type=InAppNotification.Type.BOOKING_REQUESTED,
        payload={"thing_headline": thing.headline, "requester_name": requester.name},
    )
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    booking = BookingPeriod.objects.get(thing_code=thing)

    _client(owner).post(f"/api/v1/bookings/{booking.code}/accept/")

    assert InAppNotification.objects.filter(code=legacy.code).exists()
    assert _request_notification(owner).count() == 1


# ── The collection's own inbox ────────────────────────────────────────────


@pytest.mark.django_db
def test_inbox_filters_by_collection(owner, requester, gift_in_collection, quiet_emails):
    thing, collection = gift_in_collection
    other = Collection.objects.create(code="IOCO03", owner=owner, headline="Elsewhere")
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    InAppNotification.objects.create(
        user=owner,
        type=InAppNotification.Type.BROADCAST,
        payload={"message": "Unrelated", "collection_code": other.code},
    )

    resp = _client(owner).get(f"/api/v1/inbox/?collection={collection.code}")

    assert resp.status_code == status.HTTP_200_OK
    assert [n["type"] for n in resp.data] == ["BOOKING_REQUESTED"]
    assert resp.data[0]["payload"]["collection_code"] == collection.code


@pytest.mark.django_db
def test_inbox_without_the_filter_still_lists_everything(
    owner, requester, gift_in_collection, quiet_emails
):
    thing, _ = gift_in_collection
    _client(requester).post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    InAppNotification.objects.create(
        user=owner,
        type=InAppNotification.Type.BROADCAST,
        payload={"message": "Unrelated", "collection_code": "OTHER1"},
    )

    resp = _client(owner).get("/api/v1/inbox/")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.data) == 2
