"""
Django Admin configuration for OIUEEI.
"""

from django.contrib import admin

from core.models import FAQ, RSVP, Collection, Report, Theeeme, Thing, User
from core.models.booking import BookingPeriod


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
    list_filter = ["status"]


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
    list_filter = ["type", "status"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["code", "question", "thing", "is_visible"]
    search_fields = ["code", "question"]
    list_filter = ["is_visible"]


@admin.register(RSVP)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ["code", "user_email", "user_code", "created"]
    search_fields = ["code", "user_email"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    # Platform-moderation log: how many reports landed, on what, and when.
    # The reporter column is staff-only here and never surfaced to owners.
    list_display = ["code", "thing_headline", "thing", "reporter", "created"]
    search_fields = ["code", "thing_headline", "thing__code", "reporter__code", "reporter__email"]
    list_filter = ["created"]
    readonly_fields = ["code", "thing", "thing_headline", "reporter", "created"]


@admin.register(Theeeme)
class TheeemeAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "color_01", "color_02", "color_03", "color_04", "color_05"]
    search_fields = ["code", "name"]


@admin.register(BookingPeriod)
class BookingPeriodAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "thing_code",
        "thing_type",
        "requester_code",
        "owner_code",
        "status",
        "created",
    ]
    search_fields = ["code", "requester_email"]
    list_filter = ["status", "thing_type"]
