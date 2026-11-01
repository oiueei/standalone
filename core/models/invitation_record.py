from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac

from core.utils import generate_id

from .user import User

# How long a record of an invitation is kept, counted from the day it was sent.
# A constant and not a setting on purpose: the invitation email promises "a year"
# to the person receiving it, so an operator must not be able to change the number
# the promise rests on.
INVITE_RECORD_MONTHS = 12


def address_hash(email):
    """The fingerprint of an address that an ``InvitationRecord`` keeps in its place.

    The one function that computes it: the invitation service, the data migration
    and the tests all go through here, since two spellings of the recipe would
    stop matching each other without anything failing. ``SECRET_KEY`` is part of
    the key, so rotating it makes every record forget its address, and with it
    every block; that is accepted, the alternative being an unsalted hash anyone
    could test an address against.
    """
    return salted_hmac(
        "core.invitation_record", (email or "").strip().lower(), algorithm="sha256"
    ).hexdigest()


class InvitationRecord(models.Model):
    """That an address was invited by a founder's group, and what became of it.

    One row per founder and address. It outlives the invited person's ``User`` row
    (the purge of unanswered guests deletes it after 60 days), so it holds **only a
    hash of the address**, never the address itself: its job is to stop the same
    person being invited by email again, not to remember who they are.

    ``founder`` is the owner of the collection the invitation was for. ``inviter``
    is the account the daily invitation quota was spent on: a co-curator who
    invited, or the founder for an approved recommendation.
    """

    class State(models.TextChoices):
        SENT = "SENT", "Sent"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    founder = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="invitation_records_as_founder"
    )
    inviter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="invitation_records_as_inviter"
    )
    address_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=8, choices=State.choices, default=State.SENT)
    sent_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "core"
        db_table = "invitation_records"
        constraints = [
            models.UniqueConstraint(
                fields=["founder", "address_hash"], name="unique_invitation_per_founder_address"
            ),
        ]
        indexes = [
            models.Index(fields=["inviter", "sent_at"], name="invrecord_inviter_sent_idx"),
        ]

    def __str__(self):
        return f"InvitationRecord {self.code} ({self.state})"
