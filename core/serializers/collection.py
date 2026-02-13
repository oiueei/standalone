"""
Collection serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Collection, Theeeme, Thing
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField


class CollectionThingSummarySerializer(serializers.ModelSerializer):
    """Lightweight thing serializer for collection listings."""

    owner = serializers.CharField(source="owner_id")
    thumbnail_url = serializers.SerializerMethodField()
    pending_booking = serializers.SerializerMethodField()

    class Meta:
        model = Thing
        fields = [
            "code",
            "type",
            "owner",
            "headline",
            "description",
            "status",
            "fee",
            "thumbnail_url",
            "pending_booking",
            "created",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail) if obj.thumbnail else None

    def get_pending_booking(self, obj):
        booking = BookingPeriod.objects.filter(
            thing_code=obj,
            status="PENDING",
        ).first()
        return booking.code if booking else None


class CollectionSerializer(serializers.ModelSerializer):
    """Full collection serializer."""

    thumbnail_url = serializers.SerializerMethodField()
    hero_url = serializers.SerializerMethodField()
    owner = serializers.CharField(source="owner_id")
    things = CollectionThingSummarySerializer(many=True, read_only=True)
    invites = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)
    theeeme = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Theeeme.objects.all(),
    )

    class Meta:
        model = Collection
        fields = [
            "code",
            "owner",
            "created",
            "headline",
            "description",
            "thumbnail",
            "thumbnail_url",
            "hero",
            "hero_url",
            "status",
            "things",
            "invites",
            "theeeme",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "things",
            "invites",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail)

    def get_hero_url(self, obj):
        return cloudinary_url(obj.hero)


class CollectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a collection."""

    headline = SafeHeadlineField(max_length=64)
    thumbnail = ImageIdField()
    hero = ImageIdField()
    theeeme = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Theeeme.objects.all(),
        required=False,
    )

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
            "thumbnail",
            "hero",
            "theeeme",
        ]


class CollectionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a collection."""

    headline = SafeHeadlineField(max_length=64, required=False)
    thumbnail = ImageIdField()
    hero = ImageIdField()
    theeeme = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Theeeme.objects.all(),
        required=False,
    )

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
            "thumbnail",
            "hero",
            "status",
            "theeeme",
        ]


class CollectionInviteSerializer(serializers.Serializer):
    """Serializer for inviting a user to a collection."""

    email = serializers.EmailField(max_length=64)


class CollectionAddThingSerializer(serializers.Serializer):
    """Serializer for adding a thing to a collection."""

    thing_code = serializers.CharField(max_length=6)


class CollectionRemoveInviteSerializer(serializers.Serializer):
    """Serializer for removing a user from a collection's invite list."""

    user_code = serializers.CharField(max_length=6)
