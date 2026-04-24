"""
In-app notification inbox views.
"""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.notification import InAppNotification


class InboxView(APIView):
    """
    GET  /api/v1/inbox/         — list unread notifications for current user
    DELETE /api/v1/inbox/{code}/ — dismiss (delete) a notification
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = InAppNotification.objects.filter(user=request.user)
        return Response(
            [
                {"code": n.code, "type": n.type, "payload": n.payload, "created": n.created}
                for n in notifications
            ]
        )

    def delete(self, request, code):
        notification = get_object_or_404(InAppNotification, code=code, user=request.user)
        notification.delete()
        return Response(status=204)
