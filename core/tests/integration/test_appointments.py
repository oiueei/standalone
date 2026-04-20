"""
Integration tests for APPOINTMENT_THING appointment scheduling feature.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing
from core.models.booking import BookingPeriod
from core.services.booking_service import accept_booking


@pytest.fixture
def community_collection(db, user):
    """Create a COMMUNITY collection owned by user."""
    return Collection.objects.create(
        code="APCO01",
        owner=user,
        headline="Appointment Collection",
        mode="COMMUNITY",
    )


@pytest.fixture
def appointment_thing(db, user, community_collection):
    """Create an APPOINTMENT_THING with schedule and slot_duration."""
    t = Thing.objects.create(
        code="APTH01",
        type="APPOINTMENT_THING",
        owner=user,
        headline="Consulting Session",
        slot_duration=30,
        availability_schedule=[
            {"days": [1, 2, 3, 4, 5], "start_time": "09:00", "end_time": "12:00"},
            {"days": [2, 4], "start_time": "14:00", "end_time": "16:00"},
        ],
    )
    community_collection.things.add(t)
    return t


@pytest.fixture
def guest_client(db, user2, community_collection):
    """Return an authenticated client for user2, invited to the collection."""
    community_collection.invites.add(user2)
    client = APIClient()
    refresh = RefreshToken.for_user(user2)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
class TestAppointmentThingCreation:
    """Test creating APPOINTMENT_THING with schedule and slot_duration."""

    def test_create_appointment_thing(self, authenticated_client, community_collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "type": "APPOINTMENT_THING",
                "headline": "New Appointment",
                "collection_code": community_collection.code,
                "slot_duration": 60,
                "availability_schedule": [
                    {"days": [1, 3, 5], "start_time": "10:00", "end_time": "18:00"},
                ],
            },
            format="json",
        )
        assert res.status_code == 201
        data = res.json()
        assert data["type"] == "APPOINTMENT_THING"
        assert data["slot_duration"] == 60
        assert len(data["availability_schedule"]) == 1

    def test_appointment_thing_serializer_fields(self, authenticated_client, appointment_thing):
        res = authenticated_client.get(f"/api/v1/things/{appointment_thing.code}/")
        assert res.status_code == 200
        data = res.json()
        assert data["slot_duration"] == 30
        assert len(data["availability_schedule"]) == 2
        assert data["type"] == "APPOINTMENT_THING"

    def test_appointment_in_collection_summary(
        self, authenticated_client, appointment_thing, community_collection
    ):
        res = authenticated_client.get(f"/api/v1/collections/{community_collection.code}/")
        assert res.status_code == 200
        things = res.json()["things"]
        appt = next(t for t in things if t["code"] == appointment_thing.code)
        assert appt["slot_duration"] == 30


@pytest.mark.django_db
class TestSlotsEndpoint:
    """Test the GET /api/v1/things/{code}/slots/ endpoint."""

    def test_slots_generates_correct_slots(self, guest_client, appointment_thing):
        # Use a Monday date
        res = guest_client.get(
            f"/api/v1/things/{appointment_thing.code}/slots/?week_start=2026-04-20"
        )
        assert res.status_code == 200
        data = res.json()
        assert data["week_start"] == "2026-04-20"
        assert data["slot_duration"] == 30
        assert len(data["days"]) == 7

        # Monday (day 1) should have morning slots only
        monday = data["days"][0]
        assert monday["day_of_week"] == 1
        morning_slots = [s for s in monday["slots"] if s["start_time"] < "12:00"]
        assert len(morning_slots) == 6  # 09:00-12:00 in 30-min slots

        # Tuesday (day 2) should have morning + afternoon
        tuesday = data["days"][1]
        assert tuesday["day_of_week"] == 2
        total_tuesday = len(tuesday["slots"])
        assert total_tuesday == 10  # 6 morning + 4 afternoon

        # Saturday (day 6) should have no slots
        saturday = data["days"][5]
        assert len(saturday["slots"]) == 0

    def test_slots_marks_booked_slots(self, guest_client, user, user2, appointment_thing):
        # Create a booking for Monday 09:00-09:30
        BookingPeriod.objects.create(
            thing_code=appointment_thing,
            thing_type="APPOINTMENT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date="2026-04-20",
            end_date="2026-04-20",
            start_time="09:00",
            end_time="09:30",
            status="ACCEPTED",
        )

        res = guest_client.get(
            f"/api/v1/things/{appointment_thing.code}/slots/?week_start=2026-04-20"
        )
        assert res.status_code == 200
        monday = res.data["days"][0]
        booked = [s for s in monday["slots"] if s["status"] == "booked"]
        available = [s for s in monday["slots"] if s["status"] == "available"]
        assert len(booked) == 1
        assert booked[0]["start_time"] == "09:00"
        assert booked[0]["requester_name"] == "Test User 2"
        assert len(available) == 5

    def test_slots_marks_pending_slots(self, guest_client, user, user2, appointment_thing):
        BookingPeriod.objects.create(
            thing_code=appointment_thing,
            thing_type="APPOINTMENT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date="2026-04-21",
            end_date="2026-04-21",
            start_time="14:00",
            end_time="14:30",
            status="PENDING",
        )

        res = guest_client.get(
            f"/api/v1/things/{appointment_thing.code}/slots/?week_start=2026-04-20"
        )
        assert res.status_code == 200
        tuesday = res.data["days"][1]
        pending = [s for s in tuesday["slots"] if s["status"] == "pending"]
        assert len(pending) == 1
        assert pending[0]["start_time"] == "14:00"

    def test_slots_permission_check(self, api_client, appointment_thing, user2):
        """Uninvited user cannot access slots."""
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        res = api_client.get(f"/api/v1/things/{appointment_thing.code}/slots/")
        assert res.status_code == 403

    def test_slots_non_appointment_thing(self, authenticated_client, thing):
        """Non-appointment things return 400."""
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/slots/")
        assert res.status_code == 400

    def test_slots_default_week(self, guest_client, appointment_thing):
        """Slots without week_start default to current week."""
        res = guest_client.get(f"/api/v1/things/{appointment_thing.code}/slots/")
        assert res.status_code == 200
        assert len(res.data["days"]) == 7

    def test_slots_no_schedule(self, guest_client, user, community_collection):
        """Thing with no schedule returns empty days."""
        t = Thing.objects.create(
            code="APTH02",
            type="APPOINTMENT_THING",
            owner=user,
            headline="No Schedule",
            slot_duration=30,
        )
        community_collection.things.add(t)
        res = guest_client.get(f"/api/v1/things/{t.code}/slots/")
        assert res.status_code == 200
        assert res.data["days"] == []


@pytest.mark.django_db
class TestAppointmentBooking:
    """Test booking an appointment slot (reuses hourly booking flow)."""

    def test_book_appointment_slot(self, guest_client, appointment_thing):
        res = guest_client.post(
            f"/api/v1/things/{appointment_thing.code}/request/",
            {"start_date": "2026-04-20", "start_time": "09:00", "end_time": "09:30"},
            format="json",
        )
        assert res.status_code == 200
        assert res.json()["start_time"] == "09:00:00"
        assert BookingPeriod.objects.filter(thing_code=appointment_thing).count() == 1

    def test_overlapping_appointment_rejected(self, guest_client, user, user2, appointment_thing):
        BookingPeriod.objects.create(
            thing_code=appointment_thing,
            thing_type="APPOINTMENT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date="2026-04-20",
            end_date="2026-04-20",
            start_time="09:00",
            end_time="09:30",
            status="PENDING",
        )
        res = guest_client.post(
            f"/api/v1/things/{appointment_thing.code}/request/",
            {"start_date": "2026-04-20", "start_time": "09:00", "end_time": "09:30"},
            format="json",
        )
        assert res.status_code == 409

    def test_non_overlapping_same_day_allowed(self, guest_client, user, user2, appointment_thing):
        BookingPeriod.objects.create(
            thing_code=appointment_thing,
            thing_type="APPOINTMENT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date="2026-04-20",
            end_date="2026-04-20",
            start_time="09:00",
            end_time="09:30",
            status="PENDING",
        )
        res = guest_client.post(
            f"/api/v1/things/{appointment_thing.code}/request/",
            {"start_date": "2026-04-20", "start_time": "10:00", "end_time": "10:30"},
            format="json",
        )
        assert res.status_code == 200

    def test_accept_appointment_booking(self, guest_client, user, user2, appointment_thing):
        res = guest_client.post(
            f"/api/v1/things/{appointment_thing.code}/request/",
            {"start_date": "2026-04-20", "start_time": "09:00", "end_time": "09:30"},
            format="json",
        )
        booking = BookingPeriod.objects.get(code=res.json()["booking_code"])
        accept_booking(booking)
        booking.refresh_from_db()
        assert booking.status == "ACCEPTED"
        # Thing stays ACTIVE (date-based)
        appointment_thing.refresh_from_db()
        assert appointment_thing.status == "ACTIVE"


@pytest.mark.django_db
class TestAppointmentCalendar:
    """Test that APPOINTMENT_THING uses shared calendar (all invitees see full details)."""

    def test_shared_calendar_for_appointments(self, guest_client, user, user2, appointment_thing):
        BookingPeriod.objects.create(
            thing_code=appointment_thing,
            thing_type="APPOINTMENT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date="2026-04-20",
            end_date="2026-04-20",
            start_time="09:00",
            end_time="09:30",
            status="ACCEPTED",
        )
        res = guest_client.get(f"/api/v1/things/{appointment_thing.code}/calendar/")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        # Guest should see full details (owner calendar serializer)
        assert "requester_name" in data[0]
        assert "requester_code" in data[0]
