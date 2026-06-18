"""
Wish serializers for OIUEEI.

A wish is a ``Thing`` of type WISH_THING (reusing ThingSerializer); these
serializers cover only the new ``WishResponse`` entity.
"""

from rest_framework import serializers

from core.models import WishResponse
from core.utils import cloudinary_url
from core.validators import SafeTextField


class WishResponseSerializer(serializers.ModelSerializer):
    """Full read representation of a wish response."""

    wish = serializers.CharField(source="wish_id")
    responder = serializers.CharField(source="responder_id")
    responder_name = serializers.SerializerMethodField()
    thing = serializers.CharField(source="thing_id", allow_null=True)
    thing_headline = serializers.SerializerMethodField()
    thing_type = serializers.SerializerMethodField()
    thing_thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = WishResponse
        fields = [
            "code",
            "wish",
            "responder",
            "responder_name",
            "created",
            "kind",
            "thing",
            "thing_headline",
            "thing_type",
            "thing_thumbnail_url",
            "message",
            "url",
            "fee",
            "status",
        ]
        read_only_fields = fields

    def get_responder_name(self, obj):
        return obj.responder.display_name

    def get_thing_headline(self, obj):
        return obj.thing.headline if obj.thing else None

    def get_thing_type(self, obj):
        return obj.thing.type if obj.thing else None

    def get_thing_thumbnail_url(self, obj):
        return cloudinary_url(obj.thing.thumbnail) if obj.thing else None


class WishResponseCreateSerializer(serializers.Serializer):
    """Validated input for answering a wish.

    The required fields depend on ``kind``:
    - HAVE_THIS: ``thing_code`` (a real listing owned by the responder).
    - KNOW_WHERE: ``message`` (text) + optional ``url``.
    - CAN_MAKE: ``message`` (text) + optional ``fee``.
    """

    kind = serializers.ChoiceField(choices=WishResponse.Kind.choices)
    thing_code = serializers.CharField(required=False, allow_blank=True)
    message = SafeTextField(max_length=256, required=False, allow_blank=True)
    url = serializers.URLField(max_length=255, required=False, allow_blank=True)
    fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    def validate(self, data):
        kind = data["kind"]
        if kind == WishResponse.Kind.HAVE_THIS:
            if not data.get("thing_code"):
                raise serializers.ValidationError({"thing_code": "Choose a listing to offer."})
        elif not (data.get("message") or "").strip():
            raise serializers.ValidationError({"message": "A message is required."})
        return data
