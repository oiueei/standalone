"""
RSVP model for magic link authentication and action intermediary.

RSVP serves as an intermediary for ALL email communications to avoid
exposing real codes (thing_code, booking_code, etc.) in URLs.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.utils import generate_id


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

    Expires after MAGIC_LINK_EXPIRY_HOURS (default 24 hours).
    Deleted after one-time use.
    """

    class Action(models.TextChoices):
        MAGIC_LINK = "MAGIC_LINK", "Magic Link"
        COLLECTION_INVITE = "COLLECTION_INVITE", "Collection Invite"
        COLLECTION_REJECT = "COLLECTION_REJECT", "Collection Reject"
        BOOKING_ACCEPT = "BOOKING_ACCEPT", "Booking Accept"
        BOOKING_REJECT = "BOOKING_REJECT", "Booking Reject"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
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

    def is_valid(self):
        """Check if the RSVP is still valid (not expired)."""
        from datetime import timedelta

        expiry_hours = getattr(settings, "MAGIC_LINK_EXPIRY_HOURS", 24)
        expiry_time = self.created + timedelta(hours=expiry_hours)
        return timezone.now() < expiry_time

    def action_link(self):
        """The ``/rsvp/<code>`` URL used in emails to resolve this RSVP."""
        return f"{settings.RSVP_BASE_URL}/{self.code}"

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
        # Include order info if it exists (for ORDER_THING)
        if booking.delivery_date:
            context["delivery_date"] = str(booking.delivery_date)
        if booking.quantity:
            context["quantity"] = booking.quantity

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
