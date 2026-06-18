"""
Thing views for OIUEEI.
"""

from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import Collection, Thing
from core.models.booking import BookingPeriod
from core.models.notification import InAppNotification
from core.pagination import StandardResultsPagination
from core.permissions import IsThingOwner
from core.serializers import ThingCreateSerializer, ThingSerializer, ThingUpdateSerializer
from core.services.email_service import send_wish_posted_email
from core.views._helpers import type_validity_error


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
        return [IsAuthenticated()]

    def _can_delete(self, thing, user_code):
        """Collection owner always; thing owner only if no transfers have occurred."""
        if thing.collections.filter(owner_id=user_code).exists():
            return True
        return thing.is_owner(user_code) and not thing.transfers.exists()

    def get_object(self):
        obj = get_object_or_404(Thing, code=self.kwargs[self.lookup_field])
        if self.action == "retrieve":
            if not obj.can_view(self.request.user.code):
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
            # share/album restrictions, per-collection allowlist) — shared with update.
            err = type_validity_error(thing_type, collection)
            if err:
                self._create_error = err
                return
            # Minimalist collections additionally require a photo (create-time only).
            if collection.is_minimalist and not serializer.validated_data.get("thumbnail"):
                self._create_error = "A photo is required for things in minimalist collections"
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
            ThingSerializer(self._created_thing).data,
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
        return Response(ThingSerializer(thing).data)

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
        return Response(ThingSerializer(thing).data)


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
