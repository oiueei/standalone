"""
Thing serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Thing
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField


class ThingSerializer(serializers.ModelSerializer):
    """Full thing serializer."""

    thumbnail_url = serializers.SerializerMethodField()
    owner = serializers.CharField(source="owner_id")
    owner_name = serializers.SerializerMethodField()
    faqs = serializers.SerializerMethodField()
    deal = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)
    pending_booking = serializers.SerializerMethodField()
    my_pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()
    collection_code = serializers.SerializerMethodField()
    collection_headline = serializers.SerializerMethodField()
    transfer_count = serializers.SerializerMethodField()
    attendee_count = serializers.SerializerMethodField()
    helper_count = serializers.SerializerMethodField()

    class Meta:
        model = Thing
        fields = [
            "code",
            "type",
            "owner",
            "owner_name",
            "created",
            "headline",
            "description",
            "thumbnail",
            "thumbnail_url",
            "status",
            "faqs",
            "fee",
            "availability",
            "location",
            "condition",
            "event_date",
            "deal",
            "pending_booking",
            "my_pending_booking",
            "pending_questions",
            "collection_code",
            "collection_headline",
            "transfer_count",
            "attendee_count",
            "helper_count",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "faqs",
            "deal",
        ]

    def get_owner_name(self, obj):
        return obj.owner.name or obj.owner.email

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail)

    def get_pending_booking(self, obj):
        # Use prefetched _pending_bookings if available, otherwise query
        if hasattr(obj, "_pending_bookings"):
            bookings = obj._pending_bookings
            return bookings[0].code if bookings else None
        booking = BookingPeriod.objects.filter(
            thing_code=obj,
            status="PENDING",
        ).first()
        return booking.code if booking else None

    def get_my_pending_booking(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        booking = BookingPeriod.objects.filter(
            thing_code=obj,
            requester_code=request.user,
            status="PENDING",
        ).first()
        return booking.code if booking else None

    def get_collection_code(self, obj):
        # Use prefetched collections cache if available
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return first.code if first else None

    def get_collection_headline(self, obj):
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return first.headline if first else None

    def get_faqs(self, obj):
        # Use prefetched faq_set cache if available
        return [faq.code for faq in obj.faq_set.all()]

    def get_pending_questions(self, obj):
        # Use prefetched faq_set cache if available
        return sum(1 for faq in obj.faq_set.all() if faq.answer == "")

    def get_transfer_count(self, obj):
        if hasattr(obj, "_transfer_count"):
            return obj._transfer_count
        return obj.transfers.count()

    def get_attendee_count(self, obj):
        if obj.type != "EVENT_THING":
            return None
        return obj.deal.count()

    def get_helper_count(self, obj):
        if obj.type != "WISH_THING":
            return None
        return obj.deal.count()


class ThingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a thing."""

    headline = SafeHeadlineField(max_length=64)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    location = SafeHeadlineField(max_length=32, required=False, allow_blank=True)

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "thumbnail",
            "fee",
            "availability",
            "location",
            "condition",
            "event_date",
        ]


class ThingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a thing."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    location = SafeHeadlineField(max_length=32, required=False, allow_blank=True)

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "thumbnail",
            "status",
            "fee",
            "availability",
            "location",
            "condition",
            "event_date",
        ]
        read_only_fields = ["status"]
