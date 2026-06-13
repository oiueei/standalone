"""
Wish views for OIUEEI.

A wish is a ``Thing`` of type WISH_THING. Members answer it with structured
``WishResponse`` objects (have-this / know-where / can-make) instead of a
reservation. The creator sees every answer, accepts one, and marks the wish
resolved (which hides the underlying Thing so it leaves the active board).
"""

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing, WishResponse
from core.models.notification import InAppNotification
from core.pagination import StandardResultsPagination
from core.serializers import WishResponseCreateSerializer, WishResponseSerializer
from core.serializers.thing import ThingSerializer
from core.services.email_service import send_wish_response_email, send_wish_thanks_email


def _get_wish(thing_code):
    """Fetch a Thing and confirm it is a wish, else (thing, error_response)."""
    thing = get_object_or_404(Thing, code=thing_code)
    if thing.type != Thing.Type.WISH_THING:
        return thing, Response(
            {"error": "This endpoint is only for wishes"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return thing, None


class ThingWishResponseView(APIView):
    """
    GET  /api/v1/things/{thing_code}/responses/  — list answers to a wish.
    POST /api/v1/things/{thing_code}/responses/  — answer a wish.

    The creator sees every response; a responder sees only their own.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        wish, error = _get_wish(thing_code)
        if error:
            return error

        if not wish.can_view(request.user.code):
            return Response(
                {"error": "Not authorised to view this wish"},
                status=status.HTTP_403_FORBIDDEN,
            )

        responses = wish.responses.select_related("responder", "thing")
        if not wish.is_owner(request.user.code):
            responses = responses.filter(responder=request.user)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(responses, request)
        serializer = WishResponseSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @method_decorator(ratelimit(key="user", rate="20/h", method="POST", block=True))
    def post(self, request, thing_code):
        wish, error = _get_wish(thing_code)
        if error:
            return error

        if wish.is_owner(request.user.code):
            return Response(
                {"error": "You cannot answer your own wish"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not wish.can_view(request.user.code):
            return Response(
                {"error": "Not authorised to answer this wish"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = WishResponseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        offered_thing = None
        if data["kind"] == WishResponse.Kind.HAVE_THIS:
            offered_thing = get_object_or_404(Thing, code=data["thing_code"])
            if not offered_thing.is_owner(request.user.code):
                return Response(
                    {"error": "You can only offer your own listings"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if offered_thing.status != Thing.Status.ACTIVE:
                return Response(
                    {"error": "You can only offer active listings"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        response = WishResponse.objects.create(
            wish=wish,
            responder=request.user,
            kind=data["kind"],
            thing=offered_thing,
            message=data.get("message", ""),
            url=data.get("url", ""),
            fee=data.get("fee"),
        )

        # Notify the wish creator by email and in-app.
        creator = wish.owner
        if creator and creator.email:
            responder_name = request.user.name or request.user.email
            send_wish_response_email(responder_name, wish, creator.email)
            collection = wish.collections.first()
            InAppNotification.objects.create(
                user=creator,
                type=InAppNotification.WISH_RESPONSE,
                payload={
                    "wish_headline": wish.headline,
                    "responder_name": responder_name,
                    "wish_code": wish.code,
                    "collection_code": collection.code if collection else None,
                },
            )

        return Response(
            WishResponseSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )


class WishResponseAcceptView(APIView):
    """
    POST /api/v1/wish-responses/{code}/accept/
    Accept one answer to a wish (creator only).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        response = get_object_or_404(
            WishResponse.objects.select_related("wish", "responder"), code=code
        )
        wish = response.wish

        if not wish.is_owner(request.user.code):
            return Response(
                {"error": "Only the wish creator can accept an answer"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Only one answer can be accepted at a time — picking a new one releases
        # any previously accepted answer back to PENDING, so two responders can't
        # both believe they won.
        wish.responses.exclude(code=response.code).filter(
            status=WishResponse.Status.ACCEPTED
        ).update(status=WishResponse.Status.PENDING)
        response.accept()

        # Let the responder know their answer was picked.
        responder = response.responder
        if responder:
            collection = wish.collections.first()
            InAppNotification.objects.create(
                user=responder,
                type=InAppNotification.WISH_ACCEPTED,
                payload={
                    "wish_headline": wish.headline,
                    "owner_name": request.user.name or request.user.email,
                    "wish_code": wish.code,
                    "collection_code": collection.code if collection else None,
                },
            )

        return Response(WishResponseSerializer(response).data)


class WishResolveView(APIView):
    """
    POST /api/v1/things/{thing_code}/resolve/
    Mark a wish resolved (creator only): hides it so it leaves the active
    board, and thanks the accepted responder.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, thing_code):
        wish, error = _get_wish(thing_code)
        if error:
            return error

        if not wish.is_owner(request.user.code):
            return Response(
                {"error": "Only the wish creator can resolve it"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if wish.status != Thing.Status.ACTIVE:
            return Response(
                {"error": "This wish is already resolved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wish.status = Thing.Status.INACTIVE
        wish.save(update_fields=["status"])

        # Thank the accepted responder (if one was chosen).
        accepted = (
            wish.responses.filter(status=WishResponse.Status.ACCEPTED)
            .select_related("responder")
            .first()
        )
        if accepted and accepted.responder and accepted.responder.email:
            creator_name = request.user.name or request.user.email
            send_wish_thanks_email(creator_name, wish, accepted.responder.email)

        return Response(ThingSerializer(wish).data)
