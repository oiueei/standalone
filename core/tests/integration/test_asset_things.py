"""
Integration tests for ASSET_THING (shared asset) feature.
"""

import pytest
from rest_framework.test import APIClient

from core.models import Collection, Thing, User


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com")


@pytest.fixture
def guest():
    return User.objects.create_user(email="guest@test.com")


@pytest.fixture
def stranger():
    return User.objects.create_user(email="stranger@test.com")


@pytest.fixture
def collection(owner, guest):
    col = Collection.objects.create(owner=owner, headline="Shared Office", mode="COMMUNITY")
    col.invites.add(guest)
    return col


@pytest.fixture
def asset_day(owner, collection):
    thing = Thing.objects.create(
        owner=owner,
        type="ASSET_THING",
        headline="Meeting Room",
        booking_unit="DAY",
    )
    collection.things.add(thing)
    return thing


@pytest.fixture
def asset_hour(owner, collection):
    thing = Thing.objects.create(
        owner=owner,
        type="ASSET_THING",
        headline="Projector",
        booking_unit="HOUR",
    )
    collection.things.add(thing)
    return thing


@pytest.mark.django_db
class TestAssetThingCreation:
    def test_create_asset_day(self, owner, collection):
        client = APIClient()
        client.force_authenticate(user=owner)
        res = client.post(
            "/api/v1/things/",
            {
                "type": "ASSET_THING",
                "headline": "Company Car",
                "booking_unit": "DAY",
                "collection_code": collection.code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["booking_unit"] == "DAY"

    def test_create_asset_hour(self, owner, collection):
        client = APIClient()
        client.force_authenticate(user=owner)
        res = client.post(
            "/api/v1/things/",
            {
                "type": "ASSET_THING",
                "headline": "Meeting Room",
                "booking_unit": "HOUR",
                "collection_code": collection.code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["booking_unit"] == "HOUR"


@pytest.mark.django_db
class TestAssetDayBooking:
    def test_guest_can_book_day_asset(self, guest, asset_day):
        client = APIClient()
        client.force_authenticate(user=guest)
        res = client.post(
            f"/api/v1/things/{asset_day.code}/request/",
            {"start_date": "2026-06-01", "end_date": "2026-06-03"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["message"] == "Booking request sent"

    def test_day_overlap_rejected(self, guest, asset_day):
        client = APIClient()
        client.force_authenticate(user=guest)
        client.post(
            f"/api/v1/things/{asset_day.code}/request/",
            {"start_date": "2026-06-01", "end_date": "2026-06-03"},
            format="json",
        )
        res = client.post(
            f"/api/v1/things/{asset_day.code}/request/",
            {"start_date": "2026-06-02", "end_date": "2026-06-04"},
            format="json",
        )
        assert res.status_code == 409

    def test_non_overlapping_day_allowed(self, guest, asset_day):
        client = APIClient()
        client.force_authenticate(user=guest)
        client.post(
            f"/api/v1/things/{asset_day.code}/request/",
            {"start_date": "2026-06-01", "end_date": "2026-06-03"},
            format="json",
        )
        res = client.post(
            f"/api/v1/things/{asset_day.code}/request/",
            {"start_date": "2026-06-05", "end_date": "2026-06-07"},
            format="json",
        )
        assert res.status_code == 200


@pytest.mark.django_db
class TestAssetHourBooking:
    def test_guest_can_book_hour_asset(self, guest, asset_hour):
        client = APIClient()
        client.force_authenticate(user=guest)
        res = client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "09:00", "end_time": "11:00"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["start_time"] == "09:00:00"
        assert res.data["end_time"] == "11:00:00"

    def test_hour_overlap_rejected(self, guest, asset_hour):
        client = APIClient()
        client.force_authenticate(user=guest)
        client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "09:00", "end_time": "11:00"},
            format="json",
        )
        res = client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "10:00", "end_time": "12:00"},
            format="json",
        )
        assert res.status_code == 409

    def test_non_overlapping_hour_allowed(self, guest, asset_hour):
        client = APIClient()
        client.force_authenticate(user=guest)
        client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "09:00", "end_time": "11:00"},
            format="json",
        )
        res = client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "11:00", "end_time": "13:00"},
            format="json",
        )
        assert res.status_code == 200

    def test_different_day_same_time_allowed(self, guest, asset_hour):
        client = APIClient()
        client.force_authenticate(user=guest)
        client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "09:00", "end_time": "11:00"},
            format="json",
        )
        res = client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-02", "start_time": "09:00", "end_time": "11:00"},
            format="json",
        )
        assert res.status_code == 200

    def test_end_time_before_start_rejected(self, guest, asset_hour):
        client = APIClient()
        client.force_authenticate(user=guest)
        res = client.post(
            f"/api/v1/things/{asset_hour.code}/request/",
            {"start_date": "2026-06-01", "start_time": "11:00", "end_time": "09:00"},
            format="json",
        )
        assert res.status_code == 400


@pytest.mark.django_db
class TestSharedCalendar:
    def test_guest_sees_full_details_for_asset(self, guest, owner, asset_day):
        """Guests see requester details in asset calendar (shared calendar)."""
        from core.models.booking import BookingPeriod

        BookingPeriod.objects.create(
            thing_code=asset_day,
            thing_type="ASSET_THING",
            requester_code=guest,
            requester_email=guest.email,
            owner_code=owner,
            start_date="2026-06-01",
            end_date="2026-06-03",
        )
        client = APIClient()
        client.force_authenticate(user=guest)
        res = client.get(f"/api/v1/things/{asset_day.code}/calendar/")
        assert res.status_code == 200
        assert len(res.data) == 1
        # Guest should see requester details (shared calendar)
        assert "requester_code" in res.data[0]
        assert "requester_name" in res.data[0]

    def test_stranger_cannot_see_asset_calendar(self, stranger, asset_day):
        client = APIClient()
        client.force_authenticate(user=stranger)
        res = client.get(f"/api/v1/things/{asset_day.code}/calendar/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestUsageStats:
    def test_stats_endpoint(self, guest, owner, asset_day):
        from core.models.booking import BookingPeriod

        BookingPeriod.objects.create(
            thing_code=asset_day,
            thing_type="ASSET_THING",
            requester_code=guest,
            requester_email=guest.email,
            owner_code=owner,
            start_date="2026-06-01",
            end_date="2026-06-03",
            status="ACCEPTED",
        )
        client = APIClient()
        client.force_authenticate(user=guest)
        res = client.get(f"/api/v1/things/{asset_day.code}/stats/")
        assert res.status_code == 200
        assert res.data["total_bookings"] == 1
        assert res.data["unique_users"] == 1
        assert len(res.data["monthly_usage"]) == 1

    def test_stats_no_bookings(self, guest, asset_day):
        client = APIClient()
        client.force_authenticate(user=guest)
        res = client.get(f"/api/v1/things/{asset_day.code}/stats/")
        assert res.status_code == 200
        assert res.data["total_bookings"] == 0
        assert res.data["unique_users"] == 0

    def test_stats_forbidden_for_stranger(self, stranger, asset_day):
        client = APIClient()
        client.force_authenticate(user=stranger)
        res = client.get(f"/api/v1/things/{asset_day.code}/stats/")
        assert res.status_code == 403

    def test_stats_works_for_owner(self, owner, asset_day):
        client = APIClient()
        client.force_authenticate(user=owner)
        res = client.get(f"/api/v1/things/{asset_day.code}/stats/")
        assert res.status_code == 200
