"""Unit tests for the Event log: the ``Event.log()`` helper and ``backfill_events``."""

from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import BookingPeriod, Collection, Event, Thing, User


@pytest.mark.django_db
class TestEventLog:
    """The ``Event.log()`` convenience wrapper used at every instrumentation site."""

    def test_log_from_model_instances_snapshots_codes(self):
        owner = User.objects.create(code="EVOWN1", email="evown1@test.com")
        collection = Collection.objects.create(code="EVCOL1", owner=owner, headline="C")
        thing = Thing.objects.create(code="EVTHN1", owner=owner, headline="T", type="GIFT_THING")

        event = Event.log(Event.Kind.THING_ADDED, actor=owner, collection=collection, thing=thing)

        assert event.kind == "THING_ADDED"
        assert event.actor_code == "EVOWN1"
        assert event.collection_code == "EVCOL1"
        assert event.thing_code == "EVTHN1"
        # thing_type is derived from the Thing instance when not given explicitly.
        assert event.thing_type == "GIFT_THING"

    def test_log_accepts_raw_code_strings(self):
        """Post-delete callers pass captured code strings, not instances."""
        event = Event.log(
            Event.Kind.THING_REMOVED, actor="ACTOR1", thing="GONE01", thing_type="SELL_THING"
        )
        assert event.actor_code == "ACTOR1"
        assert event.thing_code == "GONE01"
        assert event.thing_type == "SELL_THING"
        assert event.collection_code == ""

    def test_log_none_yields_empty_snapshots(self):
        event = Event.log(Event.Kind.USER_JOINED, actor=None)
        assert event.actor_code == ""
        assert event.collection_code == ""
        assert event.thing_code == ""
        assert event.thing_type == ""

    def test_log_explicit_thing_type_overrides_instance(self):
        owner = User.objects.create(code="EVOWN2", email="evown2@test.com")
        thing = Thing.objects.create(code="EVTHN2", owner=owner, headline="T", type="GIFT_THING")
        event = Event.log(Event.Kind.HOLD_REQUESTED, thing=thing, thing_type="RENT_THING")
        assert event.thing_type == "RENT_THING"

    def test_log_created_override(self):
        moment = timezone.make_aware(datetime(2025, 1, 2, 3, 4, 5))
        event = Event.log(Event.Kind.USER_JOINED, actor="ABC123", created=moment)
        assert event.created == moment

    def test_default_created_is_now(self):
        event = Event.log(Event.Kind.USER_JOINED, actor="ABC123")
        assert (timezone.now() - event.created) < timedelta(seconds=5)


@pytest.mark.django_db
class TestBackfillEvents:
    """The one-off ``backfill_events`` command seeds history idempotently."""

    def _seed_domain(self):
        owner = User.objects.create(code="BFOWN1", email="bfown@test.com")
        owner.created = date(2025, 1, 1)
        owner.save(update_fields=["created"])
        requester = User.objects.create(code="BFREQ1", email="bfreq@test.com")

        collection = Collection.objects.create(code="BFCOL1", owner=owner, headline="Backfill")
        collection.created = datetime(2025, 2, 1, 9, 0, tzinfo=dt_timezone.utc)
        collection.save(update_fields=["created"])

        thing = Thing.objects.create(code="BFTHN1", owner=owner, headline="T", type="GIFT_THING")
        thing.created = datetime(2025, 3, 1, 10, 0, tzinfo=dt_timezone.utc)
        thing.save(update_fields=["created"])
        collection.things.add(thing)

        accepted = BookingPeriod.objects.create(
            code="BFBK01",
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            status="ACCEPTED",
        )
        BookingPeriod.objects.create(
            code="BFBK02",
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
            status="PENDING",
        )
        return owner, requester, collection, thing, accepted

    def test_backfill_creates_one_event_per_row(self):
        owner, requester, collection, thing, accepted = self._seed_domain()

        out = StringIO()
        call_command("backfill_events", stdout=out)

        # 2 users, 1 collection, 1 thing, 2 bookings (HOLD_REQUESTED) + 1 accepted.
        assert Event.objects.filter(kind="USER_JOINED").count() == 2
        assert Event.objects.filter(kind="COLLECTION_CREATED").count() == 1
        assert Event.objects.filter(kind="THING_ADDED").count() == 1
        assert Event.objects.filter(kind="HOLD_REQUESTED").count() == 2
        assert Event.objects.filter(kind="HOLD_ACCEPTED").count() == 1
        assert "Backfilled 7 events" in out.getvalue()

    def test_backfill_uses_source_timestamps(self):
        owner, requester, collection, thing, accepted = self._seed_domain()
        call_command("backfill_events", stdout=StringIO())

        user_event = Event.objects.get(kind="USER_JOINED", actor_code="BFOWN1")
        expected = timezone.make_aware(datetime.combine(date(2025, 1, 1), time.min))
        assert user_event.created == expected

        coll_event = Event.objects.get(kind="COLLECTION_CREATED", collection_code="BFCOL1")
        assert coll_event.created == collection.created
        assert coll_event.actor_code == "BFOWN1"

        thing_event = Event.objects.get(kind="THING_ADDED", thing_code="BFTHN1")
        assert thing_event.created == thing.created
        assert thing_event.collection_code == "BFCOL1"
        assert thing_event.thing_type == "GIFT_THING"

    def test_backfill_is_idempotent(self):
        self._seed_domain()
        call_command("backfill_events", stdout=StringIO())
        total = Event.objects.count()

        out = StringIO()
        call_command("backfill_events", stdout=out)
        assert Event.objects.count() == total
        assert "Backfilled 0 events" in out.getvalue()

    def test_backfill_empty_db(self):
        out = StringIO()
        call_command("backfill_events", stdout=out)
        assert Event.objects.count() == 0
        assert "Backfilled 0 events" in out.getvalue()
