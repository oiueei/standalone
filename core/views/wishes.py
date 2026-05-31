"""
Wish views for OIUEEI.

Handles "I can help" offers for WISH_THING using the deal M2M field.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing


class WishOfferHelpView(APIView):
    """
    POST /api/v1/things/{thing_code}/offer-help/
    Toggle "I can help" for a wish thing.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        if thing.type != Thing.Type.WISH_THING:
            return Response(
                {"error": "This endpoint is only for wish things"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorised"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if thing.is_owner(request.user.code):
            return Response(
                {"error": "Owner cannot offer help on their own wish"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if thing.deal.filter(code=request.user.code).exists():
            thing.deal.remove(request.user)
            offering = False
        else:
            thing.deal.add(request.user)
            offering = True

        return Response(
            {
                "offering": offering,
                "helper_count": thing.deal.count(),
            }
        )


class WishHelpersView(APIView):
    """
    GET /api/v1/things/{thing_code}/helpers/
    List helpers for a wish thing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        if thing.type != Thing.Type.WISH_THING:
            return Response(
                {"error": "This endpoint is only for wish things"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorised"},
                status=status.HTTP_403_FORBIDDEN,
            )

        helpers = thing.deal.all()
        return Response(
            {
                "helper_count": helpers.count(),
                "helpers": [{"code": u.code, "name": u.name or u.email} for u in helpers],
            }
        )
