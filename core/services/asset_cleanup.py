"""Delete a record's stored assets when the record is deleted, or when a save drops one.

Wired as ``post_delete`` signal handlers on Thing, Collection, User and NetworkPoint (see
``core.apps.CoreConfig.ready``) so it covers direct deletes, the collection
view's orphan-thing sweep, and user-account cascades alike — anywhere a row
actually disappears. The destroy runs on ``transaction.on_commit`` (a
rolled-back delete keeps its images) and never raises: an orphaned asset is a
smaller problem than a delete that blows up.

**A save that replaces or removes a key destroys the old object too**
(2026-10-02). Until then only a delete did: a removed profile photo, a swapped
cover, a photo taken out of a thing's gallery or a replaced welcome PDF stayed
in the bucket, unreachable, until somebody ran ``cleanup_orphan_images`` by
hand inside its 30-day window — and past that window, for good. That broke the
``/legal`` promise that a photo goes when you remove it. ``post_init`` notes
the keys a row was loaded with and ``post_save`` destroys the ones the save
dropped, on commit, under the same rules as a delete.

Keys under ``storage.SEED_PREFIX`` are **never** destroyed. The demo's fixtures
are a shared pool: every database that has ever seeded points at the same
objects, so deleting one demo row — from the admin, from a cascade, from
anywhere — must not take an image away from every other environment. This used
to be handled only by ``seed_demo --reset`` suspending the whole mechanism,
which left the admin as an open trapdoor; the skip below closes it, and
``suspended()`` stays for what it is actually for.

**One race it does not close.** Two requests that load the same row and both
save it in full: the first replaces a key and destroys the old object; the
second, still holding the old key in memory, writes it back. The row then names
an object that is gone — a broken photo, not a leak, and the same lost update
any concurrent full save already causes to the row's other columns. Closing it
would mean locking every edit of a thing, a collection or a profile for a case
two people editing the same row at the same second can produce; it is left
open on purpose, and re-uploading the photo mends it.

**A key another row still holds is never destroyed either** (2026-10-02). A
row does not own its keys: a key is the path of its public URL, and
``ImageIdField`` binds it to a folder, not to an uploader. So a member who
could see someone else's photo could save its key on a thing of their own and
delete that thing — and this handler deleted the other person's photo with it.
The check runs at destroy time, after the commit, so the row being deleted no
longer counts.
"""

import logging
from contextlib import contextmanager

from django.db import transaction
from django.db.models.signals import post_delete, post_init, post_save
from django.dispatch import receiver

from core.models import Collection, NetworkPoint, Thing, User
from core.services import storage

logger = logging.getLogger(__name__)

# Every column that holds a storage key. The delete and save handlers, the
# in-use check and the orphan sweep (``cleanup_orphan_images``) all read this one
# table: a field missing from one copy of a hand-written list is a live photo
# deleted, or a dropped one kept forever.
ASSET_FIELDS = {
    Thing: ("thumbnail", "gallery"),
    # The welcome PDF is an object like any other — no special case left. It
    # needed one under Cloudinary, which filed it under resource_type=image.
    Collection: ("thumbnail", "welcome_doc"),
    User: ("photo",),
    # The entity's logo, held by a dinamizador's pickup point.
    NetworkPoint: ("logo",),
}
# The one column that holds an ordered list of keys rather than a single key.
_LIST_FIELDS = frozenset({"gallery"})

_suspended = False


@contextmanager
def suspended():
    """Disable asset cleanup for any delete or save performed inside the block."""
    global _suspended
    previous = _suspended
    _suspended = True
    try:
        yield
    finally:
        _suspended = previous


def _keys(field, value):
    """The keys one column value holds, in order, empties dropped."""
    if field in _LIST_FIELDS:
        return [key for key in value or [] if key]
    return [value] if value else []


def _assets(instance):
    """Yield the storage key of each asset ``instance`` (a row of ``ASSET_FIELDS``) holds."""
    for model, fields in ASSET_FIELDS.items():
        if isinstance(instance, model):
            for field in fields:
                yield from _keys(field, getattr(instance, field))


def _loaded(instance):
    """The keys ``instance`` holds per key-holding column, for the columns it has loaded.

    A deferred column (``.only()`` / ``.defer()``) is left out rather than read:
    reading it would cost a query per row on every list that defers it, and a
    column this code never saw is one it cannot say a save replaced. A tuple, not
    the list itself, so an in-place ``gallery.remove()`` still reads as a change.
    """
    values = instance.__dict__
    for model, fields in ASSET_FIELDS.items():
        if isinstance(instance, model):
            return {f: tuple(_keys(f, values[f])) for f in fields if f in values}
    return {}


def referenced_keys():
    """Every storage key some row holds — what the orphan sweep must keep."""
    referenced = set()
    for model, fields in ASSET_FIELDS.items():
        for row in model.objects.values_list(*fields):
            for field, value in zip(fields, row, strict=True):
                referenced.update(_keys(field, value))
    return referenced


def is_referenced(key):
    """Whether any row still holds ``key``."""
    for model, fields in ASSET_FIELDS.items():
        for field in fields:
            if field in _LIST_FIELDS:
                # SQLite has no JSON containment lookup, so match the list's text
                # on every backend and confirm on the decoded list: a substring of
                # another key is not this key.
                lists = model.objects.filter(**{f"{field}__icontains": key}).values_list(
                    field, flat=True
                )
                if any(key in (value or []) for value in lists):
                    return True
            elif model.objects.filter(**{field: key}).exists():
                return True
    return False


def _destroy(key):
    try:
        if is_referenced(key):
            logger.info("Asset %r is still in use by another record; kept", key)
            return
        storage.delete(key)
    except Exception:
        logger.warning("Asset cleanup failed for %r", key, exc_info=True)


@receiver(post_delete, sender=Thing)
@receiver(post_delete, sender=Collection)
@receiver(post_delete, sender=User)
@receiver(post_delete, sender=NetworkPoint)
def _cleanup_assets_on_delete(sender, instance, **kwargs):
    if _suspended:
        return
    assets = [key for key in _assets(instance) if not key.startswith(storage.SEED_PREFIX)]
    if assets:
        transaction.on_commit(lambda: [_destroy(key) for key in assets])


@receiver(post_init, sender=Thing)
@receiver(post_init, sender=Collection)
@receiver(post_init, sender=User)
@receiver(post_init, sender=NetworkPoint)
def _remember_stored_assets(sender, instance, **kwargs):
    instance._stored_assets = _loaded(instance)


@receiver(post_save, sender=Thing)
@receiver(post_save, sender=Collection)
@receiver(post_save, sender=User)
@receiver(post_save, sender=NetworkPoint)
def _cleanup_assets_a_save_dropped(sender, instance, created, update_fields, **kwargs):
    before = getattr(instance, "_stored_assets", {})
    saved = _loaded(instance)
    if update_fields is not None:
        # A column left out of update_fields was not written: whatever it holds
        # in memory is not what the row holds, so it neither drops a key nor
        # becomes the new baseline.
        saved = {field: keys for field, keys in saved.items() if field in update_fields}
    instance._stored_assets = {**before, **saved}
    if created or _suspended:
        return
    dropped = [
        key
        for field, keys in saved.items()
        for key in before.get(field, ())
        if key not in keys and not key.startswith(storage.SEED_PREFIX)
    ]
    if dropped:
        transaction.on_commit(lambda: [_destroy(key) for key in dropped])
