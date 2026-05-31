"""
Thing views for OIUEEI.
"""

from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import Collection, Thing
from core.models.booking import BookingPeriod
from core.pagination import StandardResultsPagination
from core.permissions import IsThingOwner
from core.serializers import ThingCreateSerializer, ThingSerializer, ThingUpdateSerializer
from core.services.email_service import send_event_announcement_email


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
                "deal",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status="PENDING"),
                    to_attr="_pending_bookings",
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

        thing_type = serializer.validated_data.get("type", "GIFT_THING")

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

            # WISH_THING, SHARE_THING, and ASSET_THING are only allowed in COMMUNITY collections
            if (
                thing_type in ("WISH_THING", "SHARE_THING", "ASSET_THING")
                and not collection.is_community()
            ):
                self._create_error = (
                    f"{thing_type.replace('_', ' ').title()}s can only be created"
                    " in community collections"
                )
                return

            # Swap collection: only SWAP_THING allowed
            if collection.is_swap and thing_type != "SWAP_THING":
                self._create_error = "Only swap things can be added to a swap collection"
                return

            # SWAP_THING requires a swap collection
            if thing_type == "SWAP_THING" and not collection.is_swap:
                self._create_error = "Swap things can only be created in swap collections"
                return

            # Share collection: only SHARE_THING allowed
            if collection.is_share and thing_type != "SHARE_THING":
                self._create_error = "Only share things can be added to a share collection"
                return

            # Minimalist collection: only GIFT/SHARE/SWAP allowed, thumbnail required
            if collection.is_minimalist:
                allowed = ("GIFT_THING", "SHARE_THING", "SWAP_THING")
                if thing_type not in allowed:
                    self._create_error = (
                        "Only gift, share, and swap things can be added"
                        " to a minimalist collection"
                    )
                    return
                if not serializer.validated_data.get("thumbnail"):
                    self._create_error = "A photo is required for things in minimalist collections"
                    return

            # Per-collection allowlist (set on creation/edit). Empty list means
            # "no restriction", typically the case for COMMUNITY collections in
            # v1 — the multi-select UI is wired only for PROPRIETARY for now.
            if collection.allowed_thing_types and thing_type not in collection.allowed_thing_types:
                self._create_error = (
                    f"This collection does not accept {thing_type.replace('_', ' ').title()}s."
                    " The owner has restricted it to specific types."
                )
                return
        else:
            # WISH_THING, SHARE_THING, and SWAP_THING require specific collections
            if thing_type in ("WISH_THING", "SHARE_THING"):
                self._create_error = (
                    f"{thing_type.replace('_', ' ').title()}s can only be created"
                    " in community collections"
                )
                return
            if thing_type == "SWAP_THING":
                self._create_error = "Swap things can only be created in swap collections"
                return

        thing = Thing.objects.create(
            owner=self.request.user,
            **serializer.validated_data,
        )

        if collection:
            collection.things.add(thing)

            # Send announcement email for EVENT_THING
            if thing.type == "EVENT_THING":
                invitee_emails = list(
                    collection.invites.exclude(code=self.request.user.code).values_list(
                        "email", flat=True
                    )
                )
                if invitee_emails:
                    owner_name = self.request.user.name or self.request.user.email
                    send_event_announcement_email(
                        owner_name,
                        thing.headline,
                        thing.event_date,
                        collection.headline,
                        invitee_emails,
                    )

        # Store created thing for create response
        self._created_thing = thing
        self._create_error = None

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
        if thing.status != "INACTIVE":
            return Response({"error": "Thing is not inactive."}, status=status.HTTP_400_BAD_REQUEST)
        thing.status = "ACTIVE"
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
        if thing.status != "ACTIVE":
            return Response(
                {"error": "Only active things can be hidden."}, status=status.HTTP_400_BAD_REQUEST
            )
        thing.status = "INACTIVE"
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
                collections__status="ACTIVE",
            )
            .exclude(status="INACTIVE")
            .select_related("owner")
            .annotate(_transfer_count=Count("transfers", distinct=True))
            .prefetch_related(
                "collections",
                "faq_set",
                "deal",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status="PENDING"),
                    to_attr="_pending_bookings",
                ),
            )
            .distinct()
            .order_by("-created")
        )
