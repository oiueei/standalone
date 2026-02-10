"""
URL configuration for OIUEEI project.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("oiueei-admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
]

# DRF login for browsable API (development only)
if settings.DEBUG:
    urlpatterns += [
        path("api-auth/", include("rest_framework.urls")),
    ]
