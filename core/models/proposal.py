from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.utils import generate_id

from .collection import Collection
from .user import User

# How long a suggestion is kept. Constants and not ``RETENTION_*`` settings: ``/legal``
# promises them, so there is no value an operator could choose. A suggestion holds a
# third party's address and the proposer's note, so neither kind is kept without a limit.
PROPOSAL_RESOLVED_MONTHS = 12  # counted from ``resolved``
PROPOSAL_PENDING_DAYS = 60  # counted from ``created``


class InvitationProposal(models.Model):
    """A member asking the owner to invite somebody to their collection.

    Members could not bring anyone in at all: every new person cost an owner
    action, so the only growth path ran through one person per group. But an
    owner is not just a bottleneck to route around — the group may be closed, may
    require a subscription, papers, or rules of admission we know nothing about.
    So a member proposes and **the owner decides**, and nothing reaches the
    proposed address until they do.

    The order matters: no `User` row is created and no email is sent to the
    proposed address on proposal. Somebody being suggested must not learn they
    were suggested if the answer turns out to be no.

    Approval reuses the ordinary invitation path, so an approved proposal is
    indistinguishable from an owner's own invite — including counting against the
    **owner's** `INVITE_EMAILS_PER_DAY` quota, since it leaves their group under
    their sending domain.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="invitation_proposals"
    )
    # CASCADE: if the proposer leaves OIUEEI, their pending suggestions go with
    # them — an owner should not be answering a request from an account that no
    # longer exists.
    proposer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="invitation_proposals"
    )
    email = models.CharField(max_length=64)
    # The proposer's optional word to the owner. This is what makes the approval
    # a decision rather than a coin toss: an owner asked to admit an address they
    # don't recognise has nothing to go on ("she's my downstairs neighbour",
    # "he's paid the subs"). Never shown to the proposed person.
    note = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created = models.DateTimeField(default=timezone.now, db_index=True)
    resolved = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "core"
        db_table = "invitation_proposals"
        ordering = ["-created"]
        constraints = [
            # One live proposal per address per collection. Without it, a member
            # could ask twice and the owner would answer the same question twice
            # — or, worse, approve both and fire two invitations.
            models.UniqueConstraint(
                fields=["collection", "email"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_proposal_per_email",
            )
        ]

    def __str__(self):
        return f"{self.code}: {self.email} → {self.collection_id} ({self.status})"

    @property
    def expiry_hours(self):
        """How long the owner has to answer, mirroring a collection invitation.

        A pending suggestion has no natural deadline any more than a pending
        invitation does, so it inherits the same ~30 days
        (``COLLECTION_INVITE_EXPIRY_HOURS``) and then lapses quietly — nobody is
        told, because nobody was told it existed.
        """
        return getattr(settings, "COLLECTION_INVITE_EXPIRY_HOURS", 720)

    def is_valid(self):
        """True while the owner can still act on it."""
        if self.status != self.Status.PENDING:
            return False
        return timezone.now() < self.created + timedelta(hours=self.expiry_hours)
