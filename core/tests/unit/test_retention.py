"""
The retention sweep: what stops being kept, and — as much — what doesn't.

`purge_expired_data` deletes real rows on a schedule with nobody watching, so
the tests that matter are the ones that pin what it must NOT touch. A purge that
takes one row too many is indistinguishable from a bug that eats the database,
and the person it happens to finds out by not finding their data.

Three properties are asserted throughout: **dry-run changes nothing**,
**re-running changes nothing more** (idempotence), and **0 means keep
indefinitely** — an operator under a different regime turns a period off, and
"off" has to mean off rather than "immediately".
"""

from datetime import timedelta
from io import StringIO

import pytest
import time_machine
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from core.management.commands.purge_expired_data import months_ago
from core.models import (
    RSVP,
    Collection,
    DailyActivity,
    Event,
    InAppNotification,
    InvitationRecord,
    Report,
    Thing,
    User,
)
from core.models.invitation_record import INVITE_RECORD_MONTHS, address_hash

pytestmark = pytest.mark.django_db


def _run(commit=False, extra_args=(), **settings_overrides):
    out = StringIO()
    call_command("purge_expired_data", *(["--commit"] if commit else []), *extra_args, stdout=out)
    return out.getvalue()


def _aged(model, field, months, **kwargs):
    """A row whose timestamp sits one day the wrong side of `months` ago."""
    row = model.objects.create(**kwargs)
    stamp = months_ago(months) - timedelta(days=1)
    model.objects.filter(pk=row.pk).update(**{field: stamp})
    row.refresh_from_db()
    return row


class TestMonthsAgo:
    def test_it_counts_calendar_months_not_thirty_day_blocks(self):
        now = timezone.now().replace(year=2026, month=8, day=21)

        assert months_ago(14, now).year == 2025
        assert months_ago(14, now).month == 6
        assert months_ago(14, now).day == 21

    def test_a_day_that_does_not_exist_in_the_target_month_is_clamped(self):
        # 31 March minus one month is 28 February, not "31 February" or a crash.
        now = timezone.now().replace(year=2026, month=3, day=31)

        assert (months_ago(1, now).month, months_ago(1, now).day) == (2, 28)

    def test_it_crosses_the_year_boundary(self):
        now = timezone.now().replace(year=2026, month=2, day=10)

        assert (months_ago(14, now).year, months_ago(14, now).month) == (2024, 12)


class TestTheAnalyticsLogIsAnonymisedNotDeleted:
    """What expires is the link to a person, not the fact. Deleting the row
    would throw away the history to achieve the same privacy."""

    def test_an_old_event_loses_its_actor_and_keeps_everything_else(self, user):
        event = _aged(
            Event,
            "created",
            15,
            code="OLDEV1",
            kind=Event.Kind.THING_ADDED,
            actor_code=user.code,
            thing_code="THNG01",
        )

        _run(commit=True)

        event.refresh_from_db()
        assert event.actor_code == ""
        assert event.kind == Event.Kind.THING_ADDED
        assert event.thing_code == "THNG01"

    def test_a_recent_event_still_knows_who_did_it(self, user):
        event = _aged(
            Event, "created", 13, code="NEWEV1", kind=Event.Kind.THING_ADDED, actor_code=user.code
        )

        _run(commit=True)

        event.refresh_from_db()
        assert event.actor_code == user.code

    def test_the_second_run_finds_nothing_left_to_do(self, user):
        _aged(
            Event, "created", 15, code="OLDEV2", kind=Event.Kind.THING_ADDED, actor_code=user.code
        )
        _run(commit=True)

        assert "Nothing past its retention period." in _run(commit=True)


class TestWhatGetsDeleted:
    def test_daily_activity_older_than_its_period(self, user):
        old = DailyActivity.objects.create(code="DAYOLD", user=user, date=months_ago(27).date())
        recent = DailyActivity.objects.create(code="DAYNEW", user=user, date=months_ago(25).date())

        _run(commit=True)

        assert not DailyActivity.objects.filter(pk=old.pk).exists()
        assert DailyActivity.objects.filter(pk=recent.pk).exists()

    def test_notifications_older_than_their_period(self, user):
        old = _aged(
            InAppNotification, "created", 13, code="NOTOLD", user=user, type="BOOKING_REQUESTED"
        )
        recent = _aged(
            InAppNotification, "created", 11, code="NOTNEW", user=user, type="BOOKING_REQUESTED"
        )

        _run(commit=True)

        assert not InAppNotification.objects.filter(pk=old.pk).exists()
        assert InAppNotification.objects.filter(pk=recent.pk).exists()

    def test_reports_are_dated_from_when_they_landed(self, user, thing):
        # The model has no "resolved" state to date from — see the retention table.
        old = _aged(Report, "created", 13, code="RPTOLD", thing=thing, reporter=user)
        recent = Report.objects.create(code="RPTNEW", thing=thing, reporter=None)

        _run(commit=True)

        assert not Report.objects.filter(pk=old.pk).exists()
        assert Report.objects.filter(pk=recent.pk).exists()

    def test_the_thing_a_deleted_report_was_about_survives_it(self, user, thing):
        _aged(Report, "created", 13, code="RPTOL2", thing=thing, reporter=user)

        _run(commit=True)

        assert Thing.objects.filter(pk=thing.pk).exists()


class TestTheSafetyRails:
    def test_a_dry_run_changes_nothing(self, user):
        event = _aged(
            Event, "created", 15, code="DRYEV1", kind=Event.Kind.THING_ADDED, actor_code=user.code
        )
        notification = _aged(
            InAppNotification, "created", 13, code="DRYNO1", user=user, type="BOOKING_REQUESTED"
        )

        output = _run()

        event.refresh_from_db()
        assert event.actor_code == user.code
        assert InAppNotification.objects.filter(pk=notification.pk).exists()
        assert "DRY RUN" in output
        assert "--commit" in output

    def test_the_dry_run_counts_exactly_what_the_commit_would_take(self, user):
        _aged(InAppNotification, "created", 13, code="CNTNO1", user=user, type="BOOKING_REQUESTED")

        assert "Notifications deleted (>12m): 1" in _run()
        # The same count, then the row is gone and the third run says zero.
        assert "Notifications deleted (>12m): 1" in _run(commit=True)
        assert "Notifications deleted (>12m): 0" in _run(commit=True)

    def test_zero_means_keep_indefinitely_not_delete_immediately(self, user, settings):
        # The "0 = off" idiom the quota settings already use. An operator in
        # another regime switches a period off; off must not mean "now".
        settings.RETENTION_NOTIFICATION_MONTHS = 0
        notification = _aged(
            InAppNotification, "created", 99, code="OFFNO1", user=user, type="BOOKING_REQUESTED"
        )

        _run(commit=True)

        assert InAppNotification.objects.filter(pk=notification.pk).exists()

    def test_an_operator_who_switches_everything_off_gets_a_command_that_does_nothing(
        self, user, thing, settings
    ):
        # A deployment may be under a regime that forbids some of this, or may
        # want to run its own sweep. Every period off has to mean every category
        # kept — not "kept except the ones nobody wrote a test for".
        for name in (
            "RETENTION_INACTIVE_ACCOUNT_MONTHS",
            "RETENTION_UNVISITED_GUEST_DAYS",
            "RETENTION_EVENT_ANONYMISE_MONTHS",
            "RETENTION_DAILY_ACTIVITY_MONTHS",
            "RETENTION_NOTIFICATION_MONTHS",
            "RETENTION_REPORT_MONTHS",
        ):
            setattr(settings, name, 0)
        guest = User.objects.create(code="OFFGH1", email="lala@your-domain.test")
        User.objects.filter(pk=guest.pk).update(created=months_ago(9).date())
        event = _aged(
            Event, "created", 99, code="OFFEV1", kind=Event.Kind.THING_ADDED, actor_code=user.code
        )
        day = DailyActivity.objects.create(code="OFFDA1", user=user, date=months_ago(99).date())
        report = _aged(Report, "created", 99, code="OFFRP1", thing=thing, reporter=user)

        output = _run(commit=True)

        assert "Nothing past its retention period." in output
        assert User.objects.filter(pk=guest.pk).exists()
        event.refresh_from_db()
        assert event.actor_code == user.code
        assert DailyActivity.objects.filter(pk=day.pk).exists()
        assert Report.objects.filter(pk=report.pk).exists()

    def test_a_quiet_database_says_so_and_stops(self, user):
        assert "Nothing past its retention period." in _run(commit=True)


class TestTheGuestsWhoNeverCameIn:
    """T6. An owner typing an address creates the row, so an invitation nobody
    answers leaves a stranger's email here forever.

    Every test below the first one is about **not** deleting somebody: this step
    erases accounts, and each condition it checks is a different way of being
    wrong about a person.
    """

    def _guest(self, code, days_old=90, **kwargs):
        guest = User.objects.create(code=code, email=f"{code.lower()}@your-domain.test", **kwargs)
        User.objects.filter(pk=guest.pk).update(
            created=(timezone.now() - timedelta(days=days_old)).date()
        )
        guest.refresh_from_db()
        return guest

    def test_an_invitation_nobody_ever_answered_is_erased(self):
        guest = self._guest("GHOST1")

        _run(commit=True)

        assert not User.objects.filter(pk=guest.pk).exists()

    def test_somebody_invited_last_week_is_left_alone(self):
        recent = self._guest("FRESH1", days_old=10)

        _run(commit=True)

        assert User.objects.filter(pk=recent.pk).exists()

    def test_somebody_whose_invitation_is_still_open_is_left_alone(self, collection):
        pending = self._guest("WAIT01")
        RSVP.objects.create(
            code="RSVWT1",
            user_code=pending,
            user_email=pending.email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=collection.code,
        )

        _run(commit=True)

        assert User.objects.filter(pk=pending.pk).exists()

    def test_somebody_who_accepted_and_never_came_back_is_left_alone(self, collection):
        # The trap. Membership is written on accept, so a row in `invites` is a
        # real member of a real group, activity column or not.
        member = self._guest("JOIN01")
        collection.invites.add(member)

        _run(commit=True)

        assert User.objects.filter(pk=member.pk).exists()

    def test_somebody_who_owns_a_collection_is_left_alone(self):
        owner = self._guest("OWNS01")
        Collection.objects.create(code="GHCOL1", owner=owner, headline="Theirs")

        _run(commit=True)

        assert User.objects.filter(pk=owner.pk).exists()

    def test_somebody_who_owns_a_thing_is_left_alone(self):
        owner = self._guest("OWNS02")
        Thing.objects.create(code="GHTHG1", owner=owner, headline="Theirs")

        _run(commit=True)

        assert User.objects.filter(pk=owner.pk).exists()

    def test_somebody_who_has_signed_in_even_once_is_left_alone(self):
        visitor = self._guest("SEEN01")
        User.objects.filter(pk=visitor.pk).update(last_activity=timezone.now().date())

        _run(commit=True)

        assert User.objects.filter(pk=visitor.pk).exists()

    def test_the_superuser_who_never_used_the_app_is_left_alone(self):
        # `createsuperuser` writes a row that matches every other condition here.
        admin = self._guest("ADMIN1", is_staff=True, is_superuser=True)

        _run(commit=True)

        assert User.objects.filter(pk=admin.pk).exists()

    def test_a_dry_run_erases_nobody(self):
        guest = self._guest("GHOST2")

        output = _run()

        assert User.objects.filter(pk=guest.pk).exists()
        assert "Guest accounts never used, deleted (>60d): 1" in output


class TestTheWarningThatComesFirst:
    """Nobody's account disappears without being told, and not on the same day.

    This step only sends and marks. What it says matters as much as who it
    reaches: an account that will not be deleted must not be told that it will.
    """

    def _dormant(self, code, months=30, **kwargs):
        person = User.objects.create(code=code, email=f"{code.lower()}@your-domain.test", **kwargs)
        User.objects.filter(pk=person.pk).update(
            last_activity=months_ago(months).date(), created=months_ago(months + 1).date()
        )
        person.refresh_from_db()
        return person

    def test_somebody_who_has_not_been_seen_in_two_years_hears_about_it(self):
        person = self._dormant("QUIET1")

        _run(commit=True)

        person.refresh_from_db()
        assert person.inactivity_notified == timezone.localdate()
        assert len(mail.outbox) == 1
        assert "30 days" in mail.outbox[0].body or "30" in mail.outbox[0].body

    def test_somebody_who_was_here_last_month_hears_nothing(self):
        person = self._dormant("SEEN02", months=2)

        _run(commit=True)

        person.refresh_from_db()
        assert person.inactivity_notified is None
        assert mail.outbox == []

    def test_the_owner_of_a_group_people_use_is_told_the_truth_instead(self, user2):
        # Their account is not going anywhere, so the email must not say it is.
        owner = self._dormant("KEEPS1")
        collection = Collection.objects.create(code="LIVE01", owner=owner, headline="The library")
        collection.invites.add(user2)

        _run(commit=True)

        body = mail.outbox[0].body
        assert "permanently" not in body
        assert "not taking that away" in body

    def test_an_owner_with_nobody_in_their_group_is_warned_like_anyone_else(self):
        owner = self._dormant("ALONE1")
        Collection.objects.create(code="EMPT01", owner=owner, headline="Just mine")

        _run(commit=True)

        assert "permanently" in mail.outbox[0].body

    def test_nobody_is_warned_twice(self):
        self._dormant("QUIET2")
        _run(commit=True)
        mail.outbox.clear()

        _run(commit=True)

        assert mail.outbox == []

    def test_coming_back_cancels_the_warning(self):
        person = self._dormant("BACK01")
        _run(commit=True)

        person.refresh_from_db()
        assert person.inactivity_notified is not None
        person.update_last_activity()

        person.refresh_from_db()
        assert person.inactivity_notified is None
        assert person.last_activity == timezone.localdate()

    def test_somebody_invited_this_week_is_not_told_their_account_is_expiring(self, collection):
        # True and useless: they were invited days ago.
        newcomer = self._dormant("INVI01")
        RSVP.objects.create(
            code="RSVIV1",
            user_code=newcomer,
            user_email=newcomer.email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=collection.code,
        )

        _run(commit=True)

        newcomer.refresh_from_db()
        assert newcomer.inactivity_notified is None
        assert mail.outbox == []

    def test_the_superuser_is_never_warned(self):
        admin = self._dormant("ADMIN2", is_staff=True, is_superuser=True)

        _run(commit=True)

        admin.refresh_from_db()
        assert admin.inactivity_notified is None

    def test_a_dry_run_sends_nothing_and_marks_nobody(self):
        person = self._dormant("QUIET3")

        output = _run()

        person.refresh_from_db()
        assert person.inactivity_notified is None
        assert mail.outbox == []
        assert "Inactive accounts warned (>24m): 1" in output

    def test_a_send_that_fails_does_not_start_the_clock(self, monkeypatch):
        # The grace period counts from the mark, so a mark written for an email
        # that never arrived would delete somebody who was never told.
        person = self._dormant("FAIL01")
        monkeypatch.setattr(
            "core.management.commands.purge_expired_data.send_inactivity_warning_email",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("smtp down")),
        )

        call_command("purge_expired_data", "--commit", stdout=StringIO(), stderr=StringIO())

        person.refresh_from_db()
        assert person.inactivity_notified is None


class TestTheErasureTheWarningAnnounced:
    """Irreversible, and running at night with nobody watching. Every test here
    except the first is a way of not doing it."""

    def _warned(self, code, warned_days_ago=40, inactive_months=30, **kwargs):
        person = User.objects.create(code=code, email=f"{code.lower()}@your-domain.test", **kwargs)
        User.objects.filter(pk=person.pk).update(
            last_activity=months_ago(inactive_months).date(),
            created=months_ago(inactive_months + 1).date(),
            inactivity_notified=timezone.localdate() - timedelta(days=warned_days_ago),
        )
        person.refresh_from_db()
        return person

    def test_an_account_warned_a_month_ago_and_still_silent_is_erased(self):
        person = self._warned("GONE01")

        _run(commit=True)

        assert not User.objects.filter(pk=person.pk).exists()

    def test_the_grace_period_is_honoured_to_the_day(self):
        early = self._warned("WAIT02", warned_days_ago=29)

        _run(commit=True)

        assert User.objects.filter(pk=early.pk).exists()

    def test_somebody_who_came_back_is_saved_twice_over(self):
        person = self._warned("BACK02")
        person.update_last_activity()

        _run(commit=True)

        # The stamp is cleared AND last_activity is fresh: either alone is enough.
        assert User.objects.filter(pk=person.pk).exists()

    def test_the_owner_of_a_group_people_use_is_never_erased_by_a_nightly_job(self, user2):
        # Collection.owner is CASCADE: erasing them takes the library, its
        # things and its photos from everyone who was still using it.
        owner = self._warned("LIBR01")
        collection = Collection.objects.create(code="LIVE02", owner=owner, headline="The library")
        collection.invites.add(user2)

        output = _run(commit=True)

        assert User.objects.filter(pk=owner.pk).exists()
        assert Collection.objects.filter(pk=collection.pk).exists()
        assert "LIBR01" in output
        assert "Inactive owners left for a human decision: 1" in output

    def test_an_owner_whose_group_is_empty_is_erased_like_anyone_else(self):
        owner = self._warned("ALONE2")
        Collection.objects.create(code="EMPT02", owner=owner, headline="Just mine")

        _run(commit=True)

        assert not User.objects.filter(pk=owner.pk).exists()
        assert not Collection.objects.filter(code="EMPT02").exists()

    def test_somebody_who_was_never_warned_is_never_erased(self):
        # No stamp, no clock: the email is not optional.
        person = User.objects.create(code="NOTLD1", email="lele@your-domain.test")
        User.objects.filter(pk=person.pk).update(last_activity=months_ago(30).date())

        _run(commit=True)

        assert User.objects.filter(pk=person.pk).exists()

    def test_the_superuser_is_never_erased(self):
        admin = self._warned("ADMIN3", is_staff=True, is_superuser=True)

        _run(commit=True)

        assert User.objects.filter(pk=admin.pk).exists()

    def test_a_dry_run_erases_nobody(self):
        person = self._warned("GONE02")

        output = _run()

        assert User.objects.filter(pk=person.pk).exists()
        assert "Inactive accounts deleted (30d after the warning): 1" in output

    def test_switching_the_period_off_stops_the_erasure_too(self, settings):
        settings.RETENTION_INACTIVE_ACCOUNT_MONTHS = 0
        person = self._warned("OFF001")

        _run(commit=True)

        assert User.objects.filter(pk=person.pk).exists()


@pytest.mark.django_db
class TestTheWarningsAreSpreadOverRuns:
    """The first armed run on an established database is the dangerous one.

    Every account dormant for the full period becomes a candidate on the same
    night, and this command sends synchronously — so without a cap the first run
    is one dyno making thousands of SMTP calls in a burst. That is how a sending
    domain earns a rate-limit, and it would earn it while delivering the mail
    that says "your account is about to be deleted".

    Spreading them costs nothing, and that is the property worth pinning: nobody
    is deleted un-warned by stopping early, because the deletion counts its grace
    period from each person's own mark.
    """

    def _dormant_crowd(self, how_many):
        for index in range(how_many):
            person = User.objects.create(
                code=f"D{index:05d}", email=f"lele{index}@your-domain.test"
            )
            User.objects.filter(pk=person.pk).update(
                last_activity=months_ago(30).date(), created=months_ago(31).date()
            )

    def test_a_run_stops_at_the_cap(self):
        self._dormant_crowd(5)

        output = _run(commit=True, extra_args=["--max-warnings", "2"])

        assert len(mail.outbox) == 2
        assert User.objects.filter(inactivity_notified__isnull=False).count() == 2
        assert "3 still queued" in output

    def test_the_rest_are_warned_by_the_next_run(self):
        """The cap defers; it never drops anybody."""
        self._dormant_crowd(5)

        _run(commit=True, extra_args=["--max-warnings", "2"])
        _run(commit=True, extra_args=["--max-warnings", "2"])
        _run(commit=True, extra_args=["--max-warnings", "2"])

        assert len(mail.outbox) == 5
        assert User.objects.filter(inactivity_notified__isnull=True).count() == 0

    def test_nobody_the_cap_deferred_is_deleted_unwarned(self):
        """The invariant that makes deferring safe.

        The deletion step keys off `inactivity_notified`, which only a sent
        warning writes — so an account the cap skipped is invisible to it, not
        merely early.
        """
        self._dormant_crowd(3)

        _run(commit=True, extra_args=["--max-warnings", "1"])
        # Far past any grace period, so only the mark can be holding them back.
        with time_machine.travel(timezone.now() + timedelta(days=400)):
            _run(commit=True, extra_args=["--max-warnings", "0"])

        # The one warned in the first run is gone; the two it deferred were
        # warned by the second and still have their own grace period to run.
        assert User.objects.filter(code__startswith="D").count() == 2

    def test_zero_means_no_cap(self):
        self._dormant_crowd(4)

        _run(commit=True, extra_args=["--max-warnings", "0"])

        assert len(mail.outbox) == 4

    def test_a_dry_run_counts_everybody_regardless_of_the_cap(self):
        """The cap paces sending. A preview sends nothing, so it hides nothing."""
        self._dormant_crowd(5)

        output = _run(commit=False, extra_args=["--max-warnings", "2"])

        assert mail.outbox == []
        assert "Inactive accounts warned (>24m): 5" in output


class TestInvitationRecords:
    """A record of an invitation is kept for the year the invitation email promises: the
    period is a constant, so it is not switched off by the settings that switch others off."""

    def _record(self, user, months, code):
        other = User.objects.create(email=f"{code.lower()}@your-domain.test")
        return _aged(
            InvitationRecord,
            "sent_at",
            months,
            code=code,
            founder=user,
            inviter=user,
            address_hash=address_hash(other.email),
        )

    def test_a_record_older_than_a_year_goes_and_a_newer_one_stays(self, user):
        old = self._record(user, INVITE_RECORD_MONTHS, "INVOLD")
        recent = InvitationRecord.objects.create(
            code="INVNEW",
            founder=user,
            inviter=user,
            address_hash=address_hash("n@your-domain.test"),
        )

        _run(commit=True)

        assert not InvitationRecord.objects.filter(pk=old.pk).exists()
        assert InvitationRecord.objects.filter(pk=recent.pk).exists()

    def test_a_record_just_inside_the_year_stays(self, user):
        inside = InvitationRecord.objects.create(
            code="INVIN1",
            founder=user,
            inviter=user,
            address_hash=address_hash("i@your-domain.test"),
        )
        InvitationRecord.objects.filter(pk=inside.pk).update(
            sent_at=months_ago(INVITE_RECORD_MONTHS) + timedelta(days=1)
        )

        _run(commit=True)

        assert InvitationRecord.objects.filter(pk=inside.pk).exists()

    def test_a_dry_run_counts_it_and_deletes_nothing(self, user):
        old = self._record(user, INVITE_RECORD_MONTHS, "INVDRY")

        output = _run()

        assert "Invitation records deleted" in output
        assert InvitationRecord.objects.filter(pk=old.pk).exists()
