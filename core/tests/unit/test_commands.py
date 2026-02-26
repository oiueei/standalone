"""
Unit tests for OIUEEI management commands.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import Thing, User
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
