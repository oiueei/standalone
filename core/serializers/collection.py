"""
Collection serializers for OIUEEI.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.models import RSVP, Collection, InvitationProposal, Theeeme, Thing
from core.models.collection import KIND_THING_TYPES, kind_for_thing_type
from core.serializers.network_point import NetworkPointSerializer
from core.serializers.theeeme import theeeme_colors
from core.serializers.thing import ThingComputedFieldsMixin
from core.utils import Refusal, asset_url, doc_asset_url
from core.validators import (
    LOCALIZED_DESCRIPTION_STORAGE,
    LOCALIZED_DESCRIPTION_VISIBLE,
    LOCALIZED_TAG_STORAGE,
    ImageIdField,
    LocalizedHeadlineField,
    LocalizedTextField,
    SafeTextField,
)

NO_MIXED_KINDS = "A collection holds one kind of thing: stall, library or shed."
ONLY_PRICES = "A group can take prices or not; it can't take only prices."
NETWORK_ONLY_LIBRARY = "Only a library can be a network."
NETWORK_MODE_FIXED = "A network can't become another mode, nor another mode a network."


class CollectionThingSummarySerializer(ThingComputedFieldsMixin, serializers.ModelSerializer):
    """Lightweight thing serializer for collection listings."""

    owner = serializers.CharField(source="owner_id")
    thumbnail_url = serializers.SerializerMethodField()
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
            "paused_from",
            "paused_until",
            "location",
            "condition",
            "thumbnail_url",
            "gallery_urls",
            "tags",
            "pending_booking",
            "bookings",
            "my_pending_booking",
            "pending_questions",
            "can_manage",
            "network_point",
            "transfer_count",
            "units",
            "deal",
            "created",
        ]

    def get_thumbnail_url(self, obj):
        return asset_url(obj.thumbnail) if obj.thumbnail else None


class CollectionListSerializer(serializers.ListSerializer):
    """List serializer that batch-loads the curator-only ``pending_invites``.

    ``pending_invites`` come from the RSVP table keyed by ``target_code`` (a
    plain CharField, not a FK — so there is no relation to ``prefetch_related``).
    Serialising a list of a curator's collections would otherwise fire one RSVP
    query per collection (N+1). Here we fetch them all in a single query and
    stash them on the shared context for the child serializer to read.
    """

    def to_representation(self, data):
        instances = list(data)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            owned_codes = [c.code for c in instances if c.is_curator(request.user.code)]
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
    welcome_doc = serializers.SerializerMethodField()
    welcome_doc_url = serializers.SerializerMethodField()
    things = serializers.SerializerMethodField()
    invites = serializers.SerializerMethodField()
    pending_invites = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    is_curator = serializers.SerializerMethodField()
    co_owners = serializers.SerializerMethodField()
    points = serializers.SerializerMethodField()
    is_digest_muted = serializers.SerializerMethodField()
    pending_proposals = serializers.SerializerMethodField()
    email_note = serializers.SerializerMethodField()
    # The palette the group's pages are painted with: public, like the language
    # and the kind (they are colours, and a reader with no session sees the page).
    theeeme = serializers.SlugRelatedField(slug_field="code", read_only=True)
    theeeme_colors = serializers.SerializerMethodField()
    is_paused = serializers.BooleanField(read_only=True)
    # Seed/onboarding collection — `seed_demo` sets it, no API path writes it.
    # The SPA shows a demo notice on it when this deployment supplies the copy
    # (`demoNotice.*` i18n keys); upstream there are none, so nothing renders.
    is_onboarding = serializers.BooleanField(read_only=True)

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
            "kind",
            "mode",
            "visibility",
            "digest_frequency",
            "allow_member_proposals",
            "language",
            "theeeme",
            "theeeme_colors",
            "koro",
            "allowed_thing_types",
            "rental_durations",
            "rental_weekdays",
            "reservation_max_days",
            "reservation_horizon_days",
            "reservation_max_active_per_member",
            "reservation_asks_phone",
            "reservation_unit",
            "opening_hours",
            "reservation_min_minutes",
            "reservation_max_minutes",
            "closed_dates",
            "home_page",
            "deposit_policy",
            "request_info",
            "email_note",
            "tags",
            "thumbnail",
            "thumbnail_url",
            "welcome_doc",
            "welcome_doc_url",
            "pause_message",
            "is_paused",
            "is_onboarding",
            "things",
            "invites",
            "pending_invites",
            "is_member",
            "is_curator",
            "co_owners",
            "points",
            "is_digest_muted",
            "pending_proposals",
        ]
        read_only_fields = [
            "code",
            "owner",
            "created",
            "is_paused",
            "is_onboarding",
            "things",
            "invites",
            "pending_invites",
            "is_member",
            "is_curator",
            "co_owners",
            "points",
            "is_digest_muted",
            "pending_proposals",
            "email_note",
            "welcome_doc",
        ]

    def get_owner_name(self, obj):
        # Bare name, not display_name — guests see this, so the email fallback
        # would leak the owner's address.
        return obj.owner.name

    def get_theeeme_colors(self, obj):
        return theeeme_colors(obj.theeeme)

    def get_thumbnail_url(self, obj):
        return asset_url(obj.thumbnail) if obj.thumbnail else None

    def _may_read_welcome_doc(self, obj):
        """The welcome PDF is for the group — its curators and its members —
        not for whoever can read a PUBLIC collection's page.

        It is the group's rules, mailed to each member on joining (Cat. 1) and
        read back only by the curators' edit form, yet it was served to every
        reader of the collection, anonymous visitors included. Members keep it:
        the document is addressed to them. Fails closed without a request.
        """
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            return False
        return self._requester_is_curator(obj) or any(
            u.code == request.user.code for u in obj.invites.all()
        )

    def get_welcome_doc(self, obj):
        return obj.welcome_doc if self._may_read_welcome_doc(obj) else ""

    def get_welcome_doc_url(self, obj):
        if not (obj.welcome_doc and self._may_read_welcome_doc(obj)):
            return None
        return doc_asset_url(obj.welcome_doc)

    def get_things(self, obj):
        request = self.context.get("request")
        ctx = {**self.context, "parent_collection": obj}
        is_curator = bool(
            request and request.user.is_authenticated and obj.is_curator(request.user.code)
        )
        things = obj.things.all()
        # Non-curators (including anonymous visitors on a PUBLIC collection)
        # never see someone else's INACTIVE thing; only skip the filter for
        # internal, request-less use. **A thing's own owner is the one
        # exception** — in a COMMUNITY collection a member owns what they
        # contributed, not the collection, and `Thing.can_view()` already says
        # "owner can always view their own things" regardless of status. This
        # mirrors that rule rather than re-deriving it (a per-thing
        # `can_view()` call here would walk each thing's own `collections`
        # queryset — an N+1 this method exists to avoid), so a member whose
        # gift completed (INACTIVE, non-endless) or who hid their own listing
        # can still find it on the collection they added it to, not only via
        # its standalone `/things/{code}` URL.
        # Filtered in Python (not .exclude()) so the prefetched M2M cache is reused
        # instead of firing a fresh query per thing (N+1 on home + anon collection
        # detail).
        if request and not is_curator:
            viewer_code = request.user.code if request.user.is_authenticated else None
            things = [
                t for t in things if t.status != Thing.Status.INACTIVE or t.owner_id == viewer_code
            ]
        return CollectionThingSummarySerializer(things, many=True, context=ctx).data

    def _requester_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.is_owner(request.user.code))

    def _requester_is_curator(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.is_curator(request.user.code))

    def get_is_curator(self, obj):
        """Whether the requester may act as this collection's admin (owner or
        co-owner) — the one field the frontend needs instead of deriving
        ownership itself from ``owner``."""
        return self._requester_is_curator(obj)

    def get_co_owners(self, obj):
        """The collection's co-owners — public, like ``owner_name``: a curator
        is someone the group's own page already names, not private roster
        data. Reads the prefetched M2M so this adds no query."""
        return [{"code": u.code, "name": u.name} for u in obj.co_owners.all()]

    def get_points(self, obj):
        """The pages of the group's curators — public with the collection, in every mode.
        In a network each is a pickup point, address included: it answers for an entity,
        not for a home. Elsewhere it carries only name, logo, about and contact."""
        points = sorted(obj.points.all(), key=lambda point: point.code)
        return NetworkPointSerializer(points, many=True, context=self.context).data

    def get_is_member(self, obj):
        # True when the requester is an invited member, but not a curator
        # (owner or co-owner) — a co-owner is staff, not a rank-and-file
        # member. Reads the prefetched invites so it adds no query. Drives the
        # "Leave the group" button.
        request = self.context.get("request")
        if not (request and request.user.is_authenticated) or self._requester_is_curator(obj):
            return False
        return any(u.code == request.user.code for u in obj.invites.all())

    def get_pending_proposals(self, obj):
        """Members' pending recommendations — **curator only**.

        These name a person who has not been contacted and does not know they
        were suggested, and they carry the proposer's private note. Nobody but
        the people who have to decide see them.
        """
        if not self._requester_is_curator(obj):
            return []
        # Prefetched by `_optimise_collection_queryset` for signed-in viewers;
        # the fallback keeps a request-less or unoptimised caller working.
        pending = getattr(obj, "_pending_proposals", None)
        if pending is None:
            pending = obj.invitation_proposals.filter(
                status=InvitationProposal.Status.PENDING
            ).select_related("proposer")
        return [
            {
                "code": p.code,
                "email": p.email,
                "note": p.note,
                "proposer_name": p.proposer.name,
                "created": p.created,
            }
            for p in pending
        ]

    def get_email_note(self, obj):
        """The owner's note for requesters' emails — **curator only**, ``""``
        for everyone else.

        The form tells the owner it goes into the emails a member receives
        about their own request, so that is the audience they write for: how
        to collect, where the key is, a phone to call on arrival. Served
        alongside the rest of the collection it reached every reader instead —
        anonymous visitors of a PUBLIC collection included — while the only
        page that reads it is the curators' edit form. Fails closed without a
        request, like ``pending_invites``.
        """
        return obj.email_note if self._requester_is_curator(obj) else ""

    def get_is_digest_muted(self, obj):
        # Whether *this* viewer has silenced this collection's digest. It goes to the
        # members and the founder, so the answer is theirs to read; a reader who is
        # not signed in gets False and no toggle is rendered for them.
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            return False
        return any(u.code == request.user.code for u in obj.digest_muted.all())

    def get_invites(self, obj):
        members = obj.invites.all()
        if self._requester_is_curator(obj):
            # A curator's view of the roster — emails, and in a COMMUNITY
            # collection each member's optional age range and postal code. Built
            # by the model (`Collection.owner_member_rows`) because the data
            # export answers the same question and the two must not drift; other
            # modes and non-curators never receive the demographics.
            return obj.owner_member_rows(members)
        # Co-members' emails are curator-only; logged-in guests get only
        # code + name. An ANONYMOUS reader of a PUBLIC collection gets codes
        # alone — the member count survives for the card, but real names of a
        # group's members don't belong to the open web (early-adopter hardening).
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            return [{"code": u.code} for u in members]
        return [{"code": u.code, "name": u.name} for u in members]

    def get_pending_invites(self, obj):
        # Pending invitees and their emails are curator-management data only.
        if not self._requester_is_curator(obj):
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

    headline = LocalizedHeadlineField(max_length=64)
    description = LocalizedTextField(
        max_length=LOCALIZED_DESCRIPTION_VISIBLE,
        storage_max_length=LOCALIZED_DESCRIPTION_STORAGE,
        required=False,
        allow_blank=True,
    )
    thumbnail = ImageIdField(folder="oiueei/collections", required=False, allow_blank=True)
    # The welcome PDF is a storage key like any other asset — same
    # path-traversal-safe validation.
    welcome_doc = ImageIdField(folder="oiueei/documents", required=False, allow_blank=True)
    tags = serializers.ListField(
        child=LocalizedHeadlineField(max_length=32, storage_max_length=LOCALIZED_TAG_STORAGE),
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
    # RESERVE_THING collections only: the longest a member may book the space
    # for in one reservation. Inert elsewhere. `rental_weekdays` above is reused
    # as "days reservations are allowed".
    reservation_max_days = serializers.IntegerField(min_value=1, max_value=7, required=False)
    # How far ahead a member may book this space, in days. 1..365 — a year is the
    # most a "how far ahead" limit should ever need. Default 90.
    reservation_horizon_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    # RESERVE_THING collections only: how many of a member's own reservations in
    # THIS collection may be active at once. A courtesy cap, not a security
    # invariant — see Collection.active_reservation_count. 1..50, default 10.
    reservation_max_active_per_member = serializers.IntegerField(
        min_value=1, max_value=50, required=False
    )
    # Sheds only: whether the request page asks for an optional contact phone.
    # A True on any other kind is refused (``_validate_phone_switch``).
    reservation_asks_phone = serializers.BooleanField(required=False)
    # RESERVE_THING collections only: DAY (default) or HOUR — never both. See
    # Collection.ReservationUnit.
    reservation_unit = serializers.ChoiceField(
        choices=Collection.ReservationUnit.choices, required=False
    )
    # HOUR-unit collections only: per-weekday opening blocks. See
    # `_validate_opening_hours` for the wire shape.
    opening_hours = serializers.JSONField(required=False)
    # HOUR-unit collections only, in minutes (replaced hour-granular
    # `reservation_max_hours` in 0150 — an early adopter wanted reservations
    # shorter than an hour). `reservation_min_minutes` is also the step every
    # duration/start-time choice on the request page is offered in. Cross-
    # checked against each other in `validate()` below. Inert under DAY
    # (`reservation_max_days` governs there).
    reservation_min_minutes = serializers.IntegerField(min_value=1, max_value=720, required=False)
    reservation_max_minutes = serializers.IntegerField(min_value=1, max_value=720, required=False)
    # Holidays / one-off closures. The form sends a comma-separated DD/MM/YYYY
    # line; `validate_closed_dates` parses it to sorted ISO strings, drops past
    # dates, caps the count. No pickup/return on one for LEND/RENT, no RESERVE
    # span across one. `write_only` because the read serializer returns the
    # stored ISO list straight off the JSONField.
    closed_dates = serializers.CharField(required=False, allow_blank=True, write_only=True)
    home_page = serializers.URLField(max_length=128, required=False, allow_blank=True)
    # Localized like every other owner text: a deposit policy that could
    # only be written in one language would be the single piece of group prose
    # that a bilingual group cannot say twice. 256 visible per language, 1024
    # stored — the same arithmetic as `description`.
    deposit_policy = LocalizedTextField(max_length=256, required=False, allow_blank=True)
    # A note for anyone about to request anything from this collection — every
    # verb, not just RESERVE_THING. Same localized-text shape as deposit_policy,
    # wider: 512 visible per language, 2048 stored — the
    # storage cap has to be given explicitly since it no longer matches
    # LOCALIZED_TEXT_STORAGE's default (1024, sized for deposit_policy's 256).
    request_info = LocalizedTextField(
        max_length=512, storage_max_length=2048, required=False, allow_blank=True
    )
    # The owner's note in the emails a requester receives about their request
    # — "received" and "accepted" for every verb, plus RESERVE's auto-confirm
    # — same shape and same arithmetic as request_info above, for the same
    # reason.
    email_note = LocalizedTextField(
        max_length=512, storage_max_length=2048, required=False, allow_blank=True
    )

    # A curator picks one of the twelve palettes of `theeemes` (the app's own,
    # `Braaanding`, is a different table and cannot be named here); left out, a new
    # collection draws a random one and an update keeps what it has.
    theeeme = serializers.SlugRelatedField(
        slug_field="code", queryset=Theeeme.objects.all(), required=False
    )

    class Meta:
        model = Collection
        fields = [
            "theeeme",
            "koro",
            "headline",
            "description",
            "kind",
            "mode",
            "visibility",
            "digest_frequency",
            "allow_member_proposals",
            "language",
            "allowed_thing_types",
            "rental_durations",
            "rental_weekdays",
            "reservation_max_days",
            "reservation_horizon_days",
            "reservation_max_active_per_member",
            "reservation_asks_phone",
            "reservation_unit",
            "opening_hours",
            "reservation_min_minutes",
            "reservation_max_minutes",
            "closed_dates",
            "home_page",
            "deposit_policy",
            "request_info",
            "email_note",
            "tags",
            "thumbnail",
            "welcome_doc",
        ]

    def validate_opening_hours(self, value):
        return _validate_opening_hours(value)

    def validate_tags(self, value):
        return _normalize_tags(value)

    def validate_rental_durations(self, value):
        return sorted(set(value))

    def validate_rental_weekdays(self, value):
        return sorted(set(value))

    def validate_closed_dates(self, value):
        return _parse_closed_dates(value)

    def validate(self, attrs):
        # A collection is born PRIVATE, whatever its mode, when the client doesn't
        # say otherwise; making it PUBLIC is an explicit decision.
        # COMMUNITY used to be born PUBLIC "so a stranger can reach it", but the
        # person who contributes a thing to a group is not shown whether it is
        # public (the Public/Private tag is the curators' since 2026-09-21, and
        # AddThingPage says nothing), so a group of neighbours' families was
        # readable by anyone and the members never knew — photos, text and the
        # thing's ``location`` on the open web. An explicit ``visibility`` is
        # respected in either mode.
        mode = attrs.get("mode", Collection.Mode.PROPRIETARY)
        if not attrs.get("visibility"):
            attrs["visibility"] = Collection.Visibility.PRIVATE
        listed = attrs.get("allowed_thing_types", [])
        # A client that names no kind (the API before kinds) gets the one its verbs
        # belong to; one that names neither a kind nor any verb gets a stall, the
        # model's default (and what the kind migration made of a collection with no
        # verbs); a list that spans several kinds cannot say.
        kind = attrs.get("kind") or (_kind_of_verbs(listed) if listed else Collection.Kind.STALL)
        attrs["kind"] = kind
        attrs["allowed_thing_types"] = normalize_allowed_thing_types(kind, mode, listed)
        _validate_phone_switch(kind, attrs.get("reservation_asks_phone", False))
        _validate_reservation_minutes(
            attrs.get("reservation_min_minutes", 60), attrs.get("reservation_max_minutes", 180)
        )
        _validate_hourly_opening_hours(
            attrs.get("reservation_unit", Collection.ReservationUnit.DAY),
            attrs.get("opening_hours", {}),
        )
        return attrs


def _validate_phone_switch(kind, asks_phone):
    """The contact-phone switch means something in a shed only: turning it on anywhere
    else would promise a field no request page of that kind will ever show."""
    if asks_phone and kind != Collection.Kind.SHED:
        raise serializers.ValidationError(
            {"reservation_asks_phone": "Only a shed can ask for a contact phone."}
        )


def _validate_hourly_opening_hours(unit, opening_hours):
    """A collection booked by the hour needs at least one opening block.

    With none it is closed every day: nobody can reserve, and nothing says why
    until a member tries. Judged on the state the request leaves behind (the value
    in the request, or what the instance already holds), so switching a day-unit
    collection to HOUR without hours is refused too. The app's ``hasOpeningHours``
    is the same rule.
    """
    if unit != Collection.ReservationUnit.HOUR:
        return
    if any(blocks for blocks in (opening_hours or {}).values()):
        return
    raise serializers.ValidationError(
        Refusal(
            "To book by the hour, add at least one time range to 'Weekly opening hours'.",
            "opening_hours_required",
        )
    )


def _validate_reservation_minutes(min_minutes, max_minutes):
    """HOUR-unit collections only, but cheap to run unconditionally: a
    minimum longer than the maximum would make every reservation impossible,
    silently — `reservation_hour_violation` would refuse everything and never
    say why. Shared by the create and update `validate()`, which resolve
    "the value in this request, or whatever's already on the instance" first.
    """
    if min_minutes > max_minutes:
        raise serializers.ValidationError(
            "The minimum reservation length can't be longer than the maximum."
        )


_CLOSED_DATES_MAX = 60


def _parse_closed_dates(raw):
    """Parse the owner's ``closed_dates`` input into a sorted list of ISO strings.

    Accepts either the comma-separated ``DD/MM/YYYY`` line the form sends
    ("25/12/2026, 26/12/2026") or an already-parsed list of ISO strings (an API
    client). Past dates are dropped silently — the owner re-enters holidays each
    year and a stale one is only noise. A date more than two years out is
    **rejected**, not dropped: at that range it is far likelier a typo
    (``2025`` → ``2035``) than a real plan, and silently eating it would leave
    the owner thinking they set a closure they didn't. Deduped and sorted.
    Raises ``ValidationError`` on a token that is not a real date.
    """
    if raw in (None, "", []):
        return []
    tokens = raw if isinstance(raw, list) else [t.strip() for t in str(raw).split(",")]
    today = timezone.localdate()
    horizon = today + timedelta(days=730)
    seen = set()
    for token in tokens:
        token = (token or "").strip()
        if not token:
            continue
        parsed = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(token, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            raise serializers.ValidationError(
                f"'{token}' isn't a date — use DD/MM/YYYY, separated by commas."
            )
        if parsed < today:
            continue  # a stale holiday from a past year is just noise
        if parsed > horizon:
            raise serializers.ValidationError(
                f"'{token}' is more than two years away — closure days are for "
                "this year or next. Check for a typo."
            )
        seen.add(parsed.isoformat())
    result = sorted(seen)
    if len(result) > _CLOSED_DATES_MAX:
        raise serializers.ValidationError(
            f"That's more than {_CLOSED_DATES_MAX} closure days — enter this year's."
        )
    return result


_OPENING_HOURS_DAY_KEYS = {"0", "1", "2", "3", "4", "5", "6"}
_OPENING_HOURS_MAX_BLOCKS_PER_DAY = 4


def _parse_hhmm(value):
    """ "HH:MM" -> `datetime.time`. Raises ValueError on anything else — an
    out-of-range hour/minute included, since `time()` itself rejects those."""
    if not isinstance(value, str):
        raise ValueError("not a string")
    hour_str, _, minute_str = value.partition(":")
    if not minute_str:
        raise ValueError("not HH:MM")
    return datetime.strptime(f"{int(hour_str):02d}:{int(minute_str):02d}", "%H:%M").time()


def _validate_opening_hours(value):
    """Validate + normalise a HOUR-unit collection's per-weekday opening hours.

    ``value`` is ``{"0".."6": [["HH:MM","HH:MM"], ...]}`` — Django's own string
    form of ``weekday()`` (0=Mon…6=Sun) as the JSON key, each a list of that
    day's opening blocks. Missing key / empty list = closed that day. Blocks
    are sorted and must not overlap; each one's start must be strictly before
    its end. Raises ``ValidationError`` on any other shape.
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError("Opening hours must be a day-keyed object.")
    cleaned = {}
    for key, blocks in value.items():
        if key not in _OPENING_HOURS_DAY_KEYS:
            raise serializers.ValidationError(f"'{key}' is not a day of the week (use 0-6).")
        if not isinstance(blocks, list):
            raise serializers.ValidationError(f"Day {key}: expected a list of time ranges.")
        if len(blocks) > _OPENING_HOURS_MAX_BLOCKS_PER_DAY:
            raise serializers.ValidationError(
                f"Day {key}: at most {_OPENING_HOURS_MAX_BLOCKS_PER_DAY} opening blocks."
            )
        parsed = []
        for block in blocks:
            if not isinstance(block, (list, tuple)) or len(block) != 2:
                raise serializers.ValidationError(f"Day {key}: each block is [start, end].")
            try:
                start, end = _parse_hhmm(block[0]), _parse_hhmm(block[1])
            except ValueError:
                raise serializers.ValidationError(f"Day {key}: times must be HH:MM.")
            if start >= end:
                raise serializers.ValidationError(
                    f"Day {key}: a block's start must be before its end."
                )
            parsed.append((start, end))
        parsed.sort()
        for (_start, end), (next_start, _end) in zip(parsed, parsed[1:]):
            if next_start < end:
                raise serializers.ValidationError(f"Day {key}: opening blocks overlap.")
        cleaned[key] = [[s.strftime("%H:%M"), e.strftime("%H:%M")] for s, e in parsed]
    return cleaned


def _normalize_tags(tags):
    """Trim each tag, drop empties, and dedupe case-insensitively (first wins).

    Used by both collection serializers so the owner-defined tag vocabulary is
    always clean. The ListField (max_length=12) caps the raw count and
    LocalizedHeadlineField rejects HTML / over-length labels before this runs (a
    label may be a per-language map, in which case each language is checked).
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


def _kind_of_verbs(verbs):
    """The one kind a non-empty list of verbs belongs to, else the 400 that says why not."""
    unknown = [v for v in verbs if kind_for_thing_type(v) is None]
    if unknown:
        raise serializers.ValidationError(f"These types are not allowed: {unknown}")
    kinds = {kind_for_thing_type(v) for v in verbs}
    if len(kinds) != 1:
        raise serializers.ValidationError(NO_MIXED_KINDS)
    return kinds.pop()


def normalize_allowed_thing_types(kind, mode, allowed_thing_types):
    """The verb list a ``kind``/``mode`` collection stores, or the 400 for one it can't.

    Always within the kind's own verbs and never empty. PROPRIETARY takes both of
    them (its curators put the things in and set each price); a COMMUNITY stall or
    library takes both, or only the free one when its members may not set a price
    (an empty list means both, "only the paid one" is refused); a shed takes
    RESERVE alone and is always PROPRIETARY — an operator runs the premises.
    """
    verbs = KIND_THING_TYPES[kind]
    listed = list(allowed_thing_types or [])
    invalid = [t for t in listed if t not in verbs]
    if invalid:
        raise serializers.ValidationError(f"These types are not allowed: {invalid}")
    if mode == Collection.Mode.NETWORK and kind != Collection.Kind.LIBRARY:
        raise serializers.ValidationError(NETWORK_ONLY_LIBRARY)
    if kind == Collection.Kind.SHED:
        if mode == Collection.Mode.COMMUNITY:
            raise serializers.ValidationError(
                "A reservations collection is run by one operator, so it can't "
                "be a community collection."
            )
        return list(verbs)
    if (
        mode in (Collection.Mode.PROPRIETARY, Collection.Mode.NETWORK)
        or not listed
        or set(listed) == set(verbs)
    ):
        return list(verbs)
    free = verbs[0]
    if listed == [free]:
        return [free]
    raise serializers.ValidationError(ONLY_PRICES)


class CollectionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a collection."""

    headline = LocalizedHeadlineField(max_length=64, required=False)
    description = LocalizedTextField(
        max_length=LOCALIZED_DESCRIPTION_VISIBLE,
        storage_max_length=LOCALIZED_DESCRIPTION_STORAGE,
        required=False,
        allow_blank=True,
    )
    thumbnail = ImageIdField(folder="oiueei/collections", required=False, allow_blank=True)
    # The welcome PDF is a storage key like any other asset — same
    # path-traversal-safe validation.
    welcome_doc = ImageIdField(folder="oiueei/documents", required=False, allow_blank=True)
    pause_message = SafeTextField(max_length=256, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=LocalizedHeadlineField(max_length=32, storage_max_length=LOCALIZED_TAG_STORAGE),
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
    reservation_max_days = serializers.IntegerField(min_value=1, max_value=7, required=False)
    # How far ahead a member may book this space, in days. 1..365 — a year is the
    # most a "how far ahead" limit should ever need. Default 90.
    reservation_horizon_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    # RESERVE_THING collections only: how many of a member's own reservations in
    # THIS collection may be active at once. A courtesy cap, not a security
    # invariant — see Collection.active_reservation_count. 1..50, default 10.
    reservation_max_active_per_member = serializers.IntegerField(
        min_value=1, max_value=50, required=False
    )
    # Sheds only: whether the request page asks for an optional contact phone.
    # A True on any other kind is refused (``_validate_phone_switch``).
    reservation_asks_phone = serializers.BooleanField(required=False)
    reservation_unit = serializers.ChoiceField(
        choices=Collection.ReservationUnit.choices, required=False
    )
    opening_hours = serializers.JSONField(required=False)
    reservation_min_minutes = serializers.IntegerField(min_value=1, max_value=720, required=False)
    reservation_max_minutes = serializers.IntegerField(min_value=1, max_value=720, required=False)
    # Holidays / one-off closures. The form sends a comma-separated DD/MM/YYYY
    # line; `validate_closed_dates` parses it to sorted ISO strings, drops past
    # dates, caps the count. No pickup/return on one for LEND/RENT, no RESERVE
    # span across one. `write_only` because the read serializer returns the
    # stored ISO list straight off the JSONField.
    closed_dates = serializers.CharField(required=False, allow_blank=True, write_only=True)
    home_page = serializers.URLField(max_length=128, required=False, allow_blank=True)
    # Localized like every other owner text: a deposit policy that could
    # only be written in one language would be the single piece of group prose
    # that a bilingual group cannot say twice. 256 visible per language, 1024
    # stored — the same arithmetic as `description`.
    deposit_policy = LocalizedTextField(max_length=256, required=False, allow_blank=True)
    # A note for anyone about to request anything from this collection — every
    # verb, not just RESERVE_THING. Same localized-text shape as deposit_policy,
    # wider: 512 visible per language, 2048 stored — the
    # storage cap has to be given explicitly since it no longer matches
    # LOCALIZED_TEXT_STORAGE's default (1024, sized for deposit_policy's 256).
    request_info = LocalizedTextField(
        max_length=512, storage_max_length=2048, required=False, allow_blank=True
    )
    # The owner's note in the emails a requester receives about their request
    # — "received" and "accepted" for every verb, plus RESERVE's auto-confirm
    # — same shape and same arithmetic as request_info above, for the same
    # reason.
    email_note = LocalizedTextField(
        max_length=512, storage_max_length=2048, required=False, allow_blank=True
    )

    # A curator picks one of the twelve palettes of `theeemes` (the app's own,
    # `Braaanding`, is a different table and cannot be named here); left out, a new
    # collection draws a random one and an update keeps what it has.
    theeeme = serializers.SlugRelatedField(
        slug_field="code", queryset=Theeeme.objects.all(), required=False
    )

    class Meta:
        model = Collection
        fields = [
            "theeeme",
            "koro",
            "headline",
            "description",
            "status",
            "kind",
            "mode",
            "visibility",
            "digest_frequency",
            "allow_member_proposals",
            "language",
            "allowed_thing_types",
            "rental_durations",
            "rental_weekdays",
            "reservation_max_days",
            "reservation_horizon_days",
            "reservation_max_active_per_member",
            "reservation_asks_phone",
            "reservation_unit",
            "opening_hours",
            "reservation_min_minutes",
            "reservation_max_minutes",
            "closed_dates",
            "home_page",
            "deposit_policy",
            "request_info",
            "email_note",
            "tags",
            "thumbnail",
            "welcome_doc",
            "pause_message",
        ]

    def validate_rental_durations(self, value):
        return sorted(set(value))

    def validate_rental_weekdays(self, value):
        return sorted(set(value))

    def validate_closed_dates(self, value):
        return _parse_closed_dates(value)

    def validate_opening_hours(self, value):
        return _validate_opening_hours(value)

    def validate(self, attrs):
        instance = self.instance
        # The kind is read-only: naming the one it already has is harmless, any
        # other is refused rather than silently ignored.
        if "kind" in attrs:
            if instance is not None and attrs.pop("kind") != instance.kind:
                raise serializers.ValidationError("A collection's kind can't change.")
        allowed_thing_types = attrs.get(
            "allowed_thing_types",
            instance.allowed_thing_types if instance else [],
        )
        mode = attrs.get("mode", instance.mode if instance else Collection.Mode.PROPRIETARY)
        # A network is what a library is born as and stays: the mode is shown, not
        # changed, in either direction (naming the one it already has is harmless).
        if instance is not None and mode != instance.mode:
            if Collection.Mode.NETWORK in (mode, instance.mode):
                raise serializers.ValidationError(NETWORK_MODE_FIXED)
        # A reservations collection can never be switched to COMMUNITY, even if
        # the allowlist isn't being touched in this request.
        if (
            instance is not None
            and attrs.get("mode") == Collection.Mode.COMMUNITY
            and instance.is_reservations_collection()
        ):
            raise serializers.ValidationError(
                "A reservations collection can't become a community collection."
            )
        kind = instance.kind if instance else Collection.Kind.STALL
        allowed_thing_types = normalize_allowed_thing_types(kind, mode, allowed_thing_types)
        _validate_phone_switch(kind, attrs.get("reservation_asks_phone", False))
        # Switching to PROPRIETARY widens a free-only list, so write it back whenever
        # the list or the mode is part of the edit.
        if "allowed_thing_types" in attrs or "mode" in attrs:
            attrs["allowed_thing_types"] = allowed_thing_types
        _validate_reservation_minutes(
            attrs.get(
                "reservation_min_minutes", instance.reservation_min_minutes if instance else 60
            ),
            attrs.get(
                "reservation_max_minutes", instance.reservation_max_minutes if instance else 180
            ),
        )
        # Only an edit that touches the unit or the hours is judged: a collection that
        # was hourly with no hours before the rule can still be paused, resumed or
        # renamed. The edit form sends both with HOUR, so saving it asks for hours.
        if instance is None or "reservation_unit" in attrs or "opening_hours" in attrs:
            _validate_hourly_opening_hours(
                attrs.get(
                    "reservation_unit",
                    instance.reservation_unit if instance else Collection.ReservationUnit.DAY,
                ),
                attrs.get("opening_hours", instance.opening_hours if instance else {}),
            )
        # Orphan check: narrowing the list must leave every thing of the collection's
        # own family a valid slot. A thing of the other family (a lend in a stall, kept
        # by design when a collection that held both was given a kind) is tolerated
        # and not counted: it was never covered by the list. What can be orphaned
        # inside a kind is the paid verb, when a COMMUNITY group stops letting
        # members set a price.
        if instance is not None and "allowed_thing_types" in attrs and allowed_thing_types:
            own_family = set(KIND_THING_TYPES[instance.kind])
            existing_types = set(instance.things.values_list("type", flat=True)) & own_family
            orphaned = sorted(existing_types - set(allowed_thing_types))
            if orphaned:
                raise serializers.ValidationError(
                    Refusal(
                        "Cannot restrict the allowed types: existing things would be"
                        f" orphaned (types: {', '.join(orphaned)}). Remove them first.",
                        "priced_things_remain",
                    )
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
        # Atomic so the collection edit and the cascade land together — a failure
        # mid-cascade must not leave the vocabulary changed but some things still
        # carrying a removed tag. bulk_update writes the strip in one query.
        with transaction.atomic():
            collection = super().update(instance, validated_data)
            if new_tags is not None:
                removed = set(old_tags) - set(new_tags)
                if removed:
                    stripped = []
                    for thing in collection.things.all():
                        if any(t in removed for t in (thing.tags or [])):
                            thing.tags = [t for t in thing.tags if t not in removed]
                            stripped.append(thing)
                    if stripped:
                        Thing.objects.bulk_update(stripped, ["tags"])
        return collection


class CollectionInviteSerializer(serializers.Serializer):
    """Serializer for inviting a user to a collection."""

    email = serializers.EmailField(max_length=64)


class CollectionProposeInviteSerializer(serializers.Serializer):
    """A member suggesting somebody to the collection's owner.

    The `note` is the proposer's word to the owner — the thing that makes the
    approval a decision rather than a guess ("she's my downstairs neighbour",
    "he's paid the subs"). Optional, `SafeTextField` like every other free-text
    field, and never shown to the person being proposed.
    """

    email = serializers.EmailField(max_length=64)
    note = SafeTextField(max_length=256, required=False, allow_blank=True)


class CollectionRemoveInviteSerializer(serializers.Serializer):
    """Serializer for removing a user from a collection's invite list."""

    user_code = serializers.CharField(max_length=6)


class EmailNoteTestSerializer(serializers.Serializer):
    """The ``email_note`` draft a curator asks to see as members will — the same
    field, and so the same per-language limits, as the collection's own."""

    email_note = LocalizedTextField(max_length=512, storage_max_length=2048)


class CollectionBroadcastSerializer(serializers.Serializer):
    """Serializer for broadcasting a message to collection invitees.

    The subject is auto-generated ("Hey! {collection}"); only the message is
    user-provided.
    """

    message = SafeTextField(max_length=256)
