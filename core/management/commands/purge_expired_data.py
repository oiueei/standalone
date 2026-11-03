"""
Enforce the retention periods (GDPR art. 5.1.e).

"How long do you keep this?" used to have one honest answer here — "forever" —
and that is not a valid one. This command is the other half of a decision taken
on paper first: a period per category of data, with a reason. It does not
invent any of them; every period is a setting (``RETENTION_*`` in
``config/settings/base.py``), and **0 means keep indefinitely** for a deployment
under a different regime.

**Dry-run is the default**, like ``cleanup_orphan_images``: this deletes real
rows, so it is meant to be looked at before it is trusted. Pass ``--commit``.

    python manage.py purge_expired_data            # count what would go
    python manage.py purge_expired_data --commit   # actually do it

Idempotent: every step selects only rows that are still in the "before" state,
so running it twice in a row does nothing the second time, and a run that dies
half way can simply be run again.

Two shapes of expiry, and the difference is the whole point:

- **Anonymised** — ``Event``. What expires is the link to a person
  (``actor_code``), not the fact that something happened. The series survives as
  aggregate and stops being personal data, which is what art. 5.1.e asks for;
  deleting it would throw away the history to achieve the same thing.
- **Deleted** — the guest accounts nobody ever answered for, ``DailyActivity``,
  ``InAppNotification``, ``Report``. There is no version of these that stops
  being about somebody.
"""

import calendar
import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import (
    RSVP,
    BookingPeriod,
    Collection,
    DailyActivity,
    Event,
    InAppNotification,
    InvitationRecord,
    Report,
    User,
)
from core.models.invitation_record import INVITE_RECORD_MONTHS
from core.services.account_service import delete_account
from core.services.email_service import send_inactivity_warning_email

security_logger = logging.getLogger("security")

# How many inactivity warnings one run may send. The first run on an established
# database is the one that matters: every account dormant for the full period
# becomes a candidate on the same night, and this command sends synchronously —
# so an unbounded first run is a single dyno making thousands of SMTP calls in a
# burst, which is how a sending domain earns a rate-limit or a reputation hit
# right before the mail that says "your account is about to be deleted".
#
# Nothing is lost by spreading it: the mark is only written on a successful send,
# so whoever is not reached tonight is simply still a candidate tomorrow, and the
# grace period each of them gets is counted from *their* warning. A backlog
# drains at this rate per day, and a steady state never approaches it.
#
# `--max-warnings 0` lifts the cap for an operator who knows their provider can
# take it.
DEFAULT_MAX_WARNINGS = 200


def months_ago(months, now=None):
    """The same day of the month, ``months`` calendar months back.

    Calendar arithmetic rather than ``timedelta(days=30 * months)`` because a
    retention period is stated in months and a person whose data is deleted six
    days early has a point. The day is clamped to the length of the target month
    (31 March → 28 February).
    """
    now = now or timezone.now()
    year = now.year + (now.month - 1 - months) // 12
    month = (now.month - 1 - months) % 12 + 1
    return now.replace(
        year=year, month=month, day=min(now.day, calendar.monthrange(year, month)[1])
    )


class Command(BaseCommand):
    help = "Anonymise or delete data past the retention period set for its category."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually apply it. Without this flag the command is a dry-run (default).",
        )
        parser.add_argument(
            "--max-warnings",
            type=int,
            default=DEFAULT_MAX_WARNINGS,
            help=(
                "Cap on inactivity warning emails per run "
                f"(default {DEFAULT_MAX_WARNINGS}; 0 = no cap). "
                "The rest are picked up by the next run."
            ),
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        self.max_warnings = options["max_warnings"]
        now = timezone.now()
        # Lines a step wants said after the table rather than in it — a count is
        # not always the whole story.
        self.notes = []
        steps = [
            self._unvisited_guests,
            self._warn_inactive_accounts,
            self._delete_inactive_accounts,
            self._events,
            self._daily_activity,
            self._notifications,
            self._reports,
            self._invitation_records,
            self._reservation_phones,
        ]
        results = []
        for step in steps:
            outcome = step(now, commit)
            if outcome:
                # A step may report more than one line (warning somebody is not
                # the same event as deleting them).
                results.extend(outcome if isinstance(outcome, list) else [outcome])

        self.stdout.write("Retention sweep — " + ("COMMITTED" if commit else "DRY RUN"))
        for label, count in results:
            self.stdout.write(f"  {label}: {count}")
        for note in self.notes:
            self.stdout.write(note)
        total = sum(count for _, count in results)
        if not total:
            self.stdout.write(self.style.SUCCESS("Nothing past its retention period."))
            return
        if commit:
            # An automated erasure leaves the same trail a user-requested one does.
            security_logger.info(
                "Retention sweep applied: "
                + ", ".join(f"{label}={count}" for label, count in results)
            )
            self.stdout.write(self.style.SUCCESS(f"Applied to {total} rows."))
        else:
            self.stdout.write(
                self.style.WARNING(f"{total} rows are past their period. Re-run with --commit.")
            )

    def _unvisited_guests(self, now, commit):
        """Accounts created by somebody else's invitation that were never used.

        ``User.objects.get_or_create(email=...)`` writes a row the moment an
        owner types an address, so an invitation nobody answers leaves a
        stranger's email in the database indefinitely. That address came from a
        third party (art. 14) and was used for exactly one thing: sending an
        invitation that went unanswered.

        Each condition is a distinct way of being wrong about somebody, which is
        why each has its own negative test:

        - ``last_activity`` is null — they never came in. Accepting an
          invitation means signing in, which writes it.
        - in no collection's ``invites`` — the membership M2M is written on
          **accept**, not on invite, so a row here is somebody who did answer
          and simply hasn't been back. Sweeping them would remove a real member
          from a real group.
        - owns no collection and no thing — content means a person, whatever the
          activity column says.
        - has no live ``COLLECTION_INVITE`` RSVP — their invitation is still
          open and may yet be accepted. **Not** "an expired RSVP": ``cleanup_rsvps``
          runs daily and deletes those, so by the time this looks there is no
          expired row to find. Absence is what expiry looks like from here, and
          ``User.created`` is what dates it.
        - not staff or superuser — an admin account created with
          ``createsuperuser`` and never used through the SPA matches every
          condition above.
        """
        days = settings.RETENTION_UNVISITED_GUEST_DAYS
        if not days:
            return None
        codes = list(
            User.objects.filter(
                last_activity__isnull=True,
                created__lt=(now - timedelta(days=days)).date(),
                is_staff=False,
                is_superuser=False,
                invited_to_collections__isnull=True,
                owned_collections__isnull=True,
                owned_things__isnull=True,
            )
            .exclude(rsvps__action=RSVP.Action.COLLECTION_INVITE)
            .values_list("code", flat=True)
        )
        if commit and codes:
            # Erased in bulk, counted in the log and not named there: once the
            # row is gone, writing the codes into a file that outlives it would
            # be an odd way to honour a retention period.
            User.objects.filter(code__in=codes).delete()
        return (f"Guest accounts never used, deleted (>{days}d)", len(codes))

    def _warn_inactive_accounts(self, now, commit):
        """The email that comes before anything is taken away.

        An account nobody has signed into for the retention period is deleted —
        but not without being told, and not on the same day. This step only ever
        sends and marks; the deletion counts its grace period from the mark.

        Who is skipped, and why each one is its own mistake:

        - anyone already warned — the mark is what makes this idempotent, and a
          second email would restart nothing but the recipient's alarm.
        - staff and superusers, as everywhere in this command.
        - anyone holding a live ``COLLECTION_INVITE`` — they were invited days
          ago; telling them in the same week that their account of two years is
          about to be deleted would be true and useless.

        Owning a group other people use does **not** skip the warning: that
        person hears from us, they simply hear the truthful version, because
        their account is not going anywhere (see the retention table). The
        deletion step is where that exception is enforced.

        A failed send leaves the mark unwritten on purpose. The grace period
        must not start from an email that never arrived, so that account is
        picked up again by the next run instead.
        """
        months = settings.RETENTION_INACTIVE_ACCOUNT_MONTHS
        if not months:
            return None
        grace = settings.RETENTION_INACTIVE_WARNING_DAYS
        cutoff = months_ago(months, now).date()
        candidates = list(
            User.objects.filter(
                inactivity_notified__isnull=True,
                is_staff=False,
                is_superuser=False,
            )
            .filter(Q(last_activity__lt=cutoff) | Q(last_activity__isnull=True, created__lt=cutoff))
            .exclude(rsvps__action=RSVP.Action.COLLECTION_INVITE)
        )
        label = f"Inactive accounts warned (>{months}m)"
        if not commit:
            return (label, len(candidates))
        warned = 0
        for user in candidates:
            if self.max_warnings and warned >= self.max_warnings:
                # Deliberately not an error: the remainder are still candidates
                # tomorrow, and each one's grace period starts from its own
                # warning, so nobody is deleted un-warned by stopping here.
                self.notes.append(
                    f"  Stopped at {self.max_warnings} warnings this run; "
                    f"{len(candidates) - warned} still queued for the next one."
                )
                break
            keeps_a_group = Collection.objects.filter(owner=user, invites__isnull=False).exists()
            try:
                send_inactivity_warning_email(user, months, grace, will_delete=not keeps_a_group)
            except Exception as exc:
                self.stderr.write(f"  inactivity warning failed for {user.code}: {exc}")
                continue
            User.objects.filter(pk=user.pk).update(inactivity_notified=timezone.localdate())
            warned += 1
        return (label, warned)

    def _delete_inactive_accounts(self, now, commit):
        """The erasure the warning announced, once its grace period has run out.

        Two independent things have to still be true, and either one saves an
        account: the stamp from the warning must be at least ``grace`` days old,
        **and** the account must still be inactive. Coming back clears the stamp
        *and* refreshes ``last_activity``, so somebody who did what the email
        asked is out of this queryset twice over. That redundancy is deliberate:
        this step is irreversible.

        **An account that owns a group other people are using is never deleted
        here.** ``Collection.owner`` is CASCADE, so erasing the founder of a
        working neighbourhood library takes the collection, its things and its
        photos with them — a harm done to everyone except the person who was
        actually inactive, decided by a job running at night. Those accounts are
        listed instead, for a person to look at. The retention table says so out
        loud; this is where it is enforced.

        Erasure goes through ``account_service.delete_account`` rather than a
        bulk delete: it is the one written-down map of what dies with an account,
        and it leaves the same audit line a user-requested erasure does. (The
        unused-guest sweep above deletes in bulk and logs only a count — those
        rows were never an account anybody used, and there can be hundreds.)
        """
        months = settings.RETENTION_INACTIVE_ACCOUNT_MONTHS
        if not months:
            return None
        grace = settings.RETENTION_INACTIVE_WARNING_DAYS
        cutoff = months_ago(months, now).date()
        candidates = User.objects.filter(
            inactivity_notified__lte=timezone.localdate() - timedelta(days=grace),
            is_staff=False,
            is_superuser=False,
        ).filter(Q(last_activity__lt=cutoff) | Q(last_activity__isnull=True, created__lt=cutoff))
        kept = set(
            Collection.objects.filter(owner__in=candidates, invites__isnull=False).values_list(
                "owner_id", flat=True
            )
        )
        codes = [code for code in candidates.values_list("code", flat=True) if code not in kept]
        if kept:
            self.notes.append(
                "  Kept for a person to decide (they own a group people are using): "
                + ", ".join(sorted(kept))
            )
        if commit and codes:
            for user in User.objects.filter(code__in=codes):
                delete_account(user)
        return [
            (f"Inactive accounts deleted ({grace}d after the warning)", len(codes)),
            ("Inactive owners left for a human decision", len(kept)),
        ]

    def _events(self, now, commit):
        """Cut the link to a person; keep the fact.

        Excluding rows already anonymised is what makes this idempotent — and
        what stops a second run from reporting the same thousands of rows again.
        """
        months = settings.RETENTION_EVENT_ANONYMISE_MONTHS
        if not months:
            return None
        rows = Event.objects.filter(created__lt=months_ago(months, now)).exclude(actor_code="")
        count = rows.count()
        if commit and count:
            rows.update(actor_code="")
        return (f"Event rows anonymised (>{months}m)", count)

    def _daily_activity(self, now, commit):
        months = settings.RETENTION_DAILY_ACTIVITY_MONTHS
        if not months:
            return None
        rows = DailyActivity.objects.filter(date__lt=months_ago(months, now).date())
        count = rows.count()
        if commit and count:
            rows.delete()
        return (f"Daily activity rows deleted (>{months}m)", count)

    def _notifications(self, now, commit):
        months = settings.RETENTION_NOTIFICATION_MONTHS
        if not months:
            return None
        rows = InAppNotification.objects.filter(created__lt=months_ago(months, now))
        count = rows.count()
        if commit and count:
            rows.delete()
        return (f"Notifications deleted (>{months}m)", count)

    def _reports(self, now, commit):
        """Dated from ``created``: the model has no "resolved" state to date from,
        and adding one would be a moderation feature, not a retention decision."""
        months = settings.RETENTION_REPORT_MONTHS
        if not months:
            return None
        rows = Report.objects.filter(created__lt=months_ago(months, now))
        count = rows.count()
        if commit and count:
            rows.delete()
        return (f"Reports deleted (>{months}m)", count)

    def _invitation_records(self, now, commit):
        """Dated from ``sent_at``. The period is ``INVITE_RECORD_MONTHS``, a constant and
        not a ``RETENTION_*`` setting: the invitation email promises a year, so there is
        no value an operator could choose, and no "keep indefinitely" to switch on."""
        rows = InvitationRecord.objects.filter(sent_at__lt=months_ago(INVITE_RECORD_MONTHS, now))
        count = rows.count()
        if commit and count:
            rows.delete()
        return (f"Invitation records deleted (>{INVITE_RECORD_MONTHS}m)", count)

    def _reservation_phones(self, now, commit):
        """Empties the contact phone of every reservation whose last day has passed.

        Neither a ``RETENTION_*`` setting nor switchable off: the label on the request
        page promises the number is deleted the day after the booking, so there is no
        period for an operator to choose. Cancelled reservations are emptied too.
        ``end_date`` is the day the space is free again (for an hourly booking, the
        day after the booking), so ``end_date <= today`` is "the day after".
        """
        rows = BookingPeriod.objects.filter(end_date__lte=timezone.localdate(now)).exclude(
            contact_phone=""
        )
        count = rows.count()
        if commit and count:
            rows.update(contact_phone="")
        return ("Reservation contact phones emptied (the day after the booking)", count)
