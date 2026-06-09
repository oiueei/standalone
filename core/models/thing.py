"""
Thing model for OIUEEI.
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class Thing(models.Model):
    """
    An item in a collection (gift, sale, order, rent, lend, or share).

    Reservation status (status):
    - ACTIVE: Visible to owner + invited users, available for reservation
    - TAKEN: Visible to guests, awaiting owner confirmation (not available for new requests)
    - INACTIVE: Hidden from guests, not available for reservation
    """

    class Type(models.TextChoices):
        GIFT_THING = "GIFT_THING", "Gift Thing"
        SELL_THING = "SELL_THING", "Sell Thing"
        ORDER_THING = "ORDER_THING", "Order Thing"
        RENT_THING = "RENT_THING", "Rent Thing"
        LEND_THING = "LEND_THING", "Lend Thing"
        SHARE_THING = "SHARE_THING", "Share Thing"
        WISH_THING = "WISH_THING", "Wish Thing"
        SWAP_THING = "SWAP_THING", "Swap Thing"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        TAKEN = "TAKEN", "Taken"

    class Availability(models.TextChoices):
        IMMEDIATE = "IMMEDIATE", "Immediate"
        NEXT_WEEK = "NEXT_WEEK", "Next week"
        END_OF_MONTH = "END_OF_MONTH", "End of month"
        NEXT_MONTH = "NEXT_MONTH", "Next month"

    class Condition(models.TextChoices):
        NEW = "NEW", "New"
        GOOD = "GOOD", "Good condition"
        FAIR = "FAIR", "Fair"
        USED = "USED", "Used"
        WELL_USED = "WELL_USED", "Well used"
        ALMOST_JUNK = "ALMOST_JUNK", "Almost junk"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    type = models.CharField(max_length=11, choices=Type.choices, default=Type.GIFT_THING)
    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="owner",
        related_name="owned_things",
    )
    created = models.DateTimeField(default=timezone.now)
    headline = models.CharField(max_length=64)
    description = models.CharField(max_length=256, blank=True, default="")
    thumbnail = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(
        max_length=12, choices=Availability.choices, blank=True, default=""
    )
    location = models.CharField(max_length=32, blank=True, default="")
    condition = models.CharField(max_length=12, choices=Condition.choices, blank=True, default="")
    documents = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="Attached documents: [{public_id, filename, content_type}]. Max 5.",
    )
    is_endless = models.BooleanField(default=False)
    deal = models.ManyToManyField(
        "User",
        blank=True,
        related_name="deals",
        db_table="thing_deals",
    )

    class Meta:
        app_label = "core"
        db_table = "things"

    def __str__(self):
        return f"{self.code}: {self.headline}"

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner_id == user_code

    def reserve(self, user_code):
        """Add a user to the deal M2M (tracks who has reserved)."""
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.deal.add(user)
        except User.DoesNotExist:
            pass

    def release(self, user_code):
        """Remove a user from the deal M2M."""
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.deal.remove(user)
        except User.DoesNotExist:
            pass

    def can_view(self, user_code):
        """
        Check if the given user can view this thing.

        Visibility rules:
        - Owner can always view their own things
        - Invited users can only view ACTIVE or TAKEN things (not INACTIVE)

        Args:
            user_code: The user_code to check

        Returns:
            True if user is owner, or is invited and thing is not INACTIVE
        """
        if self.is_owner(user_code):
            return True

        # INACTIVE things are only visible to the owner
        if self.status == self.Status.INACTIVE:
            return False

        # Check if thing is in any active collection where user is invited or is the owner
        from core.models.collection import Collection

        return (
            self.collections.filter(status=Collection.Status.ACTIVE)
            .filter(models.Q(invites__code=user_code) | models.Q(owner__code=user_code))
            .exists()
        )
