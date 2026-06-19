"""
BookingPeriod model - unified reservation/booking model for all thing types.

This model handles all reservation scenarios:
- GIFT_THING, SELL_THING: Single-use reservations (no dates, thing becomes INACTIVE)
- ORDER_THING: Repeatable orders (delivery_date + quantity, thing stays ACTIVE)
- LEND_THING, RENT_THING: Date-based bookings (start/end dates, thing stays ACTIVE on return)
- SHARE_THING: No dates — permanent ownership transfer on acceptance, thing stays ACTIVE
"""

from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.utils import generate_id

# Thing types that require dates for booking
DATE_BASED_TYPES = ["LEND_THING", "RENT_THING"]

# Thing types where the thing becomes INACTIVE after acceptance
SINGLE_USE_TYPES = ["GIFT_THING", "SELL_THING"]

# Thing types that can be ordered repeatedly (always available)
REPEATABLE_TYPES = ["ORDER_THING"]


class BookingPeriod(models.Model):
    """
    Unified reservation/booking model for all thing types.

    For GIFT/SELL: no dates required
    For ORDER: delivery_date and quantity required
    For LEND/RENT/SHARE: start_date and end_date required

    The thing_type field determines behavior on acceptance:
    - GIFT/SELL: thing.status -> INACTIVE
    - ORDER: thing stays ACTIVE (can be ordered again)
    - LEND/RENT/SHARE: thing stays ACTIVE (date-based availability)
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    created = models.DateTimeField(default=timezone.now)
    thing_code = models.ForeignKey(
        "Thing",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="thing_code",
        related_name="bookings",
    )
    thing_type = models.CharField(max_length=17, default="GIFT_THING")
    requester_code = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="requester_code",
        related_name="booking_requests",
    )
    requester_email = models.CharField(max_length=64)
    owner_code = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="owner_code",
        related_name="booking_owned",
    )
    start_date = models.DateField(null=True, blank=True)  # For LEND/RENT/SHARE
    end_date = models.DateField(null=True, blank=True)  # For LEND/RENT/SHARE
    delivery_date = models.DateField(null=True, blank=True)  # For ORDER_THING
    quantity = models.PositiveIntegerField(null=True, blank=True)  # For ORDER_THING
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    offered_things = models.ManyToManyField(
        "Thing",
        blank=True,
        related_name="swap_offers",
        db_table="booking_offered_things",
    )

    class Meta:
        app_label = "core"
        db_table = "booking_periods"
        indexes = [
            # has_overlap()/get_blocked_periods() filter by thing + status on
            # every booking request and calendar view; a thing's booking history
            # grows over time, so a composite turns those into an index seek
            # (status alone is already indexed; thing_code alone is the FK index).
            models.Index(fields=["thing_code", "status"], name="booking_thing_status_idx"),
        ]

    def __str__(self):
        if self.start_date and self.end_date:
            return (
                f"Booking {self.code} for {self.thing_code_id} "
                f"({self.start_date} - {self.end_date})"
            )
        if self.delivery_date:
            qty = f"x{self.quantity}" if self.quantity else ""
            return (
                f"Order {self.code} for {self.thing_code_id} (delivery: {self.delivery_date}) {qty}"
            )
        return f"Booking {self.code} for {self.thing_code_id}"

    def is_date_based(self):
        """Check if this booking requires dates (LEND/RENT/SHARE)."""
        return self.thing_type in DATE_BASED_TYPES

    def is_single_use(self):
        """Check if this booking makes the thing unavailable (GIFT/SELL)."""
        return self.thing_type in SINGLE_USE_TYPES

    def is_repeatable(self):
        """Check if this thing can be ordered repeatedly (ORDER)."""
        return self.thing_type in REPEATABLE_TYPES

    def is_valid(self):
        """Check if the booking request is still valid (not expired and PENDING)."""
        expiry_hours = getattr(settings, "BOOKING_EXPIRY_HOURS", 72)
        expiry_time = self.created + timedelta(hours=expiry_hours)
        return timezone.now() < expiry_time and self.status == self.Status.PENDING

    def accept(self):
        """Accept the booking request."""
        self.status = self.Status.ACCEPTED
        self.save(update_fields=["status"])

    def reject(self):
        """Reject the booking request."""
        self.status = self.Status.REJECTED
        self.save(update_fields=["status"])

    def cancel(self):
        """Cancel the booking (by the requester)."""
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status"])

    def expire(self):
        """Mark the booking as expired."""
        self.status = self.Status.EXPIRED
        self.save(update_fields=["status"])

    @classmethod
    def has_overlap(cls, thing_code, start_date, end_date, exclude_booking_code=None):
        """
        Check if there's an overlap with existing PENDING or ACCEPTED bookings.

        existing.start_date <= requested.end_date AND existing.end_date >= requested.start_date
        """
        queryset = cls.objects.filter(
            thing_code=thing_code,
            status__in=[cls.Status.PENDING, cls.Status.ACCEPTED],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if exclude_booking_code:
            queryset = queryset.exclude(code=exclude_booking_code)

        return queryset.exists()

    @classmethod
    def get_blocked_periods(cls, thing_code):
        """
        Get all blocked periods for a thing (PENDING and ACCEPTED bookings).
        Returns queryset of BookingPeriod objects.
        """
        return cls.objects.filter(
            thing_code=thing_code,
            status__in=[cls.Status.PENDING, cls.Status.ACCEPTED],
        ).order_by("start_date")

    @classmethod
    def expire_old_pending(cls):
        """
        Expire all PENDING bookings that have passed the expiry time.

        For single-use types (GIFT/SELL), also restores the Thing to ACTIVE —
        the thing was set to TAKEN when the booking was created, and would
        otherwise remain stuck in TAKEN indefinitely after expiry.
        """
        # Lazy import to avoid circular dependency (Thing imports BookingPeriod)
        from core.models.thing import Thing  # noqa: PLC0415

        expiry_hours = getattr(settings, "BOOKING_EXPIRY_HOURS", 72)
        cutoff_time = timezone.now() - timedelta(hours=expiry_hours)

        with transaction.atomic():
            # Collect thing codes for single-use bookings that are about to expire
            single_use_thing_codes = list(
                cls.objects.filter(
                    status=cls.Status.PENDING,
                    thing_type__in=SINGLE_USE_TYPES,
                    created__lt=cutoff_time,
                ).values_list("thing_code_id", flat=True)
            )

            if single_use_thing_codes:
                Thing.objects.filter(
                    code__in=single_use_thing_codes,
                    status=Thing.Status.TAKEN,
                    is_endless=False,
                ).update(status=Thing.Status.ACTIVE)

            expired_count = cls.objects.filter(
                status=cls.Status.PENDING,
                created__lt=cutoff_time,
            ).update(status=cls.Status.EXPIRED)

        return expired_count
