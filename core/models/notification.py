from django.db import models
from django.utils import timezone

from core.utils import generate_id

from .user import User


class InAppNotification(models.Model):
    class Type(models.TextChoices):
        BROADCAST = "BROADCAST"
        COLLECTION_DELETED = "COLLECTION_DELETED"
        COLLECTION_REVOKED = "COLLECTION_REVOKED"
        BOOKING_ACCEPTED = "BOOKING_ACCEPTED"
        BOOKING_REJECTED = "BOOKING_REJECTED"
        BOOKING_REQUESTED = "BOOKING_REQUESTED"
        BOOKING_UNAVAILABLE = "BOOKING_UNAVAILABLE"
        SWAP_REQUESTED = "SWAP_REQUESTED"
        FAQ_QUESTION = "FAQ_QUESTION"
        FAQ_ANSWERED = "FAQ_ANSWERED"
        FAQ_HIDDEN = "FAQ_HIDDEN"
        INVITE_REJECTED = "INVITE_REJECTED"
        MEMBER_LEFT = "MEMBER_LEFT"
        WISH_POSTED = "WISH_POSTED"
        WISH_RESPONSE = "WISH_RESPONSE"
        WISH_ACCEPTED = "WISH_ACCEPTED"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inbox_notifications")
    type = models.CharField(max_length=32, choices=Type.choices)
    payload = models.JSONField(default=dict)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "in_app_notifications"
        ordering = ["-created"]
