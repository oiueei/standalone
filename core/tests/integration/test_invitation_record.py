"""One invitation per person: the record that makes the invitation email's promise true.

The email tells the invited person that, whether they decline or do nothing, whoever
invited them cannot invite them by email again for a year. These tests hold that
promise from each side: who is refused, who is not, and that the refusal leaves
nothing behind (no account, no link, no email, no quota spent).
"""

import importlib
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, InvitationProposal, InvitationRecord, User
from core.models.invitation_record import address_hash
from core.models.notification import InAppNotification
from core.services.invitation_service import (
    InvitationAlreadyAsked,
    _invite_quota_left,
    deliver_invitation,
)

INVITE_URL = "/api/v1/collections/{code}/invite/"
BULK_URL = "/api/v1/collections/{code}/invite/bulk/"
GUEST = "guest@your-domain.test"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner(db):
    return User.objects.create(code="OWNR01", email="lala@your-domain.test", name="Lala")


@pytest.fixture
def group(owner):
    return Collection.objects.create(
        code="GRP001", owner=owner, headline="The street", allow_member_proposals=True
    )


@pytest.fixture
def other_group(owner):
    return Collection.objects.create(code="GRP002", owner=owner, headline="The square")


def invite(group, email=GUEST, by=None):
    return client_for(by or group.owner).post(
        INVITE_URL.format(code=group.code), {"email": email}, format="json"
    )


def answer(email, action):
    """Press the accept or decline link of the pending invitation, as the mail does."""
    rsvp = RSVP.objects.get(user_email=email, action=action)
    return APIClient().get(f"/api/v1/auth/verify/{rsvp.token}/")


def record_of(group, email=GUEST):
    return InvitationRecord.objects.get(founder=group.owner, address_hash=address_hash(email))


def assert_refused(response):
    assert response.status_code == 400
    assert response.data["code"] == "invite_already_asked"


class TestWhoIsRefused:
    def test_a_declined_invitation_cannot_be_sent_again(self, group):
        assert invite(group).status_code == 200
        answer(GUEST, RSVP.Action.COLLECTION_REJECT)
        mail.outbox.clear()

        assert_refused(invite(group))
        assert mail.outbox == []

    def test_a_declined_invitation_blocks_the_same_founders_other_groups(self, group, other_group):
        invite(group)
        answer(GUEST, RSVP.Action.COLLECTION_REJECT)
        mail.outbox.clear()

        assert_refused(invite(other_group))
        assert mail.outbox == []

    def test_an_invitation_nobody_answered_cannot_be_sent_again(self, group):
        invite(group)
        mail.outbox.clear()

        assert_refused(invite(group))
        assert mail.outbox == []
        assert (
            RSVP.objects.filter(user_email=GUEST, action=RSVP.Action.COLLECTION_INVITE).count() == 1
        )

    def test_an_unanswered_invitation_blocks_the_same_founders_other_groups(
        self, group, other_group
    ):
        invite(group)

        assert_refused(invite(other_group))

    def test_declining_marks_the_record_with_when(self, group):
        invite(group)
        assert record_of(group).state == InvitationRecord.State.SENT

        answer(GUEST, RSVP.Action.COLLECTION_REJECT)

        record = record_of(group)
        assert record.state == InvitationRecord.State.DECLINED
        assert record.resolved_at is not None

    def test_a_refusal_creates_no_account_no_link_and_spends_no_quota(self, group):
        """The record outlives the guest account (60 days); an invitation to that address
        must not bring the account back, mint a link or cost the inviter a send."""
        invite(group)
        guest = User.objects.get(email=GUEST)
        guest.delete()
        mail.outbox.clear()
        settings = {"RATELIMIT_ENABLE": True, "INVITE_EMAILS_PER_DAY": 5}

        with override_settings(**settings):
            cache.clear()
            before = _invite_quota_left(group.owner.code)
            response = invite(group)
            after = _invite_quota_left(group.owner.code)

        assert_refused(response)
        assert not User.objects.filter(email=GUEST).exists()
        assert not RSVP.objects.filter(user_email=GUEST).exists()
        assert mail.outbox == []
        assert before == after == 5

    def test_the_record_keeps_a_fingerprint_never_the_address(self, group):
        invite(group, "Guest@Your-Domain.test")

        record = record_of(group)

        assert record.address_hash == address_hash(GUEST)
        assert len(record.address_hash) == 64
        for value in (record.address_hash, str(record), record.state):
            assert "guest" not in value.lower()
        assert not any(
            "guest@" in str(value) for value in InvitationRecord.objects.values_list().first()
        )

    def test_the_fingerprint_does_not_depend_on_how_the_address_is_cased(self):
        assert address_hash("Guest@Your-Domain.test") == address_hash(GUEST)
        assert address_hash(GUEST) != address_hash("other@your-domain.test")

    def test_a_co_curators_guest_who_declined_cannot_be_invited_from_their_own_group(
        self, group, owner
    ):
        curator = User.objects.create(code="CURA01", email="lele@your-domain.test", name="Lele")
        group.invites.add(curator)
        group.co_owners.add(curator)
        assert invite(group, by=curator).status_code == 200
        answer(GUEST, RSVP.Action.COLLECTION_REJECT)
        assert record_of(group).inviter == curator
        own = Collection.objects.create(code="CURGRP", owner=curator, headline="Mine")

        assert_refused(invite(own, by=curator))

    def test_the_founder_cannot_invite_a_guest_a_co_curator_already_asked(self, group, owner):
        curator = User.objects.create(code="CURA01", email="lele@your-domain.test", name="Lele")
        group.invites.add(curator)
        group.co_owners.add(curator)
        assert invite(group, by=curator).status_code == 200

        assert_refused(invite(group, by=owner))

    def test_another_founder_can_still_invite_them(self, group):
        invite(group)
        answer(GUEST, RSVP.Action.COLLECTION_REJECT)
        stranger = User.objects.create(code="OWNR02", email="lolo@your-domain.test", name="Lolo")
        theirs = Collection.objects.create(code="OTHGRP", owner=stranger, headline="Theirs")

        assert invite(theirs).status_code == 200
        assert InvitationRecord.objects.filter(address_hash=address_hash(GUEST)).count() == 2

    def test_someone_already_in_the_group_is_told_so_not_that_they_were_asked(self, group):
        invite(group)
        guest = User.objects.get(email=GUEST)
        group.invites.add(guest)

        response = invite(group)

        assert response.status_code == 400
        assert response.data["code"] == "already_invited"


class TestWhoIsNot:
    def test_someone_who_accepted_can_be_invited_to_another_group_of_the_same_founder(
        self, group, other_group
    ):
        invite(group)
        answer(GUEST, RSVP.Action.COLLECTION_INVITE)
        assert record_of(group).state == InvitationRecord.State.ACCEPTED

        assert invite(other_group).status_code == 200

        assert record_of(group).state == InvitationRecord.State.SENT
        assert record_of(group).resolved_at is None

    def test_joining_by_link_after_ignoring_the_invitation_works_and_is_accepted(self, group):
        group.visibility = Collection.Visibility.PUBLIC
        group.save()
        invite(group)

        response = client_for(User.objects.get(email=GUEST)).post(
            f"/api/v1/collections/{group.code}/join/"
        )

        assert response.status_code == 200
        assert group.invites.filter(email=GUEST).exists()
        record = record_of(group)
        assert record.state == InvitationRecord.State.ACCEPTED
        assert record.resolved_at is not None

    def test_joining_by_link_after_declining_is_not_blocked_either(self, group):
        group.visibility = Collection.Visibility.PUBLIC
        group.save()
        invite(group)
        answer(GUEST, RSVP.Action.COLLECTION_REJECT)

        response = client_for(User.objects.get(email=GUEST)).post(
            f"/api/v1/collections/{group.code}/join/"
        )

        assert response.status_code == 200
        assert record_of(group).state == InvitationRecord.State.ACCEPTED


class TestAnInvitationWaitingWhileTheFounderInvitesElsewhere:
    def test_joining_another_group_then_being_invited_again_leaves_one_live_pair(
        self, group, other_group
    ):
        """Pending in A, the person joins B (same founder) by link, which marks the
        founder's record accepted; inviting them to A again must not stack a second pair."""
        other_group.visibility = Collection.Visibility.PUBLIC
        other_group.save()
        invite(group)
        client_for(User.objects.get(email=GUEST)).post(
            f"/api/v1/collections/{other_group.code}/join/"
        )
        assert record_of(group).state == InvitationRecord.State.ACCEPTED

        assert invite(group).status_code == 200

        for action in (RSVP.Action.COLLECTION_INVITE, RSVP.Action.COLLECTION_REJECT):
            assert (
                RSVP.objects.filter(user_email=GUEST, target_code=group.code, action=action).count()
                == 1
            )
        assert record_of(group).state == InvitationRecord.State.SENT

    def test_the_record_is_written_before_the_email_leaves(self, group):
        seen = []

        def spy(*args, **kwargs):
            seen.append(InvitationRecord.objects.filter(address_hash=address_hash(GUEST)).count())

        with patch("core.services.invitation_service.send_collection_invite_email", spy):
            deliver_invitation(group, GUEST, "Lala")

        assert seen == [1]


class TestBulk:
    def test_an_address_already_invited_is_skipped_as_already_asked(self, group):
        invite(group, "lili@your-domain.test")
        mail.outbox.clear()

        response = client_for(group.owner).post(
            BULK_URL.format(code=group.code),
            {"invites": [{"email": "lili@your-domain.test"}, {"email": "lulu@your-domain.test"}]},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["invited"] == 1
        assert response.data["skipped"] == [
            {"email": "lili@your-domain.test", "reason": "already_asked"}
        ]
        assert [m.to for m in mail.outbox] == [["lulu@your-domain.test"]]

    def test_a_bulk_invitation_is_recorded_like_a_single_one(self, group):
        client_for(group.owner).post(
            BULK_URL.format(code=group.code), {"invites": [{"email": GUEST}]}, format="json"
        )

        assert record_of(group).state == InvitationRecord.State.SENT
        assert_refused(invite(group))

    def test_an_address_whose_account_is_gone_is_skipped_without_bringing_it_back(self, group):
        invite(group)
        User.objects.get(email=GUEST).delete()

        response = client_for(group.owner).post(
            BULK_URL.format(code=group.code), {"invites": [{"email": GUEST}]}, format="json"
        )

        assert response.data["skipped"] == [{"email": GUEST, "reason": "already_asked"}]
        assert not User.objects.filter(email=GUEST).exists()


def _approve_in_app(group, proposal):
    return client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")


def _approve_by_email_link(group, proposal):
    rsvp = RSVP.objects.get(target_code=proposal.code, action=RSVP.Action.PROPOSAL_APPROVE)
    return APIClient().post(f"/api/v1/rsvp/{rsvp.token}/")


class TestRecommendations:
    @pytest.mark.parametrize("approve", [_approve_in_app, _approve_by_email_link])
    def test_approving_someone_already_asked_is_refused_by_both_routes(self, group, approve):
        member = User.objects.create(code="MEMB01", email="lele@your-domain.test", name="Lele")
        group.invites.add(member)
        invite(group)
        answer(GUEST, RSVP.Action.COLLECTION_REJECT)
        client_for(member).post(
            f"/api/v1/collections/{group.code}/invite/propose/", {"email": GUEST}, format="json"
        )
        proposal = InvitationProposal.objects.get(collection=group, email=GUEST)
        mail.outbox.clear()

        response = approve(group, proposal)

        assert response.status_code == 400
        assert response.data["code"] == "invite_already_asked"
        # Not "come back later": the block lasts a year, so the page must not say so.
        assert "retryable" not in response.data
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.PENDING
        assert mail.outbox == []

    @pytest.mark.parametrize("approve", [_approve_in_app, _approve_by_email_link])
    def test_a_refused_approval_leaves_the_link_alive_to_be_declined(self, group, approve):
        member = User.objects.create(code="MEMB01", email="lele@your-domain.test", name="Lele")
        group.invites.add(member)
        invite(group)
        client_for(member).post(
            f"/api/v1/collections/{group.code}/invite/propose/", {"email": GUEST}, format="json"
        )
        proposal = InvitationProposal.objects.get(collection=group, email=GUEST)

        approve(group, proposal)

        assert RSVP.objects.filter(
            target_code=proposal.code, action=RSVP.Action.PROPOSAL_REJECT
        ).exists()
        assert (
            client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/reject/").status_code
            == 200
        )

    def test_an_approved_recommendation_is_recorded_on_the_owners_account(self, group):
        member = User.objects.create(code="MEMB01", email="lele@your-domain.test", name="Lele")
        group.invites.add(member)
        client_for(member).post(
            f"/api/v1/collections/{group.code}/invite/propose/", {"email": GUEST}, format="json"
        )
        proposal = InvitationProposal.objects.get(collection=group, email=GUEST)

        assert _approve_in_app(group, proposal).status_code == 200

        record = record_of(group)
        assert record.inviter == group.owner
        assert record.state == InvitationRecord.State.SENT


class TestARaceBetweenTheCheckAndTheSend:
    @pytest.mark.parametrize("approve", [_approve_in_app, _approve_by_email_link])
    def test_an_invitation_that_gets_in_between_is_the_same_refusal_not_a_500(self, group, approve):
        member = User.objects.create(code="MEMB01", email="lele@your-domain.test", name="Lele")
        group.invites.add(member)
        client_for(member).post(
            f"/api/v1/collections/{group.code}/invite/propose/", {"email": GUEST}, format="json"
        )
        proposal = InvitationProposal.objects.get(collection=group, email=GUEST)
        mail.outbox.clear()

        # Free when the approval is checked, taken by the time it is delivered.
        with patch(
            "core.services.invitation_service.invitation_blocked", side_effect=[False, True]
        ):
            response = approve(group, proposal)

        assert response.status_code == 400
        assert response.data["code"] == "invite_already_asked"
        assert "retryable" not in response.data
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.PENDING
        assert proposal.resolved is None
        assert mail.outbox == []
        assert not InAppNotification.objects.filter(
            user=member, type=InAppNotification.Type.INVITE_PROPOSAL_APPROVED
        ).exists()

    def test_the_exception_carries_no_address(self, group):
        invite(group)

        with pytest.raises(InvitationAlreadyAsked) as raised:
            deliver_invitation(group, GUEST, "Lala")

        assert GUEST not in repr(raised.value)
        assert raised.value.args == ()


class TestTheDataMigration:
    def test_a_live_invitation_becomes_a_sent_record_and_a_stale_one_is_left_out(
        self, group, owner
    ):
        migration = importlib.import_module("core.migrations.0170_invitation_records")
        guest = User.objects.create(email=GUEST)
        sent = timezone.now() - timedelta(days=3)
        live = RSVP.objects.create(
            user_code=guest,
            user_email=GUEST,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=group.code,
        )
        RSVP.objects.filter(pk=live.pk).update(created=sent)
        RSVP.objects.create(
            user_code=guest,
            user_email=GUEST,
            action=RSVP.Action.COLLECTION_REJECT,
            target_code=group.code,
        )
        RSVP.objects.create(
            user_code=guest,
            user_email=GUEST,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code="GONE01",
        )

        migration.record_live_invitations(apps, None)
        migration.record_live_invitations(apps, None)  # running twice adds nothing

        record = InvitationRecord.objects.get()
        assert (record.founder, record.inviter) == (owner, owner)
        assert record.address_hash == address_hash(GUEST)
        assert record.state == InvitationRecord.State.SENT
        assert record.sent_at == sent
        assert_refused(invite(group))

    def test_a_member_who_joined_by_link_with_the_invitation_still_alive_is_not_recorded(
        self, group, other_group
    ):
        """Joining by link leaves the invitation's RSVP behind; recorded as waiting, that
        person could not be invited by this founder to another group."""
        migration = importlib.import_module("core.migrations.0170_invitation_records")
        member = User.objects.create(email="member@your-domain.test")
        group.invites.add(member)
        RSVP.objects.create(
            user_code=member,
            user_email=member.email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=group.code,
        )
        waiting = User.objects.create(email=GUEST)
        RSVP.objects.create(
            user_code=waiting,
            user_email=GUEST,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=group.code,
        )

        migration.record_live_invitations(apps, None)

        assert list(InvitationRecord.objects.values_list("address_hash", flat=True)) == [
            address_hash(GUEST)
        ]
        assert invite(other_group, member.email).status_code == 200
