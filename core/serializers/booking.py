"""
Booking serializers for OIUEEI.
"""

from datetime import date, timedelta

from rest_framework import serializers

from core.models.booking import BookingPeriod
from core.models.thing import Thing

# Bookings/orders can't be placed more than ~3 months ahead — matches the
# frontend's today+90 cap and the availability horizon (L7).
MAX_BOOKING_HORIZON_DAYS = 90


class SwapOfferedFieldsMixin(serializers.Serializer):
    """Shared swap fields: the codes/headlines of the things offered in exchange.

    Both return ``None`` for non-swap bookings, so the same two
    ``SerializerMethodField``s can be reused by every booking serializer that
    exposes a swap proposal (full owner view, owner calendar, requester view).
    """

    offered_thing_codes = serializers.SerializerMethodField()
    offered_thing_headlines = serializers.SerializerMethodField()

    def get_offered_thing_codes(self, obj):
        if obj.thing_type != Thing.Type.SWAP_THING:
            return None
        return list(obj.offered_things.values_list("code", flat=True))

    def get_offered_thing_headlines(self, obj):
        if obj.thing_type != Thing.Type.SWAP_THING:
            return None
        return list(obj.offered_things.values_list("headline", flat=True))


class BookingPeriodSerializer(SwapOfferedFieldsMixin, serializers.ModelSerializer):
    """Full booking period serializer (for owner view)."""

    thing_code = serializers.CharField(source="thing_code_id")
    thing_headline = serializers.CharField(source="thing_code.headline", read_only=True)
    requester_code = serializers.CharField(source="requester_code_id")
    requester_name = serializers.CharField(source="requester_code.name", read_only=True)
    owner_code = serializers.CharField(source="owner_code_id")

    class Meta:
        model = BookingPeriod
        fields = [
            "code",
            "created",
            "thing_code",
            "thing_headline",
            "thing_type",
            "requester_code",
            "requester_name",
            "requester_email",
            "owner_code",
            "start_date",
            "end_date",
            "delivery_date",
            "quantity",
            "status",
            "offered_thing_codes",
            "offered_thing_headlines",
        ]


class BookingPeriodCalendarSerializer(serializers.ModelSerializer):
    """Calendar view serializer (limited info for guests)."""

    class Meta:
        model = BookingPeriod
        fields = [
            "start_date",
            "end_date",
            "status",
        ]


class BookingPeriodOwnerCalendarSerializer(SwapOfferedFieldsMixin, serializers.ModelSerializer):
    """Calendar view serializer for owner (includes requester info)."""

    requester_code = serializers.CharField(source="requester_code_id")
    requester_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingPeriod
        fields = [
            "code",
            "created",
            "requester_code",
            "requester_name",
            "start_date",
            "end_date",
            "delivery_date",
            "quantity",
            "status",
            "offered_thing_codes",
            "offered_thing_headlines",
        ]

    def get_requester_name(self, obj):
        return obj.requester_code.name or obj.requester_email


class ThingRequestWithDatesSerializer(serializers.Serializer):
    """Serializer for thing request with dates (LEND/RENT/SHARE)."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate_start_date(self, value):
        """Validate that start_date is today or in the future."""
        if value < date.today():
            raise serializers.ValidationError("Start date must be today or in the future")
        return value

    def validate(self, data):
        """Validate date range."""
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError(
                    {"end_date": "End date must be on or after start date"}
                )
            horizon = date.today() + timedelta(days=MAX_BOOKING_HORIZON_DAYS)
            if end_date > horizon:
                raise serializers.ValidationError(
                    {"end_date": "Dates can be at most 3 months ahead"}
                )
        return data


class ThingOrderSerializer(serializers.Serializer):
    """Serializer for ORDER_THING requests (delivery_date + quantity)."""

    delivery_date = serializers.DateField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)

    def validate_delivery_date(self, value):
        """Validate that delivery_date is today or in the future, within 3 months."""
        if value < date.today():
            raise serializers.ValidationError("Delivery date must be today or in the future")
        if value > date.today() + timedelta(days=MAX_BOOKING_HORIZON_DAYS):
            raise serializers.ValidationError("Delivery date can be at most 3 months ahead")
        return value


class ThingSwapRequestSerializer(serializers.Serializer):
    """Validates a SWAP request's offered items: a bounded list of thing codes (L5)."""

    offered_thing_codes = serializers.ListField(
        child=serializers.CharField(max_length=6),
        min_length=1,
        max_length=20,
    )


class MyBookingSerializer(SwapOfferedFieldsMixin, serializers.ModelSerializer):
    """Serializer for user's own booking requests."""

    thing_code = serializers.CharField(source="thing_code_id")
    thing_headline = serializers.CharField(source="thing_code.headline", read_only=True)
    owner_code = serializers.CharField(source="owner_code_id")
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingPeriod
        fields = [
            "code",
            "created",
            "thing_code",
            "thing_headline",
            "thing_type",
            "owner_code",
            "owner_name",
            "start_date",
            "end_date",
            "delivery_date",
            "quantity",
            "status",
            "offered_thing_codes",
            "offered_thing_headlines",
        ]

    def get_owner_name(self, obj):
        return obj.owner_code.display_name
