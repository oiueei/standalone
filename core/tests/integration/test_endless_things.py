"""
Integration tests for is_endless GIFT/SELL things.

is_endless semantics:
- Multiple users can hold simultaneously (no TAKEN status)
- Thing status never changes on request/accept/reject/cancel
- No ThingTransfer created on acceptance
- Accept does not add requester to deal M2M
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.transfer import ThingTransfer
from core.services.booking_service import accept_booking, cancel_booking, reject_booking


def get_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def owner(db):
    return User.objects.create(code="OWN001", email="owner@example.com", name="Owner")


@pytest.fixture
def guest1(db):
    return User.objects.create(code="GST001", email="guest1@example.com", name="Guest 1")


@pytest.fixture
def guest2(db):
    return User.objects.create(code="GST002", email="guest2@example.com", name="Guest 2")


@pytest.fixture
def coll(db, owner, guest1, guest2):
    c = Collection.objects.create(code="ENDL01", owner=owner, headline="Endless Coll")
    c.invites.add(guest1, guest2)
    return c


@pytest.fixture
def endless_gift(db, owner, coll):
    t = Thing.objects.create(
        code="ENDL11",
        type="GIFT_THING",
        owner=owner,
        headline="Endless Gift",
        is_endless=True,
    )
    coll.things.add(t)
    return t


@pytest.fixture
def normal_gift(db, owner, coll):
    t = Thing.objects.create(
        code="NORM11",
        type="GIFT_THING",
        owner=owner,
        headline="Normal Gift",
        is_endless=False,
    )
    coll.things.add(t)
    return t


# --- Request behaviour ---


@pytest.mark.django_db
def test_endless_thing_stays_active_after_request(endless_gift, guest1):
    client = get_client(guest1)
    res = client.post(f"/api/v1/things/{endless_gift.code}/request/", {}, format="json")
    assert res.status_code == status.HTTP_201_CREATED
    endless_gift.refresh_from_db()
    assert endless_gift.status == "ACTIVE"


@pytest.mark.django_db
def test_endless_thing_allows_multiple_pending(endless_gift, guest1, guest2):
    client1 = get_client(guest1)
    client2 = get_client(guest2)
    res1 = client1.post(f"/api/v1/things/{endless_gift.code}/request/", {}, format="json")
    res2 = client2.post(f"/api/v1/things/{endless_gift.code}/request/", {}, format="json")
    assert res1.status_code == status.HTTP_201_CREATED
    assert res2.status_code == status.HTTP_201_CREATED
    assert BookingPeriod.objects.filter(thing_code=endless_gift, status="PENDING").count() == 2


@pytest.mark.django_db
def test_endless_thing_blocks_duplicate_from_same_user(endless_gift, guest1):
    client = get_client(guest1)
    client.post(f"/api/v1/things/{endless_gift.code}/request/", {}, format="json")
    res2 = client.post(f"/api/v1/things/{endless_gift.code}/request/", {}, format="json")
    assert res2.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_normal_gift_becomes_taken(normal_gift, guest1):
    client = get_client(guest1)
    client.post(f"/api/v1/things/{normal_gift.code}/request/", {}, format="json")
    normal_gift.refresh_from_db()
    assert normal_gift.status == "TAKEN"


@pytest.mark.django_db
def test_normal_gift_blocks_second_request_when_taken(normal_gift, guest1, guest2):
    client1 = get_client(guest1)
    client2 = get_client(guest2)
    client1.post(f"/api/v1/things/{normal_gift.code}/request/", {}, format="json")
    res2 = client2.post(f"/api/v1/things/{normal_gift.code}/request/", {}, format="json")
    assert res2.status_code == status.HTTP_400_BAD_REQUEST


# --- Accept behaviour ---


@pytest.mark.django_db
def test_accept_endless_booking_stays_active(endless_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0001",
        thing_code=endless_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=endless_gift.owner,
    )
    accept_booking(booking)
    endless_gift.refresh_from_db()
    assert endless_gift.status == "ACTIVE"


@pytest.mark.django_db
def test_accept_endless_booking_no_transfer(endless_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0002",
        thing_code=endless_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=endless_gift.owner,
    )
    accept_booking(booking)
    assert ThingTransfer.objects.filter(thing=endless_gift).count() == 0


@pytest.mark.django_db
def test_accept_endless_booking_no_deal_add(endless_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0003",
        thing_code=endless_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=endless_gift.owner,
    )
    accept_booking(booking)
    assert endless_gift.deal.filter(code=guest1.code).count() == 0


@pytest.mark.django_db
def test_accept_normal_gift_becomes_inactive(normal_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0004",
        thing_code=normal_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=normal_gift.owner,
    )
    accept_booking(booking)
    normal_gift.refresh_from_db()
    assert normal_gift.status == "INACTIVE"


@pytest.mark.django_db
def test_accept_normal_gift_creates_transfer(normal_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0005",
        thing_code=normal_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=normal_gift.owner,
    )
    accept_booking(booking)
    assert ThingTransfer.objects.filter(thing=normal_gift).count() == 1


# --- Reject / cancel behaviour ---


@pytest.mark.django_db
def test_reject_endless_booking_stays_active(endless_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0006",
        thing_code=endless_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=endless_gift.owner,
    )
    reject_booking(booking)
    endless_gift.refresh_from_db()
    assert endless_gift.status == "ACTIVE"


@pytest.mark.django_db
def test_cancel_endless_booking_stays_active(endless_gift, guest1):
    booking = BookingPeriod.objects.create(
        code="BK0007",
        thing_code=endless_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=endless_gift.owner,
    )
    cancel_booking(booking)
    endless_gift.refresh_from_db()
    assert endless_gift.status == "ACTIVE"


# --- expire_old_pending: endless things not restored ---


@pytest.mark.django_db
def test_expire_endless_pending_does_not_change_status(endless_gift, guest1):
    from datetime import timedelta

    from django.utils import timezone

    booking = BookingPeriod.objects.create(
        code="BK0008",
        thing_code=endless_gift,
        thing_type="GIFT_THING",
        requester_code=guest1,
        requester_email=guest1.email,
        owner_code=endless_gift.owner,
        created=timezone.now() - timedelta(hours=100),
    )
    endless_gift.status = "ACTIVE"
    endless_gift.save(update_fields=["status"])

    BookingPeriod.expire_old_pending()

    booking.refresh_from_db()
    assert booking.status == "EXPIRED"
    endless_gift.refresh_from_db()
    assert endless_gift.status == "ACTIVE"


# --- Serializer exposes is_endless ---


@pytest.mark.django_db
def test_serializer_exposes_is_endless(endless_gift, owner):
    client = get_client(owner)
    res = client.get(f"/api/v1/things/{endless_gift.code}/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["is_endless"] is True


@pytest.mark.django_db
def test_create_thing_with_is_endless(owner, coll):
    client = get_client(owner)
    res = client.post(
        "/api/v1/things/",
        {
            "type": "GIFT_THING",
            "headline": "My endless gift",
            "collection_code": coll.code,
            "is_endless": True,
        },
        format="json",
    )
    assert res.status_code == status.HTTP_201_CREATED
    created = Thing.objects.get(headline="My endless gift")
    assert created.is_endless is True
