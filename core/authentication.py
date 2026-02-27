"""
Cookie-based JWT authentication for OIUEEI.

Reads JWT access tokens from HttpOnly cookies instead of Authorization headers.
Falls through to the next authentication class if no cookie is present,
allowing Bearer header auth as a fallback for tests and API clients.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate using JWT access token from HttpOnly cookie."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
