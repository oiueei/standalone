"""
Django Admin configuration for OIUEEI.
"""

from django.contrib import admin

from core.models import FAQ, RSVP, Collection, Theeeme, Thing, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["code", "email", "name", "created"]
    search_fields = ["code", "email", "name"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "headline",
        "owner",
        "status",
    ]
    search_fields = ["code", "headline"]
    list_filter = ["status", "theeeme"]


@admin.register(Thing)
class ThingAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "headline",
        "owner",
        "type",
        "status",
    ]
    search_fields = ["code", "headline"]
    list_filter = ["type", "status", "available"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["code", "question", "thing", "is_visible"]
    search_fields = ["code", "question"]
    list_filter = ["is_visible"]


@admin.register(RSVP)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ["code", "user_email", "user_code", "created"]
    search_fields = ["code", "user_email"]


@admin.register(Theeeme)
class TheeemeAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    search_fields = ["code", "name"]
