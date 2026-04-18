"""
Unit tests for EVENT_THING.
"""

import pytest
from django.utils import timezone

from core.models import Collection, Thing, User


@pytest.mark.django_db
class TestEventThingModel:
    def test_event_thing_type_valid(self, user):
        thing = Thing.objects.create(
            owner=user,
            type="EVENT_THING",
            headline="Book Club",
        )
        assert thing.type == "EVENT_THING"

    def test_event_date_nullable(self, user):
        thing = Thing.objects.create(
            owner=user,
            type="EVENT_THING",
            headline="Casual meetup",
        )
        assert thing.event_date is None

    def test_event_date_set(self, user):
        dt = timezone.now()
        thing = Thing.objects.create(
            owner=user,
            type="EVENT_THING",
            headline="Reading session",
            event_date=dt,
        )
        assert thing.event_date == dt

    def test_event_attendance_via_deal(self, user, user2):
        thing = Thing.objects.create(
            owner=user,
            type="EVENT_THING",
            headline="Party",
        )
        thing.deal.add(user2)
        assert thing.deal.count() == 1
        assert thing.deal.filter(code=user2.code).exists()

    def test_event_attendance_toggle(self, user, user2):
        thing = Thing.objects.create(
            owner=user,
            type="EVENT_THING",
            headline="Party",
        )
        thing.deal.add(user2)
        assert thing.deal.count() == 1
        thing.deal.remove(user2)
        assert thing.deal.count() == 0
