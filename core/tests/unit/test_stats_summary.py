"""Tests for the stats_summary command: demo/real partition, metrics, Monday gate."""

from datetime import date, timedelta
from io import StringIO

import pytest
import time_machine
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from core.management.commands.stats_summary import STATS_RECIPIENT, build_report
from core.models import FAQ, BookingPeriod, Collection, DailyActivity, Event, Thing, User

MONDAY = date(2026, 4, 20)
TUESDAY = date(2026, 4, 21)


def _row(sections, title, label):
    section = next(s for s in sections if s["title"] == title)
    return dict(section["rows"])[label]


def _real_collection(owner, code="RCOL01", **kwargs):
    return Collection.objects.create(
        code=code, owner=owner, headline="Real", is_onboarding=False, **kwargs
    )


@pytest.mark.django_db
class TestDemoPartition:
    def test_seed_and_onboarding_excluded_from_real(self):
        call_command("seed_demo", verbosity=0)
        sections = build_report()
        # Every seeded user only owns/joins onboarding collections → all demo.
        assert _row(sections, "Users (real)", "Total real users") == 0
        assert _row(sections, "Demo funnel (NOT real metrics)", "Seed + onboarding-only users") == 5
        assert _row(sections, "Demo funnel (NOT real metrics)", "Onboarding collections") == 5

    def test_onboarding_only_popin_user_is_demo(self, user):
        onboarding = Collection.objects.create(
            code="ONB001", owner=user, headline="W", is_onboarding=True
        )
        popin = User.objects.create(code="POPIN1", email="popin@x.com")
        onboarding.invites.add(popin)
        sections = build_report()
        # user owns only an onboarding collection, popin only joined one → both demo.
        assert _row(sections, "Users (real)", "Total real users") == 0


@pytest.mark.django_db
class TestRealMetrics:
    def test_user_roles(self, user, user2):
        coll = _real_collection(user)
        coll.invites.add(user2)
        sections = build_report()
        assert _row(sections, "Users (real)", "Total real users") == 2
        assert _row(sections, "Users (real)", "Creators (own ≥1 real collection)") == 1
        assert _row(sections, "Users (real)", "Guests (invited only)") == 1

    def test_collection_mode_and_visibility(self, user):
        _real_collection(user, code="RC1", mode="COMMUNITY", visibility="PUBLIC")
        _real_collection(user, code="RC2", mode="PROPRIETARY", visibility="PRIVATE")
        sections = build_report()
        assert _row(sections, "Collections (real)", "Total") == 2
        assert _row(sections, "Collections (real)", "COMMUNITY / PROPRIETARY") == "1 / 1"
        assert _row(sections, "Collections (real)", "PUBLIC / PRIVATE") == "1 / 1"

    def test_things_by_type_and_proportions(self, user):
        coll = _real_collection(user)
        for i, ttype in enumerate(["GIFT_THING", "GIFT_THING", "SELL_THING", "LEND_THING"]):
            t = Thing.objects.create(code=f"RT{i:04d}", owner=user, headline="T", type=ttype)
            coll.things.add(t)
        sections = build_report()
        assert _row(sections, "Things (real)", "Total") == 4
        assert _row(sections, "Things (real)", "GIFT_THING") == "2 (50%)"
        assert _row(sections, "Things (real)", "SELL_THING") == "1 (25%)"

    def test_guests_who_never_booked(self, user, user2):
        coll = _real_collection(user)
        coll.invites.add(user2)  # a guest with no booking
        sections = build_report()
        assert (
            _row(sections, "Holds (real, current bookings)", "Guests who never booked")
            == "1 (100%)"
        )

    def test_hold_success_rate_and_faqs(self, user, user2):
        coll = _real_collection(user)
        coll.invites.add(user2)
        thing = Thing.objects.create(code="RTHS01", owner=user, headline="T", type="GIFT_THING")
        coll.things.add(thing)
        FAQ.objects.create(code="RFAQ01", thing=thing, questioner=user2, question="?")
        BookingPeriod.objects.create(
            code="RBK001",
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            status="ACCEPTED",
        )
        BookingPeriod.objects.create(
            code="RBK002",
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            status="PENDING",
        )
        sections = build_report()
        assert _row(sections, "Things (real)", "Avg FAQs per thing") == "1.0"
        assert _row(sections, "Holds (real, current bookings)", "Total hold requests") == 2
        assert (
            _row(sections, "Holds (real, current bookings)", "Success rate (accepted / requested)")
            == "50%"
        )


@pytest.mark.django_db
class TestEventAndRetentionMetrics:
    def test_history_counts_exclude_demo(self, user, user2):
        _real_collection(user).invites.add(user2)  # user + user2 are real
        onboarding = Collection.objects.create(
            code="ONB009", owner=user, headline="W", is_onboarding=True
        )
        demo_user = User.objects.create(code="DEMOXX", email="demo@x.com")
        onboarding.invites.add(demo_user)  # only in an onboarding collection → demo

        Event.log(Event.Kind.USER_JOINED, actor=user)  # real → counts
        Event.log(Event.Kind.USER_JOINED, actor=demo_user)  # demo → excluded

        sections = build_report()
        joined = _row(
            sections, "History (accumulated, from Event log)", "Users joined (7d / 30d / all)"
        )
        assert joined == "1 / 1 / 1"

    def test_guest_to_creator_conversion(self, user, user2):
        # user2 joins a real collection as guest, then later creates their own.
        host = _real_collection(user, code="HOST01")
        host.invites.add(user2)
        own = _real_collection(user2, code="OWN001")
        now = timezone.now()
        Event.log(
            Event.Kind.MEMBER_JOINED, actor=user2, collection=host, created=now - timedelta(days=3)
        )
        Event.log(
            Event.Kind.COLLECTION_CREATED,
            actor=user2,
            collection=own,
            created=now - timedelta(days=1),
        )
        sections = build_report()
        assert _row(sections, "Conversion", "Guest → creator conversions") == 1

    def test_retention_wau_mau_and_return(self, user, user2):
        _real_collection(user).invites.add(user2)
        today = date.today()
        # user active two days (returner); user2 active once (never came back).
        DailyActivity.objects.create(code="DA0001", user=user, date=today)
        DailyActivity.objects.create(code="DA0002", user=user, date=today - timedelta(days=2))
        DailyActivity.objects.create(code="DA0003", user=user2, date=today)
        sections = build_report()
        # user (creator) active 2 days → a creator return; user2 (guest) active once.
        assert (
            _row(sections, "Retention (from DailyActivity)", "Creator returns (active ≥2 days)")
            == "1 returned (avg 2.0 active days)"
        )
        assert (
            _row(sections, "Retention (from DailyActivity)", "Guest returns (active ≥2 days)")
            == "0 returned (avg — active days)"
        )
        assert (
            _row(
                sections,
                "Retention (from DailyActivity)",
                "Guests who never came back after 1st visit",
            )
            == 1
        )


@pytest.mark.django_db
class TestStatsCommand:
    def test_stdout_always_printed(self):
        with time_machine.travel(TUESDAY):
            out = StringIO()
            call_command("stats_summary", stdout=out)
        text = out.getvalue()
        assert "OIUEEI stats summary" in text
        assert "Not Monday" in text
        assert len(mail.outbox) == 0

    def test_monday_sends_email(self):
        with time_machine.travel(MONDAY):
            out = StringIO()
            call_command("stats_summary", stdout=out)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [STATS_RECIPIENT]
        assert "Stats email sent" in out.getvalue()

    def test_email_flag_forces_send_on_non_monday(self):
        with time_machine.travel(TUESDAY):
            out = StringIO()
            call_command("stats_summary", "--email", stdout=out)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [STATS_RECIPIENT]
