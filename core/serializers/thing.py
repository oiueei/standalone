"""
Thing serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Thing
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import (
    ImageIdField,
    SafeHeadlineField,
    SafeTextField,
    reject_spreadsheet_formula,
)


class ThingComputedFieldsMixin(serializers.Serializer):
    """Computed read-only thing fields shared by ThingSerializer and
    CollectionThingSummarySerializer.

    Every getter here is prefetch-aware — it reuses the ``_pending_bookings``,
    ``_transfer_count``, ``faq_set``, ``responses`` and ``_blocked_periods``
    caches set by the views — so serialising a list of things stays free of N+1
    queries. Fields whose logic genuinely differs between the two serializers
    (``thumbnail_url`` and the two swap-gate fields) deliberately stay on each
    serializer rather than here.
    """

    owner_name = serializers.SerializerMethodField()
    gallery_urls = serializers.SerializerMethodField()
    pending_booking = serializers.SerializerMethodField()
    my_pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()
    transfer_count = serializers.SerializerMethodField()
    response_count = serializers.SerializerMethodField()
    my_response = serializers.SerializerMethodField()
    available_today = serializers.SerializerMethodField()
    next_available = serializers.SerializerMethodField()

    def get_owner_name(self, obj):
        # Bare name by default — never the email — because this is shown to
        # co-members (and to anonymous visitors on PUBLIC collections) in the
        # community grid, where an email fallback would leak it (L2).
        # Exception: the collection owner already sees co-members' emails
        # (owner-only `invites`), so when the viewer owns the collection being
        # serialised (``parent_collection`` is only set on the collection grid)
        # we fall back to the email for owners who haven't set a name. Standalone
        # thing endpoints have no ``parent_collection`` → email is never exposed.
        if obj.owner.name:
            return obj.owner.name
        request = self.context.get("request")
        collection = self.context.get("parent_collection")
        if (
            request
            and request.user.is_authenticated
            and collection is not None
            and collection.is_owner(request.user.code)
        ):
            return obj.owner.email
        return obj.owner.name

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
        """Number of answers to a wish (WISH_THING only, null otherwise)."""
        if obj.type != Thing.Type.WISH_THING:
            return None
        return len(obj.responses.all())

    def get_my_response(self, obj):
        """The requesting user's own answer to a wish: {code, kind, status} or null."""
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

    def get_available_today(self, obj):
        window = obj.availability_window()
        return window["available_today"] if window else None

    def get_next_available(self, obj):
        window = obj.availability_window()
        return window["next_available"] if window else None


class ThingSerializer(ThingComputedFieldsMixin, serializers.ModelSerializer):
    """Full thing serializer."""

    thumbnail_url = serializers.SerializerMethodField()
    owner = serializers.CharField(source="owner_id")
    faqs = serializers.SerializerMethodField()
    deal = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)
    collection_code = serializers.SerializerMethodField()
    collection_headline = serializers.SerializerMethodField()
    collection_owner = serializers.SerializerMethodField()
    collection_swap_minimum_items = serializers.SerializerMethodField()
    my_swap_count_in_collection = serializers.SerializerMethodField()
    rental_durations = serializers.SerializerMethodField()
    rental_weekdays = serializers.SerializerMethodField()
    collection_tags = serializers.SerializerMethodField()

    class Meta:
        model = Thing
        fields = [
            "code",
            "type",
            "owner",
            "owner_name",
            "created",
            "headline",
            "description",
            "thumbnail",
            "thumbnail_url",
            "gallery",
            "gallery_urls",
            "tags",
            "collection_tags",
            "status",
            "faqs",
            "fee",
            "availability",
            "location",
            "condition",
            "available_today",
            "next_available",
            "deal",
            "pending_booking",
            "my_pending_booking",
            "pending_questions",
            "collection_code",
            "collection_headline",
            "collection_owner",
            "collection_swap_minimum_items",
            "my_swap_count_in_collection",
            "rental_durations",
            "rental_weekdays",
            "transfer_count",
            "response_count",
            "my_response",
            "is_endless",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "faqs",
            "deal",
        ]

    def get_thumbnail_url(self, obj):
        return cloudinary_url(obj.thumbnail)

    def get_collection_code(self, obj):
        # Use prefetched collections cache if available
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return first.code if first else None

    def get_collection_headline(self, obj):
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return first.headline if first else None

    def get_collection_owner(self, obj):
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return first.owner_id if first else None

    def get_collection_swap_minimum_items(self, obj):
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return first.swap_minimum_items if first else 0

    def get_rental_durations(self, obj):
        """Allowed rental lengths (days) from this thing's first collection (#7).
        Used by RequestThingPage to offer the fixed-duration picker for LEND/RENT."""
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return list(first.rental_durations) if first else []

    def get_rental_weekdays(self, obj):
        """Allowed pickup/return weekdays (0=Mon…6=Sun) from the first collection."""
        collections = obj.collections.all()
        first = collections[0] if collections else None
        return list(first.rental_weekdays) if first else []

    def get_my_swap_count_in_collection(self, obj):
        """Number of own ACTIVE/TAKEN SWAP_THINGs the requester has in this thing's
        first collection. Used by the frontend to gate the 'Propose swap' button
        against `collection_swap_minimum_items`. Returns 0 when no collection,
        no requester, or thing isn't a swap."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        collections = obj.collections.all()
        first = collections[0] if collections else None
        if not first or not first.is_swap:
            return 0
        # The count depends only on (requester, collection), not the specific
        # thing, so memoise it per collection on the shared context — a things
        # list in one swap collection then costs one query, not one per thing.
        cache = self.context.setdefault("_my_swap_count_cache", {})
        if first.code not in cache:
            cache[first.code] = Thing.objects.filter(
                owner=request.user,
                type=Thing.Type.SWAP_THING,
                status__in=(Thing.Status.ACTIVE, Thing.Status.TAKEN),
                collections=first,
            ).count()
        return cache[first.code]

    def get_faqs(self, obj):
        # Use prefetched faq_set cache if available
        return [faq.code for faq in obj.faq_set.all()]

    def get_collection_tags(self, obj):
        # The tag vocabulary available to this thing — union of its collections'
        # tags. Feeds the tag picker on the edit form without an extra fetch.
        seen = set()
        result = []
        for collection in obj.collections.all():
            for tag in collection.tags or []:
                if tag not in seen:
                    seen.add(tag)
                    result.append(tag)
        return result


class ThingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a thing."""

    headline = SafeHeadlineField(max_length=64)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    location = SafeHeadlineField(max_length=32, required=False, allow_blank=True)
    gallery = serializers.ListField(
        child=ImageIdField(allow_blank=False),
        max_length=8,
        required=False,
        allow_empty=True,
    )
    tags = serializers.ListField(
        child=SafeHeadlineField(max_length=32),
        max_length=12,
        required=False,
        allow_empty=True,
    )
    # Non-negative, bounded to the model's 10-digit / 2-decimal range (L7).
    fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "thumbnail",
            "gallery",
            "tags",
            "fee",
            "availability",
            "location",
            "condition",
            "is_endless",
        ]


class ThingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a thing."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    location = SafeHeadlineField(max_length=32, required=False, allow_blank=True)
    gallery = serializers.ListField(
        child=ImageIdField(allow_blank=False),
        max_length=8,
        required=False,
        allow_empty=True,
    )
    tags = serializers.ListField(
        child=SafeHeadlineField(max_length=32),
        max_length=12,
        required=False,
        allow_empty=True,
    )
    # Non-negative, bounded to the model's 10-digit / 2-decimal range (L7).
    fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "thumbnail",
            "gallery",
            "tags",
            "status",
            "fee",
            "availability",
            "location",
            "condition",
            "is_endless",
        ]
        read_only_fields = ["status"]

    def validate_tags(self, value):
        """Each tag must belong to the vocabulary of the thing's collection(s)."""
        if not value:
            return value
        available = set()
        if self.instance is not None:
            for collection in self.instance.collections.all():
                available.update(collection.tags or [])
        invalid = [t for t in value if t not in available]
        if invalid:
            raise serializers.ValidationError(
                f"These tags are not defined by the collection: {invalid}"
            )
        return value


class ThingBulkRowSerializer(serializers.ModelSerializer):
    """One row of a CSV bulk import (F-9).

    Reuses the project's safe text fields (HTML / line-break / unsafe-scheme
    rejection) and adds a CSV-injection guard on each free-text field. Photos and
    gallery can't be bulk-imported; tags can — a single
    ``|``-separated cell, validated against the collection's vocabulary in the
    view (the serializer has no collection context).
    """

    headline = SafeHeadlineField(max_length=64)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    location = SafeHeadlineField(max_length=32, required=False, allow_blank=True)
    fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    tags = serializers.ListField(
        child=SafeHeadlineField(max_length=32),
        max_length=12,
        required=False,
        allow_empty=True,
    )
    # Cover photo public_id. A CSV can't carry binaries, but a ZIP bundle can:
    # the client unzips, uploads each image to Cloudinary, and sends the resulting
    # public_id here (validated path-traversal-safe like the single-create path).
    thumbnail = ImageIdField(required=False, allow_blank=True)

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "fee",
            "availability",
            "location",
            "condition",
            "tags",
            "thumbnail",
            "is_endless",
        ]

    def validate_type(self, value):
        # Wishes notify the whole group when posted; bulk-importing them silently
        # would skip that, so they must be added individually.
        if value == Thing.Type.WISH_THING:
            raise serializers.ValidationError(
                "Wishes can't be bulk-imported — add them individually so the group is notified."
            )
        return value

    def validate_headline(self, value):
        return reject_spreadsheet_formula(value)

    def validate_description(self, value):
        return reject_spreadsheet_formula(value)

    def validate_location(self, value):
        return reject_spreadsheet_formula(value)

    def validate_tags(self, value):
        # Guard each tag against spreadsheet-formula (CSV) injection, like the
        # other free-text fields. The subset-against-collection check runs in
        # ThingBulkCreateView (the serializer has no collection context).
        return [reject_spreadsheet_formula(tag) for tag in value] if value else value
