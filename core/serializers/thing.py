"""
Thing serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Thing
from core.models.booking import BookingPeriod
from core.utils import cloudinary_url
from core.validators import ImageIdField, SafeHeadlineField, SafeTextField, validate_image_id

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/markdown",
}


class DocumentSerializer(serializers.Serializer):
    """Validates a single document entry."""

    public_id = serializers.CharField(max_length=255)
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)

    def validate_public_id(self, value):
        return validate_image_id(value)

    def validate_content_type(self, value):
        if value not in ALLOWED_DOCUMENT_TYPES:
            raise serializers.ValidationError(f"File type {value} is not allowed.")
        return value


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
        # Bare name, never the email fallback — this is shown to co-members in
        # the community grid, so display_name's email fallback would leak it (L2).
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
    document_urls = serializers.SerializerMethodField()
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
            "documents",
            "document_urls",
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
        return Thing.objects.filter(
            owner=request.user,
            type=Thing.Type.SWAP_THING,
            status__in=(Thing.Status.ACTIVE, Thing.Status.TAKEN),
            collections=first,
        ).count()

    def get_faqs(self, obj):
        # Use prefetched faq_set cache if available
        return [faq.code for faq in obj.faq_set.all()]

    def get_document_urls(self, obj):
        if not obj.documents:
            return []
        import cloudinary.utils

        result = []
        for doc in obj.documents:
            url, _ = cloudinary.utils.cloudinary_url(doc["public_id"], resource_type="raw")
            result.append({"filename": doc["filename"], "url": url})
        return result

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
    documents = serializers.ListField(
        child=serializers.DictField(),
        max_length=5,
        required=False,
        allow_empty=True,
    )
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
            "documents",
            "is_endless",
        ]

    def validate_documents(self, value):
        if not value:
            return value
        serializer = DocumentSerializer(data=value, many=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class ThingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a thing."""

    headline = SafeHeadlineField(max_length=64, required=False)
    description = SafeTextField(max_length=256, required=False, allow_blank=True)
    thumbnail = ImageIdField()
    location = SafeHeadlineField(max_length=32, required=False, allow_blank=True)
    documents = serializers.ListField(
        child=serializers.DictField(),
        max_length=5,
        required=False,
        allow_empty=True,
    )
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
            "documents",
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

    def validate_documents(self, value):
        if not value:
            return value
        serializer = DocumentSerializer(data=value, many=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data
