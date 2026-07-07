"""
Cookie-based JWT authentication for OIUEEI.

Reads JWT access tokens from HttpOnly cookies instead of Authorization headers.
Falls through to the next authentication class if no cookie is present,
allowing Bearer header auth as a fallback for tests and API clients.

Because the access token rides in a cookie, the browser attaches it to
cross-site requests automatically, so cookie-authenticated unsafe methods need
a CSRF guard (Bearer-header auth does not — the header is never sent
cross-site). We mirror DRF's ``SessionAuthentication`` and run the same CSRF
check for cookie-authenticated requests; ``SameSite=Lax`` on the cookie remains
the first layer, this is defence in depth. The frontend already sends
``X-CSRFToken`` on every unsafe request, and ``MeView`` (hit on every app load)
sets the ``csrftoken`` cookie via ``@ensure_csrf_cookie``.
"""

from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate using JWT access token from HttpOnly cookie."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
        except (InvalidToken, TokenError, AuthenticationFailed):
            # Stale or invalid cookie — a malformed/expired token, or a valid
            # token whose user no longer exists or is inactive (e.g. after a dev
            # ``seed_demo --reset`` leaves a live cookie pointing at a wiped
            # user). Treat as unauthenticated so AllowAny endpoints (/popin,
            # /auth/request-link/) still work; protected endpoints just 401.
            return None
        # The cookie authenticated us, so this request is CSRF-eligible — enforce
        # it (a no-op on safe methods, which CSRFCheck.process_view skips).
        self.enforce_csrf(request)
        return user, validated_token

    def enforce_csrf(self, request):
        """Run DRF's CSRF check, mirroring ``SessionAuthentication.enforce_csrf``.

        The double-submit check compares the ``X-CSRFToken`` header against the
        ``csrftoken`` cookie. The test client sets ``_dont_enforce_csrf_checks``,
        so Bearer-token and cookie-based tests are unaffected.
        """

        def dummy_get_response(request):  # pragma: no cover
            return None

        check = CSRFCheck(dummy_get_response)
        # populates request.META['CSRF_COOKIE'], used by process_view()
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
