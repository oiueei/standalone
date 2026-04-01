"""
User model for OIUEEI.
"""

from datetime import date

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models

from core.utils import generate_id


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

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    email = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=32, blank=True, default="")
    created = models.DateField(default=date.today)
    last_activity = models.DateField(default=date.today)
    headline = models.CharField(max_length=64, blank=True, default="")
    thumbnail = models.CharField(max_length=255, blank=True, default="")
    hero = models.CharField(max_length=255, blank=True, default="")
    koro = models.CharField(max_length=9, choices=KORO_CHOICES, default="basic")
    theeeme = models.ForeignKey(
        "Theeeme",
        on_delete=models.PROTECT,
        to_field="code",
        db_column="user_theeeme",
        related_name="users",
        default="BUU331",
    )

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

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def update_last_activity(self):
        """Update the user's last activity date."""
        self.last_activity = date.today()
        self.save(update_fields=["last_activity"])
