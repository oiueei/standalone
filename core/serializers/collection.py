"""
Collection serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import RSVP, Collection, Thing
from core.serializers.thing import ThingComputedFieldsMixin
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField

# Thing types valid for proprietary collections (excludes COMMUNITY-only types
# WISH_THING, SHARE_THING and the SWAP_THING which is gated by
# is_swap on COMMUNITY collections).
PROPRIETARY_THING_TYPES = (
    Thing.Type.GIFT_THING,
    Thing.Type.SELL_THING,
    Thing.Type.RENT_THING,
    Thing.Type.LEND_THING,
)
# Thing types valid for community collections without is_swap/is_share flags.
# SWAP_THING is excluded because it requires is_swap=True (which forces a
# single-type collection and bypasses the allowlist entirely).
COMMUNITY_THING_TYPES = (
    Thing.Type.GIFT_THING,
    Thing.Type.SELL_THING,
    Thing.Type.RENT_THING,
    Thing.Type.LEND_THING,
    Thing.Type.SHARE_THING,
    Thing.Type.WISH_THING,
)


class CollectionThingSummarySerializer(ThingComputedFieldsMixin, serializers.ModelSerializer):
    """Lightweight thing serializer for collection listings."""

    owner = serializers.CharField(source="owner_id")
    thumbnail_url = serializers.SerializerMethodField()
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

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail) if obj.thumbnail else None

    def get_collection_swap_minimum_items(self, obj):
        parent = self.context.get("parent_collection")
        return parent.swap_minimum_items if parent else 0

    def get_my_swap_count_in_collection(self, obj):
        # Pre-computed once at the parent CollectionSerializer level — same
        # value for every thing in this collection, so we avoid N queries.
        return self.context.get("my_swap_count_in_collection", 0)


class CollectionListSerializer(serializers.ListSerializer):
    """List serializer that batch-loads the owner-only ``pending_invites``.

    ``pending_invites`` come from the RSVP table keyed by ``target_code`` (a
    plain CharField, not a FK — so there is no relation to ``prefetch_related``).
    Serialising a list of an owner's collections would otherwise fire one RSVP
    query per collection (N+1). Here we fetch them all in a single query and
    stash them on the shared context for the child serializer to read.
    """

    def to_representation(self, data):
        instances = list(data)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            owned_codes = [c.code for c in instances if c.owner_id == request.user.code]
            if owned_codes:
                by_code = {}
                rows = RSVP.objects.filter(
                    action=RSVP.Action.COLLECTION_INVITE,
                    target_code__in=owned_codes,
                ).values("target_code", "user_code_id", "user_email")
                for row in rows:
                    by_code.setdefault(row["target_code"], []).append(
                        {"code": row["user_code_id"], "email": row["user_email"]}
                    )
                self.context["_pending_invites_by_code"] = by_code
        return super().to_representation(instances)


class CollectionSerializer(serializers.ModelSerializer):
    """Full collection serializer."""

    owner = serializers.CharField(source="owner_id")
    owner_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    things = serializers.SerializerMethodField()
    invites = serializers.SerializerMethodField()
    pending_invites = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    is_paused = serializers.BooleanField(read_only=True)

    class Meta:
        model = Collection
        list_serializer_class = CollectionListSerializer
        fields = [
            "code",
            "owner",
            "owner_name",
            "created",
            "headline",
            "description",
            "status",
            "mode",
            "visibility",
            "digest_frequency",
            "is_swap",
            "is_share",
            "newsletter_enabled",
            "swap_minimum_items",
            "allowed_thing_types",
            "rental_durations",
            "rental_weekdays",
            "tags",
            "thumbnail",
            "thumbnail_url",
            "pause_message",
            "is_paused",
            "things",
            "invites",
            "pending_invites",
            "is_member",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "is_paused",
            "things",
            "invites",
            "pending_invites",
            "is_member",
        ]

    def get_owner_name(self, obj):
        # Bare name, not display_name — guests see this, so the email fallback
        # would leak the owner's address (L2).
        return obj.owner.name

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
        is_owner = bool(
            request and request.user.is_authenticated and obj.is_owner(request.user.code)
        )
        things = obj.things.all()
        # Non-owners (including anonymous visitors on a PUBLIC collection) never
        # see INACTIVE things; only skip the filter for internal, request-less use.
        if request and not is_owner:
            things = things.exclude(status=Thing.Status.INACTIVE)
        return CollectionThingSummarySerializer(things, many=True, context=ctx).data

    def _requester_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.is_owner(request.user.code))

    def get_is_member(self, obj):
        # True when the requester is an invited member (not the owner). Reads the
        # prefetched invites so it adds no query. Drives the "Leave the group" button.
        request = self.context.get("request")
        if not (request and request.user.is_authenticated) or self._requester_is_owner(obj):
            return False
        return any(u.code == request.user.code for u in obj.invites.all())

    def get_invites(self, obj):
        members = obj.invites.all()
        if self._requester_is_owner(obj):
            # In a COMMUNITY collection the owner also sees each member's optional
            # age range and postal code (owner-only, never public). Other modes
            # and non-owners never receive them.
            community = obj.is_community()
            result = []
            for u in members:
                member = {"code": u.code, "email": u.email, "name": u.name}
                if community:
                    member["age_range"] = u.age_range
                    member["postal_code"] = u.postal_code
                result.append(member)
            return result
        # Co-members' emails are owner-only (L2); guests get only code + name —
        # enough for the member count, no PII.
        return [{"code": u.code, "name": u.name} for u in members]

    def get_pending_invites(self, obj):
        # Pending invitees and their emails are owner-management data only.
        if not self._requester_is_owner(obj):
            return []
        # Reuse the batch the list serializer pre-loaded, if present (avoids the
        # per-collection N+1 when serialising a list); fall back to a single
        # query for the detail endpoint / direct use.
        cache = self.context.get("_pending_invites_by_code")
        if cache is not None:
            return cache.get(obj.code, [])
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
    rental_durations = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=90),
        max_length=8,
        required=False,
        allow_empty=True,
    )
    rental_weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        max_length=7,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Collection
        fields = [
            "headline",
            "description",
            "mode",
            "visibility",
            "digest_frequency",
            "is_swap",
            "is_share",
            "newsletter_enabled",
            "swap_minimum_items",
            "allowed_thing_types",
            "rental_durations",
            "rental_weekdays",
            "tags",
            "thumbnail",
        ]

    def validate_tags(self, value):
        return _normalize_tags(value)

    def validate_rental_durations(self, value):
        return sorted(set(value))

    def validate_rental_weekdays(self, value):
        return sorted(set(value))

    def validate(self, attrs):
        # Default visibility follows the mode when the client doesn't set it:
        # community collections are born PUBLIC, proprietary ones PRIVATE. The
        # owner can override either way via the toggle.
        if not attrs.get("visibility"):
            mode = attrs.get("mode", Collection.Mode.PROPRIETARY)
            attrs["visibility"] = (
                Collection.Visibility.PUBLIC
                if mode == Collection.Mode.COMMUNITY
                else Collection.Visibility.PRIVATE
            )
        _validate_collection_flags(
            mode=attrs.get("mode", Collection.Mode.PROPRIETARY),
            is_swap=attrs.get("is_swap", False),
            is_share=attrs.get("is_share", False),
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


def _validate_allowed_thing_types(mode, is_swap, is_share, allowed_thing_types):
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
    - COMMUNITY (no flags) accepts the 7-type COMMUNITY set (all except SWAP,
      which requires is_swap).
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
        invalid = [t for t in allowed_thing_types if t not in PROPRIETARY_THING_TYPES]
        if invalid:
            raise serializers.ValidationError(
                f"These types are not allowed in proprietary collections: {invalid}"
            )
        return
    # COMMUNITY
    invalid = [t for t in allowed_thing_types if t not in COMMUNITY_THING_TYPES]
    if invalid:
        raise serializers.ValidationError(
            f"These types are not allowed in community collections: {invalid}"
        )


def _validate_collection_flags(
    *,
    mode,
    is_swap,
    is_share,
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
    if swap_minimum_items > 0 and not is_swap:
        raise serializers.ValidationError("swap_minimum_items can only be set on swap collections.")
    _validate_allowed_thing_types(mode, is_swap, is_share, allowed_thing_types)


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
    rental_durations = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=90),
        max_length=8,
        required=False,
        allow_empty=True,
    )
    rental_weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        max_length=7,
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
            "visibility",
            "digest_frequency",
            "is_swap",
            "is_share",
            "newsletter_enabled",
            "swap_minimum_items",
            "allowed_thing_types",
            "rental_durations",
            "rental_weekdays",
            "tags",
            "thumbnail",
            "pause_message",
        ]

    def validate_rental_durations(self, value):
        return sorted(set(value))

    def validate_rental_weekdays(self, value):
        return sorted(set(value))

    def validate(self, attrs):
        instance = self.instance
        is_swap = attrs.get("is_swap", instance.is_swap if instance else False)
        is_share = attrs.get("is_share", instance.is_share if instance else False)
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
