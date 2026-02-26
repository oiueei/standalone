"""
Thing views for OIUEEI.
"""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import Collection, Thing
from core.models.booking import BookingPeriod
from core.pagination import StandardResultsPagination
from core.permissions import IsThingOwner
from core.serializers import ThingCreateSerializer, ThingSerializer, ThingUpdateSerializer


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
            .prefetch_related(
                "collections",
                "faq_set",
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
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsThingOwner()]
        return [IsAuthenticated()]

    def get_object(self):
        obj = get_object_or_404(Thing, code=self.kwargs[self.lookup_field])
        if self.action == "retrieve":
            if not obj.can_view(self.request.user.code):
                self.permission_denied(self.request)
        else:
            self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        thing = Thing.objects.create(
            owner=self.request.user,
            **serializer.validated_data,
        )

        collection_code = self.request.data.get("collection_code")
        if collection_code:
            try:
                collection = Collection.objects.get(code=collection_code)
                if collection.is_owner(self.request.user.code):
                    collection.things.add(thing)
            except Collection.DoesNotExist:
                pass

        # Store created thing for create response
        self._created_thing = thing

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            ThingSerializer(self._created_thing).data,
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
            Thing.objects.filter(collections__invites=self.request.user, available=True)
            .select_related("owner")
            .prefetch_related(
                "collections",
                "faq_set",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status="PENDING"),
                    to_attr="_pending_bookings",
                ),
            )
            .distinct()
            .order_by("-created")
        )
