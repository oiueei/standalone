"""
Integration tests for OIUEEI booking calendar system.
Tests for LEND_THING and RENT_THING types.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Thing, User
from core.models.booking import BookingPeriod
from core.models.transfer import ThingTransfer
from core.tests.factories import ThingFactory


@pytest.fixture
def lend_thing(db, user, collection):
    """Create a LEND_THING thing."""
    t = Thing.objects.create(
        code="LEND01",
        type="LEND_THING",
        owner=user,
        headline="Lend Item",
    )
    collection.add_thing(t.code)
    return t


@pytest.fixture
def rent_thing(db, user, collection):
    """Create a RENT_THING thing with a fee."""
    t = Thing.objects.create(
        code="RENT01",
        type="RENT_THING",
        owner=user,
        headline="Rent Item",
        fee=25.00,
    )
    collection.add_thing(t.code)
    return t


def get_client_for_user(user):
    """Create an authenticated client for a user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
class TestBookingCalendarView:
    """Tests for the thing calendar endpoint."""

    def test_guest_can_view_calendar(self, user, user2, lend_thing, collection):
        """Guest invited to collection can view calendar."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_owner_can_view_calendar(self, authenticated_client, lend_thing):
        """Owner can view their thing's calendar."""
        response = authenticated_client.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.status_code == status.HTTP_200_OK

    def test_non_invited_user_cannot_view_calendar(self, user, user2, lend_thing):
        """Non-invited user cannot view calendar."""
        client2 = get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_guest_sees_limited_calendar_info(self, user, user2, lend_thing, collection):
        """A guest reading a calendar learns when the thing is out — and nothing
        about who has it.

        Asserted as the **whole** key set, not as a list of fields that must be
        absent. A "not in" assertion guards exactly the field it names: this test
        used to check `requester_code` and `code`, and adding `requester_email`
        to the serializer left the entire suite green — on an `AllowAny`
        endpoint, so a public collection's thing would have handed a stranger's
        address to anyone who asked. The allowlist is what makes the next field
        somebody adds fail here instead of in production.
        """
        collection.add_invite(user2.code)

        # Create a booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            status="ACCEPTED",
        )

        client2 = get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert set(response.data[0]) == {
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
        }
        assert response.data[0]["status"] == "ACCEPTED"

    def test_owner_sees_full_calendar_info(
        self, authenticated_client, user, user2, lend_thing, collection
    ):
        """Owner sees full details including requester info."""
        collection.add_invite(user2.code)

        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            status="PENDING",
        )

        response = authenticated_client.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        # The owner's own key set, pinned whole for the same reason as the
        # guest's: this is the richer of the two serializers, so it is the one a
        # new field lands on by default.
        assert set(response.data[0]) == {
            "quantity",
            "code",
            "created",
            "requester_code",
            "requester_name",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
            "project_note",
        }
        assert response.data[0]["requester_code"] == user2.code
        assert response.data[0]["requester_name"] == user2.name

    def test_the_owner_can_still_tell_who_asked_when_they_never_set_a_name(
        self, authenticated_client, user, user2, lend_thing, collection
    ):
        """A nameless requester shows as the address they asked with, not as blank.

        `name` is empty for every account made by `get_or_create(email=...)` —
        everyone who arrived by magic link or invitation and never filled in a
        profile — so this is the ordinary case, not an exotic one. The owner is
        one of the few readers the API does hand an address to (they already see
        it on the request itself), and the alternative here is a calendar row
        attributed to nobody. Nothing pinned this: returning `""` for a blank
        name left the whole suite green.
        """
        collection.add_invite(user2.code)
        user2.name = ""
        user2.save(update_fields=["name"])
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            status="PENDING",
        )

        response = authenticated_client.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.data[0]["requester_name"] == user2.email


@pytest.mark.django_db
class TestBookingRequest:
    """Tests for booking request creation."""

    @pytest.mark.parametrize(
        "thing_fixture,days",
        [
            ("lend_thing", 3),  # LEND_THING
            ("rent_thing", 5),  # RENT_THING (same date-based flow as lend)
        ],
    )
    def test_guest_can_request_date_based_booking(
        self, request, user, user2, collection, thing_fixture, days
    ):
        """A guest can request a date-based booking for LEND/RENT things."""
        thing = request.getfixturevalue(thing_fixture)
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{thing.code}/request/",
            {
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=days)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Booking request sent"
        assert "booking_code" in response.data

    def test_owner_cannot_request_own_thing(self, authenticated_client, lend_thing):
        """Owner cannot request booking for their own thing."""
        response = authenticated_client.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=3)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Cannot request your own thing"

    def test_non_invited_user_cannot_request_booking(self, user, user2, lend_thing):
        """Non-invited user cannot request booking."""
        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=3)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        # The denial must leave no half-created request behind.
        assert BookingPeriod.objects.count() == 0

    def test_booking_requires_dates_for_lend(self, user, user2, lend_thing, collection):
        """LEND_THING requires start_date and end_date."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "start_date" in response.data
        assert "end_date" in response.data

    def test_start_date_must_be_today_or_future(self, user, user2, lend_thing, collection):
        """Start date cannot be in the past."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() - timedelta(days=1)),
                "end_date": str(date.today() + timedelta(days=3)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_end_date_must_be_on_or_after_start_date(self, user, user2, lend_thing, collection):
        """End date must be >= start date."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=5)),
                "end_date": str(date.today()),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_same_day_booking_allowed(self, user, user2, lend_thing, collection):
        """Single day booking (start_date == end_date) is allowed."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        today = date.today()
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(today),
                "end_date": str(today),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestBookingOverlap:
    """Tests for date overlap detection."""

    def test_cannot_book_overlapping_dates_with_pending(self, user, user2, lend_thing, collection):
        """Cannot book dates that overlap with PENDING booking."""
        collection.add_invite(user2.code)

        # Create a pending booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=10),
            status="PENDING",
        )

        # Create a third user
        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        # Try to book overlapping dates
        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=7)),
                "end_date": str(date.today() + timedelta(days=12)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "overlap" in response.data["error"].lower()

    def test_cannot_book_overlapping_dates_with_accepted(self, user, user2, lend_thing, collection):
        """Cannot book dates that overlap with ACCEPTED booking."""
        collection.add_invite(user2.code)

        # Create an accepted booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=10),
            status="ACCEPTED",
        )

        # Create a third user
        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        # Try to book overlapping dates
        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=3)),
                "end_date": str(date.today() + timedelta(days=6)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_can_book_non_overlapping_dates(self, user, user2, lend_thing, collection):
        """Can book dates that don't overlap."""
        collection.add_invite(user2.code)

        # Create an accepted booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=10),
            status="ACCEPTED",
        )

        # Create a third user
        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        # Book non-overlapping dates (after existing booking)
        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=11)),
                "end_date": str(date.today() + timedelta(days=15)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_can_book_dates_with_rejected_booking(self, user, user2, lend_thing, collection):
        """Can book dates that overlap with REJECTED booking."""
        collection.add_invite(user2.code)

        # Create a rejected booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=10),
            status="REJECTED",
        )

        # Create a third user
        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        # Book overlapping dates (allowed since previous is rejected)
        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=5)),
                "end_date": str(date.today() + timedelta(days=10)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_can_pick_up_on_an_existing_return_day(self, user, user2, lend_thing, collection):
        """Back-to-back: a new pickup may land exactly on an existing return day."""
        collection.add_invite(user2.code)
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=10),
            status="ACCEPTED",
        )
        user3 = User.objects.create(code="TEST03", email="lele1@your-domain.test")
        collection.add_invite(user3.code)

        # Pick up on day 10 (the existing booking's return day) → allowed.
        response = get_client_for_user(user3).post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=10)),
                "end_date": str(date.today() + timedelta(days=13)),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert BookingPeriod.objects.filter(thing_code=lend_thing, status="PENDING").exists()

    def test_can_return_on_an_existing_pickup_day(self, user, user2, lend_thing, collection):
        """Back-to-back: a new return may land exactly on an existing pickup day."""
        collection.add_invite(user2.code)
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
            status="ACCEPTED",
        )
        user3 = User.objects.create(code="TEST03", email="lele1@your-domain.test")
        collection.add_invite(user3.code)

        # Return on day 10 (the existing booking's pickup day) → allowed.
        response = get_client_for_user(user3).post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=6)),
                "end_date": str(date.today() + timedelta(days=10)),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_cannot_book_overlapping_by_one_interior_day(self, user, user2, lend_thing, collection):
        """One shared interior day is still a conflict (strict overlap, not touching)."""
        collection.add_invite(user2.code)
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=10),
            status="ACCEPTED",
        )
        user3 = User.objects.create(code="TEST03", email="lele1@your-domain.test")
        collection.add_invite(user3.code)

        # Pick up on day 9 — interior to [5, 10] — overlapping by one day → 409.
        response = get_client_for_user(user3).post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=9)),
                "end_date": str(date.today() + timedelta(days=13)),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
class TestBookingAcceptReject:
    """Tests for booking accept/reject flow via RSVP."""

    def test_accept_booking_via_link(self, api_client, user, user2, lend_thing):
        """Owner can accept booking via RSVP email link."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        # Create RSVP for accept action (as would be done when sending email)
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, user)

        response = api_client.post(f"/api/v1/rsvp/{rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking accepted"
        assert response.data["action"] == "BOOKING_ACCEPT"

        booking.refresh_from_db()
        assert booking.status == "ACCEPTED"

    def test_reject_booking_via_link(self, api_client, user, user2, lend_thing):
        """Owner can reject booking via RSVP email link."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        # Create RSVP for reject action
        rsvp = RSVP.create_for_booking("BOOKING_REJECT", booking, user)

        response = api_client.post(f"/api/v1/rsvp/{rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking rejected"
        assert response.data["action"] == "BOOKING_REJECT"

        booking.refresh_from_db()
        assert booking.status == "REJECTED"

    def test_cannot_accept_expired_booking(self, api_client, user, user2, lend_thing):
        """Cannot accept booking that has expired (72h)."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
        )
        # Make it expired
        booking.created = timezone.now() - timedelta(hours=100)
        booking.save()

        # Create RSVP for accept action
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, user)

        response = api_client.post(f"/api/v1/rsvp/{rsvp.token}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "expired" in response.data["error"].lower()
        # The stale link must not have accepted anything.
        booking.refresh_from_db()
        assert booking.status != "ACCEPTED"
        assert ThingTransfer.objects.count() == 0

    def test_cannot_accept_already_accepted_booking(self, api_client, user, user2, lend_thing):
        """Cannot accept booking that's already accepted."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            status="ACCEPTED",
        )

        # Create RSVP for accept action
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, user)

        response = api_client.post(f"/api/v1/rsvp/{rsvp.token}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # A re-accept must not run the accept side effects again.
        assert ThingTransfer.objects.count() == 0

    def test_booking_not_found(self, api_client):
        """Should return 401 for non-existent RSVP."""
        response = api_client.get("/api/v1/rsvp/NOEXST/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLendingThingStatusNotTaken:
    """Tests that LEND/RENT things stay ACTIVE (not TAKEN)."""

    def test_lend_thing_stays_active_after_booking(self, user, user2, lend_thing, collection):
        """LEND_THING stays ACTIVE after booking request."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=3)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        lend_thing.refresh_from_db()
        assert lend_thing.status == "ACTIVE"

    def test_rent_thing_stays_active_after_booking(self, user, user2, rent_thing, collection):
        """RENT_THING stays ACTIVE after booking request."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{rent_thing.code}/request/",
            {
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=3)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        rent_thing.refresh_from_db()
        assert rent_thing.status == "ACTIVE"

    def test_thing_stays_active_after_booking_accepted(self, api_client, user, user2, lend_thing):
        """Thing stays ACTIVE even after booking is accepted."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            thing_type=lend_thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        # Accept via RSVP
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, user)
        api_client.post(f"/api/v1/rsvp/{rsvp.token}/")

        lend_thing.refresh_from_db()
        assert lend_thing.status == "ACTIVE"

    def test_multiple_bookings_allowed_for_different_dates(
        self, user, user2, lend_thing, collection
    ):
        """Multiple non-overlapping bookings can exist for same thing."""
        collection.add_invite(user2.code)

        # Create first booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            status="ACCEPTED",
        )

        # Create third user for second booking
        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=5)),
                "end_date": str(date.today() + timedelta(days=8)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify 2 bookings exist
        bookings = BookingPeriod.objects.filter(thing_code=lend_thing)
        assert bookings.count() == 2


@pytest.mark.django_db
class TestMyBookingsAndOwnerBookings:
    """Tests for my-bookings and owner-bookings endpoints."""

    def test_my_bookings_returns_user_requests(self, user, user2, lend_thing):
        """my-bookings returns bookings made by the user."""
        # Create booking by user2
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        client2 = get_client_for_user(user2)
        response = client2.get("/api/v1/my-bookings/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["thing_code"] == lend_thing.code

    def test_owner_bookings_returns_requests_for_owned_things(
        self, authenticated_client, user, user2, lend_thing
    ):
        """owner-bookings returns bookings for things owned by user."""
        # Create booking for user's thing
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        response = authenticated_client.get("/api/v1/owner-bookings/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["requester_code"] == user2.code

    def test_owner_bookings_says_whether_accepting_hands_the_thing_over(
        self, authenticated_client, user, user2
    ):
        """`thing_is_endless` rides along so the client can warn before a handover.

        Accepting a GIFT or SELL that isn't endless flips the thing INACTIVE and
        writes a ThingTransfer — it is gone. An endless one is given away again
        and again and transfers nothing, and `thing_type` is identical in both
        cases, so without this field the owner's requests page would either warn
        about a handover that isn't going to happen or skip the warning entirely.
        """
        once = ThingFactory(owner=user, type="GIFT_THING", is_endless=False)
        endless = ThingFactory(owner=user, type="GIFT_THING", is_endless=True)
        for thing in (once, endless):
            BookingPeriod.objects.create(
                thing_code=thing,
                requester_code=user2,
                requester_email=user2.email,
                owner_code=user,
                thing_type="GIFT_THING",
            )

        response = authenticated_client.get("/api/v1/owner-bookings/")

        assert response.status_code == status.HTTP_200_OK
        rows = {r["thing_code"]: r for r in response.data["results"]}
        assert rows[once.code]["thing_is_endless"] is False
        assert rows[endless.code]["thing_is_endless"] is True
        # These things sit in no collection, so the group label is null — the
        # ordinary case for a standalone thing, and the branch `_collection`
        # takes when `collections` is empty. The SPA reads this null and links
        # the row to `/things/{code}` rather than `/collections/…`.
        assert rows[once.code]["collection_code"] is None
        assert rows[once.code]["collection_headline"] is None

    def test_my_bookings_empty_when_no_bookings(self, authenticated_client):
        """my-bookings returns empty list when user has no bookings."""
        response = authenticated_client.get("/api/v1/my-bookings/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_both_lists_carry_hours_for_an_hourly_reservation(
        self, authenticated_client, user, user2
    ):
        """An HOUR-unit RESERVE_THING booking's start_time/end_time reach both
        the requester's own list and the owner's — a whole-day booking still
        serializes them as null, same as the calendar serializers already did."""
        from datetime import time

        space = ThingFactory(owner=user, type="RESERVE_THING")
        BookingPeriod.objects.create(
            thing_code=space,
            thing_type="RESERVE_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
            start_time=time(11, 0),
            end_time=time(13, 0),
            status="ACCEPTED",
        )

        client2 = get_client_for_user(user2)
        mine = client2.get("/api/v1/my-bookings/").data["results"][0]
        assert mine["start_time"] == "11:00:00" and mine["end_time"] == "13:00:00"

        owners = authenticated_client.get("/api/v1/owner-bookings/").data["results"][0]
        assert owners["start_time"] == "11:00:00" and owners["end_time"] == "13:00:00"


@pytest.mark.django_db
class TestRentArticleWithFee:
    """Tests specific to RENT_THING with pricing."""

    def test_rent_thing_has_fee(self, rent_thing):
        """RENT_THING can have a fee."""
        assert rent_thing.fee == 25.00

    def test_booking_rent_thing_works_same_as_lend(self, user, user2, rent_thing, collection):
        """Booking flow for RENT_THING is same as LEND_THING."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(
            f"/api/v1/things/{rent_thing.code}/request/",
            {
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=5)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Fee calculation is done on frontend, not backend
        # Backend just stores the booking dates


@pytest.mark.django_db
class TestStandardReservationFlowUnchanged:
    """Tests that GIFT/SELL/ORDER flow uses BookingPeriod without dates."""

    def test_gift_article_uses_standard_flow(self, user, user2, thing, collection):
        """GIFT_THING uses BookingPeriod without dates."""
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Booking request sent"
        assert "booking_code" in response.data
        # Should NOT have dates
        assert "start_date" not in response.data
        assert "end_date" not in response.data

        # Thing status should be TAKEN for GIFT_THING
        thing.refresh_from_db()
        assert thing.status == "TAKEN"

    def test_sell_thing_uses_standard_flow(self, user, user2, collection):
        """SELL_THING uses BookingPeriod without dates, same as GIFT_THING."""
        from core.models import Thing

        sell_thing = Thing.objects.create(
            code="SELL01",
            type="SELL_THING",
            owner=user,
            headline="Item for Sale",
            fee=50.00,
        )
        collection.add_thing(sell_thing.code)
        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{sell_thing.code}/request/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Booking request sent"
        assert "booking_code" in response.data

        # Thing status should be TAKEN for SELL_THING
        sell_thing.refresh_from_db()
        assert sell_thing.status == "TAKEN"


@pytest.mark.django_db
class TestSingleUseThingCompleteFlow:
    """Tests for complete single-use thing reservation flow (GIFT/SELL)."""

    def test_complete_gift_flow_accept(self, api_client, user, user2, thing, collection):
        """Complete flow: create request → owner accepts → thing INACTIVE."""
        from core.models import RSVP
        from core.models.booking import BookingPeriod

        collection.add_invite(user2.code)

        # Step 1: Requester creates booking request
        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")
        assert response.status_code == status.HTTP_201_CREATED
        booking_code = response.data["booking_code"]

        # Verify thing is TAKEN
        thing.refresh_from_db()
        assert thing.status == "TAKEN"

        # Verify booking was created
        booking = BookingPeriod.objects.get(code=booking_code)
        assert booking.status == "PENDING"
        assert booking.thing_type == "GIFT_THING"

        # Verify RSVPs were created for owner
        rsvps = RSVP.objects.filter(target_code=booking_code)
        assert rsvps.count() == 2
        accept_rsvp = rsvps.get(action="BOOKING_ACCEPT")
        assert accept_rsvp.user_email == user.email

        # Step 2: Owner accepts via RSVP
        response = api_client.post(f"/api/v1/rsvp/{accept_rsvp.token}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "BOOKING_ACCEPT"

        # Verify thing is now INACTIVE
        thing.refresh_from_db()
        assert thing.status == "INACTIVE"
        assert thing.deal.filter(code=user2.code).exists()

        # Verify booking is ACCEPTED
        booking.refresh_from_db()
        assert booking.status == "ACCEPTED"

        # Verify RSVP was deleted (one-time use)
        assert not RSVP.objects.filter(code=accept_rsvp.code).exists()

    def test_complete_gift_flow_reject(self, api_client, user, user2, thing, collection):
        """Complete flow: create request → owner rejects → thing ACTIVE again."""
        from core.models import RSVP
        from core.models.booking import BookingPeriod

        collection.add_invite(user2.code)

        # Step 1: Requester creates booking request
        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")
        assert response.status_code == status.HTTP_201_CREATED
        booking_code = response.data["booking_code"]

        # Step 2: Owner rejects via RSVP
        reject_rsvp = RSVP.objects.get(target_code=booking_code, action="BOOKING_REJECT")
        response = api_client.post(f"/api/v1/rsvp/{reject_rsvp.token}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "BOOKING_REJECT"

        # Verify thing is back to ACTIVE
        thing.refresh_from_db()
        assert thing.status == "ACTIVE"

        # Verify booking is REJECTED
        booking = BookingPeriod.objects.get(code=booking_code)
        assert booking.status == "REJECTED"

    def test_cannot_request_taken_thing(self, user, user2, thing, collection):
        """Cannot request a thing that is already TAKEN."""
        collection.add_invite(user2.code)

        # First user makes a request
        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")
        assert response.status_code == status.HTTP_201_CREATED

        # Create third user
        from core.models import User

        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        # Third user tries to request same thing
        client3 = get_client_for_user(user3)
        response = client3.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Thing is not available for reservation"

    def test_thing_active_again_after_reject(self, api_client, user, user2, thing, collection):
        """After rejection, another user can request the thing."""
        from core.models import RSVP, User

        collection.add_invite(user2.code)

        # User2 makes request
        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")
        booking_code = response.data["booking_code"]

        # Owner rejects
        reject_rsvp = RSVP.objects.get(target_code=booking_code, action="BOOKING_REJECT")
        api_client.post(f"/api/v1/rsvp/{reject_rsvp.token}/")

        # Create user3
        user3 = User.objects.create(
            code="TEST03",
            email="lele1@your-domain.test",
        )
        collection.add_invite(user3.code)

        # User3 can now request
        client3 = get_client_for_user(user3)
        response = client3.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Booking request sent"


@pytest.mark.django_db
class TestDateBasedThingCompleteFlow:
    """Tests for complete date-based thing flow (LEND/RENT)."""

    def test_complete_lend_flow_with_emails(self, api_client, user, user2, lend_thing, collection):
        """Complete flow: request with dates → owner email → accept → requester email."""
        from django.core import mail

        collection.add_invite(user2.code)

        # Step 1: Guest requests booking with dates
        client2 = get_client_for_user(user2)
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=10)

        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {"start_date": str(start), "end_date": str(end)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        booking_code = response.data["booking_code"]

        # Verify two emails sent: request to owner + confirmation to requester
        assert len(mail.outbox) == 2
        owner_email = mail.outbox[0]
        assert user.email in owner_email.to
        # Emails render dates DD/MM/YYYY, like the SPA — not ISO.
        assert start.strftime("%d/%m/%Y") in owner_email.body
        assert end.strftime("%d/%m/%Y") in owner_email.body
        confirmation_email = mail.outbox[1]
        assert user2.email in confirmation_email.to

        # Step 2: Owner accepts via RSVP
        mail.outbox.clear()
        accept_rsvp = RSVP.objects.get(target_code=booking_code, action="BOOKING_ACCEPT")
        response = api_client.post(f"/api/v1/rsvp/{accept_rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["start_date"] == str(start)
        assert response.data["end_date"] == str(end)

        # Verify confirmation email sent to requester with dates
        assert len(mail.outbox) == 1
        requester_email = mail.outbox[0]
        assert user2.email in requester_email.to
        assert "confirmed" in requester_email.body.lower()
        assert start.strftime("%d/%m/%Y") in requester_email.body

        # Verify thing stays ACTIVE
        lend_thing.refresh_from_db()
        assert lend_thing.status == "ACTIVE"

    def test_complete_lend_flow_reject_with_emails(
        self, api_client, user, user2, lend_thing, collection
    ):
        """Complete flow: request → reject → requester notified → dates available."""
        from django.core import mail

        collection.add_invite(user2.code)

        # Step 1: Guest requests booking
        client2 = get_client_for_user(user2)
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=10)

        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {"start_date": str(start), "end_date": str(end)},
            format="json",
        )
        booking_code = response.data["booking_code"]

        # Step 2: Owner rejects
        mail.outbox.clear()
        reject_rsvp = RSVP.objects.get(target_code=booking_code, action="BOOKING_REJECT")
        api_client.post(f"/api/v1/rsvp/{reject_rsvp.token}/")

        # Verify rejection email sent to requester
        assert len(mail.outbox) == 1
        requester_email = mail.outbox[0]
        assert user2.email in requester_email.to
        # Declined, not cancelled: the owner said no, nobody cancelled anything.
        assert "declined" in requester_email.body.lower()
        assert "cancelled" not in requester_email.body.lower()

        # Verify thing stays ACTIVE
        lend_thing.refresh_from_db()
        assert lend_thing.status == "ACTIVE"

        # Step 3: Another user can now book those dates
        user3 = User.objects.create(code="TEST03", email="lele1@your-domain.test")
        collection.add_invite(user3.code)

        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {"start_date": str(start), "end_date": str(end)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_calendar_shows_pending_and_accepted_only(
        self, authenticated_client, user, user2, lend_thing, collection
    ):
        """Calendar shows only PENDING and ACCEPTED, not REJECTED/EXPIRED."""
        collection.add_invite(user2.code)

        # Create bookings with different statuses
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            status="PENDING",
        )
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=7),
            status="ACCEPTED",
        )
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=12),
            status="REJECTED",
        )
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=15),
            end_date=date.today() + timedelta(days=17),
            status="EXPIRED",
        )

        # Get calendar
        response = authenticated_client.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        assert response.status_code == status.HTTP_200_OK
        # Should only show PENDING and ACCEPTED (2 bookings)
        assert len(response.data) == 2
        statuses = [b["status"] for b in response.data]
        assert "PENDING" in statuses
        assert "ACCEPTED" in statuses
        assert "REJECTED" not in statuses
        assert "EXPIRED" not in statuses

    def test_adjacent_bookings_allowed(self, user, user2, lend_thing, collection):
        """Bookings can be adjacent (one ends, next starts same day)."""
        collection.add_invite(user2.code)

        # Create first booking
        BookingPeriod.objects.create(
            thing_code=lend_thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=5),
            status="ACCEPTED",
        )

        # Create third user for second booking
        user3 = User.objects.create(code="TEST03", email="lele1@your-domain.test")
        collection.add_invite(user3.code)

        # Book starting the day after first ends
        client3 = get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {
                "start_date": str(date.today() + timedelta(days=6)),
                "end_date": str(date.today() + timedelta(days=10)),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestBookingConfirmationEmail:
    """Tests for confirmation email sent to requester on booking request."""

    def test_booking_request_sends_two_emails(self, user, user2, thing, collection):
        """Both owner request email and requester confirmation email should be sent."""
        from django.core import mail

        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_201_CREATED
        assert len(mail.outbox) == 2

        # First email goes to owner with accept/reject links
        owner_email = mail.outbox[0]
        assert user.email in owner_email.to

        # Second email goes to requester as confirmation
        confirmation_email = mail.outbox[1]
        assert user2.email in confirmation_email.to
        assert thing.headline in confirmation_email.body

    def test_booking_confirmation_email_includes_thing_details(
        self, user, user2, lend_thing, collection
    ):
        """Confirmation email should include thing name and dates for date-based types."""
        from django.core import mail

        collection.add_invite(user2.code)

        client2 = get_client_for_user(user2)
        start = date.today() + timedelta(days=3)
        end = date.today() + timedelta(days=6)
        response = client2.post(
            f"/api/v1/things/{lend_thing.code}/request/",
            {"start_date": str(start), "end_date": str(end)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        confirmation_email = mail.outbox[1]
        assert user2.email in confirmation_email.to
        assert lend_thing.headline in confirmation_email.body
        assert start.strftime("%d/%m/%Y") in confirmation_email.body
        assert end.strftime("%d/%m/%Y") in confirmation_email.body


@pytest.mark.django_db
class TestExpireOldPending:
    """Tests for BookingPeriod.expire_old_pending() classmethod."""

    def test_expire_old_pending_expires_stale_bookings(self, user, user2, lend_thing):
        """PENDING booking older than 72h should be expired."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
            status="PENDING",
        )
        booking.created = timezone.now() - timedelta(hours=100)
        booking.save()

        count = BookingPeriod.expire_old_pending()

        assert count == 1
        booking.refresh_from_db()
        assert booking.status == "EXPIRED"

    def test_expire_old_pending_does_not_expire_recent(self, user, user2, lend_thing):
        """Recent PENDING booking should not be expired."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
            status="PENDING",
        )

        count = BookingPeriod.expire_old_pending()

        assert count == 0
        booking.refresh_from_db()
        assert booking.status == "PENDING"

    def test_expire_old_pending_does_not_expire_accepted(self, user, user2, lend_thing):
        """Old ACCEPTED booking should not be expired."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
            status="ACCEPTED",
        )
        booking.created = timezone.now() - timedelta(hours=100)
        booking.save()

        count = BookingPeriod.expire_old_pending()

        assert count == 0
        booking.refresh_from_db()
        assert booking.status == "ACCEPTED"

    def test_expire_old_pending_restores_gift_thing_to_active(self, user, user2, collection):
        """Expiring a PENDING booking for a GIFT/SELL thing must restore it to ACTIVE."""
        gift_thing = Thing.objects.create(
            code="GIFT01",
            type="GIFT_THING",
            owner=user,
            headline="Gift Item",
            status="TAKEN",
        )
        collection.add_thing(gift_thing.code)
        booking = BookingPeriod.objects.create(
            thing_code=gift_thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            status="PENDING",
        )
        booking.created = timezone.now() - timedelta(hours=100)
        booking.save()

        count = BookingPeriod.expire_old_pending()

        assert count == 1
        booking.refresh_from_db()
        assert booking.status == "EXPIRED"
        gift_thing.refresh_from_db()
        assert gift_thing.status == "ACTIVE"

    def test_expiring_a_request_clears_its_notice_from_every_managers_inbox(
        self, user, user2, lend_thing
    ):
        """A request that lapses no longer asks anyone to decide it: the
        BOOKING_REQUESTED copy of each manager goes, and nothing else does."""
        from core.models import InAppNotification

        def booking(code, hours):
            b = BookingPeriod.objects.create(
                code=code,
                thing_code=lend_thing,
                requester_code=user2,
                requester_email=user2.email,
                owner_code=user,
                start_date=date.today() + timedelta(days=10),
                end_date=date.today() + timedelta(days=15),
                status="PENDING",
            )
            BookingPeriod.objects.filter(pk=b.pk).update(
                created=timezone.now() - timedelta(hours=hours)
            )
            return b

        stale = booking("BKSTAL", 100)
        fresh = booking("BKFRSH", 1)
        requested = InAppNotification.Type.BOOKING_REQUESTED
        for manager in (user, user2):  # two managers, one copy each
            InAppNotification.objects.create(
                user=manager, type=requested, payload={"booking_code": stale.code}
            )
        kept_fresh = InAppNotification.objects.create(
            user=user, type=requested, payload={"booking_code": fresh.code}
        )
        kept_decided = InAppNotification.objects.create(
            user=user2,
            type=InAppNotification.Type.BOOKING_DECIDED,
            payload={"booking_code": stale.code},
        )

        assert BookingPeriod.expire_old_pending() == 1

        assert not InAppNotification.objects.filter(
            type=requested, payload__booking_code=stale.code
        ).exists()
        assert set(InAppNotification.objects.values_list("pk", flat=True)) == {
            kept_fresh.pk,
            kept_decided.pk,
        }


@pytest.mark.django_db
class TestBookingActionView:
    """Tests for authenticated booking accept/reject via API endpoints."""

    def test_accept_booking_via_api(self, authenticated_client, user, user2, lend_thing):
        """Owner can accept a booking via the authenticated API endpoint."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        response = authenticated_client.post(f"/api/v1/bookings/{booking.code}/accept/")

        assert response.status_code == status.HTTP_200_OK
        booking.refresh_from_db()
        assert booking.status == "ACCEPTED"

    def test_reject_booking_via_api(self, authenticated_client, user, user2, lend_thing):
        """Owner can reject a booking via the authenticated API endpoint."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        response = authenticated_client.post(f"/api/v1/bookings/{booking.code}/reject/")

        assert response.status_code == status.HTTP_200_OK
        booking.refresh_from_db()
        assert booking.status == "REJECTED"

    def test_non_owner_cannot_accept(self, api_client, user, user2, lend_thing):
        """Non-owner receives 403 when trying to accept."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        # Authenticate as user2 (the requester, not the owner)
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.post(f"/api/v1/bookings/{booking.code}/accept/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        booking.refresh_from_db()
        assert booking.status == "PENDING"

    def test_cannot_accept_expired_booking(self, authenticated_client, user, user2, lend_thing):
        """Cannot accept a booking that has expired."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
        )
        booking.created = timezone.now() - timedelta(hours=100)
        booking.save()

        response = authenticated_client.post(f"/api/v1/bookings/{booking.code}/accept/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # The stale accept must not have gone through.
        booking.refresh_from_db()
        assert booking.status != "ACCEPTED"
        assert ThingTransfer.objects.count() == 0

    def test_accept_deletes_rsvps(self, authenticated_client, user, user2, lend_thing):
        """Accepting via API deletes outstanding RSVP links for the booking."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )
        RSVP.create_for_booking("BOOKING_ACCEPT", booking, user)
        RSVP.create_for_booking("BOOKING_REJECT", booking, user)
        assert RSVP.objects.filter(target_code=booking.code).count() == 2

        authenticated_client.post(f"/api/v1/bookings/{booking.code}/accept/")

        assert RSVP.objects.filter(target_code=booking.code).count() == 0

    def test_unauthenticated_returns_401(self, api_client, user, user2, lend_thing):
        """Unauthenticated requests get 401."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        response = api_client.post(f"/api/v1/bookings/{booking.code}/accept/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBookingCancelView:
    """Tests for the requester cancelling their own booking via API."""

    def test_requester_can_cancel_pending_booking(
        self, authenticated_client2, user, user2, lend_thing
    ):
        """The requester can cancel their own PENDING booking → 200, CANCELLED."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        response = authenticated_client2.post(f"/api/v1/bookings/{booking.code}/cancel/")

        assert response.status_code == status.HTTP_200_OK
        booking.refresh_from_db()
        assert booking.status == "CANCELLED"

    def test_non_requester_cannot_cancel(self, authenticated_client, user, user2, lend_thing):
        """A user who is not the requester gets 403 (authenticated_client is the owner)."""
        booking = BookingPeriod.objects.create(
            thing_code=lend_thing,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )

        response = authenticated_client.post(f"/api/v1/bookings/{booking.code}/cancel/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        booking.refresh_from_db()
        assert booking.status == "PENDING"


@pytest.mark.django_db
class TestACalendarCarriesOnlyWhatIsStillAhead:
    """`BookingPeriod.blocking_filter`: every calendar reader only ever used
    what is still to come, so a thing's reads no longer carry — and the hourly
    availability walk no longer scans — its whole booking history. One day of
    grace, because the browser's "today" can be the server's yesterday."""

    def _booking(self, thing, requester, owner, ends_days_from_today, **extra):
        end = timezone.localdate() + timedelta(days=ends_days_from_today)
        return BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            start_date=end - timedelta(days=3),
            end_date=end,
            status=BookingPeriod.Status.ACCEPTED,
            **extra,
        )

    def test_the_calendar_leaves_out_what_ended_before_yesterday(
        self, authenticated_client, lend_thing, user, user2
    ):
        long_gone = self._booking(lend_thing, user2, user, -30)
        ended_the_day_before = self._booking(lend_thing, user2, user, -2)
        ended_yesterday = self._booking(lend_thing, user2, user, -1)
        ends_today = self._booking(lend_thing, user2, user, 0)
        ahead = self._booking(lend_thing, user2, user, 10)

        response = authenticated_client.get(f"/api/v1/things/{lend_thing.code}/calendar/")

        codes = {row["code"] for row in response.json()}
        assert codes == {ended_yesterday.code, ends_today.code, ahead.code}
        assert long_gone.code not in codes and ended_the_day_before.code not in codes

    def test_an_undated_hold_is_always_still_current(self, authenticated_client, user, user2):
        gift = ThingFactory(owner=user, type=Thing.Type.GIFT_THING, status=Thing.Status.TAKEN)
        pending = BookingPeriod.objects.create(
            thing_code=gift,
            thing_type=gift.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )

        response = authenticated_client.get(f"/api/v1/things/{gift.code}/calendar/")

        assert [row["code"] for row in response.json()] == [pending.code]

    def test_the_owners_list_follows_the_same_rule_on_both_paths(
        self, authenticated_client, lend_thing, collection, user, user2
    ):
        self._booking(lend_thing, user2, user, -30)
        ahead = self._booking(lend_thing, user2, user, 10)

        # The collection page reads the prefetched rows (`optimise_thing_queryset`)
        # — the page an owner opens most; the thing's own page falls back to
        # `get_blocked_periods`. Both must say the same.
        page = authenticated_client.get(f"/api/v1/collections/{collection.code}/").json()
        [card] = [t for t in page["things"] if t["code"] == lend_thing.code]
        detail = authenticated_client.get(f"/api/v1/things/{lend_thing.code}/").json()

        assert [row["code"] for row in card["bookings"]] == [ahead.code]
        assert [row["code"] for row in detail["bookings"]] == [ahead.code]


@pytest.mark.django_db
def test_a_broken_link_in_the_email_note_never_costs_the_requester_their_email(
    authenticated_client2, user2, collection, thing
):
    """The owner's note is rendered into the requester's confirmation after
    the request has committed. A link whose host can't be read (an unclosed
    IPv6 bracket, a label too long for IDNA) makes the host lookup raise; if
    that escaped, the member would get a 500 for a request that went through —
    a gift already marked taken — and no confirmation. It renders as literal
    text instead, and the request answers as usual."""
    from django.core import mail

    collection.add_invite(user2.code)
    collection.email_note = "Normas: [aquí](https://[oops/normas)"
    collection.save(update_fields=["email_note"])
    mail.outbox.clear()

    response = authenticated_client2.post(
        f"/api/v1/things/{thing.code}/request/",
        {"collection_code": collection.code},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    [confirmation] = [m for m in mail.outbox if m.to == [user2.email]]
    assert "[aquí](https://[oops/normas)" in confirmation.alternatives[0][0]
