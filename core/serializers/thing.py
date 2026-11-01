"""
Thing serializers for OIUEEI.
"""

from django.db.models import Count, Prefetch
from rest_framework import serializers

from core.models import Collection, Thing
from core.models.booking import DATE_BASED_TYPES, BookingPeriod
from core.serializers.theeeme import theeeme_colors
from core.utils import asset_url, doc_asset_url
from core.validators import (
    LOCALIZED_DESCRIPTION_STORAGE,
    LOCALIZED_DESCRIPTION_VISIBLE,
    LOCALIZED_TAG_STORAGE,
    ImageIdField,
    LocalizedHeadlineField,
    LocalizedTextField,
    SafeHeadlineField,
    reject_spreadsheet_formula,
)

# The only two verbs a deposit can mean anything under: you get back what you
# left because the thing itself comes back. A gift or a sale ends the
# relationship — nothing to hold, nothing to return.
DEPOSIT_TYPES = (Thing.Type.LEND_THING, Thing.Type.RENT_THING)


def validate_deposit_for_type(thing_type, deposit):
    """Reject a deposit on a type with nothing to give back.

    Enforced here rather than by hiding the input, because the JSON API and the
    CSV import are two more doors into the same column — `fee` has no such rule
    and that is exactly why this one is worth writing down.

    The check is on the **resulting** row, not on the payload: turning a loan
    that carries a deposit into a gift has to clear the amount in the same
    request, or the row that lands is a gift asking for security.
    """
    if deposit is not None and thing_type not in DEPOSIT_TYPES:
        raise serializers.ValidationError(
            {
                "deposit": (
                    "Only loans and rentals can ask for a deposit — a gift or a sale has "
                    "nothing to give back. Clear the amount to change the type."
                )
            }
        )


def optimise_thing_queryset(queryset, *, with_collections=False):
    """Attach the select/prefetch chain every list-of-things view needs so
    ThingComputedFieldsMixin's getters below stay prefetch-aware and N+1-free.

    ``with_collections`` also prefetches ``collections`` — skip it when the
    queryset is already nested inside a collection's own ``Prefetch("things", ...)``
    (avoids a redundant/circular fetch).
    """
    related = ["faq_set", "deal"]
    if with_collections:
        # `collections__co_owners` feeds the `can_manage` field: a PROPRIETARY
        # collection's curator manages its whole catalogue (2026-09), and
        # `Collection.is_curator` reads `co_owners` via `.all()`.
        # The palette rides with the collection, joined here so reading it costs no
        # query per thing (`collection_theeeme_colors`).
        related.insert(
            0, Prefetch("collections", queryset=Collection.objects.select_related("theeeme"))
        )
        related.insert(1, "collections__co_owners")
    return (
        queryset.select_related("owner")
        .annotate(_transfer_count=Count("transfers", distinct=True))
        .prefetch_related(
            *related,
            Prefetch(
                "bookings",
                queryset=BookingPeriod.objects.filter(status=BookingPeriod.Status.PENDING),
                to_attr="_pending_bookings",
            ),
            Prefetch(
                "bookings",
                # Only what still shapes the calendar — see `blocking_filter`.
                queryset=BookingPeriod.objects.filter(BookingPeriod.blocking_filter())
                # The requester is joined here because this prefetch now also
                # feeds the owner-only `bookings` field, which prints their name.
                # Without it the field would trade one query per card for one per
                # booking — a worse N+1 than the one it removes.
                .select_related("requester_code")
                .order_by("start_date"),
                to_attr="_blocked_periods",
            ),
        )
    )


class ThingComputedFieldsMixin(serializers.Serializer):
    """Computed read-only thing fields shared by ThingSerializer and
    CollectionThingSummarySerializer.

    Every getter here is prefetch-aware — it reuses the ``_pending_bookings``,
    ``_transfer_count``, ``faq_set`` and ``_blocked_periods``
    caches set by the views — so serialising a list of things stays free of N+1
    queries. Fields whose logic genuinely differs between the two serializers
    (``thumbnail_url``) deliberately stay on each
    serializer rather than here.
    """

    owner_name = serializers.SerializerMethodField()
    gallery_urls = serializers.SerializerMethodField()
    pending_booking = serializers.SerializerMethodField()
    bookings = serializers.SerializerMethodField()
    my_pending_booking = serializers.SerializerMethodField()
    pending_questions = serializers.SerializerMethodField()
    transfer_count = serializers.SerializerMethodField()
    available_today = serializers.SerializerMethodField()
    next_available = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    network_point = serializers.SerializerMethodField()

    def get_network_point(self, obj):
        """Who lends the thing and where, in a network: the pickup point of its owner
        (``display_name`` is the entity's name, else the dinamizador's own — resolved
        here, once, for the page, the request, the emails and the filter alike).
        ``None`` outside a network. A dinamizador with no point still has a
        ``display_name``; the rest is empty."""
        collection = self._reading_collection(obj)
        if collection is None or not collection.is_network():
            return None
        point = collection.point_for(obj.owner_id)
        if point is None:
            return {
                "display_name": obj.owner.name,
                "address": "",
                "hours_note": "",
                "contact": "",
            }
        return {
            "display_name": point.display_name,
            "address": point.address,
            "hours_note": point.hours_note,
            "contact": point.contact,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # In a network the pickup point says where a thing is: the thing's own
        # location is neither asked nor shown (the column is left as it is).
        collection = self._reading_collection(instance)
        if collection is not None and collection.is_network() and "location" in data:
            data["location"] = ""
        return data

    def _requested_collection_code(self):
        """The ``?collection=<code>`` the SPA sends when it reads a thing from
        inside one of its collections, or ``""``. Only ever a *preference*
        among the collections the viewer may already read — never a way into
        one they can't. On the mixin, not `ThingSerializer`, because
        `_availability_window` below asks for it."""
        request = self.context.get("request")
        params = getattr(request, "query_params", None) if request is not None else None
        return ((params.get("collection") if params is not None else "") or "").strip()

    def _reading_collection(self, obj):
        """The collection this thing is being read *through*, or ``None``.

        Two call sites, two ways of knowing: the collection grid passes the
        collection it is rendering as ``parent_collection``; the thing endpoints
        resolve it per viewer (``ThingSerializer._viewable_collection``, absent
        from the summary serializer). Used to tell the person who published the
        listing apart from a member who contributed to someone else's group.
        """
        collection = self.context.get("parent_collection")
        if collection is not None:
            return collection
        resolver = getattr(self, "_viewable_collection", None)
        return resolver(obj) if resolver else None

    def _viewer_curates(self, collection, user_code):
        """Whether ``user_code`` owns or co-owns ``collection``, asked once per request.

        ``Collection.is_curator`` reads ``co_owners`` through ``.all()``: free when
        the queryset prefetched it (the lists do), one query when it did not (the
        thing's own page loads a bare row). ``can_manage`` and ``collection_menu``
        both need the answer for the same collection, so the first asker pays and the
        second reads it from the shared context.
        """
        cache = self.context.setdefault("_curator_by_collection", {})
        key = (collection.code, user_code)
        if key not in cache:
            cache[key] = collection.is_curator(user_code)
        return cache[key]

    def get_can_manage(self, obj):
        """Whether the reader may run this thing's catalogue entry — edit,
        hide, activate, delete — which the frontend gates those controls on.
        True for the thing owner, or a curator of a **PROPRIETARY** collection
        it is being read through (`Thing.can_manage`, one tier wider than
        `is_owner`).

        Judged against the *reading* collection only — the one the grid or the
        thing endpoint resolved — never by walking every collection the thing
        sits in: that keeps it prefetch-safe, and the worst it can do is hide
        a control the API would still allow (`IsThingManager` re-checks the
        real `Thing.can_manage` on the mutation itself).
        """
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            return False
        code = request.user.code
        if obj.is_owner(code):
            return True
        from core.models.collection import Collection

        collection = self._reading_collection(obj)
        return bool(
            collection is not None
            and collection.mode == Collection.Mode.PROPRIETARY
            and self._viewer_curates(collection, code)
        )

    def get_owner_name(self, obj):
        # Withheld from readers with no account when the owner is *not* the
        # person who published the collection — i.e. a member who contributed a
        # thing to someone else's group, which only happens in COMMUNITY mode.
        # That member is a third party exactly like the FAQ asker and the
        # journey's past holders: they consented to a group, not to the open
        # web, and the visibility switch belongs to the curator, not to them.
        # A group's membership stayed legible from the open web through the
        # cards of the things it shares.
        #
        # The curator's own name is *not* withheld: they chose to publish, and
        # `CollectionSerializer.get_owner_name` already serves it to the same
        # reader in the page header — hiding it here would be theatre.
        # Comparing the two owners says exactly that, and needs no mode check.
        #
        # Withheld is `""`, the value a nameless owner already produced, so no
        # client meets a kind of value it did not have to handle. Fail-closed on
        # a request-less context and on a collection we cannot resolve, like
        # `core.serializers.transfer._may_read_names`.
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            collection = self._reading_collection(obj)
            if collection is None or collection.owner_id != obj.owner_id:
                return ""
            return obj.owner.name
        # Bare name by default — never the email — because this is shown to
        # co-members in the community grid, where an email fallback would leak
        # it. Exception: the collection owner already sees co-members'
        # emails (owner-only `invites`), so when the viewer owns the collection
        # being serialised (``parent_collection`` is only set on the collection
        # grid) we fall back to the email for owners who haven't set a name.
        # Standalone thing endpoints have no ``parent_collection`` → email is
        # never exposed.
        if obj.owner.name:
            return obj.owner.name
        # Authentication is already guaranteed by the early return above.
        collection = self.context.get("parent_collection")
        if collection is not None and collection.is_owner(request.user.code):
            return obj.owner.email
        return obj.owner.name

    def get_gallery_urls(self, obj):
        return [asset_url(public_id) for public_id in (obj.gallery or [])]

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

    def get_bookings(self, obj):
        """The owner's own booking list, served from the prefetch (owner-only).

        This is the same set `GET /things/{code}/calendar/` returns, and it is
        here so the card stops asking for it. `ThingLinkbox` fetched the calendar
        once **per card** for every date-based or TAKEN thing it rendered, so a
        lending library's owner opening their own collection fired one request
        per item — on the page they visit most, from a phone (DESIGN §7). The
        rows were already in memory: `_blocked_periods` is the same PENDING +
        ACCEPTED set, prefetched to compute availability.

        `None` for anyone who can't manage the thing — requester names are not
        public — which also tells the client to fall back to fetching, so a
        serializer that hasn't been given a request still behaves as before.
        A PROPRIETARY collection's co-curator manages its bookings, so they
        see this list the same as the founder (`can_manage`, not `owner_id`).
        """
        from core.serializers.booking import BookingPeriodOwnerCalendarSerializer

        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            return None
        if not (obj.owner_id == request.user.code or self.get_can_manage(obj)):
            return None
        periods = (
            obj._blocked_periods
            if hasattr(obj, "_blocked_periods")
            else list(BookingPeriod.get_blocked_periods(obj.code))
        )
        return BookingPeriodOwnerCalendarSerializer(periods, many=True).data

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
        return sum(1 for faq in obj.faq_set.all() if faq.answer == "" and faq.is_visible)

    def get_transfer_count(self, obj):
        if hasattr(obj, "_transfer_count"):
            return obj._transfer_count
        return obj.transfers.count()

    def _availability_window(self, obj):
        # The collection grid nests things inside a collection's own Prefetch, so it
        # does NOT prefetch ``collections`` — letting availability_window() resolve
        # the rule-setting collection itself would be an N+1 there. It is exactly
        # the collection being rendered, so pass it (``parent_collection`` is only
        # set on that path; standalone thing endpoints prefetch ``collections`` and
        # resolve it for free). A standalone read that names its collection
        # (``?collection=``, see ``_viewable_collection``) walks that one's rules,
        # the same ones the request form shows and the request applies.
        collection = self.context.get("parent_collection")
        if collection is None and self._requested_collection_code():
            # `_reading_collection`, not `_viewable_collection` directly: the
            # summary serializer shares this mixin and has no resolver.
            collection = self._reading_collection(obj)
        return obj.availability_window(collection=collection)

    def get_available_today(self, obj):
        window = self._availability_window(obj)
        return window["available_today"] if window else None

    def get_next_available(self, obj):
        window = self._availability_window(obj)
        return window["next_available"] if window else None


class ThingSerializer(ThingComputedFieldsMixin, serializers.ModelSerializer):
    """Full thing serializer."""

    thumbnail_url = serializers.SerializerMethodField()
    owner = serializers.CharField(source="owner_id")
    faqs = serializers.SerializerMethodField()
    deal = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)
    collection_code = serializers.SerializerMethodField()
    collection_kind = serializers.SerializerMethodField()
    collection_mode = serializers.SerializerMethodField()
    collection_allowed_thing_types = serializers.SerializerMethodField()
    collection_headline = serializers.SerializerMethodField()
    collection_owner = serializers.SerializerMethodField()
    collection_is_onboarding = serializers.SerializerMethodField()
    collection_request_info = serializers.SerializerMethodField()
    deposit_policy = serializers.SerializerMethodField()
    live_requesters_count = serializers.SerializerMethodField()
    collection_language = serializers.SerializerMethodField()
    collection_theeeme_colors = serializers.SerializerMethodField()
    collection_koro = serializers.SerializerMethodField()
    collection_menu = serializers.SerializerMethodField()
    rental_durations = serializers.SerializerMethodField()
    rental_weekdays = serializers.SerializerMethodField()
    reservation_max_days = serializers.SerializerMethodField()
    reservation_horizon_days = serializers.SerializerMethodField()
    reservation_unit = serializers.SerializerMethodField()
    opening_hours = serializers.SerializerMethodField()
    reservation_min_minutes = serializers.SerializerMethodField()
    reservation_max_minutes = serializers.SerializerMethodField()
    closed_dates = serializers.SerializerMethodField()
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
            "deposit",
            "availability",
            "location",
            "condition",
            "available_today",
            "next_available",
            "deal",
            "pending_booking",
            "bookings",
            "my_pending_booking",
            "pending_questions",
            "can_manage",
            "network_point",
            "collection_code",
            "collection_kind",
            "collection_mode",
            "collection_allowed_thing_types",
            "collection_headline",
            "collection_owner",
            "collection_is_onboarding",
            "collection_request_info",
            "deposit_policy",
            "live_requesters_count",
            "collection_language",
            "collection_theeeme_colors",
            "collection_koro",
            "collection_menu",
            "rental_durations",
            "rental_weekdays",
            "reservation_max_days",
            "reservation_horizon_days",
            "reservation_unit",
            "opening_hours",
            "reservation_min_minutes",
            "reservation_max_minutes",
            "closed_dates",
            "transfer_count",
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
        return asset_url(obj.thumbnail)

    def _viewer_collection_codes(self):
        """Codes of every collection the requesting user owns or belongs to.

        One query per request, cached on the shared serializer context: the
        collection fields below ask this for every thing in a list, and going
        through ``Collection.can_view()`` instead would fire ``is_invited()``
        once per thing per collection — an N+1 on any list of things (``/things/``,
        the owner's own, is the one that remains).
        """
        if "_viewer_collection_codes" not in self.context:
            from django.db.models import Q

            from core.models import Collection

            request = self.context.get("request")
            user = getattr(request, "user", None)
            codes = frozenset()
            if user is not None and user.is_authenticated:
                codes = frozenset(
                    Collection.objects.filter(Q(owner=user) | Q(invites=user)).values_list(
                        "code", flat=True
                    )
                )
            self.context["_viewer_collection_codes"] = codes
        return self.context["_viewer_collection_codes"]

    def _viewable_collections(self, obj):
        """The thing's collections **this viewer is allowed to read**, in order.

        A thing lives in one collection (``core/services/single_collection.py``);
        this still walks every row of ``collections``, in case one predates that
        rule. The collection fields below answer from the first of them the viewer
        may read, never from ``collections.all()[0]`` unjudged: ``Thing.can_view()``
        lets the *thing* through on the strength of a collection the reader has,
        and nothing else re-asks the question about the collection a field names,
        so a private collection's name and code would reach someone who cannot
        open it.

        Mirrors ``Collection.can_view()`` exactly — owner regardless of status,
        never INACTIVE otherwise, then PUBLIC or membership — but reads the
        prefetched rows and one cached code set, so it costs no query per thing.

        A context with no request is internal use (a serializer called directly,
        no viewer to judge): everything is viewable, as before.
        """
        collections = obj.collections_in_order()
        request = self.context.get("request")
        if request is None:
            return collections

        from core.models import Collection

        viewer = request.user.code if request.user.is_authenticated else None
        member_codes = self._viewer_collection_codes()
        return [
            collection
            for collection in collections
            if collection.owner_id == viewer
            or (
                collection.status == Collection.Status.ACTIVE
                and (collection.is_public() or collection.code in member_codes)
            )
        ]

    def _viewable_collection(self, obj):
        """The collection this viewer reads the thing through, or ``None``.
        Memoised — a dozen fields ask for it per thing.

        The one named by ``?collection=`` when the viewer may read it (the
        collection the SPA is browsing — ``RequestThingPage`` sends it, and
        the request it then POSTs carries the same ``collection_code``), else
        the first readable one. Without that preference a thing in two
        reservations collections, one booked by the DAY and one by the HOUR,
        showed the first collection's rules while ``request_reservation``
        applied the other's — a request form the server then refused (found in
        review, 2026-09-18)."""
        if not hasattr(obj, "_viewable_collection_cache"):
            viewable = self._viewable_collections(obj)
            wanted = self._requested_collection_code()
            preferred = next((c for c in viewable if c.code == wanted), None) if wanted else None
            obj._viewable_collection_cache = preferred or (viewable[0] if viewable else None)
        return obj._viewable_collection_cache

    def get_collection_code(self, obj):
        first = self._viewable_collection(obj)
        return first.code if first else None

    def get_collection_kind(self, obj):
        """The kind of the collection ``collection_code`` names — what the app needs
        to build its address, ``/{kind}/{code}``."""
        first = self._viewable_collection(obj)
        return first.kind if first else None

    def get_collection_mode(self, obj):
        """The mode of the collection ``collection_code`` names: a network's things
        are placed by their pickup point, so their form and page leave out the
        thing's own location."""
        first = self._viewable_collection(obj)
        return first.mode if first else None

    def get_collection_allowed_thing_types(self, obj):
        """The verbs the collection ``collection_code`` names takes — the edit form needs
        to know whether members of a COMMUNITY group may set a price (both verbs of the
        kind) or not (only the free one), and a thing's page has no other way to ask."""
        first = self._viewable_collection(obj)
        return list(first.allowed_thing_types or []) if first else []

    def get_collection_headline(self, obj):
        first = self._viewable_collection(obj)
        return first.headline if first else None

    def get_collection_owner(self, obj):
        first = self._viewable_collection(obj)
        return first.owner_id if first else None

    def get_collection_is_onboarding(self, obj):
        """Whether the collection this viewer sees the thing through is a seed
        collection — the SPA shows a demo notice on it. Resolved through
        ``_viewable_collection`` like the three fields above so a thing shared
        into both a demo and a real group is judged by the row this reader has."""
        first = self._viewable_collection(obj)
        return bool(first.is_onboarding) if first else False

    def get_collection_request_info(self, obj):
        """The collection's note for anyone reaching the request page for this
        thing — served here regardless of type, but only ever rendered for
        LEND/RENT/RESERVE (not RESERVE_THING only): a GIFT/SELL claim submits
        straight from the card and never visits that page, so the note is
        invisible to it however this field answers. Raw (possibly a
        `{lang: text}` map, like `headline`/`description`) — `RequestThingPage`
        resolves it client-side the same way. `""` when there is no viewable
        collection."""
        first = self._viewable_collection(obj)
        return first.effective_text("request_info", obj.owner_id) if first else ""

    def get_live_requesters_count(self, obj):
        """How many people would be emailed if the reader deleted this thing — those with a
        pending or accepted request on it, the reader left out — for the page that warns
        before deleting. Only for someone who may delete it (``Thing.can_delete``, the
        rule of the endpoint) and only when one thing is read, not in a list, where it
        would cost queries per row; ``None`` otherwise."""
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        if isinstance(self.parent, serializers.ListSerializer):
            return None
        if not obj.can_delete(request.user.code):
            return None
        from core.services.membership_service import people_told_on_delete

        return len(people_told_on_delete(obj, request.user))

    def get_deposit_policy(self, obj):
        """How deposits work for this thing — the collection's policy or, in a network,
        its owner's pickup point's own (``Collection.effective_text``). Raw (possibly a
        ``{lang: text}`` map), like ``collection_request_info``; the page shows it under
        the deposit, which only a thing with a deposit has. ``""`` with no viewable
        collection."""
        first = self._viewable_collection(obj)
        return first.effective_text("deposit_policy", obj.owner_id) if first else ""

    def get_collection_language(self, obj):
        """The collection's own language, resolved the same way as the four
        fields above — for the frontend's `useCollectionLanguage` hook, which a
        thing-only page (`ThingPage`, `RequestThingPage`, `EditThingPage`,
        `DeleteThingPage`) has no other way to learn: those pages fetch
        `/things/{code}/` and never see the collection object itself. `""`
        (never the collection's actual blank default) when there is no
        viewable collection, so the hook's own falsy check needs no special
        case for "collection unknown" vs. "collection has no language set" —
        both mean "don't override"."""
        first = self._viewable_collection(obj)
        return (first.language if first else "") or ""

    def get_collection_theeeme_colors(self, obj):
        """The palette of the collection this viewer reads the thing through, so a
        thing-only page (`ThingPage`, `RequestThingPage`, `EditThingPage`,
        `DeleteThingPage`) paints with its group's colours without loading the
        collection. Resolved like `collection_language`; `None` when there is no
        viewable collection, and the page then paints with the app's own palette."""
        first = self._viewable_collection(obj)
        return theeeme_colors(first.theeeme) if first else None

    def get_collection_koro(self, obj):
        """The Koros wave of that same collection; `""` when there is none."""
        first = self._viewable_collection(obj)
        return (first.koro if first else "") or ""

    def _viewer_muted_collection_codes(self):
        """Codes of the collections whose digest this viewer has silenced — one
        query per request, cached on the shared context, and only ever asked for a
        member of a group that sends a digest."""
        if "_viewer_muted_collection_codes" not in self.context:
            from core.models import Collection

            user = self.context["request"].user
            self.context["_viewer_muted_collection_codes"] = frozenset(
                Collection.objects.filter(digest_muted=user).values_list("code", flat=True)
            )
        return self.context["_viewer_muted_collection_codes"]

    def _collection_has_date_things(self, collection):
        """The calendar entry's rule: a library or a shed always has dates to
        export; a stall only when it holds a thing booked by date (one the kind
        migration kept from a collection that also lent). Cached per collection
        on the shared context, so a list read through a collection asks once,
        not once per thing — and a library or a shed asks nothing."""
        cache = self.context.setdefault("_date_things_by_collection", {})
        if collection.code not in cache:
            if collection.kind != Collection.Kind.STALL:
                cache[collection.code] = True
            else:
                cache[collection.code] = collection.things.filter(
                    type__in=DATE_BASED_TYPES
                ).exists()
        return cache[collection.code]

    def get_collection_menu(self, obj):
        """What the thing's own page needs to paint the collection menu — and
        nothing more, so the page never loads the collection
        itself (``GET /collections/{code}/`` carries every one of its things).

        Present only when the SPA reads the thing **through a collection**
        (``?collection=<code>``) and the viewer is a **curator** or a **member** of
        exactly that collection: the menu is theirs, and its contents (the welcome
        document above all) are served to those two only, like the collection's own
        payload. Anyone else, an anonymous reader, a listing and a thing read with no
        ``?collection=`` get ``None``, which costs nothing.

        ``is_curator`` / ``is_member`` follow ``CollectionSerializer`` (a co-owner is
        a curator, never a member); ``digest_frequency`` and ``is_digest_muted`` feed
        the "Mute the summary" entry of a member and of a curator;
        ``has_date_things`` is the rule the collection page uses for the calendar
        entry — always for a library or a shed, for a stall whether it holds a
        date-based thing (one query, a stall's curator only).
        """
        request = self.context.get("request")
        wanted = self._requested_collection_code()
        if not (wanted and request is not None and request.user.is_authenticated):
            return None
        collection = self._viewable_collection(obj)
        if collection is None or collection.code != wanted:
            return None

        from core.models import Collection

        code = request.user.code
        is_curator = self._viewer_curates(collection, code)
        # Owned and invited collections, one cached query — and a co-owner is in
        # `invites` too, which is why the curator test comes first.
        is_member = not is_curator and collection.code in self._viewer_collection_codes()
        if not (is_curator or is_member):
            return None

        sends_digest = collection.digest_frequency != Collection.DigestFrequency.NONE
        # The digest goes to the members and the founder, so a curator may mute it too.
        is_digest_muted = sends_digest and collection.code in self._viewer_muted_collection_codes()
        has_date_things = is_curator and self._collection_has_date_things(collection)

        return {
            "is_curator": is_curator,
            "is_member": is_member,
            "welcome_doc_url": (
                doc_asset_url(collection.welcome_doc) if collection.welcome_doc else None
            ),
            "digest_frequency": collection.digest_frequency,
            "is_digest_muted": is_digest_muted,
            "has_date_things": has_date_things,
        }

    def get_rental_durations(self, obj):
        """Allowed rental lengths (days) from this thing's first collection (#7).
        Used by RequestThingPage to offer the fixed-duration picker for LEND/RENT."""
        first = self._viewable_collection(obj)
        return list(first.rental_durations) if first else []

    def get_rental_weekdays(self, obj):
        """Allowed pickup/return weekdays (0=Mon…6=Sun) from the first collection.

        Reused for RESERVE_THING as "days reservations are allowed"."""
        first = self._viewable_collection(obj)
        return first.rental_rules_for(obj.owner_id).weekdays if first else []

    def get_reservation_max_days(self, obj):
        """The longest a RESERVE_THING may be booked for, from its reservations
        collection. ``None`` for every non-RESERVE thing — RequestThingPage reads
        it to size the duration picker."""
        if obj.type != Thing.Type.RESERVE_THING:
            return None
        first = self._viewable_collection(obj)
        return first.reservation_max_days if first else 1

    def get_reservation_horizon_days(self, obj):
        """How far ahead a RESERVE_THING can be booked, from its reservations
        collection. ``None`` for non-RESERVE things — RequestThingPage reads it
        for the date picker's ``maxDate``."""
        if obj.type != Thing.Type.RESERVE_THING:
            return None
        first = self._viewable_collection(obj)
        return first.reservation_horizon_days if first else 90

    def get_closed_dates(self, obj):
        """The governing collection's holidays / closures (ISO strings) — the
        date picker greys these out and the request view refuses a handoff or a
        reservation span that touches one. ``[]`` when there is no collection."""
        first = self._viewable_collection(obj)
        return (
            sorted(d.isoformat() for d in first.rental_rules_for(obj.owner_id).closed)
            if first
            else []
        )

    def get_reservation_unit(self, obj):
        """DAY or HOUR — which reservation flow ``RequestThingPage`` renders for
        this RESERVE_THING. ``None`` for every non-RESERVE thing."""
        if obj.type != Thing.Type.RESERVE_THING:
            return None
        first = self._viewable_collection(obj)
        return first.reservation_unit if first else "DAY"

    def get_opening_hours(self, obj):
        """HOUR-unit only: the collection's per-weekday opening blocks, so the
        picker knows what to offer. ``{}`` for a DAY-unit or non-RESERVE thing."""
        if obj.type != Thing.Type.RESERVE_THING:
            return {}
        first = self._viewable_collection(obj)
        return dict(first.opening_hours) if first else {}

    def get_reservation_min_minutes(self, obj):
        """HOUR-unit only: the shortest a single reservation may run, in
        minutes — also the step the request page's duration/start-time
        choices are offered in. ``None`` for every non-RESERVE thing."""
        if obj.type != Thing.Type.RESERVE_THING:
            return None
        first = self._viewable_collection(obj)
        return first.reservation_min_minutes if first else 60

    def get_reservation_max_minutes(self, obj):
        """HOUR-unit only: the longest a single reservation may run, in
        minutes. ``None`` for every non-RESERVE thing."""
        if obj.type != Thing.Type.RESERVE_THING:
            return None
        first = self._viewable_collection(obj)
        return first.reservation_max_minutes if first else 180

    def get_faqs(self, obj):
        # Use prefetched faq_set cache if available
        return [faq.code for faq in obj.faq_set.all()]

    def get_collection_tags(self, obj):
        # The tag vocabulary available to this thing — union of the collections
        # the viewer may read. Feeds the tag picker on the edit form without an
        # extra fetch. Narrowed for the same reason as the fields above: a label
        # set is weaker evidence than a headline, but it still describes a group
        # the reader has no business seeing. The thing's owner loses nothing —
        # a thing only reaches a collection because its owner added it, which
        # takes ownership or membership either way.
        seen = set()
        result = []
        for collection in self._viewable_collections(obj):
            for tag in collection.tags or []:
                if tag not in seen:
                    seen.add(tag)
                    result.append(tag)
        return result


class ThingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a thing."""

    headline = LocalizedHeadlineField(max_length=64)
    description = LocalizedTextField(
        max_length=LOCALIZED_DESCRIPTION_VISIBLE,
        storage_max_length=LOCALIZED_DESCRIPTION_STORAGE,
        required=False,
        allow_blank=True,
    )
    thumbnail = ImageIdField(folder="oiueei/things")
    location = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    gallery = serializers.ListField(
        child=ImageIdField(folder="oiueei/things", allow_blank=False),
        max_length=8,
        required=False,
        allow_empty=True,
    )
    tags = serializers.ListField(
        child=LocalizedHeadlineField(max_length=32, storage_max_length=LOCALIZED_TAG_STORAGE),
        max_length=12,
        required=False,
        allow_empty=True,
    )
    # Non-negative, bounded to the model's 10-digit / 2-decimal range.
    fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    deposit = serializers.DecimalField(
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
            "deposit",
            "availability",
            "location",
            "condition",
            "is_endless",
        ]

    def validate(self, attrs):
        # With no type named the view works the verb out from the collection and
        # the price, and runs this same check on the result.
        if "type" in attrs:
            validate_deposit_for_type(attrs["type"], attrs.get("deposit"))
        return attrs


class ThingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a thing."""

    headline = LocalizedHeadlineField(max_length=64, required=False)
    description = LocalizedTextField(
        max_length=LOCALIZED_DESCRIPTION_VISIBLE,
        storage_max_length=LOCALIZED_DESCRIPTION_STORAGE,
        required=False,
        allow_blank=True,
    )
    thumbnail = ImageIdField(folder="oiueei/things")
    location = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    gallery = serializers.ListField(
        child=ImageIdField(folder="oiueei/things", allow_blank=False),
        max_length=8,
        required=False,
        allow_empty=True,
    )
    tags = serializers.ListField(
        child=LocalizedHeadlineField(max_length=32, storage_max_length=LOCALIZED_TAG_STORAGE),
        max_length=12,
        required=False,
        allow_empty=True,
    )
    # Non-negative, bounded to the model's 10-digit / 2-decimal range.
    fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    deposit = serializers.DecimalField(
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
            "deposit",
            "availability",
            "location",
            "condition",
            "is_endless",
        ]
        read_only_fields = ["status"]

    def validate(self, attrs):
        # Whatever the row will look like once this edit lands: an untouched
        # field keeps the stored value, so changing only the type still has to
        # answer for the deposit already on it.
        stored = self.instance
        validate_deposit_for_type(
            attrs.get("type", stored.type if stored else None),
            attrs.get("deposit", stored.deposit if stored else None),
        )
        return attrs

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


class LocaleDecimalField(serializers.DecimalField):
    """A ``DecimalField`` that also accepts a decimal comma (bulk-CSV only).

    Spanish/Catalan spreadsheet exports write decimals as ``1,5``; a plain
    ``DecimalField`` 400s on that. When the input is a string with exactly one
    ``,`` and no ``.``, the comma is the decimal separator and gets normalised
    to a dot before validation runs. A string carrying **both** ``.`` and
    ``,`` is ambiguous (thousands separator or decimal?) and is rejected
    outright rather than guessed — never guess with money. Anything else
    (already-dotted, an integer, multiple commas with no dot, ...) is left for
    the parent field to accept or reject as it always did.
    """

    def to_internal_value(self, data):
        if isinstance(data, str) and "," in data:
            if "." in data:
                raise serializers.ValidationError(
                    "Ambiguous number: use either a comma or a dot as the decimal "
                    "separator, not both."
                )
            if data.count(",") == 1:
                data = data.replace(",", ".")
        return super().to_internal_value(data)


class ThingBulkRowSerializer(serializers.ModelSerializer):
    """One row of a CSV bulk import (F-9).

    Reuses the project's safe text fields (HTML / line-break / unsafe-scheme
    rejection) and adds a CSV-injection guard on each free-text field. A cover and a
    gallery arrive as storage keys the client uploaded first; tags can — a single
    ``|``-separated cell, validated against the collection's vocabulary in the
    view (the serializer has no collection context).
    """

    headline = LocalizedHeadlineField(max_length=64)
    description = LocalizedTextField(
        max_length=LOCALIZED_DESCRIPTION_VISIBLE,
        storage_max_length=LOCALIZED_DESCRIPTION_STORAGE,
        required=False,
        allow_blank=True,
    )
    location = SafeHeadlineField(max_length=64, required=False, allow_blank=True)
    # LocaleDecimalField (not the plain DecimalField the other Thing
    # serializers use): a CSV row is the one path with no NumberInput to
    # normalise a locale decimal comma before it reaches the server.
    fee = LocaleDecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    deposit = LocaleDecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    tags = serializers.ListField(
        child=LocalizedHeadlineField(max_length=32, storage_max_length=LOCALIZED_TAG_STORAGE),
        max_length=12,
        required=False,
        allow_empty=True,
    )
    # Cover photo public_id. A CSV can't carry binaries, but a ZIP bundle can:
    # the client unzips, uploads each image to the bucket, and sends the resulting
    # public_id here (validated path-traversal-safe like the single-create path).
    thumbnail = ImageIdField(folder="oiueei/things", required=False, allow_blank=True)
    # Extra photos (the carousel), in the order the row lists them: the same field as the
    # single-create path, so a row accepts exactly what a form does — at most 8 keys, each
    # bound to the things folder.
    gallery = serializers.ListField(
        child=ImageIdField(folder="oiueei/things", allow_blank=False),
        max_length=8,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Thing
        fields = [
            "type",
            "headline",
            "description",
            "fee",
            "deposit",
            "availability",
            "location",
            "condition",
            "tags",
            "thumbnail",
            "gallery",
            "is_endless",
        ]

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

    def validate(self, attrs):
        if "type" in attrs:
            validate_deposit_for_type(attrs["type"], attrs.get("deposit"))
        return attrs
