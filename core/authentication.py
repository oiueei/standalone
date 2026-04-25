"""
Cookie-based JWT authentication for OIUEEI.

Reads JWT access tokens from HttpOnly cookies instead of Authorization headers.
Falls through to the next authentication class if no cookie is present,
allowing Bearer header auth as a fallback for tests and API clients.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate using JWT access token from HttpOnly cookie."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            # Stale or invalid cookie — treat as unauthenticated so AllowAny
            # endpoints (e.g. /popin, /auth/request-link/) still work.
            return None
        return self.get_user(validated_token), validated_token
