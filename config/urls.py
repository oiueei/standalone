"""
URL configuration for OIUEEI project.
"""

import os

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django_ratelimit.decorators import ratelimit

# Throttle admin login attempts (M3): wrap the admin site's login view with an
# IP-keyed POST rate limit so the password form can't be brute-forced. Applied
# before `admin.site.urls` is built below so get_urls() picks up the wrapper.
# (django-ratelimit only — no django-axes; MFA is deferred. The admin path is
# also non-default, see below.)
admin.site.login = ratelimit(key="ip", rate="5/m", method="POST", block=True)(admin.site.login)

urlpatterns = [
    path("oiueei-admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
]

# DRF login for browsable API (development only)
if settings.DEBUG:
    urlpatterns += [
        path("api-auth/", include("rest_framework.urls")),
    ]


def spa_index(request):
    """Serve the React SPA index.html for all non-API routes."""
    index_path = os.path.join(settings.BASE_DIR, "frontend", "dist", "index.html")
    try:
        with open(index_path, encoding="utf-8") as f:
            return HttpResponse(f.read(), content_type="text/html")
    except FileNotFoundError:
        return HttpResponse("Frontend not built. Run: cd frontend && yarn build", status=503)


# Catch-all: serve React SPA for all routes not handled above
urlpatterns += [re_path(r"^(?!static/|api/|oiueei-admin).*", spa_index)]
