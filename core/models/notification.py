import secrets
import string

from django.db import models

from .user import User


def _generate_code():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


class InAppNotification(models.Model):
    BROADCAST = "BROADCAST"
    COLLECTION_DELETED = "COLLECTION_DELETED"

    code = models.CharField(max_length=6, primary_key=True, default=_generate_code)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inbox_notifications")
    type = models.CharField(max_length=32)
    payload = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "in_app_notifications"
        ordering = ["-created"]
