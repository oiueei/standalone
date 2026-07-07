"""
RSVP model for magic link authentication and action intermediary.

RSVP serves as an intermediary for ALL email communications to avoid
exposing real codes (thing_code, booking_code, etc.) in URLs.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.utils import generate_id, generate_token


class RSVP(models.Model):
    """
    Magic link token for passwordless authentication and action intermediary.

    Used for:
    - MAGIC_LINK: Passwordless authentication
    - COLLECTION_INVITE: Accept invitation to view a collection
    - COLLECTION_REJECT: Decline invitation to a collection
    - BOOKING_ACCEPT: Accept a booking request (all thing types)
    - BOOKING_REJECT: Reject a booking request (all thing types)

    All booking actions (GIFT, SELL, ORDER, LEND, RENT, SHARE) use the unified
    BOOKING_ACCEPT/BOOKING_REJECT actions via the BookingPeriod model.

    Expiry is per action (see ``expiry_hours_for``): magic links stay short-lived
    (24h), booking accept/reject links live the full 72h PENDING window they act
    on, and a pending collection invitation lingers far longer (~30 days).
    Deleted after one-time use.
    """

    class Action(models.TextChoices):
        MAGIC_LINK = "MAGIC_LINK", "Magic Link"
        COLLECTION_INVITE = "COLLECTION_INVITE", "Collection Invite"
        COLLECTION_REJECT = "COLLECTION_REJECT", "Collection Reject"
        BOOKING_ACCEPT = "BOOKING_ACCEPT", "Booking Accept"
        BOOKING_REJECT = "BOOKING_REJECT", "Booking Reject"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    # High-entropy (~134-bit) token that backs every email action link. The
    # 6-char PK (~31 bits) stays for joins/target lookups, but URLs use this so
    # magic links and accept/reject links can't be brute-forced.
    token = models.CharField(max_length=26, unique=True, default=generate_token)
    created = models.DateTimeField(default=timezone.now)
    user_code = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="user_code",
        related_name="rsvps",
    )
    user_email = models.CharField(max_length=64)

    # Action type and target
    action = models.CharField(
        max_length=20, choices=Action.choices, default=Action.MAGIC_LINK, db_index=True
    )
    target_code = models.CharField(max_length=6, null=True, blank=True, db_index=True)

    # Additional context data (JSON) for the action
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "core"
        db_table = "rsvps"

    def __str__(self):
        return f"RSVP {self.code} ({self.action}) for {self.user_email}"

    # Per-action link lifetime (hours). Booking accept/reject links must outlive the
    # 72h PENDING window they act on (BOOKING_EXPIRY_HOURS); a pending collection
    # invitation has no natural deadline, so its link lingers far longer; magic links
    # stay short-lived. Each is overridable via settings. Single source of truth for
    # both is_valid() and the cleanup_rsvps command so they can never drift.
    @classmethod
    def expiry_hours_for(cls, action):
        if action in (cls.Action.BOOKING_ACCEPT, cls.Action.BOOKING_REJECT):
            return getattr(settings, "BOOKING_EXPIRY_HOURS", 72)
        if action in (cls.Action.COLLECTION_INVITE, cls.Action.COLLECTION_REJECT):
            return getattr(settings, "COLLECTION_INVITE_EXPIRY_HOURS", 720)
        return getattr(settings, "MAGIC_LINK_EXPIRY_HOURS", 24)

    def is_valid(self):
        """Check if the RSVP is still valid (not expired). Expiry is per-action."""
        from datetime import timedelta

        expiry_time = self.created + timedelta(hours=self.expiry_hours_for(self.action))
        return timezone.now() < expiry_time

    def action_link(self):
        """The ``/rsvp/<token>`` URL used in emails to resolve this RSVP.

        Uses the high-entropy ``token`` (not the 6-char PK) so the link can't be
        brute-forced.
        """
        return f"{settings.RSVP_BASE_URL}/{self.token}"

    @classmethod
    def create_for_booking(cls, action, booking, owner_email):
        """
        Create an RSVP for a booking accept/reject action.

        Args:
            action: 'BOOKING_ACCEPT' or 'BOOKING_REJECT'
            booking: BookingPeriod instance
            owner_email: Email of the owner to send the link to
        """
        context = {
            "thing_code": booking.thing_code_id,
            "thing_type": booking.thing_type,
            "requester_code": booking.requester_code_id,
            "requester_email": booking.requester_email,
        }
        # Include dates if they exist (for LEND/RENT/SHARE)
        if booking.start_date:
            context["start_date"] = str(booking.start_date)
        if booking.end_date:
            context["end_date"] = str(booking.end_date)

        return cls.objects.create(
            user_code=booking.owner_code,
            user_email=owner_email,
            action=action,
            target_code=booking.code,
            context=context,
        )

    @classmethod
    def create_booking_pair(cls, booking, owner_email):
        """Create the accept + reject RSVP pair for a booking decision.

        Returns ``(accept_rsvp, reject_rsvp)``.
        """
        return (
            cls.create_for_booking(cls.Action.BOOKING_ACCEPT, booking, owner_email),
            cls.create_for_booking(cls.Action.BOOKING_REJECT, booking, owner_email),
        )
