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

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="GIFT_THING")
    owner = models.CharField(max_length=6)  # FK to User.code
    created = models.DateTimeField(default=timezone.now)
    headline = models.CharField(max_length=64)
    description = models.CharField(max_length=256, blank=True, default="")
    thumbnail = models.CharField(max_length=16, blank=True, default="")
    pictures = models.JSONField(default=list, blank=True)  # Array of image IDs
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="ACTIVE")
    faqs = models.JSONField(default=list, blank=True)  # Array of faq codes
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deal = models.JSONField(default=list, blank=True)  # Array of user codes who reserved
    available = models.BooleanField(default=True)

    class Meta:
        app_label = "core"
        db_table = "things"

    def __str__(self):
        return f"{self.code}: {self.headline}"

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner == user_code

    def reserve(self, user_code):
        """Reserve this thing for a user."""
        if user_code not in self.deal:
            self.deal.append(user_code)
            self.available = False
            self.save(update_fields=["deal", "available"])

    def release(self, user_code):
        """Release a user's reservation."""
        if user_code in self.deal:
            self.deal.remove(user_code)
            if not self.deal:
                self.available = True
            self.save(update_fields=["deal", "available"])

    def add_faq(self, faq_code):
        """Add a FAQ to this thing."""
        if faq_code not in self.faqs:
            self.faqs.append(faq_code)
            self.save(update_fields=["faqs"])

    def remove_faq(self, faq_code):
        """Remove a FAQ from this thing."""
        if faq_code in self.faqs:
            self.faqs.remove(faq_code)
            self.save(update_fields=["faqs"])

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

        # Import here to avoid circular import
        from core.models import Collection

        # Check if thing is in any collection where user is invited
        # Using Python-side filtering for SQLite compatibility
        for collection in Collection.objects.all():
            if self.code in collection.things and user_code in collection.invites:
                return True
        return False
