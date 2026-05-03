"""
Collection serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import RSVP, Collection, Thing, User
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField

# Thing types valid for proprietary collections (excludes COMMUNITY-only types
# WISH_THING, SHARE_THING, ASSET_THING and the SWAP_THING which is gated by
# is_swap on COMMUNITY collections).
PROPRIETARY_THING_TYPES = (
    "GIFT_THING",
    "SELL_THING",
    "ORDER_THING",
    "RENT_THING",
    "LEND_THING",
    "EVENT_THING",
    "APPOINTMENT_THING",
)
MINIMALIST_THING_TYPES = ("GIFT_THING", "SHARE_THING", "SWAP_THING")


class CollectionThingSummarySerializer(serializers.ModelSerializer):
    """Lightweight thing serializer for collection listings."""

    owner = serializers.CharField(source="owner_id")
    owner_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    pending_booking = serializers.SerializerMethodField()
    my_pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()
    transfer_count = serializers.SerializerMethodField()
    attendee_count = serializers.SerializerMethodField()
    helper_count = serializers.SerializerMethodField()
    collection_swap_minimum_items = serializers.SerializerMethodField()
    my_swap_count_in_collection = serializers.SerializerMethodField()
    deal = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)

    class Meta:
        model = Thing
        fields = [
            "code",
            "type",
            "owner",
            "owner_name",
            "headline",
            "description",
            "status",
            "fee",
            "availability",
            "location",
            "condition",
            "event_date",
            "booking_unit",
            "slot_duration",
            "thumbnail_url",
            "pending_booking",
            "my_pending_booking",
            "pending_questions",
            "transfer_count",
            "attendee_count",
            "helper_count",
            "collection_swap_minimum_items",
            "my_swap_count_in_collection",
            "deal",
            "created",
        ]

    def get_owner_name(self, obj):
        return obj.owner.name or obj.owner.email

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

    def get_collection_swap_minimum_items(self, obj):
        parent = self.context.get("parent_collection")
        return parent.swap_minimum_items if parent else 0

    def get_my_swap_count_in_collection(self, obj):
        # Pre-computed once at the parent CollectionSerializer level — same
        # value for every thing in this collection, so we avoid N queries.
        return self.context.get("my_swap_count_in_collection", 0)


class CollectionInviteSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for invited users."""

    class Meta:
        model = User
        fields = ["code", "email", "name"]


class CollectionSerializer(serializers.ModelSerializer):
    """Full collection serializer."""

    owner = serializers.CharField(source="owner_id")
    owner_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    things = serializers.SerializerMethodField()
    invites = CollectionInviteSummarySerializer(many=True, read_only=True)
    pending_invites = serializers.SerializerMethodField()
    is_paused = serializers.BooleanField(read_only=True)

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
            "mode",
            "digest_frequency",
            "is_swap",
            "is_share",
            "newsletter_enabled",
            "is_minimalist",
            "swap_minimum_items",
            "allowed_thing_types",
            "thumbnail",
            "thumbnail_url",
            "pause_message",
            "is_paused",
            "things",
            "invites",
            "pending_invites",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "is_paused",
            "things",
            "invites",
            "pending_invites",
        ]

    def get_owner_name(self, obj):
        return obj.owner.name or obj.owner.email

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail) if obj.thumbnail else None

    def get_things(self, obj):
        request = self.context.get("request")
        ctx = {**self.context, "parent_collection": obj}
        if request and request.user.is_authenticated and obj.is_swap:
            ctx["my_swap_count_in_collection"] = Thing.objects.filter(
                owner=request.user,
                type="SWAP_THING",
                status__in=("ACTIVE", "TAKEN"),
                collections=obj,
            ).count()
        things = obj.things.all()
        if request and not obj.is_owner(request.user.code):
            things = things.exclude(status="INACTIVE")
        return CollectionThingSummarySerializer(things, many=True, context=ctx).data

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
    thumbnail = ImageIdField(required=False, allow_blank=True)

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
            "mode",
            "digest_frequency",
            "is_swap",
            "is_share",
            "newsletter_enabled",
            "is_minimalist",
            "swap_minimum_items",
            "allowed_thing_types",
            "thumbnail",
        ]

    def validate(self, attrs):
        is_swap = attrs.get("is_swap", False)
        is_share = attrs.get("is_share", False)
        is_minimalist = attrs.get("is_minimalist", False)
        newsletter_enabled = attrs.get("newsletter_enabled", False)
        swap_minimum_items = attrs.get("swap_minimum_items", 0)
        mode = attrs.get("mode", "PROPRIETARY")
        allowed_thing_types = attrs.get("allowed_thing_types", [])
        if is_swap and is_share:
            raise serializers.ValidationError(
                "A collection cannot be both swap-only and share-only."
            )
        if (is_swap or is_share) and mode != "COMMUNITY":
            raise serializers.ValidationError("Swap and share modes require COMMUNITY mode.")
        if newsletter_enabled and not is_share:
            raise serializers.ValidationError("Newsletter requires share mode to be enabled.")
        if is_minimalist and is_swap:
            raise serializers.ValidationError(
                "A collection cannot be both minimalist and swap-only."
            )
        if swap_minimum_items > 0 and not is_swap:
            raise serializers.ValidationError(
                "swap_minimum_items can only be set on swap collections."
            )
        _validate_allowed_thing_types(mode, is_minimalist, allowed_thing_types)
        return attrs


def _validate_allowed_thing_types(mode, is_minimalist, allowed_thing_types):
    """Validate the allowed_thing_types list when non-empty.

    Empty list means "no restriction" — accepted in any mode (preserves the
    pre-feature behaviour and keeps the API tolerant for non-form callers).
    The "user must pick at least one" rule is enforced in the create/edit
    form on the frontend, where it belongs as a UX nudge.

    When non-empty:
    - PROPRIETARY excludes COMMUNITY-only types (WISH/SHARE/ASSET/SWAP)
    - PROPRIETARY + is_minimalist must be exactly [GIFT_THING]
    """
    if not allowed_thing_types:
        return
    if mode == "PROPRIETARY":
        if is_minimalist:
            if list(allowed_thing_types) != ["GIFT_THING"]:
                raise serializers.ValidationError(
                    "Album collections only accept gifts — allowed_thing_types"
                    " must be exactly ['GIFT_THING']."
                )
            return
        invalid = [t for t in allowed_thing_types if t not in PROPRIETARY_THING_TYPES]
        if invalid:
            raise serializers.ValidationError(
                f"These types are not allowed in proprietary collections: {invalid}"
            )


class CollectionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a collection."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField(required=False, allow_blank=True)
    pause_message = SafeTextField(max_length=256, required=False, allow_blank=True)

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
            "status",
            "mode",
            "digest_frequency",
            "is_swap",
            "is_share",
            "newsletter_enabled",
            "is_minimalist",
            "swap_minimum_items",
            "allowed_thing_types",
            "thumbnail",
            "pause_message",
        ]

    def validate(self, attrs):
        instance = self.instance
        is_swap = attrs.get("is_swap", instance.is_swap if instance else False)
        is_share = attrs.get("is_share", instance.is_share if instance else False)
        is_minimalist = attrs.get("is_minimalist", instance.is_minimalist if instance else False)
        newsletter_enabled = attrs.get(
            "newsletter_enabled", instance.newsletter_enabled if instance else False
        )
        swap_minimum_items = attrs.get(
            "swap_minimum_items", instance.swap_minimum_items if instance else 0
        )
        mode = attrs.get("mode", instance.mode if instance else "PROPRIETARY")
        allowed_thing_types = attrs.get(
            "allowed_thing_types",
            instance.allowed_thing_types if instance else [],
        )
        if is_swap and is_share:
            raise serializers.ValidationError(
                "A collection cannot be both swap-only and share-only."
            )
        if (is_swap or is_share) and mode != "COMMUNITY":
            raise serializers.ValidationError("Swap and share modes require COMMUNITY mode.")
        if newsletter_enabled and not is_share:
            raise serializers.ValidationError("Newsletter requires share mode to be enabled.")
        if is_minimalist and is_swap:
            raise serializers.ValidationError(
                "A collection cannot be both minimalist and swap-only."
            )
        if swap_minimum_items > 0 and not is_swap:
            raise serializers.ValidationError(
                "swap_minimum_items can only be set on swap collections."
            )
        _validate_allowed_thing_types(mode, is_minimalist, allowed_thing_types)
        # Orphan check: if this is an update narrowing the list, every existing
        # thing currently in the collection must keep a valid slot in the new
        # list. Otherwise the rule would become incoherent ("type X is not
        # allowed but the collection contains 3 of them").
        if instance is not None and "allowed_thing_types" in attrs and allowed_thing_types:
            existing_types = set(instance.things.values_list("type", flat=True))
            orphaned = sorted(existing_types - set(allowed_thing_types))
            if orphaned:
                raise serializers.ValidationError(
                    "Cannot restrict the allowed types: existing things would be"
                    f" orphaned (types: {orphaned}). Remove them first."
                )
        return attrs


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


class CollectionBroadcastSerializer(serializers.Serializer):
    """Serializer for broadcasting a message to collection invitees."""

    subject = SafeHeadlineField(max_length=64)
    message = SafeTextField(max_length=256)
