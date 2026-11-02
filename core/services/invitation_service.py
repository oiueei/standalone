"""Sending a collection invitation, and the member-proposal flow around it.

`deliver_invitation` is the single place an invitation actually goes out. Both
callers reach it: the owner inviting directly (`CollectionInviteView`) and an
owner approving a member's proposal. An approved proposal is therefore
indistinguishable from an owner's own invite — same RSVP pair, same email, same
quota — which is the point. Two code paths would drift, and the one used less
often is the one that would rot.
"""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from core.models import RSVP, InvitationProposal, InvitationRecord, User
from core.models.event import Event
from core.models.invitation_record import address_hash
from core.models.notification import InAppNotification
from core.services.email_service import (
    send_collection_invite_email,
    send_invitation_proposal_email,
    send_proposal_declined_email,
)
from core.utils import Refusal

# ── The daily invitation-email quota ────────────────────────────────────────
# Lives here rather than in the views because both senders are here now, and a
# service reaching back into a view for it was a layering inversion. The views
# import these.
_INVITE_QUOTA_TTL = 60 * 60 * 24  # ~24h; the date is in the key, so it rolls over anyway.
_INVITE_QUOTA_MESSAGE = Refusal(
    "Daily invitation limit reached. Try again tomorrow.", "invite_quota_exhausted"
)

# ── One invitation per person ───────────────────────────────────────────────
_ALREADY_ASKED_MESSAGE = Refusal(
    "This person has already been invited. They can join with the share link.",
    "invite_already_asked",
)


class InvitationAlreadyAsked(Exception):
    """The address was already invited by email; nothing was created or sent."""


def invitation_blocked(collection, email, inviter_code):
    """Whether ``email`` may no longer be invited by email to ``collection``.

    An address is blocked once it has been invited (``SENT``) and has not answered,
    or has said no (``DECLINED``), by this collection's founder or by whoever is
    inviting now. Not answering counts from the first send, so an invitation
    cannot be sent twice. ``ACCEPTED`` blocks nothing: someone who joined one group
    can be invited to another of the same founder.

    Only the outgoing email is stopped. Joining by the share link or a public
    collection never asks this.
    """
    return (
        InvitationRecord.objects.filter(
            address_hash=address_hash(email),
            state__in=[InvitationRecord.State.SENT, InvitationRecord.State.DECLINED],
        )
        .filter(Q(founder_id=collection.owner_id) | Q(inviter_id=inviter_code))
        .exists()
    )


def record_invitation(collection, email, inviter_code):
    """Write that ``email`` was invited by ``collection``'s founder, on ``inviter_code``'s quota.

    An address that had accepted an earlier invitation goes back to ``SENT``.
    """
    InvitationRecord.objects.update_or_create(
        founder_id=collection.owner_id,
        address_hash=address_hash(email),
        defaults={
            "inviter_id": inviter_code,
            "state": InvitationRecord.State.SENT,
            "sent_at": timezone.now(),
            "resolved_at": None,
        },
    )


def invitation_acceptance(days=30, settle_days=7):
    """How the invitations each account sent were answered, for a deployment's report.

    One row per ``inviter`` over the records sent between ``days`` and ``settle_days``
    ago, both ends included: ``{"inviter": code, "sent", "accepted", "declined",
    "unanswered"}``, most sent first. Anything sent in the last ``settle_days`` is left
    out, or somebody who has just sent a batch would look like an account whose
    invitations nobody accepts.

    It only measures: nobody is stopped or blocked by what it says.
    """
    now = timezone.now()
    State = InvitationRecord.State
    rows = (
        InvitationRecord.objects.filter(
            sent_at__gte=now - timedelta(days=days),
            sent_at__lte=now - timedelta(days=settle_days),
        )
        .values("inviter_id")
        .annotate(
            sent=Count("pk"),
            accepted=Count("pk", filter=Q(state=State.ACCEPTED)),
            declined=Count("pk", filter=Q(state=State.DECLINED)),
            unanswered=Count("pk", filter=Q(state=State.SENT)),
        )
        .order_by("-sent", "inviter_id")
    )
    return [
        {
            "inviter": row["inviter_id"],
            "sent": row["sent"],
            "accepted": row["accepted"],
            "declined": row["declined"],
            "unanswered": row["unanswered"],
        }
        for row in rows
    ]


def resolve_invitation(collection, email, state):
    """The invited person answered: mark the founder's record ``ACCEPTED`` or ``DECLINED``."""
    InvitationRecord.objects.filter(
        founder_id=collection.owner_id, address_hash=address_hash(email)
    ).update(state=state, resolved_at=timezone.now())


def _invite_quota_cap():
    """Configured daily cap, or ``None`` when the quota is off.

    Off means either the whole rate-limiting layer is disabled (dev, tests) or
    the operator left the cap unset/zero — the standalone default.
    """
    if not getattr(settings, "RATELIMIT_ENABLE", True):
        return None
    cap = getattr(settings, "INVITE_EMAILS_PER_DAY", 0) or 0
    return cap if cap > 0 else None


def _invite_quota_key(user_code):
    return f"invq:{user_code}:{timezone.localdate().isoformat()}"


def _invite_quota_left(user_code):
    """Invitation emails this account may still send today; ``None`` = unlimited."""
    cap = _invite_quota_cap()
    if cap is None:
        return None
    return max(cap - cache.get(_invite_quota_key(user_code), 0), 0)


def _consume_invite_quota(user_code, count):
    """Record ``count`` invitation emails against today's quota."""
    if count <= 0 or _invite_quota_cap() is None:
        return
    key = _invite_quota_key(user_code)
    cache.set(key, cache.get(key, 0) + count, _INVITE_QUOTA_TTL)


def proposal_approval_blocked(proposal):
    """Why this approval cannot be delivered right now, or ``None``.

    Returns ``(message, http_status)``. Shared by the owner's **two** routes to
    the same decision — the in-app POST and the emailed approve link — so the
    operator's daily cap and the collection's member ceiling mean the same thing
    whichever one they reach for.

    They used not to. The in-app view checked both and the email link approved
    unconditionally, which made `INVITE_EMAILS_PER_DAY` — a cap that exists to
    protect a deployment's sending reputation, not to police the product —
    walkable one recommendation at a time by the owner simply clicking the link
    in their mail client instead of the button in the app. Nothing documented
    the difference, and the in-app path's own reasoning ("an approval that can't
    be delivered should say so rather than half-happen") argues against it.

    The quota is charged to the **owner** on both paths (see
    ``deliver_invitation``), so it is the owner's allowance that is read here —
    never the member's, who cannot send anything on their own.
    """
    collection = proposal.collection
    if _invite_quota_left(collection.owner_id) == 0:
        return _INVITE_QUOTA_MESSAGE, 429
    # The invitation is the owner's (their quota, their group), so it is the
    # owner's record that decides. Somebody already inside is no invitation.
    if not collection.invites.filter(email=proposal.email).exists() and invitation_blocked(
        collection, proposal.email, collection.owner_id
    ):
        return _ALREADY_ASKED_MESSAGE, 400
    # Someone already in the group costs the counter nothing, so a full
    # collection must not refuse an approval that would add nobody.
    if (
        collection.capacity_ceiling("invites")
        and not collection.invites.filter(email=proposal.email).exists()
    ):
        full = collection.capacity_violation("invites", adding=1)
        if full:
            return full, 400
    return None


def deliver_invitation(collection, email, inviter_name, quota_user_code=None, proposer_name=None):
    """Create the invitee (if new), mint the RSVP pair and send the invitation.

    Assumes the caller has already checked permission, the daily quota and the
    member ceiling — those produce different HTTP answers per caller, so they
    stay in the views.

    ``quota_user_code`` is whose daily allowance this send is charged to. For an
    approved proposal that is the **owner**, not the member who suggested it: the
    email leaves the owner's group under the deployment's sending domain, and the
    reputation being protected is theirs.

    The invitation is recorded against ``quota_user_code`` (the group's owner when
    none is given). An address that was already invited by this founder or by this
    inviter raises ``InvitationAlreadyAsked`` before anything is created, so a
    blocked address leaves no ``User``, no RSVP, no email and no quota spent.

    Returns ``(invited_user, already_invited)``.
    """
    email = email.lower()
    inviter_code = quota_user_code or collection.owner_id
    # Somebody inside is not an invitation: they get the usual "already invited"
    # answer, whatever their record says.
    inside = User.objects.filter(email=email).first()
    if inside is not None and (
        collection.is_owner(inside.code) or collection.is_invited(inside.code)
    ):
        return inside, True
    if invitation_blocked(collection, email, inviter_code):
        # No argument: an exception's message reaches logs and error reports, and
        # the address must not.
        raise InvitationAlreadyAsked
    invited_user, created = User.objects.get_or_create(email=email, defaults={"email": email})
    if created:
        Event.log(Event.Kind.USER_JOINED, actor=invited_user)

    # The founder counts as already inside: they are an FK, never an ``invites`` row,
    # so no invitation (RSVP, email, quota) is ever minted for them.
    if collection.is_owner(invited_user.code) or collection.is_invited(invited_user.code):
        return invited_user, True

    # This is not a resend (a pending invitation blocks the address). The record is per
    # founder, so joining another of the founder's groups through a link marks it
    # ``ACCEPTED`` while this group's invitation is still waiting; inviting here again
    # then finds nobody blocked, and without this the old pair would live on beside
    # the new one.
    RSVP.objects.filter(
        user_code=invited_user,
        target_code=collection.code,
        action__in=[RSVP.Action.COLLECTION_INVITE, RSVP.Action.COLLECTION_REJECT],
    ).delete()
    accept_rsvp = RSVP.objects.create(
        user_code=invited_user,
        user_email=email,
        action=RSVP.Action.COLLECTION_INVITE,
        target_code=collection.code,
        # An approved recommendation is delivered as an ordinary invitation on
        # purpose (one code path, so neither can rot). This is the one mark that
        # keeps the two apart in the join stats — without it a member's
        # recommendation is indistinguishable from the owner's own invite, and
        # the whole feature is unmeasurable.
        context={"via": "recommendation"} if proposer_name else {},
    )
    reject_rsvp = RSVP.objects.create(
        user_code=invited_user,
        user_email=email,
        action=RSVP.Action.COLLECTION_REJECT,
        target_code=collection.code,
    )

    record_invitation(collection, email, inviter_code)

    send_collection_invite_email(
        inviter_name,
        collection.headline,
        email,
        accept_rsvp.action_link(),
        reject_rsvp.action_link(),
        collection=collection,
        proposer_name=proposer_name,
    )
    if quota_user_code:
        _consume_invite_quota(quota_user_code, 1)
    return invited_user, False


def proposal_team(collection, proposer=None):
    """The people a recommendation is put to: the founder and every co-curator.

    Any of them may decide it (the members page lets a co-curator approve or
    decline, ``require_collection_curator``), so the question goes to all of them,
    the way a hold request goes to everyone who runs the thing. The one who made
    the recommendation is left out if they happen to be on the team; the view
    already sends a curator to the real invitation, so in practice that never
    removes anyone. The founder comes first.
    """
    team = [collection.owner, *collection.co_owners.all()]
    return [
        curator
        for curator in team
        if curator.email and (proposer is None or curator.code != proposer.code)
    ]


def create_proposal(collection, proposer, email, note=""):
    """Record a member's suggestion and put it in front of the whole team.

    **Nothing reaches the proposed address here** — no User row, no email. If the
    team says no, that person must never learn they were suggested.

    Each curator (``proposal_team``) gets their **own** approve/reject pair, minted
    to them, an in-app ``INVITE_PROPOSED`` and an email in their language. Using a
    link signs the decision as whoever it was minted to and re-checks, at the
    click, that they still run the group (``VerifyLinkView``); once anyone decides,
    every notice and link of the suggestion goes (``clear_proposal_traces``).

    Returns ``(proposal, approve_rsvp, reject_rsvp)`` — the pair of the first on
    the team, the founder.
    """
    email = email.lower()
    team = proposal_team(collection, proposer)
    sent = []
    with transaction.atomic():
        proposal = InvitationProposal.objects.create(
            collection=collection, proposer=proposer, email=email, note=note
        )
        for curator in team:
            approve_rsvp = RSVP.objects.create(
                user_code=curator,
                user_email=curator.email,
                action=RSVP.Action.PROPOSAL_APPROVE,
                target_code=proposal.code,
            )
            reject_rsvp = RSVP.objects.create(
                user_code=curator,
                user_email=curator.email,
                action=RSVP.Action.PROPOSAL_REJECT,
                target_code=proposal.code,
            )
            InAppNotification.objects.create(
                user=curator,
                type=InAppNotification.Type.INVITE_PROPOSED,
                payload={
                    "collection_headline": collection.headline,
                    "collection_code": collection.code,
                    # What lets every copy go once the suggestion is decided.
                    "proposal_code": proposal.code,
                    "proposer_name": proposer.display_name,
                    "email": email,
                    "note": note,
                },
            )
            sent.append((curator, approve_rsvp, reject_rsvp))

    for curator, approve_rsvp, reject_rsvp in sent:
        send_invitation_proposal_email(
            owner_email=curator.email,
            proposer_name=proposer.display_name,
            collection_headline=collection.headline,
            proposed_email=email,
            note=note,
            approve_link=approve_rsvp.action_link(),
            reject_link=reject_rsvp.action_link(),
            collection=collection,
        )
    if not sent:
        return proposal, None, None
    _, approve_rsvp, reject_rsvp = sent[0]
    return proposal, approve_rsvp, reject_rsvp


def clear_proposal_traces(proposal):
    """Take a decided suggestion off every curator's desk.

    The suggestion was a question put to the whole team, so it must not outlive
    its answer: every copy of its in-app notice goes (matched by
    ``payload.proposal_code``, deliberately not by user, so the copy of a
    co-curator who did not decide goes too) and so does every approve/reject link
    minted for it. Notices written before the payload carried the code never match
    and stay until dismissed.
    """
    InAppNotification.objects.filter(
        type=InAppNotification.Type.INVITE_PROPOSED,
        payload__proposal_code=proposal.code,
    ).delete()
    RSVP.objects.filter(
        target_code=proposal.code,
        action__in=[RSVP.Action.PROPOSAL_APPROVE, RSVP.Action.PROPOSAL_REJECT],
    ).delete()


class ProposalAlreadyDecided(Exception):
    """Another curator settled the recommendation first (or it is no longer pending)."""


def _claim_decision(proposal, status):
    """Reserve the one decision a recommendation gets, before any effect of it.

    A conditional ``UPDATE ... WHERE status = PENDING``: of two curators answering
    at the same time the first takes the row (in Postgres the second waits for the
    first's commit, then finds the status changed), and the other raises
    ``ProposalAlreadyDecided`` with nothing sent. Must run inside the caller's
    ``transaction.atomic()`` so a failing effect undoes the reservation.
    """
    resolved = timezone.now()
    claimed = InvitationProposal.objects.filter(
        pk=proposal.pk, status=InvitationProposal.Status.PENDING
    ).update(status=status, resolved=resolved)
    if not claimed:
        raise ProposalAlreadyDecided(proposal.code)
    proposal.status = status
    proposal.resolved = resolved


def approve_proposal(proposal):
    """A curator said yes: send the invitation for real.

    Charged to the owner's quota (see ``deliver_invitation``). Returns
    ``(invited_user, already_invited)``; `already_invited` means somebody else
    got there first while the proposal was waiting, which is a no-op, not an
    error.

    The decision is reserved first (``_claim_decision``): a recommendation is
    settled once, and raises ``ProposalAlreadyDecided`` if another curator got
    there before this call, with nothing sent.
    """
    with transaction.atomic():
        _claim_decision(proposal, InvitationProposal.Status.APPROVED)
        return _approve_claimed(proposal)


def _approve_claimed(proposal):
    collection = proposal.collection
    invited_user, already = deliver_invitation(
        collection,
        proposal.email,
        # Bare name: the invitation goes to somebody outside the group.
        collection.owner.name,
        quota_user_code=collection.owner_id,
        # The invitee almost certainly knows the member who suggested them, not
        # the owner — without this line a warm recommendation lands as an email
        # from a stranger. Bare `name`, so a proposer who never set one simply
        # doesn't get a line rather than having their address forwarded.
        proposer_name=proposal.proposer.name,
    )

    InAppNotification.objects.create(
        user=proposal.proposer,
        type=InAppNotification.Type.INVITE_PROPOSAL_APPROVED,
        payload={
            "collection_headline": collection.headline,
            "collection_code": collection.code,
            "email": proposal.email,
            # Kept for the inbox's back-compatibility branch, which still has to
            # read rows written as INVITE_PROPOSED before this type existed.
            "approved": True,
        },
    )
    clear_proposal_traces(proposal)
    return invited_user, already


def reject_proposal(proposal):
    """A curator said no. The proposer is told; the proposed person never is.

    **No reason travels with it.** The owner may be enforcing rules we know
    nothing about — a subscription, papers, a waiting list — and a product that
    demanded a justification would either put words in their mouth or turn a
    quiet no into an argument. The proposer learns the answer and nothing else.

    Reserves the decision first, like ``approve_proposal``: raises
    ``ProposalAlreadyDecided`` and sends nothing if another curator answered.
    """
    with transaction.atomic():
        _claim_decision(proposal, InvitationProposal.Status.REJECTED)
        _reject_claimed(proposal)


def _reject_claimed(proposal):
    collection = proposal.collection

    InAppNotification.objects.create(
        user=proposal.proposer,
        type=InAppNotification.Type.INVITE_PROPOSAL_DECLINED,
        payload={
            "collection_headline": collection.headline,
            "collection_code": collection.code,
            "owner_name": collection.owner.name,
            "email": proposal.email,
        },
    )
    send_proposal_declined_email(
        proposer_email=proposal.proposer.email,
        owner_name=collection.owner.name,
        collection_headline=collection.headline,
        proposed_email=proposal.email,
        collection=collection,
    )
    clear_proposal_traces(proposal)
