"""
Collection views for OIUEEI.
"""

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import RSVP, Collection, Theeeme, Thing, User
from core.serializers import (
    CollectionAddThingSerializer,
    CollectionCreateSerializer,
    CollectionInviteSerializer,
    CollectionRemoveInviteSerializer,
    CollectionSerializer,
    CollectionUpdateSerializer,
)


class CollectionListView(APIView):
    """
    GET /api/v1/collections/
    List user's own collections.

    POST /api/v1/collections/
    Create a new collection.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        collections = Collection.objects.filter(owner=request.user)
        serializer = CollectionSerializer(collections, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CollectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use default theeeme if not provided
        validated_data = serializer.validated_data
        if "theeeme" not in validated_data:
            default_theeeme = Theeeme.objects.filter(code="JMPA01").first()
            if default_theeeme:
                validated_data["theeeme"] = default_theeeme

        collection = Collection.objects.create(
            owner=request.user,
            **validated_data,
        )

        return Response(
            CollectionSerializer(collection).data,
            status=status.HTTP_201_CREATED,
        )


class CollectionDetailView(APIView):
    """
    GET /api/v1/collections/{collection_code}/
    View a collection.

    POST /api/v1/collections/{collection_code}/
    Add a thing to a collection (owner only).

    PUT /api/v1/collections/{collection_code}/
    Update a collection (owner only).

    DELETE /api/v1/collections/{collection_code}/
    Delete a collection (owner only).
    """

    permission_classes = [IsAuthenticated]

    def get_collection(self, collection_code):
        try:
            return Collection.objects.get(code=collection_code)
        except Collection.DoesNotExist:
            return None

    def get(self, request, collection_code):
        collection = self.get_collection(collection_code)
        if not collection:
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not collection.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to view this collection"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionSerializer(collection)
        return Response(serializer.data)

    def post(self, request, collection_code):
        """Add a thing to the collection."""
        collection = self.get_collection(collection_code)
        if not collection:
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not collection.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can add things to this collection"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionAddThingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thing_code = serializer.validated_data["thing_code"]

        try:
            thing = Thing.objects.get(code=thing_code)
        except Thing.DoesNotExist:
            return Response(
                {"error": "Thing not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

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
                "collection": CollectionSerializer(collection).data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, collection_code):
        collection = self.get_collection(collection_code)
        if not collection:
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not collection.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can update this collection"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionUpdateSerializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(CollectionSerializer(collection).data)

    def delete(self, request, collection_code):
        collection = self.get_collection(collection_code)
        if not collection:
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not collection.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can delete this collection"},
                status=status.HTTP_403_FORBIDDEN,
            )

        collection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CollectionInviteView(APIView):
    """
    POST /api/v1/collections/{collection_code}/invite/
    Invite a user to a collection.

    DELETE /api/v1/collections/{collection_code}/invite/
    Remove a user from the collection's invite list.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, collection_code):
        try:
            collection = Collection.objects.get(code=collection_code)
        except Collection.DoesNotExist:
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

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

        # Create RSVP with collection_code (invitation pending acceptance)
        rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=email,
            action="COLLECTION_INVITE",
            collection_code=collection_code,
        )

        # Send invitation email with specific RSVP link
        magic_link_base = getattr(
            settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/magic-link"
        )
        invite_link = f"{magic_link_base}/{rsvp.code}"

        send_mail(
            subject=f"{request.user.name or 'Someone'} te ha invitado a una colección",
            message=f"Has sido invitado a ver: {collection.headline}. "
            f"Accede aquí: {invite_link}",
            from_email=None,
            recipient_list=[email],
            html_message=f"""
            <html>
            <p>{request.user.name or 'Someone'} te ha invitado a ver:</p>
            <p><strong>{collection.headline}</strong></p>
            <p><a href="{invite_link}">Aceptar invitación</a></p>
            </html>
            """,
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
        try:
            collection = Collection.objects.get(code=collection_code)
        except Collection.DoesNotExist:
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not collection.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can remove invites"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionRemoveInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_code = serializer.validated_data["user_code"]

        if not collection.invites.filter(code=user_code).exists():
            return Response(
                {"error": "User is not invited to this collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Remove from invites
        collection.invites.remove(collection.invites.get(code=user_code))

        # Send notification email to removed user
        try:
            user = User.objects.get(code=user_code)
            owner_name = request.user.name or request.user.email
            send_mail(
                subject=f"Tu acceso a '{collection.headline}' ha sido revocado",
                message=f"{owner_name} ha revocado tu acceso a la colección "
                f"'{collection.headline}'.",
                from_email=None,
                recipient_list=[user.email],
                html_message=f"""
                <html>
                <p>{owner_name} ha revocado tu acceso a:</p>
                <p><strong>{collection.headline}</strong></p>
                <p>Ya no podrás ver el contenido de esta colección.</p>
                </html>
                """,
            )
        except User.DoesNotExist:
            pass

        return Response(
            {
                "message": "User removed from collection",
                "user_code": user_code,
            },
            status=status.HTTP_200_OK,
        )


class InvitedCollectionsView(APIView):
    """
    GET /api/v1/invited-collections/
    List collections where the current user is in invites.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        invited_collections = request.user.invited_to_collections.all()
        serializer = CollectionSerializer(invited_collections, many=True)
        return Response(serializer.data)
