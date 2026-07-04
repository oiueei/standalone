"""
Middleware for OIUEEI: security headers + first-party daily-activity tracking.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Add Content-Security-Policy and Permissions-Policy headers to every response.

    Enabled in all environments (registered in base MIDDLEWARE), not just
    production, so the API and the served SPA shell always carry a CSP (I5).

    Two deliberate relaxations:
    - ``style-src 'unsafe-inline'`` stays in every environment: HDS components and
      the per-user theeeme set inline ``style`` attributes throughout the React
      app, so dropping it would break styling — the "remove unsafe-inline"
      hardening is not viable for styles.
    - ``script-src`` gains ``'unsafe-inline'`` only under ``DEBUG`` so the dev-only
      DRF browsable API (inline scripts) keeps working; production stays strict.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        script_src = (
            "script-src 'self' 'unsafe-inline'; " if settings.DEBUG else "script-src 'self'; "
        )
        response["Content-Security-Policy"] = (
            "default-src 'self'; " + script_src + "style-src 'self' 'unsafe-inline'; "
            "img-src 'self'  blob: https://res.cloudinary.com; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.cloudinary.com "
            "https://res.cloudinary.com; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        return response


class DailyActivityMiddleware:
    """Record that the authenticated user was active today — at most one row per day.

    Runs *after* the view so it can read the DRF-authenticated user: this app has no
    Django session (auth is JWT-cookie via DRF authenticators), so ``request.user``
    is only resolved once a view/permission accesses it, at which point DRF writes
    the real user back onto the underlying request. Anonymous / non-DRF requests are
    skipped.

    A cache key (``da:{user}:{date}``, TTL ~24h, on the shared DatabaseCache) gates
    the write so it costs one DB write per user per day, not one per request. Any
    failure here is swallowed — activity bookkeeping must never turn a successful
    response into a 500 (DESIGN §9: this stays first-party, in our DB).
    """

    CACHE_TTL = 60 * 60 * 24  # ~24h; the date is in the key, so it rolls over anyway.

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._record(request)
        except Exception:  # noqa: BLE001 — never let tracking break the response.
            logger.warning("DailyActivity recording failed", exc_info=True)
        return response

    def _record(self, request):
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return
        user_code = getattr(user, "code", None)
        if not user_code:
            return

        today = timezone.localdate()
        cache_key = f"da:{user_code}:{today.isoformat()}"
        if cache.get(cache_key):
            return

        from core.models.activity import DailyActivity

        # get_or_create (not create) so a warm-DB / cold-cache request can't trip the
        # unique(user, date) constraint.
        DailyActivity.objects.get_or_create(user_id=user_code, date=today)
        cache.set(cache_key, 1, self.CACHE_TTL)
