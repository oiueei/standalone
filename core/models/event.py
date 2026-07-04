"""Append-only analytics event log for OIUEEI.

The domain tables can't answer historical questions on their own: Collections and
Things are **hard-deleted**, `Collection.invites` has no join timestamp, and there
is no session concept. This log is an append-only stream of the handful of events
we care about, written alongside the notification/email each action already fires
(see the instrumentation in ``core/views/`` and ``core/services/``).

Everything is a **text snapshot**, not a foreign key: ``actor_code`` /
``collection_code`` / ``thing_code`` are plain 6-char strings so a row survives the
object it references being deleted — that's the whole point of keeping this history.
Consumed only by the ``stats_summary`` management command; never exposed to users
(DESIGN §9 — this is less than the server logs already hold and never leaves our DB).
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


def _snapshot_code(value):
    """Coerce a model instance (any object with ``.code``) or a raw code to a string.

    Accepts ``None`` (→ ``""``), a 6-char code string, or a model instance. Model
    instances whose PK has already been nulled by a ``.delete()`` must be passed as
    the captured code string instead — read ``instance.code`` into a local *before*
    deleting.
    """
    if value is None:
        return ""
    return getattr(value, "code", value) or ""


class Event(models.Model):
    """One append-only analytics event. See module docstring."""

    class Kind(models.TextChoices):
        USER_JOINED = "USER_JOINED"
        COLLECTION_CREATED = "COLLECTION_CREATED"
        COLLECTION_DELETED = "COLLECTION_DELETED"
        THING_ADDED = "THING_ADDED"
        THING_REMOVED = "THING_REMOVED"
        MEMBER_JOINED = "MEMBER_JOINED"
        MEMBER_LEFT = "MEMBER_LEFT"
        FAQ_ASKED = "FAQ_ASKED"
        HOLD_REQUESTED = "HOLD_REQUESTED"
        HOLD_ACCEPTED = "HOLD_ACCEPTED"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    kind = models.CharField(max_length=18, choices=Kind.choices)
    # Snapshots, not FKs — the history must outlive the hard-deleted objects.
    actor_code = models.CharField(max_length=6, blank=True, default="")
    collection_code = models.CharField(max_length=6, blank=True, default="")
    thing_code = models.CharField(max_length=6, blank=True, default="")
    thing_type = models.CharField(max_length=17, blank=True, default="")
    # default=timezone.now (not auto_now_add) so backfill_events can stamp rows with
    # the original historical timestamp instead of "now".
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "events"
        ordering = ["-created"]
        indexes = [models.Index(fields=["kind", "created"])]

    def __str__(self):
        return f"{self.kind} {self.actor_code} @ {self.created:%Y-%m-%d}"

    @classmethod
    def log(cls, kind, *, actor=None, collection=None, thing=None, thing_type=None, created=None):
        """Append one event. The one-liner used at every instrumentation call site.

        ``actor`` / ``collection`` / ``thing`` accept either a model instance or a raw
        code string (use the string form when the object is about to be, or has just
        been, deleted). ``thing_type`` defaults to ``thing.type`` when ``thing`` is a
        Thing instance; pass it explicitly when only a code string is available.
        """
        if thing_type is None:
            thing_type = getattr(thing, "type", "") or ""
        fields = {
            "kind": kind,
            "actor_code": _snapshot_code(actor),
            "collection_code": _snapshot_code(collection),
            "thing_code": _snapshot_code(thing),
            "thing_type": thing_type,
        }
        if created is not None:
            fields["created"] = created
        return cls.objects.create(**fields)
