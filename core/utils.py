"""
Utility functions for OIUEEI.
"""

import secrets
import string


def generate_id():
    """Generate a unique 6-character alphanumeric ID in uppercase."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))


def get_client_ip(request):
    """Get client IP address from request.

    On Heroku (and similar proxies), the real client IP is the last value
    appended by the load balancer — not the first, which is attacker-controlled.
    Taking the rightmost IP prevents X-Forwarded-For spoofing that would otherwise
    bypass IP-based rate limiting.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def cloudinary_url(image_id):
    """Build Cloudinary URL from a stored public_id."""
    if not image_id:
        return None
    import cloudinary.utils

    url, _ = cloudinary.utils.cloudinary_url(image_id, fetch_format="auto", quality="auto")
    return url
