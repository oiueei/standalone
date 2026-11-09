"""Custom DRF exception handling."""

from django_ratelimit.exceptions import Ratelimited
from rest_framework import serializers, status
from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler

# Validation refusals the SPA says in the reader's language. DRF's validation body
# carries no top-level ``code``, so the handler lifts one of these from the nested
# ``ErrorDetail``; the field still carries the English sentence for a client that
# does not know the code. Every code here needs a ``requestErrors.<code>`` string.
CODED_VALIDATION_REFUSALS = frozenset(
    {
        "no_prices_here",
        "priced_things_remain",
        "things_limit",
        "opening_hours_required",
        "units_below_booked",
    }
)


class RefusedField(serializers.ValidationError):
    """A 400 on one field that carries a ``Refusal``'s code *and* its params.

    The handler below lifts the code to the top of the body; the params ride with
    the exception because DRF's ``ErrorDetail`` keeps a code but nothing else.
    """

    def __init__(self, field, refusal):
        super().__init__({field: [ErrorDetail(str(refusal), code=refusal.code)]})
        self.params = dict(refusal.params)


def _refusal_codes(detail):
    """The coded refusals found anywhere in a (nested) validation ``detail``."""
    if isinstance(detail, dict):
        return set().union(*(_refusal_codes(value) for value in detail.values()), set())
    if isinstance(detail, (list, tuple)):
        return set().union(*(_refusal_codes(value) for value in detail), set())
    code = getattr(detail, "code", None)
    return {code} if code in CODED_VALIDATION_REFUSALS else set()


def api_exception_handler(exc, context):
    """Map django-ratelimit's ``Ratelimited`` to 429, delegate everything else.

    ``@ratelimit(block=True)`` raises ``Ratelimited`` — a subclass of Django's
    ``PermissionDenied`` — which DRF's default handler renders as **403**. That is
    indistinguishable from a genuine authorisation failure, so clients (and the
    frontend's ``res.status === 429`` branches) can't tell "slow down" from "not
    allowed". Returning **429 Too Many Requests** fixes that. All other
    exceptions fall through to DRF's default handler unchanged — except that a
    validation error carrying exactly one of ``CODED_VALIDATION_REFUSALS`` gets that
    code at the top of its body, where the SPA reads it. Nothing else in the body
    changes, and no other code (``invalid``, ``required``…) is ever lifted.
    """
    if isinstance(exc, Ratelimited):
        return Response(
            {"detail": "Too many requests. Please slow down and try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    response = exception_handler(exc, context)
    if (
        response is not None
        and isinstance(exc, serializers.ValidationError)
        and isinstance(response.data, dict)
    ):
        codes = _refusal_codes(exc.detail)
        if len(codes) == 1:
            response.data["code"] = next(iter(codes))
            params = getattr(exc, "params", None)
            if params:
                response.data["params"] = params
    return response
