"""
User serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Theeeme, User
from core.validators import SafeHeadlineField


class UserSerializer(serializers.ModelSerializer):
    """Full user serializer for authenticated user."""

    own_collections = serializers.SerializerMethodField()
    invited_collections = serializers.SerializerMethodField()
    things = serializers.SerializerMethodField()
    theeeme = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Theeeme.objects.all(),
        required=False,
    )
    theeeme_colors = serializers.SerializerMethodField()

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
            "koro",
            "theeeme",
            "theeeme_colors",
        ]
        read_only_fields = [
            "code",
            "email",
            "created",
            "last_activity",
            "own_collections",
            "invited_collections",
            "things",
            "theeeme",
        ]

    def get_own_collections(self, obj):
        return list(obj.owned_collections.values_list("code", flat=True))

    def get_invited_collections(self, obj):
        return list(obj.invited_to_collections.values_list("code", flat=True))

    def get_things(self, obj):
        return list(obj.owned_things.values_list("code", flat=True))

    def get_theeeme_colors(self, obj):
        t = obj.theeeme
        if not t:
            return None
        return {
            "color_01": t.color_01,
            "color_02": t.color_02,
            "color_03": t.color_03,
            "color_04": t.color_04,
            "color_05": t.color_05,
            "color_06": t.color_06,
        }


class UserPublicSerializer(serializers.ModelSerializer):
    """Public user profile serializer (limited fields)."""

    class Meta:
        model = User
        fields = [
            "code",
            "name",
            "headline",
            "created",
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    name = SafeHeadlineField(max_length=32, required=False, allow_blank=True)
    headline = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    theeeme = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Theeeme.objects.all(),
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "name",
            "headline",
            "koro",
            "theeeme",
        ]
