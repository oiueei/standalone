"""
Collection model for OIUEEI.
"""

import secrets

from django.db import models
from django.utils import timezone

from core.utils import generate_id


def generate_share_token():
    """22-char URL-safe token for public share links. Bearer credential — must be unguessable."""
    return secrets.token_urlsafe(16)


class Collection(models.Model):
    """
    A collection of things (gifts, sales, orders) owned by a user.
    Can be shared with other users via invites.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class Mode(models.TextChoices):
        PROPRIETARY = "PROPRIETARY", "Proprietary"
        COMMUNITY = "COMMUNITY", "Community"

    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        PRIVATE = "PRIVATE", "Private"

    class DigestFrequency(models.TextChoices):
        NONE = "NONE", "None"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="owner",
        related_name="owned_collections",
    )
    created = models.DateTimeField(default=timezone.now)
    headline = models.CharField(max_length=64)
    description = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.PROPRIETARY)
    visibility = models.CharField(
        max_length=7, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    digest_frequency = models.CharField(
        max_length=7, choices=DigestFrequency.choices, default=DigestFrequency.NONE
    )
    is_onboarding = models.BooleanField(default=False)
    is_swap = models.BooleanField(default=False)
    is_share = models.BooleanField(default=False)
    newsletter_enabled = models.BooleanField(default=False)
    is_minimalist = models.BooleanField(default=False)
    swap_minimum_items = models.PositiveIntegerField(default=0)
    allowed_thing_types = models.JSONField(default=list, blank=True)
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Owner-defined tag vocabulary for this collection: an ordered list of "
            "free-text labels. Things in the collection may be tagged with a subset. Max 12."
        ),
    )
    thumbnail = models.CharField(max_length=255, blank=True, default="")
    pause_message = models.CharField(max_length=256, blank=True, default="")
    share_token = models.CharField(max_length=22, blank=True, null=True, unique=True)
    things = models.ManyToManyField(
        "Thing",
        blank=True,
        related_name="collections",
        db_table="collection_things",
    )
    invites = models.ManyToManyField(
        "User",
        blank=True,
        related_name="invited_to_collections",
        db_table="collection_invites",
    )

    class Meta:
        app_label = "core"
        db_table = "collections"

    def __str__(self):
        return f"{self.code}: {self.headline}"

    def add_thing(self, thing_code):
        """Add a thing to this collection."""
        from core.models import Thing

        try:
            thing = Thing.objects.get(code=thing_code)
            self.things.add(thing)
        except Thing.DoesNotExist:
            pass

    def remove_thing(self, thing_code):
        """Remove a thing from this collection."""
        from core.models import Thing

        try:
            thing = Thing.objects.get(code=thing_code)
            self.things.remove(thing)
        except Thing.DoesNotExist:
            pass

    def add_invite(self, user_code):
        """Add a user to the invites list."""
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.invites.add(user)
        except User.DoesNotExist:
            pass

    def remove_invite(self, user_code):
        """Remove a user from the invites list."""
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.invites.remove(user)
        except User.DoesNotExist:
            pass

    @property
    def is_paused(self):
        return bool(self.pause_message)

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner_id == user_code

    def is_invited(self, user_code):
        """Check if the given user is invited."""
        return self.invites.filter(code=user_code).exists()

    def is_community(self):
        """Check if this is a community collection."""
        return self.mode == self.Mode.COMMUNITY

    def is_public(self):
        """Check if this collection is publicly readable (anonymous-friendly)."""
        return self.visibility == self.Visibility.PUBLIC

    def can_add_thing(self, user_code):
        """Check if the given user can add things to this collection.

        Owner can always add. Invited users can add in COMMUNITY mode.
        """
        if self.is_owner(user_code):
            return True
        return self.is_community() and self.is_invited(user_code)

    def can_view(self, user_code):
        """Check if the given user can view this collection.

        Owner always; INACTIVE collections only the owner; PUBLIC collections
        anyone — including anonymous visitors (``user_code=None``); otherwise an
        invited member only.
        """
        if self.is_owner(user_code):
            return True
        if self.status == self.Status.INACTIVE:
            return False
        if self.is_public():
            return True
        return self.is_invited(user_code)
