"""The pickup point of a network's dinamizador, read and written.

The conditions (``deposit_policy``, ``request_info``, ``email_note``) are the
collection's own fields with the same widths and the same localized form, so a
point cannot say in one language what the collection could not.
"""

from rest_framework import serializers

from core.models import NetworkPoint
from core.utils import asset_url
from core.validators import ImageIdField, LocalizedTextField, SafeHeadlineField

POINT_FIELDS = [
    "code",
    "user",
    "display_name",
    "entity_name",
    "address",
    "hours_note",
    "contact",
    "logo",
    "logo_url",
    "weekdays",
    "closed_dates",
    "deposit_policy",
    "request_info",
    "email_note",
]


class NetworkPointSerializer(serializers.ModelSerializer):
    """A point as the network's readers see it: public with the collection, address
    included. Only ``email_note`` is not: the note the entity writes into the emails
    its requesters get is read back by its own dinamizador and by the founder, who
    answers for the network, and by nobody else."""

    user = serializers.CharField(source="user_id")
    display_name = serializers.CharField(read_only=True)
    email_note = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = NetworkPoint
        fields = POINT_FIELDS
        read_only_fields = POINT_FIELDS

    def get_logo_url(self, obj):
        return asset_url(obj.logo) if obj.logo else None

    def get_email_note(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return ""
        if user.code == obj.user_id or obj.collection.is_owner(user.code):
            return obj.email_note
        return ""


class NetworkPointWriteSerializer(serializers.ModelSerializer):
    """What a dinamizador may set on their own point."""

    entity_name = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    address = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    hours_note = SafeHeadlineField(max_length=128, required=False, allow_blank=True)
    contact = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    # The same folder as a collection's logo: an entity's is the same kind of image.
    logo = ImageIdField(folder="oiueei/collections", required=False, allow_blank=True)
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        max_length=7,
    )
    # Same line the collection takes: comma-separated DD/MM/YYYY, parsed to sorted ISO.
    closed_dates = serializers.CharField(required=False, allow_blank=True)
    deposit_policy = LocalizedTextField(max_length=256, required=False, allow_blank=True)
    request_info = LocalizedTextField(
        max_length=512, storage_max_length=2048, required=False, allow_blank=True
    )
    email_note = LocalizedTextField(
        max_length=512, storage_max_length=2048, required=False, allow_blank=True
    )

    class Meta:
        model = NetworkPoint
        fields = [
            "entity_name",
            "address",
            "hours_note",
            "contact",
            "logo",
            "weekdays",
            "closed_dates",
            "deposit_policy",
            "request_info",
            "email_note",
        ]

    def validate_weekdays(self, value):
        return sorted(set(value))

    def validate_closed_dates(self, value):
        from core.serializers.collection import _parse_closed_dates

        return _parse_closed_dates(value)
