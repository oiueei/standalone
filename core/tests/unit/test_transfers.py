"""
Unit tests for ThingTransfer model and close_transfers management command.
"""

from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from core.models.booking import BookingPeriod
from core.models.transfer import ThingTransfer
from core.services.booking_service import accept_booking


@pytest.mark.django_db
class TestThingTransferModel:
    """Tests for ThingTransfer model."""

    def test_create_transfer(self, user, user2, thing):
        """Should create a transfer record."""
        transfer = ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
        )
        assert transfer.code
        assert len(transfer.code) == 6
        assert transfer.thing == thing
        assert transfer.from_user == user
        assert transfer.to_user == user2
        assert transfer.returned_date is None

    def test_transfer_str_active(self, user, user2, thing):
        """String representation should show active status."""
        transfer = ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
        )
        assert "active" in str(transfer)

    def test_transfer_str_returned(self, user, user2, thing):
        """String representation should show returned status."""
        transfer = ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
            returned_date=date.today(),
        )
        assert "returned" in str(transfer)

    def test_transfer_ordering(self, user, user2, thing):
        """Transfers should be ordered by -lent_date."""
        t1 = ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today() - timedelta(days=10),
        )
        t2 = ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
        )
        transfers = list(ThingTransfer.objects.filter(thing=thing))
        assert transfers[0] == t2
        assert transfers[1] == t1


@pytest.mark.django_db
class TestTransferCreatedOnBookingAccept:
    """Tests that accepting a booking creates a ThingTransfer."""

    def _make_booking(self, thing, owner, requester, thing_type="LEND_THING", **kwargs):
        return BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing_type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            **kwargs,
        )

    def test_accept_date_based_creates_transfer(self, user, user2, thing):
        """Accepting a date-based booking should create a transfer."""
        start = date.today()
        end = date.today() + timedelta(days=7)
        thing.type = "LEND_THING"
        thing.save()
        booking = self._make_booking(
            thing,
            user,
            user2,
            thing_type="LEND_THING",
            start_date=start,
            end_date=end,
        )

        accept_booking(booking)

        transfer = ThingTransfer.objects.get(thing=thing)
        assert transfer.from_user == user
        assert transfer.to_user == user2
        assert transfer.lent_date == start
        assert transfer.returned_date is None
        assert transfer.booking == booking

    def test_accept_gift_creates_transfer(self, user, user2, thing):
        """Accepting a gift booking should create a transfer with today's date."""
        booking = self._make_booking(thing, user, user2, thing_type="GIFT_THING")

        accept_booking(booking)

        transfer = ThingTransfer.objects.get(thing=thing)
        assert transfer.from_user == user
        assert transfer.to_user == user2
        assert transfer.lent_date == date.today()
        assert transfer.returned_date is None


@pytest.mark.django_db
class TestCloseTransfersCommand:
    """Tests for close_transfers management command."""

    def test_close_ended_transfers(self, user, user2, thing):
        """Should close transfers for bookings that have ended."""
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() - timedelta(days=7),
            end_date=date.today() - timedelta(days=1),
            status="ACCEPTED",
        )
        ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            booking=booking,
            lent_date=date.today() - timedelta(days=7),
        )

        out = StringIO()
        call_command("close_transfers", stdout=out)

        transfer = ThingTransfer.objects.get(thing=thing)
        assert transfer.returned_date == date.today()
        assert "Closed 1 transfers" in out.getvalue()

    def test_no_transfers_to_close(self):
        """Should report zero when no transfers to close."""
        out = StringIO()
        call_command("close_transfers", stdout=out)
        assert "Closed 0 transfers" in out.getvalue()

    def test_skip_active_bookings(self, user, user2, thing):
        """Should not close transfers for bookings still in progress."""
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date.today() - timedelta(days=3),
            end_date=date.today() + timedelta(days=4),
            status="ACCEPTED",
        )
        ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            booking=booking,
            lent_date=date.today() - timedelta(days=3),
        )

        out = StringIO()
        call_command("close_transfers", stdout=out)

        transfer = ThingTransfer.objects.get(thing=thing)
        assert transfer.returned_date is None
        assert "Closed 0 transfers" in out.getvalue()
