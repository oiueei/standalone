"""``invitation_acceptance``: how the invitations each account sent were answered.

It is the figure a deployment reads to see who invites people who then say no or
never answer, so what it must not do is as pinned as what it counts: a recent batch
does not count (or whoever just sent one looks like a spammer), and it counts by who
spent the quota, not by whose group it was.
"""

from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from core.models import InvitationRecord, User
from core.models.invitation_record import address_hash
from core.services.invitation_service import invitation_acceptance

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_now():
    with time_machine.travel(NOW, tick=False):
        yield


@pytest.fixture
def founder():
    return User.objects.create(code="FOUN01", email="lala@your-domain.test")


@pytest.fixture
def curator():
    return User.objects.create(code="CURA01", email="lele@your-domain.test")


_count = 0


def sent(founder, inviter, ago, state=InvitationRecord.State.SENT):
    global _count
    _count += 1
    return InvitationRecord.objects.create(
        founder=founder,
        inviter=inviter,
        address_hash=address_hash(f"guest{_count}@your-domain.test"),
        state=state,
        sent_at=NOW - ago,
    )


class TestWhatIsCounted:
    def test_each_answer_is_counted_apart(self, founder):
        sent(founder, founder, timedelta(days=10), InvitationRecord.State.ACCEPTED)
        sent(founder, founder, timedelta(days=10), InvitationRecord.State.ACCEPTED)
        sent(founder, founder, timedelta(days=10), InvitationRecord.State.DECLINED)
        sent(founder, founder, timedelta(days=10), InvitationRecord.State.SENT)

        assert invitation_acceptance() == [
            {"inviter": "FOUN01", "sent": 4, "accepted": 2, "declined": 1, "unanswered": 1}
        ]

    def test_it_counts_by_who_invited_not_by_whose_group_it_was(self, founder, curator):
        sent(founder, curator, timedelta(days=10), InvitationRecord.State.DECLINED)
        sent(founder, curator, timedelta(days=10))
        sent(founder, founder, timedelta(days=10), InvitationRecord.State.ACCEPTED)

        result = {row["inviter"]: row for row in invitation_acceptance()}

        assert result["CURA01"]["sent"] == 2
        assert result["CURA01"]["declined"] == 1
        assert result["FOUN01"]["sent"] == 1
        assert result["FOUN01"]["accepted"] == 1

    def test_the_account_that_sent_most_comes_first(self, founder, curator):
        sent(founder, founder, timedelta(days=10))
        for _ in range(3):
            sent(founder, curator, timedelta(days=10))

        assert [row["inviter"] for row in invitation_acceptance()] == ["CURA01", "FOUN01"]

    def test_with_nothing_sent_it_is_empty(self):
        assert invitation_acceptance() == []


class TestTheWindow:
    def test_an_invitation_sent_inside_the_settling_days_is_left_out(self, founder):
        sent(founder, founder, timedelta(days=7) - timedelta(seconds=1))

        assert invitation_acceptance() == []

    def test_an_invitation_sent_exactly_the_settling_days_ago_counts(self, founder):
        sent(founder, founder, timedelta(days=7))

        assert invitation_acceptance()[0]["sent"] == 1

    def test_an_invitation_older_than_the_window_is_left_out(self, founder):
        sent(founder, founder, timedelta(days=30) + timedelta(seconds=1))

        assert invitation_acceptance() == []

    def test_an_invitation_exactly_the_window_ago_counts(self, founder):
        sent(founder, founder, timedelta(days=30))

        assert invitation_acceptance()[0]["sent"] == 1

    def test_both_edges_move_with_the_arguments(self, founder):
        sent(founder, founder, timedelta(days=3))
        sent(founder, founder, timedelta(days=50))

        assert invitation_acceptance(days=60, settle_days=1)[0]["sent"] == 2
        assert invitation_acceptance(days=60, settle_days=7)[0]["sent"] == 1
        assert invitation_acceptance(days=10, settle_days=1)[0]["sent"] == 1
