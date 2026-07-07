"""
In-app notification inbox views.
"""

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.notification import InAppNotification


class InboxView(APIView):
    """
    GET  /api/v1/inbox/         — list unread notifications for current user
    DELETE /api/v1/inbox/{code}/ — dismiss (delete) a notification

    Both routes resolve to this one view, so each handler takes an optional
    ``code`` and rejects the combination it doesn't serve (list has no code to
    delete; the item route has no list to GET) with a clean 405 instead of the
    TypeError-driven 500 that a signature mismatch would otherwise raise.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, code=None):
        if code is not None:
            # There is no single-notification GET — only the collection is listable.
            raise MethodNotAllowed("GET")
        notifications = InAppNotification.objects.filter(user=request.user)
        return Response(
            [
                {"code": n.code, "type": n.type, "payload": n.payload, "created": n.created}
                for n in notifications
            ]
        )

    def delete(self, request, code=None):
        if code is None:
            # Dismiss targets a specific notification; the collection route can't delete.
            raise MethodNotAllowed("DELETE")
        notification = get_object_or_404(InAppNotification, code=code, user=request.user)
        notification.delete()
        return Response(status=204)
