"""
Wish models for OIUEEI.

A "wish" (pedido) is a Thing of ``type=WISH_THING``: something a member is
looking for, posted on a community board. Instead of a reservation, other
members answer it with a ``WishResponse`` — "I have this" (links a real
listing), "I know where" (text + link), or "I can make it" (text + offer).
The wish creator can accept one response and mark the wish resolved (which
hides the underlying Thing, so it leaves the active board).
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class WishResponse(models.Model):
    """A member's structured answer to a wish (a ``Thing`` of type WISH_THING)."""

    class Kind(models.TextChoices):
        HAVE_THIS = "HAVE_THIS", "Have this"
        KNOW_WHERE = "KNOW_WHERE", "Know where"
        CAN_MAKE = "CAN_MAKE", "Can make it"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    wish = models.ForeignKey(
        "Thing",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="wish",
        related_name="responses",
    )
    responder = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="responder",
        related_name="wish_responses",
    )
    created = models.DateTimeField(default=timezone.now)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # HAVE_THIS: the real listing the responder offers (its own mode lend/sell/gift).
    thing = models.ForeignKey(
        "Thing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="code",
        db_column="offered_thing",
        related_name="offered_in_responses",
    )
    # KNOW_WHERE / CAN_MAKE: free-text body.
    message = models.CharField(max_length=256, blank=True, default="")
    # KNOW_WHERE: optional link.
    url = models.CharField(max_length=255, blank=True, default="")
    # CAN_MAKE: optional offer/price.
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)

    class Meta:
        app_label = "core"
        db_table = "wish_responses"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.code}: {self.kind} -> {self.wish_id}"

    def is_responder(self, user_code):
        """Check if the given user authored this response."""
        return self.responder_id == user_code

    def accept(self):
        """Mark this response as the accepted one."""
        self.status = self.Status.ACCEPTED
        self.save(update_fields=["status"])
