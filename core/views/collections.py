"""
Collection views for OIUEEI.
"""

from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.models import RSVP, Collection, Thing, User
from core.models.booking import BookingPeriod
from core.permissions import IsCollectionOwner
from core.serializers import (
    CollectionAddThingSerializer,
    CollectionCreateSerializer,
    CollectionInviteSerializer,
    CollectionRemoveInviteSerializer,
    CollectionRemoveThingSerializer,
    CollectionSerializer,
    CollectionUpdateSerializer,
)
from core.services.email_service import send_collection_invite_email, send_collection_revoke_email


def _optimise_collection_queryset(queryset):
    """Add select/prefetch_related for nested serializer access on collections."""
    return queryset.select_related("owner").prefetch_related(
        "invites",
        Prefetch(
            "things",
            queryset=Thing.objects.select_related("owner").prefetch_related(
                "faq_set",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status="PENDING"),
                    to_attr="_pending_bookings",
                ),
            ),
        ),
    )


class CollectionViewSet(ModelViewSet):
    """
    ViewSet for Collection CRUD operations.

    list:    GET /api/v1/collections/
    create:  POST /api/v1/collections/
    retrieve: GET /api/v1/collections/{code}/
    update:  PUT /api/v1/collections/{code}/
    destroy: DELETE /api/v1/collections/{code}/
    add_thing: POST /api/v1/collections/{code}/add-thing/
    """

    lookup_field = "code"

    def get_queryset(self):
        qs = Collection.objects.filter(owner=self.request.user).order_by("-created")
        if self.action in ("list", "retrieve"):
            return _optimise_collection_queryset(qs)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return CollectionCreateSerializer
        if self.action in ("update", "partial_update"):
            return CollectionUpdateSerializer
        if self.action == "add_thing":
            return CollectionAddThingSerializer
        return CollectionSerializer

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy", "add_thing", "remove_thing"):
            return [IsAuthenticated(), IsCollectionOwner()]
        return [IsAuthenticated()]

    def get_object(self):
        obj = get_object_or_404(Collection, code=self.kwargs[self.lookup_field])
        if self.action == "retrieve":
            if not obj.can_view(self.request.user.code):
                self.permission_denied(self.request)
        else:
            self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        validated_data = serializer.validated_data
        collection = Collection.objects.create(
            owner=self.request.user,
            **validated_data,
        )
        self._created_collection = collection

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            CollectionSerializer(self._created_collection, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="add-thing")
    def add_thing(self, request, code=None):
        """Add a thing to the collection."""
        collection = self.get_object()

        serializer = CollectionAddThingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thing_code = serializer.validated_data["thing_code"]
        thing = get_object_or_404(Thing, code=thing_code)

        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "You can only add your own things to collections"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if collection.things.filter(code=thing_code).exists():
            return Response(
                {"error": "Thing is already in this collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        collection.things.add(thing)

        return Response(
            {
                "message": "Thing added to collection",
                "collection": CollectionSerializer(collection, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-thing")
    def remove_thing(self, request, code=None):
        """Remove a thing from the collection (without deleting it)."""
        collection = self.get_object()

        serializer = CollectionRemoveThingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thing_code = serializer.validated_data["thing_code"]

        if not collection.things.filter(code=thing_code).exists():
            return Response(
                {"error": "Thing is not in this collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        collection.things.remove(collection.things.get(code=thing_code))

        return Response(
            {
                "message": "Thing removed from collection",
                "collection": CollectionSerializer(collection, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class CollectionInviteView(APIView):
    """
    POST /api/v1/collections/{collection_code}/invite/
    Invite a user to a collection.

    DELETE /api/v1/collections/{collection_code}/invite/
    Remove a user from the collection's invite list.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        if not collection.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can invite users"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()

        # Get or create user to invite
        invited_user, created = User.objects.get_or_create(
            email=email,
            defaults={"email": email},
        )

        if collection.is_invited(invited_user.code):
            return Response(
                {"detail": "This user is already invited to this collection."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete any old pending RSVPs for this user+collection (allows resend)
        RSVP.objects.filter(
            user_code=invited_user,
            target_code=collection_code,
            action__in=["COLLECTION_INVITE", "COLLECTION_REJECT"],
        ).delete()

        # Create RSVPs for accept and reject actions
        accept_rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=email,
            action="COLLECTION_INVITE",
            target_code=collection_code,
        )
        reject_rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=email,
            action="COLLECTION_REJECT",
            target_code=collection_code,
        )

        # Send invitation email with accept and reject links
        rsvp_base = getattr(settings, "RSVP_BASE_URL", "http://localhost:3000/rsvp")
        accept_link = f"{rsvp_base}/{accept_rsvp.code}"
        reject_link = f"{rsvp_base}/{reject_rsvp.code}"

        send_collection_invite_email(
            request.user.name or request.user.email,
            collection.headline,
            email,
            accept_link,
            reject_link,
        )

        return Response(
            {
                "message": "Invitation sent",
                "email": email,
                "user_code": invited_user.code,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        if not collection.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can remove invites"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionRemoveInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_code = serializer.validated_data["user_code"]

        # Check if user is a confirmed invite
        try:
            invited_user = collection.invites.get(code=user_code)
        except User.DoesNotExist:
            invited_user = None

        if invited_user:
            collection.invites.remove(invited_user)

            # Send notification email to removed user
            try:
                user = User.objects.get(code=user_code)
                owner_name = request.user.name or request.user.email
                send_collection_revoke_email(owner_name, collection.headline, user.email)
            except User.DoesNotExist:
                pass

            return Response(
                {
                    "message": "User removed from collection",
                    "user_code": user_code,
                },
                status=status.HTTP_200_OK,
            )

        # Check if user has a pending invite (RSVP)
        pending_rsvps = RSVP.objects.filter(
            user_code_id=user_code,
            target_code=collection_code,
            action__in=["COLLECTION_INVITE", "COLLECTION_REJECT"],
        )
        if pending_rsvps.exists():
            pending_rsvps.delete()
            return Response(
                {
                    "message": "Pending invitation cancelled",
                    "user_code": user_code,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "User is not invited to this collection"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class InvitedCollectionsView(APIView):
    """
    GET /api/v1/invited-collections/
    List collections where the current user is in invites.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        invited_collections = _optimise_collection_queryset(
            request.user.invited_to_collections.filter(status="ACTIVE")
        )
        serializer = CollectionSerializer(
            invited_collections, many=True, context={"request": request}
        )
        return Response(serializer.data)


class MyPendingInvitationsView(APIView):
    """
    GET /api/v1/my-invitations/
    List pending (not yet accepted) collection invitations for the current user.
    Returns accept + reject RSVP codes, collection headline and owner name.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        accept_rsvps = (
            RSVP.objects.filter(user_code=request.user, action="COLLECTION_INVITE")
            .select_related("user_code")
        )

        result = []
        for accept_rsvp in accept_rsvps:
            try:
                collection = Collection.objects.select_related("owner").get(
                    code=accept_rsvp.target_code
                )
            except Collection.DoesNotExist:
                continue

            reject_rsvp = RSVP.objects.filter(
                user_code=request.user,
                action="COLLECTION_REJECT",
                target_code=accept_rsvp.target_code,
            ).first()

            result.append({
                "accept_code": accept_rsvp.code,
                "reject_code": reject_rsvp.code if reject_rsvp else None,
                "collection_code": collection.code,
                "collection_headline": collection.headline,
                "owner_name": collection.owner.name or collection.owner.email,
            })

        return Response(result)
