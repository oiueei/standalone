"""
User model for OIUEEI.
"""

import random
from datetime import date

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models

from core.utils import generate_id

_THEEEME_CODES = [
    "BUU331",
    "3NNG31",
    "H00774",
    "K3SS44",
    "K0P4R1",
    "KU11T4",
    "M377RO",
    "S0M0UU",
    "SP4740",
    "SU0M3N",
    "V44K0N",
    "5BC8W6",
]


def _random_theeeme():
    return random.choice(_THEEEME_CODES)


class UserManager(BaseUserManager):
    """Custom manager for User model."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, **extra_fields)


class User(AbstractBaseUser):
    """
    Custom User model with 6-character alphanumeric ID.
    Uses magic link authentication (no password).
    """

    KORO_CHOICES = [
        ("basic", "Basic"),
        ("beat", "Beat"),
        ("calm", "Calm"),
        ("pulse", "Pulse"),
        ("vibration", "Vibration"),
        ("wave", "Wave"),
    ]

    class AgeRange(models.TextChoices):
        UP_TO_21 = "UP_TO_21", "21 or under"
        FROM_22_35 = "22_35", "22-35"
        FROM_36_55 = "36_55", "36-55"
        FROM_56 = "56_PLUS", "56 or over"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    email = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=32, blank=True, default="")
    created = models.DateField(default=date.today)
    last_activity = models.DateField(null=True, blank=True, default=None)
    headline = models.CharField(max_length=64, blank=True, default="")
    about = models.CharField(max_length=2000, blank=True, default="")
    photo = models.CharField(max_length=255, blank=True, default="")
    koro = models.CharField(max_length=9, choices=KORO_CHOICES, default="basic")
    theeeme = models.ForeignKey(
        "Theeeme",
        on_delete=models.PROTECT,
        to_field="code",
        db_column="user_theeeme",
        related_name="users",
        default=_random_theeeme,
    )

    # Notification preferences (see core/services/email_service.py categories)
    notify_activity = models.BooleanField(default=True)
    notify_news = models.BooleanField(default=True)

    # Optional demographics. Per member they're shared only with the owner of a
    # COMMUNITY collection (on the guests page); in aggregate they appear in any
    # collection owner's stats CSV. Never public. Both default empty.
    age_range = models.CharField(max_length=8, choices=AgeRange.choices, blank=True, default="")
    postal_code = models.CharField(max_length=10, blank=True, default="")

    # Required for Django auth
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        app_label = "core"
        db_table = "users"

    def __str__(self):
        return f"{self.code} ({self.email})"

    @property
    def display_name(self):
        """Human-facing name: the chosen name, falling back to the email."""
        return self.name or self.email

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def update_last_activity(self):
        """Update the user's last activity date."""
        self.last_activity = date.today()
        self.save(update_fields=["last_activity"])
