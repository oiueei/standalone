"""
Thing views for OIUEEI.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Collection, Thing
from core.serializers import ThingCreateSerializer, ThingSerializer, ThingUpdateSerializer


class ThingListView(APIView):
    """
    GET /api/v1/things/
    List user's own things.

    POST /api/v1/things/
    Create a new thing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        things = Thing.objects.filter(owner=request.user)
        serializer = ThingSerializer(things, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ThingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thing = Thing.objects.create(
            owner=request.user,
            **serializer.validated_data,
        )

        # If collection_code is provided, add to collection
        collection_code = request.data.get("collection_code")
        if collection_code:
            try:
                collection = Collection.objects.get(code=collection_code)
                if collection.is_owner(request.user.code):
                    collection.things.add(thing)
            except Collection.DoesNotExist:
                pass

        return Response(
            ThingSerializer(thing).data,
            status=status.HTTP_201_CREATED,
        )


class ThingDetailView(APIView):
    """
    GET /api/v1/things/{thing_code}/
    View a thing.

    PUT /api/v1/things/{thing_code}/
    Update a thing (owner only).

    DELETE /api/v1/things/{thing_code}/
    Delete a thing (owner only).
    """

    permission_classes = [IsAuthenticated]

    def get_thing(self, thing_code):
        return get_object_or_404(Thing, code=thing_code)

    def get(self, request, thing_code):
        thing = self.get_thing(thing_code)

        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to view this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ThingSerializer(thing)
        return Response(serializer.data)

    def put(self, request, thing_code):
        thing = self.get_thing(thing_code)

        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can update this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ThingUpdateSerializer(thing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ThingSerializer(thing).data)

    def delete(self, request, thing_code):
        thing = self.get_thing(thing_code)

        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "Only the owner can delete this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        thing.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitedThingsView(APIView):
    """
    GET /api/v1/invited-things/
    List things from collections where the current user is invited.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        things = Thing.objects.filter(collections__invites=request.user, available=True).distinct()
        serializer = ThingSerializer(things, many=True)
        return Response(serializer.data)
