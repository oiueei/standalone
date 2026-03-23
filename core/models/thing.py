"""
Thing model for OIUEEI.
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class Thing(models.Model):
    """
    An item in a collection (gift, sale, order, rent, lend, or share).

    Visibility (available):
    - True: Visible to owner AND all collection invites
    - False: Visible ONLY to owner (hidden from invites)

    Reservation status (status):
    - ACTIVE: Available for reservation
    - TAKEN: Awaiting owner confirmation (not available for new requests)
    - INACTIVE: No longer available (completed or disabled)
    """

    TYPE_CHOICES = [
        ("GIFT_THING", "Gift Thing"),
        ("SELL_THING", "Sell Thing"),
        ("ORDER_THING", "Order Thing"),
        ("RENT_THING", "Rent Thing"),
        ("LEND_THING", "Lend Thing"),
        ("SHARE_THING", "Share Thing"),
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
    thumbnail = models.CharField(max_length=16, blank=True, default="")
    pictures = models.JSONField(default=list, blank=True)  # Array of image IDs
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="ACTIVE")
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(max_length=12, choices=AVAILABILITY_CHOICES, blank=True, default="")
    location = models.CharField(max_length=32, blank=True, default="")
    condition = models.CharField(max_length=12, choices=CONDITION_CHOICES, blank=True, default="")
    deal = models.ManyToManyField(
        "User",
        blank=True,
        related_name="deals",
        db_table="thing_deals",
    )
    available = models.BooleanField(default=True)

    class Meta:
        app_label = "core"
        db_table = "things"

    def __str__(self):
        return f"{self.code}: {self.headline}"

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner_id == user_code

    def reserve(self, user_code):
        """Reserve this thing for a user."""
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.deal.add(user)
            self.available = False
            self.save(update_fields=["available"])
        except User.DoesNotExist:
            pass

    def release(self, user_code):
        """Release a user's reservation."""
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.deal.remove(user)
            if not self.deal.exists():
                self.available = True
            self.save(update_fields=["available"])
        except User.DoesNotExist:
            pass

    def can_view(self, user_code):
        """
        Check if the given user can view this thing.

        Visibility rules:
        - Owner can always view their own things
        - Invited users can only view if available=True

        Args:
            user_code: The user_code to check

        Returns:
            True if user is owner, or is invited and thing is available
        """
        if self.is_owner(user_code):
            return True

        # If thing is not available, only owner can see it
        if not self.available:
            return False

        # Check if thing is in any collection where user is invited
        return self.collections.filter(invites__code=user_code).exists()
