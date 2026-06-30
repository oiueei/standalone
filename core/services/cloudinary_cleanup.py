"""Delete a record's Cloudinary assets when the record itself is deleted.

Wired as ``post_delete`` signal handlers on Thing, Collection and User (see
``core.apps.CoreConfig.ready``) so it covers direct deletes, the collection
view's orphan-thing sweep, and user-account cascades alike — anywhere a row
actually disappears. The destroy runs on ``transaction.on_commit`` (a
rolled-back delete keeps its images) and never raises: an orphaned asset is a
smaller problem than a delete that blows up.

It is **suspended** during ``seed_demo --reset``: the demo reuses a fixed pool
of shared Cloudinary public ids, so wiping them on reset would break the very
images the immediate re-seed points back at.
"""

import logging
from contextlib import contextmanager

import cloudinary.uploader
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.models import Collection, Thing, User

logger = logging.getLogger(__name__)

_suspended = False


@contextmanager
def suspended():
    """Disable Cloudinary cleanup for any delete performed inside the block."""
    global _suspended
    previous = _suspended
    _suspended = True
    try:
        yield
    finally:
        _suspended = previous


def _assets(instance):
    """Yield ``(public_id, destroy_kwargs)`` for each Cloudinary asset owned by
    ``instance`` (a Thing, Collection or User)."""
    if isinstance(instance, Thing):
        if instance.thumbnail:
            yield instance.thumbnail, {}
        for public_id in instance.gallery or []:
            yield public_id, {}
    elif isinstance(instance, Collection):
        if instance.thumbnail:
            yield instance.thumbnail, {}
    elif isinstance(instance, User):
        if instance.photo:
            yield instance.photo, {}


def _destroy(public_id, **kwargs):
    try:
        cloudinary.uploader.destroy(public_id, invalidate=True, **kwargs)
    except Exception:
        logger.warning("Cloudinary cleanup failed for %r", public_id, exc_info=True)


@receiver(post_delete, sender=Thing)
@receiver(post_delete, sender=Collection)
@receiver(post_delete, sender=User)
def _cleanup_assets_on_delete(sender, instance, **kwargs):
    if _suspended:
        return
    assets = list(_assets(instance))
    if assets:
        transaction.on_commit(lambda: [_destroy(pid, **kw) for pid, kw in assets])
