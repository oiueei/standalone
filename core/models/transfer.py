"""
ThingTransfer model — tracks the physical journey of items between users.

Each transfer represents a handoff: owner lends to requester (on booking acceptance),
and the item is returned (on end_date or manually). The chain of transfers tells
the story of an item's journey through the community.
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class ThingTransfer(models.Model):
    """
    A record of an item being transferred from one user to another.

    Created automatically when a booking is accepted. The returned_date
    is set when the booking end_date passes (via close_transfers command)
    or can be set manually by the owner.

    For single-use types (GIFT/SELL), returned_date stays null — the
    transfer is permanent.
    """

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    thing = models.ForeignKey(
        "Thing",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="thing",
        related_name="transfers",
    )
    from_user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="from_user",
        related_name="transfers_out",
    )
    to_user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="to_user",
        related_name="transfers_in",
    )
    booking = models.ForeignKey(
        "BookingPeriod",
        on_delete=models.SET_NULL,
        to_field="code",
        db_column="booking",
        related_name="transfer",
        null=True,
        blank=True,
    )
    lent_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "core"
        db_table = "thing_transfers"
        ordering = ["-lent_date"]
        indexes = [
            # The journey view filters by thing and the model always orders by
            # -lent_date; a composite serves both the lookup and the sort for a
            # thing whose transfer history grows as it is passed around.
            models.Index(fields=["thing", "lent_date"], name="transfer_thing_lentdate_idx"),
        ]
        constraints = [
            # A booking may create at most one transfer per thing. Prevents
            # duplicate ThingTransfer rows if an accept is processed twice
            # (and matches the 1:1 intent of booking's related_name="transfer").
            # `booking` is nullable; NULLs are distinct, so manual transfers
            # (booking=NULL) are unaffected.
            models.UniqueConstraint(
                fields=["booking", "thing"],
                name="uniq_transfer_per_booking_thing",
            ),
        ]

    def __str__(self):
        status = "returned" if self.returned_date else "active"
        return (
            f"Transfer {self.code}: {self.thing_id} "
            f"{self.from_user_id} → {self.to_user_id} ({status})"
        )
