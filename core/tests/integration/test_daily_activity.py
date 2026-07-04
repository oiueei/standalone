"""Tests for DailyActivityMiddleware — one activity row per user per day, best-effort."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import time_machine
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.middleware import DailyActivityMiddleware
from core.models import DailyActivity


def client_for(user):
    """A dedicated authenticated client (the conftest ``authenticated_client``s
    share one APIClient, so multi-user flows need separate instances)."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db
class TestDailyActivityMiddleware:
    def test_authenticated_request_records_one_row(self, authenticated_client, user):
        resp = authenticated_client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        rows = DailyActivity.objects.filter(user=user)
        assert rows.count() == 1
        assert rows.first().date == date.today()

    def test_second_request_same_day_does_not_duplicate(self, authenticated_client, user):
        authenticated_client.get("/api/v1/auth/me/")
        authenticated_client.get("/api/v1/auth/me/")
        authenticated_client.get("/api/v1/collections/")
        assert DailyActivity.objects.filter(user=user).count() == 1

    def test_anonymous_request_records_nothing(self, api_client):
        # 401 (IsAuthenticated) — DRF resolves request.user to AnonymousUser.
        resp = api_client.get("/api/v1/collections/")
        assert resp.status_code == 401
        assert DailyActivity.objects.count() == 0

    def test_separate_users_get_separate_rows(self, user, user2):
        client_for(user).get("/api/v1/auth/me/")
        client_for(user2).get("/api/v1/auth/me/")
        assert DailyActivity.objects.filter(user=user).count() == 1
        assert DailyActivity.objects.filter(user=user2).count() == 1

    def test_write_failure_never_breaks_the_response(self, authenticated_client, user):
        with patch(
            "core.models.activity.DailyActivity.objects.get_or_create",
            side_effect=Exception("db down"),
        ):
            resp = authenticated_client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        assert DailyActivity.objects.count() == 0


@pytest.mark.django_db
class TestDailyActivityMiddlewareUnit:
    """Direct calls for the branches a real request can't easily hit."""

    def _mw(self):
        return DailyActivityMiddleware(lambda request: HttpResponse())

    def test_skips_anonymous_user(self):
        request = HttpRequest()
        request.user = AnonymousUser()
        self._mw()(request)
        assert DailyActivity.objects.count() == 0

    def test_skips_user_without_code(self):
        request = HttpRequest()
        request.user = SimpleNamespace(is_authenticated=True, code=None)
        self._mw()(request)
        assert DailyActivity.objects.count() == 0

    def test_skips_when_no_user_attribute(self):
        # A bare request (e.g. a path that never ran AuthenticationMiddleware).
        self._mw()(HttpRequest())
        assert DailyActivity.objects.count() == 0

    def test_records_once_per_day_and_rolls_over(self, user):
        # Direct call with a real user avoids JWT-vs-time-travel (a token minted
        # "now" is invalid under a travelled clock). The date is in the cache key,
        # so a new day is a fresh write; a repeat within a day is a cache hit.
        mw = self._mw()
        request = HttpRequest()
        request.user = user
        with time_machine.travel(date(2026, 3, 1)):
            mw(request)
            mw(request)  # same day → cache hit, no second row
        with time_machine.travel(date(2026, 3, 2)):
            mw(request)
        dates = set(DailyActivity.objects.filter(user=user).values_list("date", flat=True))
        assert dates == {date(2026, 3, 1), date(2026, 3, 2)}
