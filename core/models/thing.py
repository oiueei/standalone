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

    TYPE_CHOICES = [
        ("GIFT_THING", "Gift Thing"),
        ("SELL_THING", "Sell Thing"),
        ("ORDER_THING", "Order Thing"),
        ("RENT_THING", "Rent Thing"),
        ("LEND_THING", "Lend Thing"),
        ("SHARE_THING", "Share Thing"),
        ("EVENT_THING", "Event Thing"),
        ("WISH_THING", "Wish Thing"),
        ("ASSET_THING", "Asset Thing"),
    ]

    BOOKING_UNIT_CHOICES = [
        ("DAY", "Day"),
        ("HOUR", "Hour"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("TAKEN", "Taken"),
    ]

    AVAILABILITY_CHOICES = [
        ("IMMEDIATE", "Immediate"),
        ("NEXT_WEEK", "Next week"),
        ("END_OF_MONTH", "End of month"),
        ("NEXT_MONTH", "Next month"),
    ]

    CONDITION_CHOICES = [
        ("NEW", "New"),
        ("GOOD", "Good condition"),
        ("FAIR", "Fair"),
        ("USED", "Used"),
        ("WELL_USED", "Well used"),
        ("ALMOST_JUNK", "Almost junk"),
    ]

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="GIFT_THING")
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
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="ACTIVE")
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(
        max_length=12, choices=AVAILABILITY_CHOICES, blank=True, default=""
    )
    location = models.CharField(max_length=32, blank=True, default="")
    condition = models.CharField(max_length=12, choices=CONDITION_CHOICES, blank=True, default="")
    event_date = models.DateTimeField(null=True, blank=True)
    booking_unit = models.CharField(
        max_length=4, choices=BOOKING_UNIT_CHOICES, blank=True, default=""
    )
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
        if self.status == "INACTIVE":
            return False

        # Check if thing is in any active collection where user is invited
        return self.collections.filter(invites__code=user_code, status="ACTIVE").exists()
