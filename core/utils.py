"""
Utility functions for OIUEEI.
"""

import hashlib
import secrets
import string


def redact_email(email):
    """Return a stable, non-reversible tag for an email, safe to write to logs.

    A short SHA-256 prefix — never the address itself — so ops can still correlate
    events for the same user (same email → same tag) without writing PII to logs (M5).
    """
    if not email:
        return "email#none"
    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:12]
    return f"email#{digest}"


def generate_id():
    """Generate a unique 6-character alphanumeric ID in uppercase."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))


def generate_token():
    """Generate a high-entropy URL token for email/magic links.

    26 lowercase alphanumeric characters from a 36-symbol alphabet via
    ``secrets.choice`` → ~134 bits of entropy (log2(36**26)). Used for the RSVP
    ``token`` column that backs every email action link, so the link can't be
    brute-forced the way the 6-char PK (~31 bits) could. Lowercase-only keeps the
    alphabet unambiguous in URLs and avoids the entropy collapse of
    ``token_urlsafe().lower()``.
    """
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(26))


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
