"""
Thing views for OIUEEI.
"""

from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.models import Collection, Thing
from core.models.booking import BookingPeriod
from core.models.notification import InAppNotification
from core.pagination import StandardResultsPagination
from core.permissions import IsThingOwner
from core.serializers import (
    ThingBulkRowSerializer,
    ThingCreateSerializer,
    ThingSerializer,
    ThingUpdateSerializer,
)
from core.services.email_service import send_wish_posted_email
from core.utils import signed_document_url, verify_document_token
from core.views._helpers import type_validity_error, viewer_code


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
        return (
            Thing.objects.filter(owner=self.request.user)
            .select_related("owner")
            .annotate(_transfer_count=Count("transfers", distinct=True))
            .prefetch_related(
                "collections",
                "faq_set",
                "responses",
                "deal",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status=BookingPeriod.Status.PENDING),
                    to_attr="_pending_bookings",
                ),
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(
                        status__in=[
                            BookingPeriod.Status.PENDING,
                            BookingPeriod.Status.ACCEPTED,
                        ]
                    ).order_by("start_date"),
                    to_attr="_blocked_periods",
                ),
            )
            .order_by("-created")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ThingCreateSerializer
        if self.action in ("update", "partial_update"):
            return ThingUpdateSerializer
        return ThingSerializer

    def get_permissions(self):
        if self.action in ("update", "partial_update", "activate"):
            return [IsAuthenticated(), IsThingOwner()]
        # Anonymous read for retrieve; can_view() still gates it (a thing is only
        # visible without membership when it sits in a PUBLIC, ACTIVE collection).
        if self.action == "retrieve":
            return [AllowAny()]
        return [IsAuthenticated()]

    def _can_delete(self, thing, user_code):
        """Collection owner always; thing owner only if no transfers have occurred."""
        if thing.collections.filter(owner_id=user_code).exists():
            return True
        return thing.is_owner(user_code) and not thing.transfers.exists()

    def get_object(self):
        obj = get_object_or_404(Thing, code=self.kwargs[self.lookup_field])
        if self.action == "retrieve":
            if not obj.can_view(viewer_code(self.request)):
                self.permission_denied(self.request)
        elif self.action == "destroy":
            if not self._can_delete(obj, self.request.user.code):
                self.permission_denied(self.request)
        else:
            self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        collection_code = self.request.data.get("collection_code")
        collection = None

        thing_type = serializer.validated_data.get("type", Thing.Type.GIFT_THING)

        if collection_code:
            try:
                collection = Collection.objects.get(code=collection_code)
                if not collection.can_add_thing(self.request.user.code):
                    self._create_error = (
                        "You do not have permission to add things to this collection"
                    )
                    return
            except Collection.DoesNotExist:
                self._create_error = "Collection not found"
                return

            # Type must be valid for the collection (community-only types, swap/
            # share restrictions, per-collection allowlist) — shared with update.
            err = type_validity_error(thing_type, collection)
            if err:
                self._create_error = err
                return
        else:
            # No collection: WISH/SHARE/SWAP require a specific collection.
            err = type_validity_error(thing_type, None)
            if err:
                self._create_error = err
                return

        # Tags must come from the collection's owner-defined vocabulary.
        tags = serializer.validated_data.get("tags", [])
        if tags:
            available = set(collection.tags) if collection else set()
            invalid = [t for t in tags if t not in available]
            if invalid:
                self._create_error = f"These tags are not defined by the collection: {invalid}"
                return

        thing = Thing.objects.create(
            owner=self.request.user,
            **serializer.validated_data,
        )

        if collection:
            collection.things.add(thing)
            if thing.type == Thing.Type.WISH_THING and self._wants_group_notice():
                self._broadcast_new_wish(thing, collection)

        # Store created thing for create response
        self._created_thing = thing
        self._create_error = None

    def perform_update(self, serializer):
        # The type stays editable, but a PATCH can't move a thing to a type its
        # collection forbids — re-validate against every collection it's in (L4).
        thing = serializer.instance
        new_type = serializer.validated_data.get("type", thing.type)
        if new_type != thing.type:
            for collection in list(thing.collections.all()) or [None]:
                err = type_validity_error(new_type, collection)
                if err:
                    raise ValidationError({"type": err})
        serializer.save()

    def _wants_group_notice(self):
        """Whether to broadcast a new wish to the group ('Avisar al grupo')."""
        raw = self.request.data.get("notify_group", True)
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() not in ("false", "0", "")

    def _broadcast_new_wish(self, wish, collection):
        """Notify every group member (except the creator) about a new wish."""
        # Dedupe by code: the owner may also appear in the invites M2M.
        by_code = {m.code: m for m in collection.invites.all()}
        by_code[collection.owner_id] = collection.owner
        members = [m for code, m in by_code.items() if code != self.request.user.code]
        if not members:
            return

        creator_name = self.request.user.display_name
        send_wish_posted_email(creator_name, wish, [m.email for m in members])
        InAppNotification.objects.bulk_create(
            [
                InAppNotification(
                    user=member,
                    type=InAppNotification.Type.WISH_POSTED,
                    payload={
                        "wish_headline": wish.headline,
                        "creator_name": creator_name,
                        "wish_code": wish.code,
                        "collection_code": collection.code,
                    },
                )
                for member in members
            ]
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        if getattr(self, "_create_error", None):
            return Response(
                {"error": self._create_error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            ThingSerializer(self._created_thing, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, code=None):
        thing = self.get_object()
        if thing.status != Thing.Status.INACTIVE:
            return Response({"error": "Thing is not inactive."}, status=status.HTTP_400_BAD_REQUEST)
        thing.status = Thing.Status.ACTIVE
        thing.save(update_fields=["status"])
        thing.deal.clear()
        return Response(ThingSerializer(thing, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="hide")
    def hide(self, request, code=None):
        thing = get_object_or_404(Thing, code=code)
        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "You do not have permission to hide this thing."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if thing.status != Thing.Status.ACTIVE:
            return Response(
                {"error": "Only active things can be hidden."}, status=status.HTTP_400_BAD_REQUEST
            )
        thing.status = Thing.Status.INACTIVE
        thing.save(update_fields=["status"])
        return Response(ThingSerializer(thing, context=self.get_serializer_context()).data)


class DocumentDownloadView(APIView):
    """
    GET /api/v1/things/{thing_code}/documents/{index}/download/

    Redirect a viewer to a short-lived signed Cloudinary URL for the thing's Nth
    document. Documents are uploaded privately (``type=authenticated``), so this
    authorisation-gated endpoint is the only way to obtain a working URL, and the
    URL it mints expires — it can't be bookmarked, shared, or leaked for long.

    Access is granted to (a) a signed-in user who can view the thing — the same
    audience as the serialised ``document_urls``; or (b) the bearer of a valid
    ``?token=`` for this thing, so the download links in the booking-acceptance
    email work for a recipient who isn't logged in (L9). The token is scoped to
    the thing and expires after ~30 days.
    """

    permission_classes = [AllowAny]

    def get(self, request, thing_code, index):
        token_ok = verify_document_token(request.query_params.get("token")) == thing_code
        user = request.user
        # Refuse an anonymous, tokenless caller before the lookup, so a 404-vs-403
        # can't be used to probe which thing codes exist (this is an AllowAny view).
        if not token_ok and not user.is_authenticated:
            return Response(
                {"error": "You do not have permission to view this document."},
                status=status.HTTP_403_FORBIDDEN,
            )
        thing = get_object_or_404(Thing, code=thing_code)
        if not token_ok and not thing.can_view(user.code):
            return Response(
                {"error": "You do not have permission to view this document."},
                status=status.HTTP_403_FORBIDDEN,
            )
        documents = thing.documents or []
        if index < 0 or index >= len(documents):
            raise Http404("Document not found.")
        url = signed_document_url(documents[index])
        if not url:
            raise Http404("Document not found.")
        return HttpResponseRedirect(url)


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
                {"error": "You do not have permission to add things to this collection."},
                status=status.HTTP_403_FORBIDDEN,
            )

        rows = request.data.get("rows") if isinstance(request.data, dict) else None
        if not isinstance(rows, list) or not rows:
            return Response({"error": "No rows to import."}, status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > self.MAX_ROWS:
            return Response(
                {"error": f"At most {self.MAX_ROWS} rows can be imported at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate every row first; report all failures by row index and create
        # nothing unless the whole batch is valid (all-or-nothing).
        validated = []
        errors = []
        for index, row in enumerate(rows):
            serializer = ThingBulkRowSerializer(data=row)
            if not serializer.is_valid():
                errors.append({"row": index, "errors": serializer.errors})
                continue
            thing_type = serializer.validated_data.get("type", Thing.Type.GIFT_THING)
            type_error = type_validity_error(thing_type, collection)
            if type_error:
                errors.append({"row": index, "errors": {"type": [type_error]}})
                continue
            # Tags must belong to the collection's vocabulary (mirrors the
            # single-create subset check in ThingViewSet.perform_create).
            tags = serializer.validated_data.get("tags", [])
            if tags:
                available = set(collection.tags or [])
                invalid = [tag for tag in tags if tag not in available]
                if invalid:
                    errors.append(
                        {
                            "row": index,
                            "errors": {
                                "tags": [f"These tags are not defined by the collection: {invalid}"]
                            },
                        }
                    )
                    continue
            validated.append(serializer.validated_data)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            created = [Thing.objects.create(owner=request.user, **data) for data in validated]
            collection.things.add(*created)

        return Response(
            {"created": len(created), "codes": [thing.code for thing in created]},
            status=status.HTTP_201_CREATED,
        )


class InvitedThingsView(ListAPIView):
    """
    GET /api/v1/invited-things/
    List things from collections where the current user is invited.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ThingSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return (
            Thing.objects.filter(
                collections__invites=self.request.user,
                collections__status=Collection.Status.ACTIVE,
            )
            .exclude(status=Thing.Status.INACTIVE)
            .select_related("owner")
            .annotate(_transfer_count=Count("transfers", distinct=True))
            .prefetch_related(
                "collections",
                "faq_set",
                "responses",
                "deal",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status=BookingPeriod.Status.PENDING),
                    to_attr="_pending_bookings",
                ),
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(
                        status__in=[
                            BookingPeriod.Status.PENDING,
                            BookingPeriod.Status.ACCEPTED,
                        ]
                    ).order_by("start_date"),
                    to_attr="_blocked_periods",
                ),
            )
            .distinct()
            .order_by("-created")
        )
