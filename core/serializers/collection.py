"""
Collection serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import RSVP, Collection, Thing, User
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField

# Thing types valid for proprietary collections (excludes COMMUNITY-only types
# WISH_THING, SHARE_THING and the SWAP_THING which is gated by
# is_swap on COMMUNITY collections).
PROPRIETARY_THING_TYPES = (
    Thing.Type.GIFT_THING,
    Thing.Type.SELL_THING,
    Thing.Type.ORDER_THING,
    Thing.Type.RENT_THING,
    Thing.Type.LEND_THING,
)
# Thing types valid for community collections without is_swap/is_share flags.
# SWAP_THING is excluded because it requires is_swap=True (which forces a
# single-type collection and bypasses the allowlist entirely).
COMMUNITY_THING_TYPES = (
    Thing.Type.GIFT_THING,
    Thing.Type.SELL_THING,
    Thing.Type.ORDER_THING,
    Thing.Type.RENT_THING,
    Thing.Type.LEND_THING,
    Thing.Type.SHARE_THING,
    Thing.Type.WISH_THING,
)
# Album mode in COMMUNITY narrows to GIFT and SHARE (SWAP needs is_swap, which
# is mutually exclusive with is_minimalist).
COMMUNITY_MINIMALIST_THING_TYPES = (Thing.Type.GIFT_THING, Thing.Type.SHARE_THING)


class CollectionThingSummarySerializer(serializers.ModelSerializer):
    """Lightweight thing serializer for collection listings."""

    owner = serializers.CharField(source="owner_id")
    owner_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    gallery_urls = serializers.SerializerMethodField()
    pending_booking = serializers.SerializerMethodField()
    my_pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()
    transfer_count = serializers.SerializerMethodField()
    response_count = serializers.SerializerMethodField()
    my_response = serializers.SerializerMethodField()
    collection_swap_minimum_items = serializers.SerializerMethodField()
    my_swap_count_in_collection = serializers.SerializerMethodField()
    available_today = serializers.SerializerMethodField()
    next_available = serializers.SerializerMethodField()
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
            "available_today",
            "next_available",
            "location",
            "condition",
            "thumbnail_url",
            "gallery_urls",
            "tags",
            "pending_booking",
            "my_pending_booking",
            "pending_questions",
            "transfer_count",
            "response_count",
            "my_response",
            "collection_swap_minimum_items",
            "my_swap_count_in_collection",
            "deal",
            "created",
        ]

    def get_owner_name(self, obj):
        return obj.owner.name or obj.owner.email

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail) if obj.thumbnail else None

    def get_gallery_urls(self, obj):
        return [cloudinary_url(public_id) for public_id in (obj.gallery or [])]

    def get_pending_booking(self, obj):
        # Use prefetched _pending_bookings if available, otherwise query
        if hasattr(obj, "_pending_bookings"):
            bookings = obj._pending_bookings
            return bookings[0].code if bookings else None
        booking = BookingPeriod.objects.filter(
            thing_code=obj,
            status=BookingPeriod.Status.PENDING,
        ).first()
        return booking.code if booking else None

    def get_my_pending_booking(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        # Reuse the prefetched PENDING bookings (all requesters) when present.
        if hasattr(obj, "_pending_bookings"):
            for b in obj._pending_bookings:
                if b.requester_code_id == request.user.code:
                    return b.code
            return None
        booking = BookingPeriod.objects.filter(
            thing_code=obj,
            requester_code=request.user,
            status=BookingPeriod.Status.PENDING,
        ).first()
        return booking.code if booking else None

    def get_pending_questions(self, obj):
        # Use prefetched faq_set cache if available
        return sum(1 for faq in obj.faq_set.all() if faq.answer == "")

    def get_transfer_count(self, obj):
        if hasattr(obj, "_transfer_count"):
            return obj._transfer_count
        return obj.transfers.count()

    def get_response_count(self, obj):
        if obj.type != Thing.Type.WISH_THING:
            return None
        return len(obj.responses.all())

    def get_my_response(self, obj):
        if obj.type != Thing.Type.WISH_THING:
            return None
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        for response in obj.responses.all():
            if response.responder_id == request.user.code:
                return {
                    "code": response.code,
                    "kind": response.kind,
                    "status": response.status,
                }
        return None

    def get_collection_swap_minimum_items(self, obj):
        parent = self.context.get("parent_collection")
        return parent.swap_minimum_items if parent else 0

    def get_my_swap_count_in_collection(self, obj):
        # Pre-computed once at the parent CollectionSerializer level — same
        # value for every thing in this collection, so we avoid N queries.
        return self.context.get("my_swap_count_in_collection", 0)

    def get_available_today(self, obj):
        # Live availability for date-based types (LEND/RENT); null otherwise.
        # Prefetch-aware via obj._blocked_periods (set by the collection view).
        window = obj.availability_window()
        return window["available_today"] if window else None

    def get_next_available(self, obj):
        window = obj.availability_window()
        return window["next_available"] if window else None


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
            "tags",
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
                type=Thing.Type.SWAP_THING,
                status__in=(Thing.Status.ACTIVE, Thing.Status.TAKEN),
                collections=obj,
            ).count()
        things = obj.things.all()
        if request and not obj.is_owner(request.user.code):
            things = things.exclude(status=Thing.Status.INACTIVE)
        return CollectionThingSummarySerializer(things, many=True, context=ctx).data

    def get_pending_invites(self, obj):
        rsvps = RSVP.objects.filter(
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=obj.code,
        ).values("user_code_id", "user_email")
        return [{"code": r["user_code_id"], "email": r["user_email"]} for r in rsvps]


class CollectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a collection."""

    headline = SafeHeadlineField(max_length=64)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField(required=False, allow_blank=True)
    tags = serializers.ListField(
        child=SafeHeadlineField(max_length=32),
        max_length=12,
        required=False,
        allow_empty=True,
    )

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
            "tags",
            "thumbnail",
        ]

    def validate_tags(self, value):
        return _normalize_tags(value)

    def validate(self, attrs):
        _validate_collection_flags(
            mode=attrs.get("mode", Collection.Mode.PROPRIETARY),
            is_swap=attrs.get("is_swap", False),
            is_share=attrs.get("is_share", False),
            is_minimalist=attrs.get("is_minimalist", False),
            newsletter_enabled=attrs.get("newsletter_enabled", False),
            swap_minimum_items=attrs.get("swap_minimum_items", 0),
            allowed_thing_types=attrs.get("allowed_thing_types", []),
        )
        return attrs


def _normalize_tags(tags):
    """Trim each tag, drop empties, and dedupe case-insensitively (first wins).

    Used by both collection serializers so the owner-defined tag vocabulary is
    always clean. The ListField (max_length=12) caps the raw count and
    SafeHeadlineField rejects HTML / over-length labels before this runs.
    """
    seen = set()
    result = []
    for raw in tags:
        label = (raw or "").strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _validate_allowed_thing_types(mode, is_minimalist, is_swap, is_share, allowed_thing_types):
    """Validate the allowed_thing_types list when non-empty.

    Empty list means "no restriction" — accepted in any mode (preserves the
    pre-feature behaviour and keeps the API tolerant for non-form callers).
    The "user must pick at least one" rule is enforced in the create/edit
    form on the frontend, where it belongs as a UX nudge.

    When non-empty:
    - is_swap forces SWAP_THING via its flag, so the only consistent list is
      [Thing.Type.SWAP_THING]. Anything else is rejected so the form and the data
      cannot disagree.
    - is_share is the same with [Thing.Type.SHARE_THING].
    - PROPRIETARY excludes COMMUNITY-only types (WISH/SHARE/ASSET/SWAP).
    - PROPRIETARY + is_minimalist must be exactly [GIFT_THING].
    - COMMUNITY (no flags) accepts the 7-type COMMUNITY set (all except SWAP,
      which requires is_swap).
    - COMMUNITY + is_minimalist narrows to [GIFT_THING, SHARE_THING] (SWAP is
      out because is_minimalist and is_swap are mutually exclusive).
    """
    if not allowed_thing_types:
        return
    if is_swap:
        if list(allowed_thing_types) != [Thing.Type.SWAP_THING]:
            raise serializers.ValidationError(
                "Swap collections only accept swap things —"
                " allowed_thing_types must be ['SWAP_THING'] or empty."
            )
        return
    if is_share:
        if list(allowed_thing_types) != [Thing.Type.SHARE_THING]:
            raise serializers.ValidationError(
                "Share-only collections only accept share things —"
                " allowed_thing_types must be ['SHARE_THING'] or empty."
            )
        return
    if mode == Collection.Mode.PROPRIETARY:
        if is_minimalist:
            if list(allowed_thing_types) != [Thing.Type.GIFT_THING]:
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
        return
    # COMMUNITY
    valid = COMMUNITY_MINIMALIST_THING_TYPES if is_minimalist else COMMUNITY_THING_TYPES
    invalid = [t for t in allowed_thing_types if t not in valid]
    if invalid:
        if is_minimalist:
            raise serializers.ValidationError(
                "Album mode in community collections only accepts gifts and"
                f" shares — these types are not allowed: {invalid}"
            )
        raise serializers.ValidationError(
            f"These types are not allowed in community collections: {invalid}"
        )


def _validate_collection_flags(
    *,
    mode,
    is_swap,
    is_share,
    is_minimalist,
    newsletter_enabled,
    swap_minimum_items,
    allowed_thing_types,
):
    """Shared flag-consistency rules for collection create/update validate().

    Both serializers resolve the effective flag values differently (create uses
    plain defaults, update falls back to the existing instance) and then call this
    with the resolved values, so the rules live in exactly one place.
    """
    if is_swap and is_share:
        raise serializers.ValidationError("A collection cannot be both swap-only and share-only.")
    if (is_swap or is_share) and mode != Collection.Mode.COMMUNITY:
        raise serializers.ValidationError("Swap and share modes require COMMUNITY mode.")
    if newsletter_enabled and not is_share:
        raise serializers.ValidationError("Newsletter requires share mode to be enabled.")
    if is_minimalist and is_swap:
        raise serializers.ValidationError("A collection cannot be both minimalist and swap-only.")
    if swap_minimum_items > 0 and not is_swap:
        raise serializers.ValidationError("swap_minimum_items can only be set on swap collections.")
    _validate_allowed_thing_types(mode, is_minimalist, is_swap, is_share, allowed_thing_types)


class CollectionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a collection."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField(required=False, allow_blank=True)
    pause_message = SafeTextField(max_length=256, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=SafeHeadlineField(max_length=32),
        max_length=12,
        required=False,
        allow_empty=True,
    )

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
            "tags",
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
        mode = attrs.get("mode", instance.mode if instance else Collection.Mode.PROPRIETARY)
        allowed_thing_types = attrs.get(
            "allowed_thing_types",
            instance.allowed_thing_types if instance else [],
        )
        _validate_collection_flags(
            mode=mode,
            is_swap=is_swap,
            is_share=is_share,
            is_minimalist=is_minimalist,
            newsletter_enabled=newsletter_enabled,
            swap_minimum_items=swap_minimum_items,
            allowed_thing_types=allowed_thing_types,
        )
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

    def validate_tags(self, value):
        return _normalize_tags(value)

    def update(self, instance, validated_data):
        """Cascade-strip: when the owner removes a tag from the collection's
        vocabulary, drop it from every thing in the collection that still had it
        (tags are cosmetic, so we silently clean up rather than block the edit)."""
        new_tags = validated_data.get("tags")
        old_tags = list(instance.tags or [])
        collection = super().update(instance, validated_data)
        if new_tags is not None:
            removed = set(old_tags) - set(new_tags)
            if removed:
                for thing in collection.things.all():
                    if any(t in removed for t in (thing.tags or [])):
                        thing.tags = [t for t in thing.tags if t not in removed]
                        thing.save(update_fields=["tags"])
        return collection


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
    """Serializer for broadcasting a message to collection invitees.

    The subject is auto-generated ("Hey! {collection}"); only the message is
    user-provided.
    """

    message = SafeTextField(max_length=256)
