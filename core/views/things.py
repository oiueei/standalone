"""
Thing views for OIUEEI.
"""

from django.db import transaction
from django.db.models import prefetch_related_objects
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.exceptions import RefusedField
from core.models import Collection, Thing
from core.models.collection import KIND_THING_TYPES
from core.models.event import Event
from core.models.notification import InAppNotification
from core.permissions import IsThingManager, IsThingManagerOrRescuer
from core.serializers import (
    ThingBulkRowSerializer,
    ThingCreateSerializer,
    ThingSerializer,
    ThingUpdateSerializer,
)
from core.serializers.thing import (
    UNITS_TYPES,
    optimise_thing_queryset,
    validate_deposit_for_type,
    validate_units_for_type,
)
from core.services.creator_policy import (
    capabilities_for,
    community_contribution_types,
    thing_type_denial,
)
from core.services.email_service import send_thing_hidden_by_founder_email
from core.services.membership_service import delete_thing
from core.utils import parse_localized
from core.views._helpers import refusal_body, type_validity_error, verb_from_price, viewer_code


def _resolve_tag_aliases(tags, vocabulary):
    """Resolve bulk-CSV tags against a collection's tag vocabulary, accepting
    any language of a localized entry as an alias for its canonical string —
    without this a CSV must carry the byte-identical
    ``{"es": "Crianza", "ca": "Criança"}`` JSON, which no human can type.

    Builds ``{value.casefold(): canonical}`` over the vocabulary: a localized
    entry (see ``core.utils.parse_localized``) contributes each of its
    per-language values, a plain entry contributes its own casefolded self.
    A tag matches (a) exactly — kept as-is, today's behaviour — or (b) via the
    alias map, in which case the **canonical** vocabulary string is what's
    returned, so a thing's stored tags stay directly comparable to the
    vocabulary and to each other regardless of which language the CSV used.

    Returns ``(resolved, unknown, ambiguous)``. ``resolved`` mirrors ``tags``
    with every match replaced by its canonical string. ``unknown`` lists tags
    that matched nothing (today's error). ``ambiguous`` lists tags whose
    casefolded alias maps to more than one distinct canonical entry — rejected
    rather than guessed, since vocabularies are owner-authored and a
    collision is a real ambiguity, not noise.
    """
    vocabulary = vocabulary or []
    exact = set(vocabulary)

    alias_map = {}
    ambiguous_keys = set()
    for canonical in vocabulary:
        localized = parse_localized(canonical)
        values = localized.values() if localized else [canonical]
        for value in values:
            key = value.casefold()
            existing = alias_map.get(key)
            if existing is not None and existing != canonical:
                ambiguous_keys.add(key)
            alias_map[key] = canonical

    resolved, unknown, ambiguous = [], [], []
    for tag in tags:
        if tag in exact:
            resolved.append(tag)
            continue
        key = tag.casefold()
        if key in ambiguous_keys:
            ambiguous.append(tag)
        elif key in alias_map:
            resolved.append(alias_map[key])
        else:
            unknown.append(tag)
    return resolved, unknown, ambiguous


class ThingViewSet(ModelViewSet):
    """
    ViewSet for Thing CRUD operations.

    list:   GET /api/v1/things/
    create: POST /api/v1/things/
    retrieve: GET /api/v1/things/{code}/
    update: PUT /api/v1/things/{code}/
    destroy: DELETE /api/v1/things/{code}/
    """

    lookup_field = "code"

    def get_queryset(self):
        return optimise_thing_queryset(
            Thing.objects.filter(owner=self.request.user), with_collections=True
        ).order_by("-created")

    def get_serializer_class(self):
        if self.action == "create":
            return ThingCreateSerializer
        if self.action in ("update", "partial_update"):
            return ThingUpdateSerializer
        return ThingSerializer

    def get_permissions(self):
        if self.action == "hide":
            # A manager of the thing, or the founder of the network it sits in.
            return [IsAuthenticated(), IsThingManagerOrRescuer()]
        if self.action in ("update", "partial_update", "activate"):
            # IsThingManager: the thing owner, or a curator of a PROPRIETARY
            # collection it sits in — those curators run the catalogue.
            return [IsAuthenticated(), IsThingManager()]
        # Anonymous read for retrieve; can_view() still gates it (a thing is only
        # visible without membership when it sits in a PUBLIC, ACTIVE collection).
        if self.action == "retrieve":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_object(self):
        obj = get_object_or_404(Thing, code=self.kwargs[self.lookup_field])
        if self.action == "retrieve":
            if not obj.can_view(viewer_code(self.request)):
                self.permission_denied(self.request)
            # The thing's collections and their co-owners, once: `can_manage`, the
            # collection menu and `live_requesters_count` all ask who curates them.
            prefetch_related_objects([obj], "collections__co_owners")
        elif self.action == "destroy":
            if not obj.can_delete(self.request.user.code):
                self.permission_denied(self.request)
        else:
            self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        # Errors are raised as DRF exceptions (403 PermissionDenied / 404 NotFound
        # / 400 ValidationError) and handled by the default exception handler —
        # no instance-state protocol, so create() stays a plain 201 path.
        collection_code = self.request.data.get("collection_code")
        # A thing lives in a collection from the moment it exists, and its owner
        # always has access to it: refused before any other check.
        if not collection_code:
            raise ValidationError({"collection_code": ["A thing is created in a collection."]})
        collection = (
            Collection.objects.filter(code=collection_code).first() if collection_code else None
        )

        # In a collection the server puts the verb: it follows the price. Only for
        # someone who may add to it — to anyone else the collection is not
        # answered for, so the verb refusal below never turns on its kind.
        if collection is not None and collection.can_add_thing(self.request.user.code):
            thing_type, mismatch = verb_from_price(
                collection,
                serializer.validated_data.get("fee"),
                serializer.validated_data.get("type"),
            )
            if mismatch:
                raise ValidationError({"type": mismatch})
            serializer.validated_data["type"] = thing_type
        else:
            thing_type = serializer.validated_data.get("type", Thing.Type.GIFT_THING)
        validate_deposit_for_type(thing_type, serializer.validated_data.get("deposit"))
        validate_units_for_type(thing_type, serializer.validated_data.get("units"))

        # Whether this deployment offers the verb at all. The one exception is a
        # member contributing an owner-allow-listed type to a COMMUNITY group
        # they were invited to (`community_contribution_types`). It is confirmed
        # positively against the resolved collection, so a refusal still never
        # turns on — or reveals — a collection that does not exist or that the
        # person has no standing in: both still fall through to the same 403,
        # before the 404/permission checks below run.
        denial = thing_type_denial(self.request.user, thing_type)
        if denial and thing_type not in community_contribution_types(collection, self.request.user):
            raise PermissionDenied(denial)

        if collection_code:
            if collection is None:
                raise NotFound("Collection not found")
            if not collection.can_add_thing(self.request.user.code):
                raise PermissionDenied(
                    "You do not have permission to add things to this collection"
                )

            # Type must be valid for the collection: its owner-defined allowlist,
            # and — for RESERVE — that it is a reservations collection at all.
            # Shared with update, so key it under "type" like perform_update.
            err = type_validity_error(thing_type, collection)
            if err:
                raise ValidationError({"type": err})

            # Mass-upload ceiling. Checked before the Thing row is created so a
            # refused add leaves nothing orphaned behind it.
            full = collection.capacity_violation("things", adding=1)
            if full:
                raise RefusedField("collection_code", full)

        # Tags must come from the collection's owner-defined vocabulary.
        tags = serializer.validated_data.get("tags", [])
        if tags:
            available = set(collection.tags) if collection else set()
            invalid = [t for t in tags if t not in available]
            if invalid:
                raise ValidationError(
                    {"tags": f"These tags are not defined by the collection: {invalid}"}
                )

        thing = Thing.objects.create(
            owner=self.request.user,
            **serializer.validated_data,
        )

        if collection:
            collection.things.add(thing)
            collection.note_capacity("things")

        Event.log(
            Event.Kind.THING_ADDED,
            actor=self.request.user,
            collection=collection,
            thing=thing,
        )

        # Store created thing for the create response
        self._created_thing = thing

    def perform_destroy(self, instance):
        # The THING_REMOVED event is written by the model's delete receiver; the
        # actor is whoever deleted it (collection owner or thing owner), not
        # necessarily the current owner. Whoever had a live request is emailed.
        delete_thing(instance, actor=self.request.user)

    def perform_update(self, serializer):
        # The type stays editable, but a PATCH can't move a thing to a type its
        # collection forbids — re-validate against every collection it's in.
        thing = serializer.instance
        collections = thing.collections_in_order()
        validated = serializer.validated_data
        # Its collection's kind and its price give the verb, and an edit that
        # touches either puts it back in step. A thing of the other family that a
        # mixed collection kept through the migration is left as it is.
        home = collections[0] if collections else None
        if (
            home is not None
            and thing.type in KIND_THING_TYPES[home.kind]
            and ("fee" in validated or "type" in validated)
        ):
            derived, mismatch = verb_from_price(
                home, validated.get("fee", thing.fee), validated.get("type")
            )
            if mismatch:
                raise ValidationError({"type": mismatch})
            validated["type"] = derived
        new_type = validated.get("type", thing.type)
        if new_type not in UNITS_TYPES:
            # A thing that is neither a reservation nor a loan or a rental has one
            # unit, whatever it had before.
            validated["units"] = 1
        if new_type != thing.type:
            # Only on a change: a thing already offered under a verb the policy
            # has since stopped handing out stays editable by its owner. The
            # gate is on creating that state, not on living in it — otherwise
            # narrowing a deployment would freeze the things people already own.
            # Same COMMUNITY-contribution exception as create: a member may
            # re-type their contribution into another verb their group's owner
            # allow-listed. Every collection the thing sits in has to allow it —
            # a thing also in the member's own collection is still them
            # initiating there.
            denial = thing_type_denial(self.request.user, new_type)
            contributing = bool(collections) and all(
                new_type in community_contribution_types(c, self.request.user) for c in collections
            )
            if denial and not contributing:
                raise PermissionDenied(denial)
            for collection in collections or [None]:
                err = type_validity_error(new_type, collection)
                if err:
                    raise ValidationError({"type": err})
        serializer.save()

    # Single-thing create is the one-by-one equivalent of the 10/h bulk endpoint;
    # cap it too so the bulk limit can't be bypassed into unbounded rows. Generous
    # enough for manual entry (the bulk endpoint is there for large batches).
    @method_decorator(ratelimit(key="user", rate="60/h", method="POST", block=True))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            ThingSerializer(self._created_thing, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, code=None):
        thing = self.get_object()
        if thing.status != Thing.Status.INACTIVE:
            return Response(
                refusal_body("Thing is not inactive.", code="thing_not_inactive"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        thing.status = Thing.Status.ACTIVE
        thing.save(update_fields=["status"])
        thing.deal.clear()
        return Response(ThingSerializer(thing, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="hide")
    def hide(self, request, code=None):
        # Manager-gated via IsThingManager (get_permissions) + get_object()'s
        # check_object_permissions — same as activate, instead of a hand-rolled
        # owner check with a bespoke 403 body.
        thing = self.get_object()
        if thing.status != Thing.Status.ACTIVE:
            return Response(
                refusal_body("Only active things can be hidden.", code="thing_not_active"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        # A rescue is hiding what you do not run but may rescue; a curator hiding
        # another curator's thing in a PROPRIETARY collection is just managing it.
        is_rescue = not thing.can_manage(request.user.code) and thing.can_rescue(request.user.code)
        thing.status = Thing.Status.INACTIVE
        thing.save(update_fields=["status"])
        if is_rescue:
            self._tell_owner_of_rescue(thing, request.user)
        return Response(ThingSerializer(thing, context=self.get_serializer_context()).data)

    @staticmethod
    def _tell_owner_of_rescue(thing, founder):
        """The founder of a network hid an entity's thing: its owner hears of it."""
        collection = next(
            (c for c in thing.collections_in_order() if c.can_rescue(founder.code)), None
        )
        InAppNotification.objects.create(
            user=thing.owner,
            type=InAppNotification.Type.THING_HIDDEN,
            payload={
                "thing_headline": thing.headline,
                "founder_name": founder.name,
                "thing_code": thing.code,
                "collection_code": collection.code if collection else "",
            },
        )
        send_thing_hidden_by_founder_email(
            thing,
            founder,
            collection.headline if collection else "",
            thing.owner.email,
            collection=collection,
        )


class ThingBulkCreateView(APIView):
    """
    POST /api/v1/collections/{collection_code}/things/bulk/

    Create many things in one atomic transaction from a CSV the client parsed and
    previewed (F-9). Either every row is created or none is. Free-text fields are
    guarded against spreadsheet-formula (CSV) injection, and the import is
    rate-limited per user. Only the owner (or a member who can add things) may
    import. Body: ``{"rows": [{type, headline, ...}, ...]}``.
    """

    permission_classes = [IsAuthenticated]
    MAX_ROWS = 100

    @method_decorator(ratelimit(key="user", rate="10/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)
        if not collection.can_add_thing(request.user.code):
            return Response(
                refusal_body(
                    "You do not have permission to add things to this collection.",
                    code="cannot_add_things",
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        rows = request.data.get("rows") if isinstance(request.data, dict) else None
        if not isinstance(rows, list) or not rows:
            return Response(
                refusal_body("No rows to import.", code="no_rows_to_import"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(rows) > self.MAX_ROWS:
            return Response(
                refusal_body(
                    f"At most {self.MAX_ROWS} rows can be imported at once.",
                    code="too_many_rows",
                    max=self.MAX_ROWS,
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate every row first; report all failures by row index and create
        # nothing unless the whole batch is valid (all-or-nothing).
        validated = []
        errors = []
        # Resolved once for the batch, not once per row. What a deployment lets
        # someone offer is a fact about the person, not about the line of CSV
        # they are on, so re-asking per row buys nothing — and a policy that
        # reaches the database (the kind this setting exists for) would run one
        # query per row, up to MAX_ROWS of them, on an endpoint whose whole
        # point is importing a hundred things at once.
        capabilities = capabilities_for(request.user)
        # Verbs the (vetted) owner has opened this COMMUNITY group to: the
        # deployment's own policy steps aside for those, exactly as on the
        # single-create path. Resolved once for the batch — it turns on
        # (this user, this collection), never on the row.
        community_free = community_contribution_types(collection, request.user)
        for index, row in enumerate(rows):
            serializer = ThingBulkRowSerializer(data=row)
            if not serializer.is_valid():
                errors.append({"row": index, "errors": serializer.errors})
                continue
            thing_type, mismatch = verb_from_price(
                collection,
                serializer.validated_data.get("fee"),
                serializer.validated_data.get("type"),
            )
            if mismatch:
                errors.append({"row": index, "errors": {"type": [mismatch]}})
                continue
            serializer.validated_data["type"] = thing_type
            try:
                validate_deposit_for_type(thing_type, serializer.validated_data.get("deposit"))
            except ValidationError as exc:
                errors.append({"row": index, "errors": exc.detail})
                continue
            # The deployment's own gate, checked per row because the verb is per
            # row. Reported as a row error rather than a 403 for the batch: this
            # endpoint's contract is that one response names every bad row, and
            # an importer who used a withheld verb in row 40 of 100 needs to be
            # told which rows to fix, not just that something was refused.
            if thing_type not in community_free:
                row_denial = thing_type_denial(request.user, thing_type, capabilities=capabilities)
                if row_denial:
                    errors.append({"row": index, "errors": {"type": [row_denial]}})
                    continue
            type_error = type_validity_error(thing_type, collection)
            if type_error:
                errors.append({"row": index, "errors": {"type": [type_error]}})
                continue
            # Tags must belong to the collection's vocabulary (mirrors the
            # single-create subset check in ThingViewSet.perform_create), but
            # a CSV tag may also name a localized entry by any of its
            # languages — resolved to the vocabulary's canonical string.
            tags = serializer.validated_data.get("tags", [])
            if tags:
                resolved, unknown, ambiguous = _resolve_tag_aliases(tags, collection.tags)
                if unknown:
                    errors.append(
                        {
                            "row": index,
                            "errors": {
                                "tags": [f"These tags are not defined by the collection: {unknown}"]
                            },
                        }
                    )
                    continue
                if ambiguous:
                    errors.append(
                        {
                            "row": index,
                            "errors": {
                                "tags": [
                                    "These tags match more than one entry in the collection's "
                                    f"vocabulary — use the exact label: {ambiguous}"
                                ]
                            },
                        }
                    )
                    continue
                serializer.validated_data["tags"] = resolved
            validated.append(serializer.validated_data)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        # Mass-upload ceiling, checked against the WHOLE batch: the point of the
        # guard is that a bulk import cannot step over the line 100 rows at a
        # time. All-or-nothing, like every other failure on this endpoint.
        full = collection.capacity_violation("things", adding=len(validated))
        if full:
            return Response(refusal_body(full), status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Re-check under a row lock. The count above was read outside the
            # transaction, so two batches arriving together could each have seen
            # room for themselves and landed 200 rows through a ceiling of 100 —
            # the one place the drift is worth paying for, since a single request
            # here carries up to MAX_ROWS. Locking the collection row serialises
            # the two, and the loser re-counts with the winner's rows included.
            # The single-add paths accept a drift of at most one row per racing
            # request and take no lock; a ceiling this coarse doesn't earn
            # serialising every add to a busy COMMUNITY collection. None of it
            # runs when no ceiling is set — the standalone default.
            if collection.capacity_ceiling("things"):
                locked = Collection.objects.select_for_update().get(code=collection.code)
                full = locked.capacity_violation("things", adding=len(validated))
                if full:
                    return Response(refusal_body(full), status=status.HTTP_400_BAD_REQUEST)
            created = [Thing.objects.create(owner=request.user, **data) for data in validated]
            collection.things.add(*created)
            for thing in created:
                Event.log(
                    Event.Kind.THING_ADDED,
                    actor=request.user,
                    collection=collection,
                    thing=thing,
                )

        # After the commit: the alarm reports the real count, and a failing
        # alarm can never roll back a good import.
        collection.note_capacity("things")

        return Response(
            {"created": len(created), "codes": [thing.code for thing in created]},
            status=status.HTTP_201_CREATED,
        )
