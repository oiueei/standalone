"""
User serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import User
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField


class UserSerializer(serializers.ModelSerializer):
    """Full user serializer for authenticated user."""

    thumbnail_url = serializers.SerializerMethodField()
    hero_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "code",
            "email",
            "name",
            "created",
            "last_activity",
            "own_collections",
            "invited_collections",
            "things",
            "headline",
            "thumbnail",
            "thumbnail_url",
            "hero",
            "hero_url",
        ]
        read_only_fields = [
            "code",
            "email",
            "created",
            "last_activity",
            "own_collections",
            "invited_collections",
            "things",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail)

    def get_hero_url(self, obj):
        return cloudinary_url(obj.hero)


class UserPublicSerializer(serializers.ModelSerializer):
    """Public user profile serializer (limited fields)."""

    thumbnail_url = serializers.SerializerMethodField()
    hero_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "code",
            "name",
            "headline",
            "thumbnail",
            "thumbnail_url",
            "hero",
            "hero_url",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail)

    def get_hero_url(self, obj):
        return cloudinary_url(obj.hero)


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    headline = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    hero = ImageIdField()

    class Meta:
        model = User
        fields = [
            "name",
            "headline",
            "thumbnail",
            "hero",
        ]
