"""A member proposes, the owner decides, and nobody is contacted before that.

Members could not bring anyone in at all: every new person cost an owner action.
But an owner is not merely a bottleneck to route around — the group may be
closed, may run on subscriptions, papers or rules of admission the product knows
nothing about. So a member suggests and the owner answers, and the guarantee
these tests exist to hold is the ordering: **the proposed address learns nothing
until the owner says yes.**
"""

from unittest.mock import patch

import pytest
from django.core import mail
from django.core.cache import caches
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, Event, InvitationProposal, User
from core.models.notification import InAppNotification
from core.services.invitation_service import deliver_invitation

PROPOSE_URL = "/api/v1/collections/{code}/invite/propose/"
CO_OWNERS_URL = "/api/v1/collections/{code}/co-owners/"

# The quota follows RATELIMIT_ENABLE, which the test settings turn off; switch it
# on with a local-memory cache, the same way test_invite_quota.py does.
QUOTA_SETTINGS = {
    "RATELIMIT_ENABLE": True,
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "proposal-quota-test",
        }
    },
}


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def member(db):
    return User.objects.create(code="MEMB01", email="lele@your-domain.test", name="Lele")


@pytest.fixture
def group(db, member):
    owner = User.objects.create(code="OWNR01", email="lala@your-domain.test", name="Lala")
    # Proposals are off for a new collection since 2026-10-02; this group is the
    # one where its owner turned them on, which is what every test here is about.
    collection = Collection.objects.create(
        code="GRP001", owner=owner, headline="The street", allow_member_proposals=True
    )
    collection.invites.add(member)
    return collection


@pytest.mark.django_db
class TestProposing:
    def test_a_member_can_suggest_someone_and_nothing_reaches_them(self, group, member):
        """The whole point: the proposal goes to the owner, not to the guest.

        If the owner says no, the person suggested must never learn they were —
        so at this stage there is no email to them and not even a User row.
        """
        mail.outbox.clear()
        resp = client_for(member).post(
            PROPOSE_URL.format(code=group.code),
            {"email": "lele11@your-domain.test", "note": "my downstairs neighbour"},
            format="json",
        )

        assert resp.status_code == 200
        proposal = InvitationProposal.objects.get(collection=group)
        assert proposal.email == "lele11@your-domain.test"
        assert proposal.status == InvitationProposal.Status.PENDING

        assert not User.objects.filter(email="lele11@your-domain.test").exists(), (
            "the proposed person must not exist as an account yet"
        )
        recipients = [addr for m in mail.outbox for addr in m.to]
        assert "lele11@your-domain.test" not in recipients, (
            "the proposed person must not be emailed"
        )
        assert group.owner.email in recipients, "the owner is the one who has to decide"

    def test_the_owner_is_told_in_the_app_too_with_the_note(self, group, member):
        """The owner needs the proposer's word to decide — an address alone is
        nothing to go on when the group has rules of admission."""
        client_for(member).post(
            PROPOSE_URL.format(code=group.code),
            {"email": "lele11@your-domain.test", "note": "she's paid the subs"},
            format="json",
        )

        note = InAppNotification.objects.get(
            user=group.owner, type=InAppNotification.Type.INVITE_PROPOSED
        )
        assert note.payload["email"] == "lele11@your-domain.test"
        assert note.payload["note"] == "she's paid the subs"
        assert note.payload["proposer_name"] == "Lele"

    def test_a_stranger_cannot_propose(self, group, db):
        outsider = User.objects.create(code="OUTS01", email="lolo@your-domain.test")
        resp = client_for(outsider).post(
            PROPOSE_URL.format(code=group.code), {"email": "lala1@your-domain.test"}, format="json"
        )
        assert resp.status_code == 400
        assert InvitationProposal.objects.count() == 0

    def test_the_owner_can_switch_proposals_off(self, group, member):
        """`allow_member_proposals` is the owner saying they don't want to be
        asked at all — a group with a waiting list or an admission process may
        not want the question raised every week."""
        group.allow_member_proposals = False
        group.save(update_fields=["allow_member_proposals"])

        resp = client_for(member).post(
            PROPOSE_URL.format(code=group.code), {"email": "lele11@your-domain.test"}, format="json"
        )

        assert resp.status_code == 403
        assert InvitationProposal.objects.count() == 0

    def test_the_same_person_cannot_be_queued_twice(self, group, member):
        url = PROPOSE_URL.format(code=group.code)
        first = client_for(member).post(url, {"email": "lele1@your-domain.test"}, format="json")
        assert first.status_code == 200
        second = client_for(member).post(url, {"email": "lele1@your-domain.test"}, format="json")
        assert second.status_code == 400
        assert InvitationProposal.objects.filter(email="lele1@your-domain.test").count() == 1

    def test_the_owner_is_sent_to_the_real_invite_instead(self, group):
        """An owner has the actual invitation one endpoint over. Queuing a
        suggestion for themselves to approve would be a round trip to nowhere."""
        resp = client_for(group.owner).post(
            PROPOSE_URL.format(code=group.code), {"email": "lele11@your-domain.test"}, format="json"
        )

        assert resp.status_code == 400
        assert "invite them directly" in str(resp.data)
        assert InvitationProposal.objects.count() == 0

    def test_suggesting_somebody_already_in_the_group_is_refused(self, group, member):
        """Answered here rather than by the owner: it needs no decision."""
        resp = client_for(member).post(
            PROPOSE_URL.format(code=group.code), {"email": member.email}, format="json"
        )

        assert resp.status_code == 400
        assert InvitationProposal.objects.count() == 0

    def test_an_address_already_inside_is_answered_exactly_like_one_merely_queued(
        self, group, member
    ):
        """The refusal must not say **which** of the two it was.

        Split, the membership branch was an oracle: a member could put any
        address to this endpoint, 30 a day, and read a yes/no on whether it
        belongs to a co-member. The roster a non-owner receives carries `code`
        and `name` and no email precisely so those addresses stay the owner's to
        see, and this handed the same fact back one guess at a time. So the
        two answers have to be byte-identical — a difference in wording, status
        or shape is the whole vulnerability.
        """
        url = PROPOSE_URL.format(code=group.code)
        client_for(member).post(url, {"email": "lili@your-domain.test"}, format="json")

        inside = client_for(member).post(url, {"email": member.email}, format="json")
        queued = client_for(member).post(url, {"email": "lili@your-domain.test"}, format="json")

        founder = client_for(member).post(url, {"email": group.owner.email}, format="json")

        assert inside.status_code == queued.status_code == founder.status_code == 400
        assert inside.data == queued.data == founder.data
        # And a stranger nobody has mentioned still gets a *different* answer —
        # otherwise this test would pass on an endpoint that refused everything.
        fresh = client_for(member).post(url, {"email": "lolo1@your-domain.test"}, format="json")
        assert fresh.status_code == 200


@pytest.mark.django_db
class TestDeciding:
    def _propose(self, group, member, email="lele11@your-domain.test"):
        client_for(member).post(
            PROPOSE_URL.format(code=group.code), {"email": email}, format="json"
        )
        return InvitationProposal.objects.get(collection=group, email=email)

    def test_approving_sends_the_real_invitation(self, group, member):
        proposal = self._propose(group, member)
        mail.outbox.clear()

        resp = client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")

        assert resp.status_code == 200
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.APPROVED
        # Indistinguishable from an owner's own invite: same RSVP pair.
        assert RSVP.objects.filter(
            user_email="lele11@your-domain.test",
            target_code=group.code,
            action=RSVP.Action.COLLECTION_INVITE,
        ).exists()
        assert "lele11@your-domain.test" in [addr for m in mail.outbox for addr in m.to]

    def test_the_invitation_says_who_suggested_them(self, group, member):
        """Lili knows Lele, not Lala.

        Without this line the invitation reads as an email from a stranger, which
        is the difference between a recommendation and a cold approach. The
        invitation is still the owner's — the proposer is context, not authorship.
        """
        proposal = self._propose(group, member)
        mail.outbox.clear()

        client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")

        sent = next(m for m in mail.outbox if "lele11@your-domain.test" in m.to)
        assert "Lele" in sent.body

    def test_a_nameless_proposer_is_not_outed_by_their_email_address(self, group, member):
        """`display_name` falls back to the email, and this message goes to a
        third party outside the group. A proposer who never set a name must lose
        the line, not have their address forwarded to a stranger."""
        member.name = ""
        member.save(update_fields=["name"])
        proposal = self._propose(group, member)
        mail.outbox.clear()

        client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")

        sent = next(m for m in mail.outbox if "lele11@your-domain.test" in m.to)
        assert member.email not in sent.body
        assert member.email not in str(sent.alternatives)

    def test_the_note_is_for_the_owner_only(self, group, member):
        """The proposer's word about somebody is written for the owner's decision.
        It must not travel on to the person it describes."""
        client_for(member).post(
            PROPOSE_URL.format(code=group.code),
            {"email": "lele11@your-domain.test", "note": "she can be a bit much but she's sound"},
            format="json",
        )
        proposal = InvitationProposal.objects.get(collection=group)
        mail.outbox.clear()

        client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")

        sent = next(m for m in mail.outbox if "lele11@your-domain.test" in m.to)
        assert "a bit much" not in sent.body
        assert "a bit much" not in str(sent.alternatives)

    def test_declining_tells_the_proposer_and_never_the_proposed(self, group, member):
        """Say no clearly, give no reason.

        Silence would leave the member waiting and asking again. A reason would
        either put words in the owner's mouth or turn a quiet no into an
        argument — the group's rules are not the product's business.
        """
        proposal = self._propose(group, member)
        mail.outbox.clear()

        resp = client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/reject/")

        assert resp.status_code == 200
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.REJECTED

        recipients = [addr for m in mail.outbox for addr in m.to]
        assert member.email in recipients, "the proposer is told"
        assert "lele11@your-domain.test" not in recipients, "the proposed person is never contacted"
        assert not User.objects.filter(email="lele11@your-domain.test").exists()

        note = InAppNotification.objects.get(
            user=member, type=InAppNotification.Type.INVITE_PROPOSAL_DECLINED
        )
        assert "reason" not in note.payload

    def test_the_proposer_cannot_approve_their_own_suggestion(self, group, member):
        """Otherwise the approval is theatre and the owner's gate is not a gate."""
        proposal = self._propose(group, member)

        resp = client_for(member).post(f"/api/v1/proposals/{proposal.code}/approve/")

        assert resp.status_code == 403
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.PENDING
        assert not User.objects.filter(email="lele11@your-domain.test").exists()

    def test_a_decision_cannot_be_made_twice(self, group, member):
        proposal = self._propose(group, member)
        owner_client = client_for(group.owner)
        assert owner_client.post(f"/api/v1/proposals/{proposal.code}/approve/").status_code == 200
        again = owner_client.post(f"/api/v1/proposals/{proposal.code}/reject/")
        assert again.status_code == 400


@pytest.mark.django_db
class TestTheEmailLinks:
    """The owner's other route: the approve/reject links in the email."""

    def _proposal_rsvps(self, group, member):
        client_for(member).post(
            PROPOSE_URL.format(code=group.code), {"email": "lele11@your-domain.test"}, format="json"
        )
        proposal = InvitationProposal.objects.get(collection=group)
        approve = RSVP.objects.get(target_code=proposal.code, action=RSVP.Action.PROPOSAL_APPROVE)
        reject = RSVP.objects.get(target_code=proposal.code, action=RSVP.Action.PROPOSAL_REJECT)
        return proposal, approve, reject

    def test_a_get_only_previews_so_a_link_scanner_cannot_invite_anyone(self, group, member):
        """Approving mails a third party. A mail client prefetching the link must
        not be able to do that on the owner's behalf — the same guard the booking
        decisions use."""
        proposal, approve, _ = self._proposal_rsvps(group, member)
        mail.outbox.clear()

        resp = APIClient().get(f"/api/v1/rsvp/{approve.token}/")

        assert resp.status_code == 200
        assert resp.data["requires_confirmation"] is True
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.PENDING
        assert mail.outbox == [], "a bare GET must send nothing"
        assert not User.objects.filter(email="lele11@your-domain.test").exists()

    def test_the_get_preview_carries_none_of_the_proposed_persons_details(self, group, member):
        """A GET is what a mail client's link scanner issues. The proposed
        address, the proposer's private note and the proposer's name (its display
        fallback is *their* email) are exactly what this flow promises never to
        leak — the person suggested does not know they were suggested. The
        preview must answer 'a decision is needed' and nothing more; the SPA
        auto-commits with a POST and reads the address it shows from that."""
        client_for(member).post(
            PROPOSE_URL.format(code=group.code),
            {"email": "lele11@your-domain.test", "note": "she still owes me twenty euros"},
            format="json",
        )
        proposal = InvitationProposal.objects.get(collection=group)
        tokens = RSVP.objects.filter(
            target_code=proposal.code,
            action__in=[RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT],
        ).values_list("token", flat=True)

        for token in tokens:
            resp = APIClient().get(f"/api/v1/rsvp/{token}/")
            assert resp.status_code == 200
            assert set(resp.data) == {"action", "requires_confirmation"}
            blob = str(resp.data)
            assert "lele11@your-domain.test" not in blob
            assert "still owes me" not in blob
            assert "Lele" not in blob  # the proposer's name

    def test_a_post_commits_and_burns_both_links(self, group, member):
        proposal, approve, reject = self._proposal_rsvps(group, member)

        resp = APIClient().post(f"/api/v1/rsvp/{approve.token}/")

        assert resp.status_code == 200
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.APPROVED
        # The other link must not still work on a settled decision.
        assert not RSVP.objects.filter(
            target_code=proposal.code,
            action__in=[RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT],
        ).exists()
        assert APIClient().post(f"/api/v1/rsvp/{reject.token}/").status_code == 401

    def test_the_no_link_declines_and_burns_both_too(self, group, member):
        """The other half of the owner's email, and the one that had never been
        exercised: every test above posts the *approve* token.

        Saying no from the mail client must reach exactly the same place as
        saying no in the app — the proposer told, the proposed person never
        contacted, and neither link left alive.
        """
        proposal, approve, reject = self._proposal_rsvps(group, member)
        mail.outbox.clear()

        resp = APIClient().post(f"/api/v1/rsvp/{reject.token}/")

        assert resp.status_code == 200
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.REJECTED

        recipients = [addr for m in mail.outbox for addr in m.to]
        assert member.email in recipients, "the proposer is told"
        assert "lele11@your-domain.test" not in recipients, "the proposed person is never contacted"
        assert not User.objects.filter(email="lele11@your-domain.test").exists()
        assert not RSVP.objects.filter(
            target_code=proposal.code,
            action__in=[RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT],
        ).exists()
        assert APIClient().post(f"/api/v1/rsvp/{approve.token}/").status_code == 401

    def test_a_link_to_a_settled_suggestion_says_so_and_dies(self, group, member):
        """Two links reach one decision, and an owner may have both open — in the
        app and in their mail. The second one to arrive must not re-run it."""
        proposal, approve, reject = self._proposal_rsvps(group, member)
        client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/reject/")
        # The in-app path burns the pair, so mint a link that outlived its
        # decision the way a forwarded or cached one would.
        stale = RSVP.objects.create(
            user_code=group.owner,
            user_email=group.owner.email,
            action=RSVP.Action.PROPOSAL_APPROVE,
            target_code=proposal.code,
        )
        mail.outbox.clear()

        resp = APIClient().post(f"/api/v1/rsvp/{stale.token}/")

        assert resp.status_code == 400
        assert "no longer pending" in str(resp.data)
        # The other 400: this one really is over, and must not invite the owner
        # to try again — the link is gone and the decision already stands.
        assert "retryable" not in resp.data
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.REJECTED
        assert mail.outbox == [], "a settled suggestion must not invite anybody"
        assert not RSVP.objects.filter(code=stale.code).exists(), "the dead link is consumed"


@pytest.mark.django_db
class TestQuota:
    @patch("core.services.invitation_service.send_collection_invite_email")
    def test_an_approved_invitation_is_charged_to_the_owner(self, mock_send, group, member):
        """The email leaves the owner's group under
        the deployment's sending domain, so it is the owner's daily allowance it
        spends — not the member's, who cannot send anything on their own."""
        client_for(member).post(
            PROPOSE_URL.format(code=group.code), {"email": "lele11@your-domain.test"}, format="json"
        )
        proposal = InvitationProposal.objects.get(collection=group)

        with patch("core.services.invitation_service._consume_invite_quota") as consume:
            client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")

        consume.assert_called_once_with(group.owner_id, 1)


# ── The two guards on approval, on BOTH of the owner's routes ────────────────
#
# An approval sends an email to a third party and adds a member, so it answers
# to the operator's daily cap and the collection's member ceiling. There are two
# ways for the owner to approve — the in-app button and the emailed link — and
# the link used to apply neither, which made the cap walkable by clicking the
# mail instead of the app. These run every case against both doors.


def _proposal_for(group, member, email="lele11@your-domain.test"):
    client_for(member).post(PROPOSE_URL.format(code=group.code), {"email": email}, format="json")
    return InvitationProposal.objects.get(collection=group, email=email)


def _approve_in_app(group, proposal):
    return client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/approve/")


def _approve_by_email_link(group, proposal):
    rsvp = RSVP.objects.get(target_code=proposal.code, action=RSVP.Action.PROPOSAL_APPROVE)
    return APIClient().post(f"/api/v1/rsvp/{rsvp.token}/")


BOTH_DOORS = [
    pytest.param(_approve_in_app, id="in-app"),
    pytest.param(_approve_by_email_link, id="email-link"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("approve", BOTH_DOORS)
@override_settings(**QUOTA_SETTINGS, INVITE_EMAILS_PER_DAY=1)
def test_an_exhausted_daily_quota_refuses_the_approval(approve, group, member):
    """`INVITE_EMAILS_PER_DAY` guards a deployment's sending reputation, so it
    cannot depend on which of the two doors the owner happens to use.

    The email link used to skip this check entirely: an owner with a mailbox
    full of pending suggestions could approve every one past the cap.
    """
    caches["default"].clear()
    proposal = _proposal_for(group, member)
    # Spend the day's single allowance on an ordinary invite.
    with patch("core.services.invitation_service.send_collection_invite_email"):
        assert (
            client_for(group.owner)
            .post(
                f"/api/v1/collections/{group.code}/invite/",
                {"email": "lulu2@your-domain.test"},
                "json",
            )
            .status_code
            == 200
        )
    mail.outbox.clear()

    resp = approve(group, proposal)

    assert resp.status_code == 429
    proposal.refresh_from_db()
    assert proposal.status == InvitationProposal.Status.PENDING, (
        "a refused approval decides nothing"
    )
    assert not User.objects.filter(email="lele11@your-domain.test").exists()
    assert mail.outbox == [], "nothing may reach the proposed address"


@pytest.mark.django_db
@pytest.mark.parametrize("approve", BOTH_DOORS)
@override_settings(**QUOTA_SETTINGS, INVITE_EMAILS_PER_DAY=1)
def test_a_refused_approval_leaves_the_owner_a_way_back(approve, group, member):
    """ "Not now", not "never": the suggestion and both its links survive, so the
    owner can answer tomorrow instead of asking the member to suggest again.

    And the answer has to *say* so. The owner reading it is looking at a screen,
    not at the database: a refusal that keeps the link alive and one that
    consumes it both arrive as a 4xx with a sentence in it, so without
    ``retryable`` the SPA cannot tell them apart — and the emailed-link screen
    called this one "invalid or expired link", which is the one thing it is not.
    """
    caches["default"].clear()
    proposal = _proposal_for(group, member)
    with patch("core.services.invitation_service.send_collection_invite_email"):
        client_for(group.owner).post(
            f"/api/v1/collections/{group.code}/invite/", {"email": "lulu2@your-domain.test"}, "json"
        )

    resp = approve(group, proposal)

    assert resp.status_code == 429
    assert resp.data["retryable"] is True, "the owner must be told to come back, not to give up"

    assert RSVP.objects.filter(
        target_code=proposal.code, action=RSVP.Action.PROPOSAL_APPROVE
    ).exists()
    assert RSVP.objects.filter(
        target_code=proposal.code, action=RSVP.Action.PROPOSAL_REJECT
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("approve", BOTH_DOORS)
@override_settings(COLLECTION_INVITES_BLOCK=2)
def test_a_full_collection_refuses_the_approval(approve, group, member):
    """The member ceiling is checked where invitations are *sent*, so approving
    one is exactly where it bites. Both doors, for the same reason as the quota.
    """
    group.invites.add(User.objects.create(email="lele5@your-domain.test"))
    proposal = _proposal_for(group, member)
    mail.outbox.clear()

    resp = approve(group, proposal)

    assert resp.status_code == 400
    assert "reached its limit" in str(resp.data)
    # A 400 that the owner can retry, unlike the 400 a settled suggestion gives:
    # the seat may free up, and the link is still theirs to use when it does.
    assert resp.data["retryable"] is True
    proposal.refresh_from_db()
    assert proposal.status == InvitationProposal.Status.PENDING
    assert not User.objects.filter(email="lele11@your-domain.test").exists()
    assert mail.outbox == []


@pytest.mark.django_db
@pytest.mark.parametrize("approve", BOTH_DOORS)
@override_settings(COLLECTION_INVITES_BLOCK=2)
def test_declining_is_never_blocked_by_a_full_collection(approve, group, member):
    """Saying no adds nobody and sends one email to a member who is already
    inside the count. A ceiling that stopped the owner clearing their queue
    would leave them with a queue they cannot answer."""
    group.invites.add(User.objects.create(email="lele5@your-domain.test"))
    proposal = _proposal_for(group, member)

    resp = client_for(group.owner).post(f"/api/v1/proposals/{proposal.code}/reject/")

    assert resp.status_code == 200
    proposal.refresh_from_db()
    assert proposal.status == InvitationProposal.Status.REJECTED


@pytest.mark.django_db
class TestApprovedRecommendationIsDistinguishable:
    """A recommendation and an owner's own invite must not blur into one number.

    The whole design of `deliver_invitation` is that an approved proposal is
    *indistinguishable* from an owner's invite — same RSVP pair, same email,
    same quota — so neither code path can rot. That is right for delivery and
    wrong for measurement: without a mark, the feature that lets members grow
    the group is unmeasurable, and there is no way to tell whether it works.
    """

    def test_the_accept_rsvp_carries_the_mark_only_when_a_member_suggested_them(
        self, collection, user
    ):
        deliver_invitation(collection, "lolo2@your-domain.test", "Owner")
        deliver_invitation(collection, "lele2@your-domain.test", "Owner", proposer_name="Lele")

        direct = RSVP.objects.get(
            user_email="lolo2@your-domain.test", action=RSVP.Action.COLLECTION_INVITE
        )
        recommended = RSVP.objects.get(
            user_email="lele2@your-domain.test", action=RSVP.Action.COLLECTION_INVITE
        )
        assert direct.context == {}
        assert recommended.context == {"via": "recommendation"}

    def test_accepting_each_lands_in_its_own_door(self, client, collection):
        deliver_invitation(collection, "lolo2@your-domain.test", "Owner")
        deliver_invitation(collection, "lele2@your-domain.test", "Owner", proposer_name="Lele")

        for email in ("lolo2@your-domain.test", "lele2@your-domain.test"):
            rsvp = RSVP.objects.get(user_email=email, action=RSVP.Action.COLLECTION_INVITE)
            assert client.get(f"/api/v1/auth/verify/{rsvp.token}/").status_code == 200

        by_email = {
            User.objects.get(code=e.actor_code).email: e.source
            for e in Event.objects.filter(kind=Event.Kind.MEMBER_JOINED)
        }
        assert by_email["lolo2@your-domain.test"] == Event.Source.INVITE
        assert by_email["lele2@your-domain.test"] == Event.Source.RECOMMENDATION


# ── The boundaries the mutation pass found unguarded ─────────────────────────
#
# `proposal_approval_blocked` carries two pieces of arithmetic that no test
# pinned: the carve-out for somebody already inside, and how many seats an
# approval claims. Both survived mutation (`and` → `or`, `adding=1` → `2`)
# against the whole suite, which means a full collection could start refusing
# approvals it owes — the queue the owner cannot clear, one release later.


@pytest.mark.django_db
@pytest.mark.parametrize("approve", BOTH_DOORS)
@override_settings(COLLECTION_INVITES_BLOCK=2)
def test_a_full_collection_still_approves_somebody_already_inside(approve, group, member):
    """ "Someone already in the group costs the counter nothing, so a full
    collection must not refuse an approval that would add nobody" — the code's
    own carve-out, and until now only its opposite was tested.

    The real sequence, since you cannot propose somebody already inside: the
    suggestion is made, the person gets in by another door meanwhile (the owner
    invites them directly, or they pop in from a public link), and the owner
    reaches the now-stale suggestion when the group is full.

    Turn the `and` into an `or` and this goes red: the ceiling would swallow an
    approval that adds no one, and the owner would be stuck with a suggestion
    they can neither approve nor clear.
    """
    proposal = _proposal_for(group, member)
    # They arrive by another route, filling the collection to its ceiling of 2.
    group.invites.add(User.objects.create(email="lele11@your-domain.test"))
    mail.outbox.clear()

    resp = approve(group, proposal)

    assert resp.status_code == 200, resp.data
    proposal.refresh_from_db()
    assert proposal.status == InvitationProposal.Status.APPROVED


@pytest.mark.django_db
@pytest.mark.parametrize("approve", BOTH_DOORS)
@override_settings(COLLECTION_INVITES_BLOCK=3)
def test_an_approval_claims_exactly_one_seat_so_the_last_free_one_is_enough(approve, group, member):
    """Two of three seats taken (the member plus one) and one person arriving:
    it fits, exactly. An approval that claimed two would refuse this — the
    off-by-one that hides until a group is nearly full, which is precisely when
    an owner is most likely to be approving."""
    group.invites.add(User.objects.create(email="lele5@your-domain.test"))
    proposal = _proposal_for(group, member)
    mail.outbox.clear()

    resp = approve(group, proposal)

    assert resp.status_code == 200, resp.data
    proposal.refresh_from_db()
    assert proposal.status == InvitationProposal.Status.APPROVED
    # The invitation actually went out — approving is what sends it; the person
    # joins `invites` later, when they accept it.
    assert RSVP.objects.filter(
        user_email="lele11@your-domain.test",
        target_code=group.code,
        action=RSVP.Action.COLLECTION_INVITE,
    ).exists()
    assert "lele11@your-domain.test" in [addr for m in mail.outbox for addr in m.to]


@pytest.mark.django_db
def test_the_approved_notification_is_marked_approved_for_the_old_inbox_branch(group, member):
    """The inbox still reads rows written before `INVITE_PROPOSAL_APPROVED`
    existed, and `payload["approved"]` is the only thing telling those apart
    from a pending suggestion. The frontend has a test for rendering such a row;
    nothing checked that the backend actually writes the flag, so flipping it to
    False survived the whole suite."""
    proposal = _proposal_for(group, member)

    _approve_in_app(group, proposal)

    note = InAppNotification.objects.get(
        user=member, type=InAppNotification.Type.INVITE_PROPOSAL_APPROVED
    )
    assert note.payload["approved"] is True
    assert note.payload["email"] == "lele11@your-domain.test"
    assert note.payload["collection_code"] == group.code


@pytest.mark.django_db
class TestANewCollectionAsksItsOwnerNothing:
    """``allow_member_proposals`` is off for a new collection. Being
    asked to approve strangers is something the person who runs a group chooses,
    not something every group is handed. Collections that already existed kept the
    value they had; only the default for new ones changed."""

    def test_one_created_without_mentioning_it_has_proposals_off(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/", {"headline": "A new street", "kind": "STALL"}, format="json"
        )

        assert res.status_code == 201, res.data
        assert res.data["allow_member_proposals"] is False
        assert Collection.objects.get(code=res.data["code"]).allow_member_proposals is False

    def test_the_owner_who_turns_it_on_at_creation_gets_it_on(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "A new street", "kind": "STALL", "allow_member_proposals": True},
            format="json",
        )

        assert res.status_code == 201, res.data
        assert Collection.objects.get(code=res.data["code"]).allow_member_proposals is True

    def test_a_member_of_such_a_collection_is_not_offered_the_suggestion(
        self, authenticated_client, user2
    ):
        code = authenticated_client.post(
            "/api/v1/collections/", {"headline": "A new street", "kind": "STALL"}, format="json"
        ).data["code"]
        Collection.objects.get(code=code).invites.add(user2)

        resp = client_for(user2).post(
            PROPOSE_URL.format(code=code), {"email": "lele11@your-domain.test"}, format="json"
        )

        assert resp.status_code == 403
        assert InvitationProposal.objects.count() == 0


@pytest.fixture
def team(group):
    """The founder plus two co-curators, each with an address of their own."""
    first = User.objects.create(code="COOW01", email="lili@your-domain.test", name="Lili")
    second = User.objects.create(code="COOW02", email="lolo@your-domain.test", name="Lolo")
    group.invites.add(first, second)
    group.co_owners.add(first, second)
    return group.owner, first, second


def _suggest(group, member, email="lele11@your-domain.test"):
    client_for(member).post(PROPOSE_URL.format(code=group.code), {"email": email}, format="json")
    return InvitationProposal.objects.get(collection=group, email=email)


def _pair(proposal, curator):
    return (
        RSVP.objects.get(
            target_code=proposal.code, user_code=curator, action=RSVP.Action.PROPOSAL_APPROVE
        ),
        RSVP.objects.get(
            target_code=proposal.code, user_code=curator, action=RSVP.Action.PROPOSAL_REJECT
        ),
    )


def _proposal_notices(proposal=None):
    notices = InAppNotification.objects.filter(type=InAppNotification.Type.INVITE_PROPOSED)
    if proposal is not None:
        notices = notices.filter(payload__proposal_code=proposal.code)
    return notices


def _proposal_links(proposal):
    return RSVP.objects.filter(
        target_code=proposal.code,
        action__in=[RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT],
    )


@pytest.mark.django_db
class TestTheWholeTeamIsAsked:
    """A recommendation is a question for everyone who can answer it."""

    def test_each_curator_gets_an_email_a_notice_and_a_pair_of_links_of_their_own(
        self, group, member, team
    ):
        mail.outbox.clear()
        proposal = _suggest(group, member)

        for curator in team:
            approve, reject = _pair(proposal, curator)
            notice = _proposal_notices(proposal).get(user=curator)
            assert notice.payload["collection_code"] == group.code
            sent = [m for m in mail.outbox if m.to == [curator.email]]
            assert len(sent) == 1, curator.email
            # Their own links, nobody else's.
            assert approve.action_link() in sent[0].body
            assert reject.action_link() in sent[0].body
        tokens = {r.token for r in _proposal_links(proposal)}
        assert len(tokens) == 6, "three curators, two links each, all different"

    def test_the_one_who_recommended_is_told_nothing(self, group, member, team):
        mail.outbox.clear()
        proposal = _suggest(group, member)

        assert not _proposal_notices(proposal).filter(user=member).exists()
        assert not _proposal_links(proposal).filter(user_code=member).exists()
        assert member.email not in [addr for m in mail.outbox for addr in m.to]

    def test_each_email_speaks_its_recipients_language(self, group, member, team):
        from core.services.email_service import _texts

        _, first, _ = team
        first.language = "ca"
        first.save(update_fields=["language"])
        mail.outbox.clear()
        _suggest(group, member)

        subject = {m.to[0]: m.subject for m in mail.outbox}
        assert subject[first.email] == _texts("ca")("proposal_subject").format(
            collection=group.headline
        )
        assert subject[group.owner.email] != subject[first.email]

    def test_nobody_reaches_the_proposed_address_even_with_a_team(self, group, member, team):
        mail.outbox.clear()
        _suggest(group, member)

        assert "lele11@your-domain.test" not in [addr for m in mail.outbox for addr in m.to]
        assert not User.objects.filter(email="lele11@your-domain.test").exists()

    @pytest.mark.parametrize("answer", ["approve", "reject"])
    def test_one_curator_deciding_in_the_app_takes_it_off_everyones_desk(
        self, group, member, team, answer
    ):
        proposal = _suggest(group, member)
        _, first, _ = team

        resp = client_for(first).post(f"/api/v1/proposals/{proposal.code}/{answer}/")

        assert resp.status_code == 200
        assert not _proposal_notices(proposal).exists()
        assert not _proposal_links(proposal).exists()

    @pytest.mark.parametrize("which", ["approve", "reject"])
    def test_one_curator_deciding_by_link_takes_it_off_everyones_desk(
        self, group, member, team, which
    ):
        proposal = _suggest(group, member)
        _, _, second = team
        approve, reject = _pair(proposal, second)
        link = approve if which == "approve" else reject

        resp = APIClient().post(f"/api/v1/rsvp/{link.token}/")

        assert resp.status_code == 200
        assert not _proposal_notices(proposal).exists()
        assert not _proposal_links(proposal).exists()

    def test_the_decision_clears_only_its_own_suggestion(self, group, member, team):
        settled = _suggest(group, member, "lele11@your-domain.test")
        other = _suggest(group, member, "lele12@your-domain.test")

        client_for(team[1]).post(f"/api/v1/proposals/{settled.code}/reject/")

        assert not _proposal_notices(settled).exists()
        assert _proposal_notices(other).count() == 3
        assert _proposal_links(other).count() == 6

    def test_a_demoted_curators_link_is_refused_and_the_suggestion_stays_pending(
        self, group, member, team
    ):
        proposal = _suggest(group, member)
        owner, first, _ = team
        approve, reject = _pair(proposal, first)
        group.co_owners.remove(first)
        mail.outbox.clear()

        resp = APIClient().post(f"/api/v1/rsvp/{approve.token}/")

        assert resp.status_code == 403
        assert resp.data["code"] == "no_longer_manages"
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.PENDING
        assert mail.outbox == []
        assert not User.objects.filter(email="lele11@your-domain.test").exists()
        # Their link is burnt; the founder's pair still decides.
        assert not RSVP.objects.filter(pk=approve.pk).exists()
        assert _pair(proposal, owner)

    def test_a_removed_curators_decline_link_cannot_decline_either(self, group, member, team):
        proposal = _suggest(group, member)
        _, first, _ = team
        _, reject = _pair(proposal, first)
        group.co_owners.remove(first)
        group.invites.remove(first)

        resp = APIClient().post(f"/api/v1/rsvp/{reject.token}/")

        assert resp.status_code == 403
        proposal.refresh_from_db()
        assert proposal.status == InvitationProposal.Status.PENDING

    def test_a_curator_who_still_runs_the_group_decides_with_their_link(self, group, member, team):
        proposal = _suggest(group, member)
        owner, first, _ = team
        group.co_owners.remove(first)
        approve, _ = _pair(proposal, owner)

        assert APIClient().post(f"/api/v1/rsvp/{approve.token}/").status_code == 200

    def test_demoting_a_curator_takes_their_recommendation_notices_of_that_group(
        self, group, member, team
    ):
        owner, first, second = team
        other_group = Collection.objects.create(code="GRP002", owner=owner, headline="Elsewhere")
        other_group.co_owners.add(first)
        proposal = _suggest(group, member)
        elsewhere = InAppNotification.objects.create(
            user=first,
            type=InAppNotification.Type.INVITE_PROPOSED,
            payload={"collection_code": other_group.code, "proposal_code": "ZZZZZZ"},
        )
        kept_for_proposer = InAppNotification.objects.create(
            user=first,
            type=InAppNotification.Type.INVITE_PROPOSED,
            payload={"collection_code": group.code, "approved": True},
        )

        resp = client_for(owner).delete(
            CO_OWNERS_URL.format(code=group.code), {"user_code": first.code}, format="json"
        )

        assert resp.status_code == 200
        assert not _proposal_notices(proposal).filter(user=first).exists()
        assert _proposal_notices(proposal).filter(user=owner).exists()
        assert _proposal_notices(proposal).filter(user=second).exists()
        assert InAppNotification.objects.filter(pk=elsewhere.pk).exists()
        assert InAppNotification.objects.filter(pk=kept_for_proposer.pk).exists()

    def test_a_curator_who_is_the_one_recommending_is_left_out_of_the_team(self, group, team):
        from core.services.invitation_service import create_proposal

        owner, first, second = team
        mail.outbox.clear()

        proposal, _, _ = create_proposal(group, first, "lele13@your-domain.test")

        asked = set(_proposal_notices(proposal).values_list("user_id", flat=True))
        assert asked == {owner.code, second.code}
        assert not _proposal_links(proposal).filter(user_code=first).exists()
        assert first.email not in [addr for m in mail.outbox for addr in m.to]


@pytest.mark.django_db
class TestARecommendationIsSettledOnce:
    """Two curators answering at once: the first decision stands, the second sends nothing.

    Deterministic stand-in for the race: the proposal is loaded as pending, then
    settled in the database by "the other curator", then the stale copy is decided.
    """

    def _stale(self, group, member, settled_as):
        from core.services.invitation_service import create_proposal

        proposal, _, _ = create_proposal(group, member, "lele14@your-domain.test")
        stale = InvitationProposal.objects.get(pk=proposal.pk)
        InvitationProposal.objects.filter(pk=proposal.pk).update(status=settled_as)
        mail.outbox.clear()
        return stale

    def test_approving_a_recommendation_another_curator_rejected_invites_nobody(
        self, group, member
    ):
        from core.services.invitation_service import ProposalAlreadyDecided, approve_proposal

        stale = self._stale(group, member, InvitationProposal.Status.REJECTED)

        with pytest.raises(ProposalAlreadyDecided):
            approve_proposal(stale)

        assert mail.outbox == []
        assert not User.objects.filter(email="lele14@your-domain.test").exists()
        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.INVITE_PROPOSAL_APPROVED
        ).exists()
        stale.refresh_from_db()
        assert stale.status == InvitationProposal.Status.REJECTED

    def test_rejecting_a_recommendation_another_curator_approved_tells_the_proposer_nothing(
        self, group, member
    ):
        from core.services.invitation_service import ProposalAlreadyDecided, reject_proposal

        stale = self._stale(group, member, InvitationProposal.Status.APPROVED)

        with pytest.raises(ProposalAlreadyDecided):
            reject_proposal(stale)

        assert mail.outbox == []
        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.INVITE_PROPOSAL_DECLINED
        ).exists()
        stale.refresh_from_db()
        assert stale.status == InvitationProposal.Status.APPROVED

    def test_the_winner_sees_the_status_it_wrote(self, group, member):
        from core.services.invitation_service import create_proposal, reject_proposal

        proposal, _, _ = create_proposal(group, member, "lele15@your-domain.test")

        reject_proposal(proposal)

        assert proposal.status == InvitationProposal.Status.REJECTED
        assert proposal.resolved is not None

    @pytest.mark.parametrize("action", ["approve", "reject"])
    def test_the_app_answers_a_lost_race_as_a_settled_suggestion(self, group, member, action):
        stale = self._stale(group, member, InvitationProposal.Status.REJECTED)

        # The view passed its is_valid() check just before the other curator decided.
        with patch.object(InvitationProposal, "is_valid", return_value=True):
            resp = client_for(group.owner).post(f"/api/v1/proposals/{stale.code}/{action}/")

        assert resp.status_code == 400
        assert resp.data["code"] == "proposal_not_pending"
        assert mail.outbox == []

    @pytest.mark.parametrize("action", [RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT])
    def test_the_email_link_answers_a_lost_race_as_a_settled_suggestion(
        self, group, member, action
    ):
        stale = self._stale(group, member, InvitationProposal.Status.REJECTED)
        link = RSVP.objects.get(target_code=stale.code, user_code=group.owner, action=action)

        with patch.object(InvitationProposal, "is_valid", return_value=True):
            resp = APIClient().post(f"/api/v1/rsvp/{link.token}/")

        assert resp.status_code == 400
        assert resp.data["code"] == "proposal_not_pending"
        assert mail.outbox == []
        assert not RSVP.objects.filter(pk=link.pk).exists(), "the pressed link is consumed"
