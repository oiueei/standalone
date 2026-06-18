"""Custom DRF exception handling."""

from django_ratelimit.exceptions import Ratelimited
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Map django-ratelimit's ``Ratelimited`` to 429, delegate everything else.

    ``@ratelimit(block=True)`` raises ``Ratelimited`` — a subclass of Django's
    ``PermissionDenied`` — which DRF's default handler renders as **403**. That is
    indistinguishable from a genuine authorisation failure, so clients (and the
    frontend's ``res.status === 429`` branches) can't tell "slow down" from "not
    allowed". Returning **429 Too Many Requests** fixes that. All other
    exceptions fall through to DRF's default handler unchanged.
    """
    if isinstance(exc, Ratelimited):
        return Response(
            {"detail": "Too many requests. Please slow down and try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return exception_handler(exc, context)
