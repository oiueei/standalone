"""
Collection serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import RSVP, Collection, Thing, User
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import SafeHeadlineField, SafeTextField


class CollectionThingSummarySerializer(serializers.ModelSerializer):
    """Lightweight thing serializer for collection listings."""

    owner = serializers.CharField(source="owner_id")
    thumbnail_url = serializers.SerializerMethodField()
    pending_booking = serializers.SerializerMethodField()
    my_pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()

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
            "availability",
            "location",
            "condition",
            "thumbnail_url",
            "pending_booking",
            "my_pending_booking",
            "pending_questions",
            "created",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail) if obj.thumbnail else None

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

    def get_pending_questions(self, obj):
        # Use prefetched faq_set cache if available
        return sum(1 for faq in obj.faq_set.all() if faq.answer == "")


class CollectionInviteSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for invited users."""

    class Meta:
        model = User
        fields = ["code", "email", "name"]


class CollectionSerializer(serializers.ModelSerializer):
    """Full collection serializer."""

    owner = serializers.CharField(source="owner_id")
    owner_name = serializers.SerializerMethodField()
    things = serializers.SerializerMethodField()
    invites = CollectionInviteSummarySerializer(many=True, read_only=True)
    pending_invites = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = [
            "code",
            "owner",
            "owner_name",
            "created",
            "headline",
            "description",
            "status",
            "things",
            "invites",
            "pending_invites",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "things",
            "invites",
            "pending_invites",
        ]

    def get_owner_name(self, obj):
        return obj.owner.name or obj.owner.email

    def get_things(self, obj):
        request = self.context.get("request")
        things = obj.things.all()
        if request and not obj.is_owner(request.user.code):
            things = things.exclude(status="INACTIVE")
        return CollectionThingSummarySerializer(things, many=True, context=self.context).data

    def get_pending_invites(self, obj):
        rsvps = RSVP.objects.filter(
            action="COLLECTION_INVITE",
            target_code=obj.code,
        ).values("user_code_id", "user_email")
        return [{"code": r["user_code_id"], "email": r["user_email"]} for r in rsvps]

class CollectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a collection."""

    headline = SafeHeadlineField(max_length=64)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
        ]


class CollectionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a collection."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
            "status",
        ]


class CollectionInviteSerializer(serializers.Serializer):
    """Serializer for inviting a user to a collection."""

    email = serializers.EmailField(max_length=64)


class CollectionAddThingSerializer(serializers.Serializer):
    """Serializer for adding a thing to a collection."""

    thing_code = serializers.CharField(max_length=6)


class CollectionRemoveThingSerializer(serializers.Serializer):
    """Serializer for removing a thing from a collection."""

    thing_code = serializers.CharField(max_length=6)


class CollectionRemoveInviteSerializer(serializers.Serializer):
    """Serializer for removing a user from a collection's invite list."""

    user_code = serializers.CharField(max_length=6)
