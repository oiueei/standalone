"""
Thing serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Thing
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, validate_image_id


class ThingSerializer(serializers.ModelSerializer):
    """Full thing serializer."""

    thumbnail_url = serializers.SerializerMethodField()
    pictures_urls = serializers.SerializerMethodField()
    owner = serializers.CharField(source="owner_id")
    faqs = serializers.SerializerMethodField()
    deal = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)

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

    def get_faqs(self, obj):
        return list(obj.faq_set.values_list("code", flat=True))


class ImageIdListField(serializers.ListField):
    """A list field that validates each item as an image ID."""

    child = serializers.CharField(max_length=16, allow_blank=True)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return [validate_image_id(item) if item else item for item in value]


class ThingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a thing."""

    headline = SafeHeadlineField(max_length=64)
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
    thumbnail = ImageIdField()
    pictures = ImageIdListField(required=False)

    class Meta:
        model = Thing
        fields = [
            "headline",
            "description",
            "thumbnail",
            "pictures",
            "status",
            "fee",
            "available",
        ]
