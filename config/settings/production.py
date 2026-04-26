"""
Production settings for OIUEEI project.
Uses PostgreSQL and configured for Heroku deployment.
"""

import os

import dj_database_url

from .base import *  # noqa: F401, F403

DEBUG = False

# Database: PostgreSQL via DATABASE_URL
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
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
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@oiueei.com")

# Static files with WhiteNoise
# React build output (frontend/dist/) is included so collectstatic picks it up
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]  # noqa: F405

# SecurityHeadersMiddleware must be inserted BEFORE WhiteNoiseMiddleware.
# WhiteNoise short-circuits the middleware chain for static files (including the
# React SPA's index.html), so any middleware inserted after it never runs for
# those responses. CSP and Permissions-Policy headers would be missing from the
# app shell if the order were reversed.
MIDDLEWARE.insert(1, "core.middleware.SecurityHeadersMiddleware")  # noqa: F405
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
MAGIC_LINK_BASE_URL = os.environ.get("MAGIC_LINK_BASE_URL", "https://oiueei.com/magic-link")
RSVP_BASE_URL = os.environ.get("RSVP_BASE_URL", "https://oiueei.com/rsvp")
SHARE_LINK_BASE_URL = os.environ.get("SHARE_LINK_BASE_URL", "https://oiueei.com/share")

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
