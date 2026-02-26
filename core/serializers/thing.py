"""
Thing serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Thing
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField, validate_image_id


class ThingSerializer(serializers.ModelSerializer):
    """Full thing serializer."""

    thumbnail_url = serializers.SerializerMethodField()
    pictures_urls = serializers.SerializerMethodField()
    owner = serializers.CharField(source="owner_id")
    faqs = serializers.SerializerMethodField()
    deal = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)
    pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()
    collection_code = serializers.SerializerMethodField()
    collection_headline = serializers.SerializerMethodField()

    class Meta:
        model = Thing
        fields = [
            "code",
            "type",
            "owner",
            "created",
            "headline",
            "description",
            "thumbnail",
            "thumbnail_url",
            "pictures",
            "pictures_urls",
            "status",
            "faqs",
            "fee",
            "deal",
            "available",
            "pending_booking",
            "pending_questions",
            "collection_code",
            "collection_headline",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "faqs",
            "deal",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail)

    def get_pictures_urls(self, obj):
        return [cloudinary_url(pic_id) for pic_id in obj.pictures if pic_id]

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


class ImageIdListField(serializers.ListField):
    """A list field that validates each item as an image ID."""

    child = serializers.CharField(max_length=16, allow_blank=True)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return [validate_image_id(item) if item else item for item in value]


class ThingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a thing."""

    headline = SafeHeadlineField(max_length=64)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    pictures = ImageIdListField(required=False)

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "thumbnail",
            "pictures",
            "fee",
        ]


class ThingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a thing."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    pictures = ImageIdListField(required=False)

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "thumbnail",
            "pictures",
            "status",
            "fee",
            "available",
        ]
        read_only_fields = ["status"]
