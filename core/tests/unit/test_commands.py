"""
Unit tests for OIUEEI management commands.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import RSVP, Thing, User
from core.models.booking import BookingPeriod


@pytest.mark.django_db
class TestExpireBookingsCommand:
    """Tests for expire_bookings management command."""

    def _create_booking(self, hours_ago=0):
        owner = User.objects.create(email=f"owner{hours_ago}@example.com")
        requester = User.objects.create(email=f"req{hours_ago}@example.com")
        thing = Thing.objects.create(owner=owner, headline="Thing")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
        )
        if hours_ago:
            booking.created = timezone.now() - timedelta(hours=hours_ago)
            booking.save(update_fields=["created"])
        return booking

    def test_expire_old_bookings(self):
        """Should expire bookings older than 72 hours."""
        old_booking = self._create_booking(hours_ago=73)
        new_booking = self._create_booking(hours_ago=0)

        out = StringIO()
        call_command("expire_bookings", stdout=out)

        old_booking.refresh_from_db()
        new_booking.refresh_from_db()
        assert old_booking.status == "EXPIRED"
        assert new_booking.status == "PENDING"
        assert "Expired 1 bookings" in out.getvalue()

    def test_no_bookings_to_expire(self):
        """Should report zero when no bookings to expire."""
        out = StringIO()
        call_command("expire_bookings", stdout=out)
        assert "Expired 0 bookings" in out.getvalue()


@pytest.mark.django_db
class TestCleanupRsvpsCommand:
    """Tests for cleanup_rsvps management command."""

    def _create_rsvp(self, hours_ago=0):
        user = User.objects.create(email=f"user{hours_ago}@example.com")
        rsvp = RSVP.objects.create(user_code=user, user_email=user.email)
        if hours_ago:
            rsvp.created = timezone.now() - timedelta(hours=hours_ago)
            rsvp.save(update_fields=["created"])
        return rsvp

    def test_cleanup_expired_rsvps(self):
        """Should delete RSVPs older than 24 hours."""
        old_rsvp = self._create_rsvp(hours_ago=25)
        new_rsvp = self._create_rsvp(hours_ago=0)

        out = StringIO()
        call_command("cleanup_rsvps", stdout=out)

        assert not RSVP.objects.filter(code=old_rsvp.code).exists()
        assert RSVP.objects.filter(code=new_rsvp.code).exists()
        assert "Cleaned up 1 expired RSVPs" in out.getvalue()

    def test_no_rsvps_to_cleanup(self):
        """Should report zero when no RSVPs to clean up."""
        out = StringIO()
        call_command("cleanup_rsvps", stdout=out)
        assert "Cleaned up 0 expired RSVPs" in out.getvalue()
