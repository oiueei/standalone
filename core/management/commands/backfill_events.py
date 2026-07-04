"""One-off backfill for the append-only :class:`~core.models.event.Event` log.

Repo convention keeps data out of migrations, so seeding the historical events
lives here instead. Run **once** on the day the tracking machine ships, before the
forward instrumentation has had a chance to record anything for pre-existing rows:

    python manage.py backfill_events

It stamps one event per existing row at that row's original timestamp:

- every ``User``          → ``USER_JOINED``       at ``user.created``
- every ``Collection``    → ``COLLECTION_CREATED`` at ``collection.created``
- every ``Thing``         → ``THING_ADDED``        at ``thing.created``
- every ``BookingPeriod`` → ``HOLD_REQUESTED``     at ``booking.created``
  (plus ``HOLD_ACCEPTED`` at the same timestamp when the booking is ACCEPTED)

Past deletions and real join/accept moments are unknowable, so accumulated counts
simply start honest from D-day. **Idempotent**: an event is only written when no
equal one (same kind + snapshots + timestamp) already exists, so re-running is safe
and never double-counts.
"""

from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BookingPeriod, Collection, Event, Thing, User


class Command(BaseCommand):
    help = "Backfill the Event log from existing users, collections, things and bookings."

    def handle(self, *args, **options):
        created = 0

        # Users → USER_JOINED (User.created is a DateField → midnight of that day).
        for user in User.objects.all():
            joined_at = timezone.make_aware(datetime.combine(user.created, time.min))
            created += self._ensure(Event.Kind.USER_JOINED, joined_at, actor_code=user.code)

        # Collections → COLLECTION_CREATED.
        for collection in Collection.objects.select_related("owner"):
            created += self._ensure(
                Event.Kind.COLLECTION_CREATED,
                collection.created,
                actor_code=collection.owner_id,
                collection_code=collection.code,
            )

        # Things → THING_ADDED (record the earliest-coded collection it sits in, if any).
        for thing in Thing.objects.prefetch_related("collections"):
            first_collection = thing.collections.order_by("code").first()
            created += self._ensure(
                Event.Kind.THING_ADDED,
                thing.created,
                actor_code=thing.owner_id,
                collection_code=first_collection.code if first_collection else "",
                thing_code=thing.code,
                thing_type=thing.type,
            )

        # Bookings → HOLD_REQUESTED (+ HOLD_ACCEPTED for accepted ones), both at
        # booking.created since the real accept moment isn't recorded historically.
        for booking in BookingPeriod.objects.all():
            created += self._ensure(
                Event.Kind.HOLD_REQUESTED,
                booking.created,
                actor_code=booking.requester_code_id,
                thing_code=booking.thing_code_id,
                thing_type=booking.thing_type,
            )
            if booking.status == BookingPeriod.Status.ACCEPTED:
                created += self._ensure(
                    Event.Kind.HOLD_ACCEPTED,
                    booking.created,
                    actor_code=booking.requester_code_id,
                    thing_code=booking.thing_code_id,
                    thing_type=booking.thing_type,
                )

        self.stdout.write(self.style.SUCCESS(f"Backfilled {created} events"))

    def _ensure(
        self, kind, created, *, actor_code="", collection_code="", thing_code="", thing_type=""
    ):
        """Create the event unless an identical one already exists. Returns 1/0."""
        snapshot = {
            "kind": kind,
            "actor_code": actor_code or "",
            "collection_code": collection_code or "",
            "thing_code": thing_code or "",
            "created": created,
        }
        if Event.objects.filter(**snapshot).exists():
            return 0
        Event.objects.create(thing_type=thing_type or "", **snapshot)
        return 1
