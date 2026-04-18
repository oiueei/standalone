"""
Event views for OIUEEI.

Handles attendance for EVENT_THING using the deal M2M field.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing, User


class EventAttendView(APIView):
    """
    POST /api/v1/things/{thing_code}/attend/
    Toggle attendance for an event thing.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        if thing.type != "EVENT_THING":
            return Response(
                {"error": "This endpoint is only for event things"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorised"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if thing.is_owner(request.user.code):
            return Response(
                {"error": "Owner cannot attend their own event"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if thing.deal.filter(code=request.user.code).exists():
            thing.deal.remove(request.user)
            attending = False
        else:
            thing.deal.add(request.user)
            attending = True

        return Response(
            {
                "attending": attending,
                "attendee_count": thing.deal.count(),
            }
        )


class EventAttendeesView(APIView):
    """
    GET /api/v1/things/{thing_code}/attendees/
    List attendees for an event thing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        if thing.type != "EVENT_THING":
            return Response(
                {"error": "This endpoint is only for event things"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorised"},
                status=status.HTTP_403_FORBIDDEN,
            )

        attendees = thing.deal.all()
        return Response(
            {
                "attendee_count": attendees.count(),
                "attendees": [{"code": u.code, "name": u.name or u.email} for u in attendees],
            }
        )
