"""
CSRF enforcement for cookie-JWT authentication (SECURITY #1).

CookieJWTAuthentication runs DRF's CSRF check for cookie-authenticated unsafe
methods (Bearer-header auth is exempt — the header is never sent cross-site).
These tests use APIClient(enforce_csrf_checks=True); the rest of the suite uses
the default client, which disables the check, so those tests are unaffected.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

BODY = {"headline": "CSRF probe", "mode": "PROPRIETARY"}
COLLECTIONS_URL = "/api/v1/collections/"


def _access_cookie(user):
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db
class TestCsrfEnforcement:
    def test_cookie_auth_unsafe_without_csrf_is_rejected(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["access_token"] = _access_cookie(user)
        res = client.post(COLLECTIONS_URL, BODY, format="json")
        assert res.status_code == 403

    def test_cookie_auth_unsafe_with_csrf_succeeds(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["access_token"] = _access_cookie(user)
        # /auth/me/ sets the csrftoken cookie via @ensure_csrf_cookie.
        me = client.get("/api/v1/auth/me/")
        assert me.status_code == 200
        token = client.cookies["csrftoken"].value
        res = client.post(COLLECTIONS_URL, BODY, format="json", HTTP_X_CSRFTOKEN=token)
        assert res.status_code == 201

    def test_bearer_auth_unsafe_without_csrf_still_works(self, user):
        # Bearer-header auth is not cookie-based, so CSRF does not apply.
        client = APIClient(enforce_csrf_checks=True)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {_access_cookie(user)}")
        res = client.post(COLLECTIONS_URL, BODY, format="json")
        assert res.status_code == 201

    def test_cookie_auth_safe_method_needs_no_csrf(self, user):
        # GET is safe — no token required even under cookie auth.
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["access_token"] = _access_cookie(user)
        assert client.get("/api/v1/auth/me/").status_code == 200

    def test_me_get_sets_csrftoken_cookie(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies["access_token"] = _access_cookie(user)
        res = client.get("/api/v1/auth/me/")
        assert res.status_code == 200
        assert "csrftoken" in res.cookies


@pytest.mark.django_db
class TestLogoutIsNeverBlocked:
    """LogoutView authenticates nothing, so the CSRF check that guards every other
    cookie-authed POST can't stop a user from ending their own session."""

    def test_logout_without_csrf_token_still_succeeds(self, user):
        client = APIClient(enforce_csrf_checks=True)
        refresh = RefreshToken.for_user(user)
        client.cookies["access_token"] = str(refresh.access_token)
        client.cookies["refresh_token"] = str(refresh)

        res = client.post("/api/v1/auth/logout/")

        assert res.status_code == 200
        assert res.cookies["access_token"].value == ""
        assert res.cookies["refresh_token"].value == ""

    def test_logout_without_csrf_token_blacklists_the_refresh_token(self, user):
        client = APIClient(enforce_csrf_checks=True)
        refresh = str(RefreshToken.for_user(user))
        client.cookies["refresh_token"] = refresh

        assert client.post("/api/v1/auth/logout/").status_code == 200

        client.cookies["refresh_token"] = refresh
        assert client.post("/api/v1/auth/refresh/").status_code == 401
