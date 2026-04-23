"""
Unit tests for OIUEEI management commands.
"""

from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from core.models import RSVP, Collection, Thing, User
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


@pytest.mark.django_db
class TestSendRemindersCommand:
    """Tests for send_reminders management command."""

    def test_return_reminder(self):
        """Should send return reminder when end_date is tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        owner = User.objects.create(code="RMOWN1", email="rmowner@test.com", name="Owner")
        requester = User.objects.create(code="RMREQ1", email="rmreq@test.com", name="Requester")
        thing = Thing.objects.create(
            code="RMTHN1", owner=owner, headline="Drill", type="LEND_THING"
        )
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            start_date=date.today(),
            end_date=tomorrow,
            status="ACCEPTED",
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        assert len(mail.outbox) == 1
        assert "ends tomorrow" in mail.outbox[0].subject
        assert "rmowner@test.com" in mail.outbox[0].to
        assert "Sent 1 reminder" in out.getvalue()

    def test_delivery_reminder(self):
        """Should send delivery reminder when delivery_date is tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        owner = User.objects.create(code="RMOWN2", email="rmowner2@test.com", name="Owner")
        requester = User.objects.create(code="RMREQ2", email="rmreq2@test.com", name="Buyer")
        thing = Thing.objects.create(
            code="RMTHN2", owner=owner, headline="Cookies", type="ORDER_THING"
        )
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="ORDER_THING",
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            delivery_date=tomorrow,
            quantity=5,
            status="ACCEPTED",
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        assert len(mail.outbox) == 1
        assert "delivery" in mail.outbox[0].subject.lower()
        assert "Sent 1 reminder" in out.getvalue()

    def test_event_reminder(self):
        """Should send event reminder to attendees when event is tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        event_dt = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.min.time().replace(hour=18))
        )
        owner = User.objects.create(code="RMOWN3", email="rmowner3@test.com", name="Host")
        attendee = User.objects.create(code="RMATT1", email="rmatt@test.com", name="Attendee")
        event = Thing.objects.create(
            code="RMEVT1", owner=owner, headline="Party", type="EVENT_THING", event_date=event_dt
        )
        event.deal.add(attendee)

        collection = Collection.objects.create(code="RMCOL1", owner=owner, headline="Events")
        collection.things.add(event)
        collection.invites.add(attendee)

        out = StringIO()
        call_command("send_reminders", stdout=out)

        assert len(mail.outbox) == 1
        assert "Party" in mail.outbox[0].subject
        assert "rmatt@test.com" in mail.outbox[0].to
        assert "Sent 1 reminder" in out.getvalue()

    def test_no_reminders(self):
        """Should report zero when nothing is due tomorrow."""
        out = StringIO()
        call_command("send_reminders", stdout=out)
        assert "Sent 0 reminder" in out.getvalue()

    def test_skips_non_accepted_bookings(self):
        """Should not send reminders for PENDING or REJECTED bookings."""
        tomorrow = date.today() + timedelta(days=1)
        owner = User.objects.create(code="RMOWN4", email="rmowner4@test.com")
        requester = User.objects.create(code="RMREQ4", email="rmreq4@test.com")
        thing = Thing.objects.create(code="RMTHN4", owner=owner, headline="X", type="LEND_THING")
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            start_date=date.today(),
            end_date=tomorrow,
            status="PENDING",
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        assert len(mail.outbox) == 0
        assert "Sent 0 reminder" in out.getvalue()

    def test_event_skips_inactive_events(self):
        """Should not send reminders for INACTIVE events."""
        tomorrow = date.today() + timedelta(days=1)
        event_dt = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.min.time().replace(hour=18))
        )
        owner = User.objects.create(code="RMOWN6", email="rmowner6@test.com", name="Host")
        attendee = User.objects.create(code="RMATT2", email="rmatt2@test.com", name="Attendee")
        event = Thing.objects.create(
            code="RMEVT3",
            owner=owner,
            headline="Cancelled Party",
            type="EVENT_THING",
            event_date=event_dt,
            status="INACTIVE",
        )
        event.deal.add(attendee)

        out = StringIO()
        call_command("send_reminders", stdout=out)

        assert len(mail.outbox) == 0
        assert "Sent 0 reminder" in out.getvalue()

    def test_skips_events_with_no_attendees(self):
        """Should not send event reminders when nobody is attending."""
        tomorrow = date.today() + timedelta(days=1)
        event_dt = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.min.time().replace(hour=10))
        )
        owner = User.objects.create(code="RMOWN5", email="rmowner5@test.com", name="Host")
        event = Thing.objects.create(
            code="RMEVT2",
            owner=owner,
            headline="Empty Event",
            type="EVENT_THING",
            event_date=event_dt,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        assert len(mail.outbox) == 0
        assert "Sent 0 reminder" in out.getvalue()


@pytest.mark.django_db
class TestSendDigestsCommand:
    """Tests for send_digests management command."""

    def _setup_collection_with_things(
        self, code_prefix, frequency, thing_days_ago=3, anchor_date=None
    ):
        owner = User.objects.create(
            code=f"{code_prefix}O1", email=f"{code_prefix}owner@test.com", name="Owner"
        )
        invitee = User.objects.create(
            code=f"{code_prefix}I1", email=f"{code_prefix}inv@test.com", name="Invitee"
        )
        collection = Collection.objects.create(
            code=f"{code_prefix}C1",
            owner=owner,
            headline=f"{code_prefix} Club",
            digest_frequency=frequency,
        )
        collection.invites.add(invitee)

        thing = Thing.objects.create(code=f"{code_prefix}T1", owner=owner, headline="New Widget")
        if anchor_date is not None:
            thing.created = datetime.combine(
                anchor_date - timedelta(days=thing_days_ago), time(12, 0), tzinfo=dt_timezone.utc
            )
        else:
            thing.created = timezone.now() - timedelta(days=thing_days_ago)
        thing.save(update_fields=["created"])
        collection.things.add(thing)

        return collection, owner, invitee

    @patch("core.management.commands.send_digests.date")
    def test_weekly_digest_on_monday(self, mock_date):
        """Should send weekly digest on Mondays."""
        monday = date(2026, 4, 20)  # 2026-04-20 is a Monday
        mock_date.today.return_value = monday
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        self._setup_collection_with_things("DGW", "WEEKLY", thing_days_ago=3, anchor_date=monday)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 1
        assert "New Widget" in mail.outbox[0].body
        assert "DGWinv@test.com" in mail.outbox[0].to
        assert "Sent 1 digest" in out.getvalue()

    @patch("core.management.commands.send_digests.date")
    def test_weekly_digest_not_on_tuesday(self, mock_date):
        """Should not send weekly digest on non-Mondays."""
        tuesday = date(2026, 4, 21)  # Tuesday
        mock_date.today.return_value = tuesday
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        self._setup_collection_with_things("DGX", "WEEKLY", thing_days_ago=3)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 0
        assert "Sent 0 digest" in out.getvalue()

    @patch("core.management.commands.send_digests.date")
    def test_monthly_digest_on_first(self, mock_date):
        """Should send monthly digest on the 1st of the month."""
        first = date(2026, 5, 1)  # 1st May
        mock_date.today.return_value = first
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        self._setup_collection_with_things("DGM", "MONTHLY", thing_days_ago=15)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 1
        assert "Sent 1 digest" in out.getvalue()

    @patch("core.management.commands.send_digests.date")
    def test_skips_none_frequency(self, mock_date):
        """Should not send digests for collections with NONE frequency."""
        monday = date(2026, 4, 20)
        mock_date.today.return_value = monday
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        self._setup_collection_with_things("DGN", "NONE", thing_days_ago=3)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 0

    @patch("core.management.commands.send_digests.date")
    def test_skips_when_no_new_things(self, mock_date):
        """Should not send digest when no new things in the period."""
        monday = date(2026, 4, 20)
        mock_date.today.return_value = monday
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # Thing created 30 days ago — outside the weekly window
        self._setup_collection_with_things("DGO", "WEEKLY", thing_days_ago=30)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 0
