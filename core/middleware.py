"""
Security headers middleware for OIUEEI.
"""


class SecurityHeadersMiddleware:
    """Add Content-Security-Policy and Permissions-Policy headers to all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self'  blob: https://res.cloudinary.com; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.cloudinary.com "
            "https://res.cloudinary.com https://api-eu.mixpanel.com; "
            "frame-ancestors 'none'; "
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        return response
