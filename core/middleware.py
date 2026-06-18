"""
Security headers middleware for OIUEEI.
"""

from django.conf import settings


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
