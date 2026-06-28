from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Registers the post_delete Cloudinary-cleanup signal handlers.
        from core.services import cloudinary_cleanup  # noqa: F401
