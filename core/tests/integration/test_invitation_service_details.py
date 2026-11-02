"""What the invitation service writes and sends, field by field.

The proposal flow is covered end to end in ``test_invitation_proposals.py``; these
tests pin the pieces that flow only brushes past: what lands in each notice and
RSVP, what each email is told, which language it speaks, and how far the daily
quota counter and the decision claim reach.
"""

from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from django.core import mail
from django.core.cache import caches
from django.test import override_settings

from core.models import RSVP, Collection, InvitationProposal, User
from core.models.notification import InAppNotification
from core.services import invitation_service as svc
from core.services.email_service import T

QUOTA_SETTINGS = {
    "RATELIMIT_ENABLE": True,
    "INVITE_EMAILS_PER_DAY": 5,
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "invitation-service-details",
        }
    },
}


@pytest.fixture
def owner(db):
    return User.objects.create(code="DOWN01", email="lala@your-domain.test", name="Lala")


@pytest.fixture
def member(db):
    return User.objects.create(code="DMEM01", email="lele@your-domain.test", name="Lele")


@pytest.fixture
def group(owner, member):
    collection = Collection.objects.create(
        code="DGRP01", owner=owner, headline="The street", language="es"
    )
    collection.invites.add(member)
    return collection


def _body(address):
    (message,) = [m for m in mail.outbox if m.to == [address]]
    return message


def _text(message):
    """Everything the reader can see: the plain part and the HTML one."""
    return message.body + "".join(html for html, _ in message.alternatives)


class TestTheDailyQuotaCounter:
    def test_an_unset_cap_leaves_the_quota_off_even_with_rate_limiting_on(self, settings):
        settings.RATELIMIT_ENABLE = True
        del settings.INVITE_EMAILS_PER_DAY

        assert svc._invite_quota_cap() is None
        assert svc._invite_quota_left("DOWN01") is None

    @override_settings(**QUOTA_SETTINGS)
    def test_what_was_sent_is_still_counted_hours_later(self):
        caches["default"].clear()
        # A fixed mid-morning, not the clock: the quota key carries the date, so a run in
        # the last hour of the day would see the +1 h cross into a fresh counter.
        now = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)
        with time_machine.travel(now, tick=False):
            svc._consume_invite_quota("DOWN01", 2)
            assert svc._invite_quota_left("DOWN01") == 3
        # The counter's own lifetime, not the cache's default few minutes.
        with time_machine.travel(now + timedelta(hours=1), tick=False):
            assert svc._invite_quota_left("DOWN01") == 3


class TestDeliveringAnInvitation:
    def test_the_pair_is_minted_for_the_collection_and_the_address(self, group):
        mail.outbox.clear()

        user, already = svc.deliver_invitation(group, "Lili@Your-Domain.test", "Lala")

        assert already is False
        assert user.email == "lili@your-domain.test"
        accept = RSVP.objects.get(user_code=user, action=RSVP.Action.COLLECTION_INVITE)
        reject = RSVP.objects.get(user_code=user, action=RSVP.Action.COLLECTION_REJECT)
        assert accept.target_code == reject.target_code == group.code
        assert accept.user_email == reject.user_email == "lili@your-domain.test"

    def test_the_email_names_the_inviter_carries_both_links_and_speaks_the_groups_language(
        self, group
    ):
        mail.outbox.clear()

        user, _ = svc.deliver_invitation(group, "lili@your-domain.test", "Lala")

        sent = _body("lili@your-domain.test")
        accept = RSVP.objects.get(user_code=user, action=RSVP.Action.COLLECTION_INVITE)
        reject = RSVP.objects.get(user_code=user, action=RSVP.Action.COLLECTION_REJECT)
        assert accept.action_link() in sent.body
        assert reject.action_link() in sent.body
        assert "Lala" in _text(sent)
        assert sent.subject == T("invite_subject", lang="es").format(collection="The street")

    def test_a_pending_invitation_blocks_the_same_founders_other_groups_and_keeps_its_pair(
        self, group, owner
    ):
        other = Collection.objects.create(code="DGRP02", owner=owner, headline="Elsewhere")
        user, _ = svc.deliver_invitation(other, "lili@your-domain.test", "Lala")
        pair = set(RSVP.objects.filter(user_code=user).values_list("pk", flat=True))

        with pytest.raises(svc.InvitationAlreadyAsked):
            svc.deliver_invitation(group, "lili@your-domain.test", "Lala")

        assert set(RSVP.objects.filter(user_code=user).values_list("pk", flat=True)) == pair
        assert not RSVP.objects.filter(user_code=user, target_code=group.code).exists()


class TestCreatingAProposal:
    def test_the_note_defaults_to_nothing(self, group, member):
        proposal, _, _ = svc.create_proposal(group, member, "Lili@Your-Domain.test")

        assert proposal.note == ""
        assert proposal.email == "lili@your-domain.test"

    def test_the_note_is_kept_on_the_proposal(self, group, member):
        proposal, _, _ = svc.create_proposal(
            group, member, "lili@your-domain.test", note="my neighbour"
        )

        proposal.refresh_from_db()
        assert proposal.note == "my neighbour"

    def test_the_pair_returned_is_the_founders_and_is_theirs(self, group, member, owner):
        proposal, approve, reject = svc.create_proposal(group, member, "lili@your-domain.test")

        assert approve.action == RSVP.Action.PROPOSAL_APPROVE
        assert reject.action == RSVP.Action.PROPOSAL_REJECT
        assert approve.user_email == reject.user_email == owner.email
        assert approve.target_code == reject.target_code == proposal.code

    def test_a_team_nobody_can_reach_gets_a_proposal_and_no_pair(self, group, member):
        group.owner.email = ""

        proposal, approve, reject = svc.create_proposal(group, member, "lili@your-domain.test")

        assert (approve, reject) == (None, None)
        assert InvitationProposal.objects.filter(pk=proposal.pk).exists()

    def test_the_notice_and_the_email_carry_who_what_and_why(self, group, member, owner):
        mail.outbox.clear()

        proposal, _, _ = svc.create_proposal(
            group, member, "lili@your-domain.test", note="my neighbour"
        )

        notice = InAppNotification.objects.get(
            user=owner, type=InAppNotification.Type.INVITE_PROPOSED
        )
        assert notice.payload == {
            "collection_headline": "The street",
            "collection_code": group.code,
            "proposal_code": proposal.code,
            "proposer_name": "Lele",
            "email": "lili@your-domain.test",
            "note": "my neighbour",
        }
        sent = _body(owner.email)
        assert "Lele" in _text(sent)
        assert "lili@your-domain.test" in _text(sent)
        assert "my neighbour" in _text(sent)
        assert sent.subject == T("proposal_subject", lang="es").format(collection="The street")


class TestDecidingAProposal:
    @pytest.fixture
    def proposal(self, group, member):
        return svc.create_proposal(group, member, "lili@your-domain.test", note="n")[0]

    def test_deciding_one_proposal_leaves_the_others_pending(self, group, member, proposal):
        other = svc.create_proposal(group, member, "lulu@your-domain.test")[0]

        svc.reject_proposal(proposal)

        other.refresh_from_db()
        assert other.status == InvitationProposal.Status.PENDING
        assert other.resolved is None

    def test_the_decision_is_dated(self, proposal):
        svc.approve_proposal(proposal)

        stored = InvitationProposal.objects.get(pk=proposal.pk)
        assert stored.status == InvitationProposal.Status.APPROVED
        assert stored.resolved is not None

    def test_a_second_decision_names_the_proposal_it_lost(self, proposal):
        svc.approve_proposal(proposal)

        with pytest.raises(svc.ProposalAlreadyDecided) as lost:
            svc.reject_proposal(proposal)

        assert str(lost.value) == proposal.code

    def test_approving_tells_the_proposer_and_invites_in_the_owners_name(
        self, group, member, owner, proposal
    ):
        mail.outbox.clear()

        svc.approve_proposal(proposal)

        notice = InAppNotification.objects.get(
            user=member, type=InAppNotification.Type.INVITE_PROPOSAL_APPROVED
        )
        assert notice.payload == {
            "collection_headline": "The street",
            "collection_code": group.code,
            "email": "lili@your-domain.test",
            "approved": True,
        }
        invite = _body("lili@your-domain.test")
        assert owner.name in _text(invite)
        assert member.name in _text(invite)

    def test_declining_tells_the_proposer_in_the_app_and_by_email_and_nothing_else(
        self, group, member, owner, proposal
    ):
        mail.outbox.clear()

        svc.reject_proposal(proposal)

        notice = InAppNotification.objects.get(
            user=member, type=InAppNotification.Type.INVITE_PROPOSAL_DECLINED
        )
        assert notice.payload == {
            "collection_headline": "The street",
            "collection_code": group.code,
            "owner_name": "Lala",
            "email": "lili@your-domain.test",
        }
        sent = _body(member.email)
        assert "Lala" in _text(sent)
        assert "The street" in _text(sent)
        assert "lili@your-domain.test" in _text(sent)
        assert sent.subject == T("proposal_declined_subject", lang="es").format(
            collection="The street"
        )
        assert [m.to for m in mail.outbox] == [[member.email]]


class TestClearingADecidedProposal:
    def test_only_that_proposals_notices_and_links_go(self, group, member, owner):
        proposal, _, _ = svc.create_proposal(group, member, "lili@your-domain.test")
        bystander = InAppNotification.objects.create(
            user=owner,
            type=InAppNotification.Type.INVITE_PROPOSAL_APPROVED,
            payload={"proposal_code": proposal.code},
        )
        other_link = RSVP.objects.create(
            user_code=owner,
            user_email=owner.email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=proposal.code,
        )

        svc.clear_proposal_traces(proposal)

        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.INVITE_PROPOSED, payload__proposal_code=proposal.code
        ).exists()
        assert not RSVP.objects.filter(
            target_code=proposal.code, action=RSVP.Action.PROPOSAL_APPROVE
        ).exists()
        assert InAppNotification.objects.filter(pk=bystander.pk).exists()
        assert RSVP.objects.filter(pk=other_link.pk).exists()
