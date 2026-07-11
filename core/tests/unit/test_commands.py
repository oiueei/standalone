"""
Unit tests for OIUEEI management commands.
"""

from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from io import StringIO

import pytest
import time_machine
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

    def _create_rsvp(self, hours_ago=0, action=RSVP.Action.MAGIC_LINK):
        user = User.objects.create(email=f"user{hours_ago}{action}@example.com")
        rsvp = RSVP.objects.create(user_code=user, user_email=user.email, action=action)
        if hours_ago:
            rsvp.created = timezone.now() - timedelta(hours=hours_ago)
            rsvp.save(update_fields=["created"])
        return rsvp

    def test_cleanup_expired_rsvps(self):
        """Should delete magic-link RSVPs older than 24 hours."""
        old_rsvp = self._create_rsvp(hours_ago=25)
        new_rsvp = self._create_rsvp(hours_ago=0)

        out = StringIO()
        call_command("cleanup_rsvps", stdout=out)

        assert not RSVP.objects.filter(code=old_rsvp.code).exists()
        assert RSVP.objects.filter(code=new_rsvp.code).exists()
        assert "Cleaned up 1 expired RSVPs" in out.getvalue()

    def test_cleanup_keeps_booking_link_within_72h(self):
        """A booking link at 25h is past the old flat cutoff but still valid (72h)."""
        booking_rsvp = self._create_rsvp(hours_ago=25, action=RSVP.Action.BOOKING_ACCEPT)
        call_command("cleanup_rsvps", stdout=StringIO())
        assert RSVP.objects.filter(code=booking_rsvp.code).exists()

    def test_cleanup_deletes_booking_link_past_72h(self):
        """A booking link past 72h is expired and swept."""
        booking_rsvp = self._create_rsvp(hours_ago=73, action=RSVP.Action.BOOKING_ACCEPT)
        call_command("cleanup_rsvps", stdout=StringIO())
        assert not RSVP.objects.filter(code=booking_rsvp.code).exists()

    def test_cleanup_keeps_invite_within_30_days(self):
        """A pending invitation at 48h is no longer deleted a day after sending."""
        invite_rsvp = self._create_rsvp(hours_ago=48, action=RSVP.Action.COLLECTION_INVITE)
        call_command("cleanup_rsvps", stdout=StringIO())
        assert RSVP.objects.filter(code=invite_rsvp.code).exists()

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
            code=f"{code_prefix}I1",
            email=f"{code_prefix}inv@test.com",
            name="Invitee",
            notify_news=True,  # digest recipient must opt into Cat. 3 (default is now off)
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

    @time_machine.travel(date(2026, 4, 20))  # 2026-04-20 is a Monday
    def test_weekly_digest_on_monday(self):
        """Should send weekly digest on Mondays."""
        monday = date(2026, 4, 20)
        self._setup_collection_with_things("DGW", "WEEKLY", thing_days_ago=3, anchor_date=monday)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 1
        assert "New Widget" in mail.outbox[0].body
        assert "DGWinv@test.com" in mail.outbox[0].to
        assert "Sent 1 digest" in out.getvalue()

    @time_machine.travel(date(2026, 4, 21))  # a Tuesday
    def test_weekly_digest_not_on_tuesday(self):
        """Should not send weekly digest on non-Mondays."""
        self._setup_collection_with_things("DGX", "WEEKLY", thing_days_ago=3)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 0
        assert "Sent 0 digest" in out.getvalue()

    @time_machine.travel(date(2026, 5, 1))  # the 1st of the month
    def test_monthly_digest_on_first(self):
        """Should send monthly digest on the 1st of the month."""
        first = date(2026, 5, 1)
        self._setup_collection_with_things("DGM", "MONTHLY", thing_days_ago=15, anchor_date=first)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 1
        assert "Sent 1 digest" in out.getvalue()

    @time_machine.travel(date(2026, 4, 20))  # a Monday
    def test_skips_none_frequency(self):
        """Should not send digests for collections with NONE frequency."""
        self._setup_collection_with_things("DGN", "NONE", thing_days_ago=3)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 0

    @time_machine.travel(date(2026, 4, 20))  # a Monday
    def test_skips_when_no_new_things(self):
        """Should not send digest when no new things in the period."""
        monday = date(2026, 4, 20)
        # Thing created 30 days ago — outside the weekly window
        self._setup_collection_with_things("DGO", "WEEKLY", thing_days_ago=30, anchor_date=monday)

        out = StringIO()
        call_command("send_digests", stdout=out)

        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestSeedDemoCommand:
    """Tests for the seed_demo management command (demo data integrity)."""

    SUCCULENTS = {"l0l001", "l0l002", "l0l003", "l0l004", "l0l005", "l0l006", "l0l007"}

    def test_maps_gallery_key(self):
        """Regression guard: _seed_things must copy the `gallery` key onto the model
        (image ids are stored under the SEED_IMAGE_FOLDER Cloudinary prefix)."""
        call_command("seed_demo")
        assert Thing.objects.get(code="La1a01").gallery == ["oiueei/seed/La1a01_b"]

    def test_maps_tags_key(self):
        """Regression guard: _seed_collections and _seed_things must copy `tags`."""
        call_command("seed_demo")
        assert "modules" in Collection.objects.get(code="L3L3C1").tags
        assert Thing.objects.get(code="L3L302").tags == ["sensors"]

    def test_maps_user_photo_key(self):
        """Regression guard: _seed_users must copy the `photo` key onto the user
        (image ids are stored under the SEED_IMAGE_FOLDER Cloudinary prefix)."""
        call_command("seed_demo")
        assert User.objects.get(code="La1aN1").photo == "oiueei/seed/La1aPH"

    def test_maps_allowed_thing_types_key(self):
        """Regression guard: _seed_collections must copy `allowed_thing_types`."""
        call_command("seed_demo")
        assert Collection.objects.get(code="l1l1C1").allowed_thing_types == ["RENT_THING"]

    def test_lolo_owns_succulent_collection(self):
        call_command("seed_demo")
        coll = Collection.objects.get(code="l0l0C1")
        assert coll.owner_id == "l0l0oh"
        codes = set(coll.things.values_list("code", flat=True))
        assert self.SUCCULENTS <= codes
        assert all(t.owner_id == "l0l0oh" for t in coll.things.filter(code__in=self.SUCCULENTS))
        invites = set(coll.invites.values_list("code", flat=True))
        assert "L3L3oo" in invites and "l0l0oh" not in invites

    def test_is_idempotent(self):
        call_command("seed_demo")
        counts = (User.objects.count(), Collection.objects.count(), Thing.objects.count())
        call_command("seed_demo")
        assert (User.objects.count(), Collection.objects.count(), Thing.objects.count()) == counts

    def test_skeleton_and_locales_stay_in_sync(self):
        """R17: every structural skeleton row has matching localised text in both
        languages — no untranslated skeleton row, no orphan text."""
        from core.management.commands.seed_demo import _MERGE_KEYS, load_seed_data

        en, es = load_seed_data("en"), load_seed_data("es")
        for entity, key in _MERGE_KEYS.items():
            en_rows, es_rows = getattr(en, entity), getattr(es, entity)
            assert len(en_rows) == len(es_rows) > 0
            assert {r[key] for r in en_rows} == {r[key] for r in es_rows}

    def test_merge_yields_structure_and_text(self):
        """R17: merged rows carry both skeleton fields and localised text, and the
        languages genuinely differ in their text."""
        from core.management.commands.seed_demo import load_seed_data

        en = {t["code"]: t for t in load_seed_data("en").THINGS}
        es = {t["code"]: t for t in load_seed_data("es").THINGS}
        sample = en["La1a01"]
        assert sample["type"] == "SELL_THING" and sample["owner_code"] == "La1aN1"  # skeleton
        assert sample["headline"] and sample["headline"] != es["La1a01"]["headline"]  # text


@pytest.mark.django_db
class TestAddTotpDeviceCommand:
    """Tests for the add_totp_device management command (admin 2FA bootstrap)."""

    def test_creates_confirmed_device_for_staff_user(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        user = User.objects.create(email="staff@example.com", is_staff=True)
        out = StringIO()
        call_command("add_totp_device", "staff@example.com", stdout=out)

        device = TOTPDevice.objects.get(user=user)
        assert device.confirmed is True
        assert "otpauth://" in out.getvalue()

    def test_rejects_non_staff_user(self):
        from django.core.management.base import CommandError

        User.objects.create(email="guest@example.com", is_staff=False)
        with pytest.raises(CommandError):
            call_command("add_totp_device", "guest@example.com")

    def test_rejects_unknown_email(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command("add_totp_device", "nobody@example.com")

    def test_refuses_to_duplicate_without_replace(self):
        from django.core.management.base import CommandError

        User.objects.create(email="staff@example.com", is_staff=True)
        call_command("add_totp_device", "staff@example.com")
        with pytest.raises(CommandError):
            call_command("add_totp_device", "staff@example.com")

    def test_replace_regenerates_the_device(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        user = User.objects.create(email="staff@example.com", is_staff=True)
        call_command("add_totp_device", "staff@example.com")
        first_key = TOTPDevice.objects.get(user=user).key

        call_command("add_totp_device", "staff@example.com", "--replace")
        assert TOTPDevice.objects.filter(user=user).count() == 1
        assert TOTPDevice.objects.get(user=user).key != first_key
