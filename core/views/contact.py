"""
Contact view — the support channel (early-bird ops).

A locked-out user can't authenticate, so the endpoint is anonymous; the cost
of that openness is a per-IP rate limit and a fixed recipient (the operator) —
the form can annoy exactly one mailbox, never relay spam to third parties.
"""

import logging

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers import ContactSerializer
from core.services.email_service import send_contact_email
from core.utils import get_client_ip, redact_email

security_logger = logging.getLogger("security")


class ContactView(APIView):
    """
    POST /api/v1/contact/

    Forwards a support/feedback message to the operator's mailbox
    (``CONTACT_EMAIL`` env var, defaulting to ``DEFAULT_FROM_EMAIL``), with the
    sender's address as Reply-To so answering is one click. Always returns the
    same 200 on success — there is nothing here worth enumerating.
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True))
    def post(self, request):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        send_contact_email(data["name"], data["email"], data["message"], kind=data["kind"])
        security_logger.info(
            f"Contact form message from {redact_email(data['email'])} (IP {get_client_ip(request)})"
        )
        return Response({"message": "Message received"}, status=status.HTTP_200_OK)
