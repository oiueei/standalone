"""
Collection model for OIUEEI.
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class Collection(models.Model):
    """
    A collection of things (gifts, sales, orders) owned by a user.
    Can be shared with other users via invites.
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    ]

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
    thumbnail = models.CharField(max_length=16, blank=True, default="")
    hero = models.CharField(max_length=16, blank=True, default="")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="ACTIVE")
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
    theeeme = models.ForeignKey(
        "Theeeme",
        on_delete=models.PROTECT,
        to_field="code",
        db_column="collection_theeeme",
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

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner_id == user_code

    def is_invited(self, user_code):
        """Check if the given user is invited."""
        return self.invites.filter(code=user_code).exists()

    def can_view(self, user_code):
        """Check if the given user can view this collection."""
        return self.is_owner(user_code) or self.is_invited(user_code)
