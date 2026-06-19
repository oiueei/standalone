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
    gallery = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Additional photos beyond the cover thumbnail: an ordered list of "
            "Cloudinary public_ids. Max 8. Things only (not collections)."
        ),
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Owner-defined tags assigned to this thing — a subset of its "
            "collection's tag vocabulary (Collection.tags). Max 12."
        ),
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

    def availability_window(self, horizon_days=90):
        """Live availability for date-based things (LEND/RENT) from the booking calendar.

        Returns ``{"available_today": bool, "next_available": date|None}`` for
        DATE_BASED_TYPES, or ``None`` for any other type (where a booking calendar
        doesn't apply). Prefetch-aware: reuses ``self._blocked_periods`` when the
        view prefetched it, otherwise issues a single ``get_blocked_periods`` query.
        Result is memoised on the instance so the two serializer fields that read
        it don't recompute.
        """
        if hasattr(self, "_availability_window_cache"):
            return self._availability_window_cache

        from core.models.booking import DATE_BASED_TYPES, BookingPeriod

        if self.type not in DATE_BASED_TYPES:
            self._availability_window_cache = None
            return None

        if hasattr(self, "_blocked_periods"):
            blocked = self._blocked_periods
        else:
            blocked = list(BookingPeriod.get_blocked_periods(self.code))

        from core.services.booking_service import compute_availability

        available_today, next_available = compute_availability(blocked, horizon_days=horizon_days)
        self._availability_window_cache = {
            "available_today": available_today,
            "next_available": next_available,
        }
        return self._availability_window_cache

    def can_view(self, user_code):
        """
        Check if the given user can view this thing.

        Visibility rules:
        - Owner can always view their own things
        - Invited users can only view ACTIVE or TAKEN things (not INACTIVE)
        - Anyone (including anonymous, ``user_code=None``) can view an ACTIVE/TAKEN
          thing that sits in at least one ACTIVE, PUBLIC collection

        Args:
            user_code: The user_code to check (None for an anonymous visitor)

        Returns:
            True if user is owner, or the thing is not INACTIVE and lives in an
            ACTIVE collection the user is invited to (or that is PUBLIC)
        """
        if self.is_owner(user_code):
            return True

        # INACTIVE things are only visible to the owner
        if self.status == self.Status.INACTIVE:
            return False

        # Visible if the thing is in any ACTIVE collection where the user is
        # invited, owns it, or the collection is PUBLIC (anonymous read).
        from core.models.collection import Collection

        # For an anonymous visitor (user_code=None) the membership/ownership
        # terms are dropped entirely: ``invites__code=None`` would otherwise
        # become ``IS NULL`` and, under the OR outer join, spuriously match
        # any collection that simply has no invitees.
        access = models.Q(visibility=Collection.Visibility.PUBLIC)
        if user_code is not None:
            access |= models.Q(invites__code=user_code) | models.Q(owner__code=user_code)

        return self.collections.filter(status=Collection.Status.ACTIVE).filter(access).exists()
