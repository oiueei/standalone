"""
User serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Collection, Theeeme, User
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField


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
    photo_url = serializers.SerializerMethodField()
    in_community = serializers.SerializerMethodField()

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
            "about",
            "photo",
            "photo_url",
            "koro",
            "theeeme",
            "theeeme_colors",
            "notify_activity",
            "notify_news",
            "age_range",
            "postal_code",
            "in_community",
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

    def get_photo_url(self, obj):
        return cloudinary_url(obj.photo)

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

    def get_in_community(self, obj):
        """True when the user owns or belongs to >=1 COMMUNITY collection — gates
        the optional age/postal fields in the profile editor."""
        community = Collection.Mode.COMMUNITY
        return (
            obj.owned_collections.filter(mode=community).exists()
            or obj.invited_to_collections.filter(mode=community).exists()
        )


class UserPublicSerializer(serializers.ModelSerializer):
    """Public user profile serializer (limited fields)."""

    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "code",
            "name",
            "headline",
            "about",
            "photo_url",
            "created",
        ]

    def get_photo_url(self, obj):
        return cloudinary_url(obj.photo)


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    name = SafeHeadlineField(max_length=32, required=False, allow_blank=True)
    headline = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    about = SafeTextField(max_length=2000, required=False, allow_blank=True)
    photo = ImageIdField(required=False, allow_blank=True)
    theeeme = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Theeeme.objects.all(),
        required=False,
    )
    age_range = serializers.ChoiceField(
        choices=User.AgeRange.choices, required=False, allow_blank=True
    )
    postal_code = SafeHeadlineField(max_length=10, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "name",
            "headline",
            "about",
            "photo",
            "koro",
            "theeeme",
            "notify_activity",
            "notify_news",
            "age_range",
            "postal_code",
        ]
