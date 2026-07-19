"""Unit tests for the custom DRF exception handler (rate-limit → 429)."""

from django_ratelimit.exceptions import Ratelimited
from rest_framework.exceptions import NotFound, PermissionDenied

from core.exceptions import api_exception_handler


def test_ratelimited_maps_to_429():
    res = api_exception_handler(Ratelimited(), {})
    assert res.status_code == 429
    assert "detail" in res.data


def test_genuine_permission_denied_still_403():
    res = api_exception_handler(PermissionDenied(), {})
    assert res.status_code == 403
    assert "detail" in res.data


def test_not_found_delegates_to_default():
    res = api_exception_handler(NotFound(), {})
    assert res.status_code == 404
    assert "detail" in res.data
