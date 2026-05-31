"""
Unit tests for OIUEEI security features.
"""

import string

from django.test import RequestFactory

from core.middleware import SecurityHeadersMiddleware
from core.utils import generate_id, get_client_ip


class TestSecureIdGeneration:
    """Tests for cryptographically secure ID generation."""

    def test_generate_id_length(self):
        """ID should be exactly 6 characters."""
        for _ in range(100):
            assert len(generate_id()) == 6

    def test_generate_id_characters(self):
        """ID should only contain uppercase letters and digits."""
        valid_chars = set(string.ascii_uppercase + string.digits)
        for _ in range(100):
            id_ = generate_id()
            assert all(c in valid_chars for c in id_)

    def test_generate_id_uniqueness(self):
        """IDs should be unique (statistically unlikely to collide in 1000 attempts)."""
        ids = set(generate_id() for _ in range(1000))
        # With 36^6 = 2.17 billion possibilities, 1000 IDs should be unique
        assert len(ids) == 1000

    def test_generate_id_uses_secrets_module(self):
        """Verify that secrets module is used (via inspection)."""
        import inspect

        from core import utils

        source = inspect.getsource(utils.generate_id)
        assert "secrets.choice" in source
        assert "random.choice" not in source


class TestGetClientIp:
    """Tests for get_client_ip() — ensures IP-based rate limiting cannot be spoofed."""

    def setup_method(self):
        self.factory = RequestFactory()

    def test_returns_remote_addr_when_no_forwarded_header(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "1.2.3.4"
        assert get_client_ip(request) == "1.2.3.4"

    def test_returns_last_ip_from_forwarded_header(self):
        """Heroku appends the real client IP at the end — must take the last value."""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "attacker-injected, real-client-ip"
        assert get_client_ip(request) == "real-client-ip"

    def test_spoofed_first_ip_is_ignored(self):
        """An attacker injecting a fake IP at position 0 should not affect rate limiting."""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "0.0.0.1, 5.6.7.8"
        assert get_client_ip(request) == "5.6.7.8"

    def test_single_ip_in_forwarded_header(self):
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "9.9.9.9"
        assert get_client_ip(request) == "9.9.9.9"

    def test_whitespace_stripped_from_ip(self):
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "1.1.1.1,  2.2.2.2 "
        assert get_client_ip(request) == "2.2.2.2"

    def test_falls_back_to_unknown_when_no_remote_addr(self):
        request = self.factory.get("/")
        request.META.pop("REMOTE_ADDR", None)
        request.META.pop("HTTP_X_FORWARDED_FOR", None)
        assert get_client_ip(request) == "unknown"


class TestRateLimitClientIp:
    """django-ratelimit must bucket per REAL client IP, not the shared Heroku
    router REMOTE_ADDR. Guards the RATELIMIT_IP_META_KEY wiring so the
    anti-spoof get_client_ip() is actually used by the limiter (not only logging)."""

    def setup_method(self):
        self.factory = RequestFactory()

    def test_setting_points_to_anti_spoof_helper(self):
        """The limiter's IP key must resolve to core.utils.get_client_ip."""
        from django.conf import settings
        from django.utils.module_loading import import_string

        assert settings.RATELIMIT_IP_META_KEY == "core.utils.get_client_ip"
        assert import_string(settings.RATELIMIT_IP_META_KEY) is get_client_ip

    def test_ratelimit_resolves_ip_via_rightmost_forwarded_for(self):
        """The limiter's IP resolver must use the rightmost X-Forwarded-For (the
        real client appended by the Heroku router), never REMOTE_ADDR (the shared
        router address) nor an attacker-spoofed leading value."""
        from django_ratelimit.core import _get_ip

        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"  # shared router IP — must NOT be the bucket key
        request.META["HTTP_X_FORWARDED_FOR"] = "6.6.6.6, 203.0.113.7"  # spoofed, real-client
        assert _get_ip(request) == "203.0.113.7"


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware — CSP and Permissions-Policy headers."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(
            get_response=lambda r: __import__(
                "django.http", fromlist=["HttpResponse"]
            ).HttpResponse()
        )

    def test_csp_header_is_present(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        assert "Content-Security-Policy" in response

    def test_permissions_policy_header_is_present(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        assert "Permissions-Policy" in response

    def test_csp_blocks_frame_ancestors(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        assert "frame-ancestors 'none'" in response["Content-Security-Policy"]

    def test_csp_restricts_default_src_to_self(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        assert "default-src 'self'" in response["Content-Security-Policy"]

    def test_csp_allows_cloudinary_images(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        assert "https://res.cloudinary.com" in response["Content-Security-Policy"]

    def test_permissions_policy_disables_sensitive_apis(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        policy = response["Permissions-Policy"]
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_csp_includes_hardening_directives(self):
        """object-src/base-uri/form-action block plugin embedding, base-tag
        injection, and cross-origin form hijacking respectively."""
        request = self.factory.get("/")
        response = self.middleware(request)
        csp = response["Content-Security-Policy"]
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp
