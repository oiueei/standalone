"""
Production settings for OIUEEI project.
Uses PostgreSQL and configured for Heroku deployment.
"""

import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

DEBUG = False

# Fail fast if production is started with a weak or placeholder SECRET_KEY — the
# CI test key, or anything too short to be a real Django-generated secret. base.py
# already requires it to be set; this additionally enforces production-grade entropy.
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("test-secret-key"):  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be a strong production value (>= 50 characters).")


def _require_env(name):
    """Fail fast instead of silently shipping a YOUR-DOMAIN.com placeholder."""
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"{name} must be set in production.")
    return value


# Database: PostgreSQL via DATABASE_URL
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )
}

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# CORS: Configure from environment variable
# React served by Django = same origin = no CORS needed typically
# Only set if frontend is on different domain
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

# Email: Configure for production (e.g., SendGrid, Mailgun)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = True
# Cap the SMTP socket so a slow/hung provider can't stall a web dyno until the
# 30s Heroku router timeout (H12). Email is currently sent synchronously.
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", 10))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = _require_env("DEFAULT_FROM_EMAIL")

# Dispatch magic-link emails off the request thread (see base.EMAIL_SEND_ASYNC /
# core.views.auth._send_magic_link) so request-link returns in constant time and
# can't be used as an email-enumeration timing oracle (L10). Other emails stay
# synchronous; EMAIL_TIMEOUT bounds the SMTP socket in both cases.
EMAIL_SEND_ASYNC = True

# Static files with WhiteNoise
# React build output (frontend/dist/) is included so collectstatic picks it up
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]  # noqa: F405

# WhiteNoise serves the static React build. It goes right AFTER the
# SecurityHeadersMiddleware (added in base at index 1), never before it: WhiteNoise
# short-circuits the middleware chain for static files (including the SPA's
# index.html), so any middleware after it never runs for those responses — CSP and
# Permissions-Policy would be missing from the app shell if the order were reversed.
MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Disable BrowsableAPIRenderer in production
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# Magic link and RSVP base URLs for production
MAGIC_LINK_BASE_URL = _require_env("MAGIC_LINK_BASE_URL")
RSVP_BASE_URL = _require_env("RSVP_BASE_URL")
SHARE_LINK_BASE_URL = _require_env("SHARE_LINK_BASE_URL")

# Logging for production with security logger
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "security": {
            "format": "{levelname} {asctime} [SECURITY] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "security_console": {
            "class": "logging.StreamHandler",
            "formatter": "security",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "security": {
            "handlers": ["security_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
