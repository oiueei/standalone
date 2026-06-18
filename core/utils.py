"""
Utility functions for OIUEEI.
"""

import hashlib
import hmac
import secrets
import string

from django.conf import settings


def redact_email(email):
    """Return a keyed, non-reversible tag for an email, safe to write to logs.

    An HMAC-SHA256 (keyed by ``SECRET_KEY``) prefix — never the address — so ops
    can still correlate events for the same user (same email → same tag) without
    writing PII, and without the tag being recoverable via a dictionary attack on
    a bare hash of a low-entropy email (M5). Tags change if ``SECRET_KEY`` rotates.
    """
    if not email:
        return "email#none"
    digest = hmac.new(
        settings.SECRET_KEY.encode(), email.strip().lower().encode(), hashlib.sha256
    ).hexdigest()[:12]
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

    Assumption (I6): exactly ONE trusted proxy hop sits in front of the app (the
    Heroku router), so the last XFF entry is the genuine client. If the deployment
    ever gains another trusted proxy (e.g. a CDN in front of Heroku), this must
    take the Nth-from-last entry instead — revisit it then. The value is used only
    as a rate-limit bucket key, so a malformed header degrades to a coarse key, not
    a security bypass.
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


# Documents are uploaded privately (Cloudinary type=authenticated): their plain
# delivery URL 404s, so the only way to fetch one is a short-lived signed URL
# minted on demand by the gated download view. Five minutes is long enough to
# start a download yet short enough that a leaked URL dies quickly.
DOCUMENT_URL_TTL_SECONDS = 300


def signed_document_url(doc, ttl_seconds=DOCUMENT_URL_TTL_SECONDS):
    """Mint a short-lived, signed Cloudinary download URL for a stored document.

    ``doc`` is a stored ``{public_id, filename, content_type, type}`` dict. New
    documents carry ``type='authenticated'`` (private); legacy documents stored
    before this change have no ``type`` and were public ``upload`` assets — both
    are served through the same signed, expiring download API so the underlying
    Cloudinary URL is never eternal nor exposed in API responses or emails (M2).
    Returns ``None`` when the document has no ``public_id``.
    """
    import time

    import cloudinary.utils

    public_id = doc.get("public_id")
    if not public_id:
        return None
    return cloudinary.utils.private_download_url(
        public_id,
        "",
        resource_type="raw",
        type=doc.get("type", "upload"),
        expires_at=int(time.time()) + ttl_seconds,
    )
