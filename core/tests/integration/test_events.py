"""
Integration tests for EVENT_THING endpoints.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch

from core.models import Collection, Thing, User


@pytest.fixture
def event_setup(db):
    """Create owner, invitee, collection, and event thing."""
    owner = User.objects.create(code="EVOWN1", email="owner@test.com", name="Owner")
    invitee = User.objects.create(code="EVINV1", email="invitee@test.com", name="Invitee")
    stranger = User.objects.create(code="EVSTR1", email="stranger@test.com", name="Stranger")

    collection = Collection.objects.create(code="EVCOL1", owner=owner, headline="Book Club")
    collection.invites.add(invitee)

    event = Thing.objects.create(
        code="EVEVT1",
        type="EVENT_THING",
        owner=owner,
        headline="Reading Session",
        event_date=timezone.now() + timezone.timedelta(days=7),
    )
    collection.things.add(event)

    owner_client = APIClient()
    owner_token = RefreshToken.for_user(owner)
    owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token.access_token}")

    invitee_client = APIClient()
    invitee_token = RefreshToken.for_user(invitee)
    invitee_client.credentials(HTTP_AUTHORIZATION=f"Bearer {invitee_token.access_token}")

    stranger_client = APIClient()
    stranger_token = RefreshToken.for_user(stranger)
    stranger_client.credentials(HTTP_AUTHORIZATION=f"Bearer {stranger_token.access_token}")

    return {
        "owner": owner,
        "invitee": invitee,
        "stranger": stranger,
        "collection": collection,
        "event": event,
        "owner_client": owner_client,
        "invitee_client": invitee_client,
        "stranger_client": stranger_client,
    }


@pytest.mark.django_db
class TestEventAttend:
    def test_invitee_can_attend(self, event_setup):
        s = event_setup
        res = s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        assert res.status_code == 200
        assert res.data["attending"] is True
        assert res.data["attendee_count"] == 1

    def test_invitee_can_toggle_off(self, event_setup):
        s = event_setup
        s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        res = s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        assert res.status_code == 200
        assert res.data["attending"] is False
        assert res.data["attendee_count"] == 0

    def test_owner_cannot_attend(self, event_setup):
        s = event_setup
        res = s["owner_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        assert res.status_code == 400

    def test_stranger_cannot_attend(self, event_setup):
        s = event_setup
        res = s["stranger_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        assert res.status_code == 403

    def test_attend_non_event_rejected(self, event_setup):
        s = event_setup
        gift = Thing.objects.create(
            code="EVGFT1", type="GIFT_THING", owner=s["owner"], headline="A gift"
        )
        s["collection"].things.add(gift)
        res = s["invitee_client"].post(f"/api/v1/things/{gift.code}/attend/")
        assert res.status_code == 400


@pytest.mark.django_db
class TestEventAttendees:
    def test_list_attendees(self, event_setup):
        s = event_setup
        s["event"].deal.add(s["invitee"])
        res = s["owner_client"].get(f"/api/v1/things/{s['event'].code}/attendees/")
        assert res.status_code == 200
        assert res.data["attendee_count"] == 1
        assert res.data["attendees"][0]["code"] == s["invitee"].code

    def test_empty_attendees(self, event_setup):
        s = event_setup
        res = s["owner_client"].get(f"/api/v1/things/{s['event'].code}/attendees/")
        assert res.status_code == 200
        assert res.data["attendee_count"] == 0

    def test_stranger_cannot_list(self, event_setup):
        s = event_setup
        res = s["stranger_client"].get(f"/api/v1/things/{s['event'].code}/attendees/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestEventReservationGuard:
    def test_reservation_blocked_for_event(self, event_setup):
        s = event_setup
        res = s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/request/")
        assert res.status_code == 400
        assert "does not support reservations" in res.data["error"]


@pytest.mark.django_db
class TestEventThingCreate:
    def test_create_event_thing(self, event_setup):
        s = event_setup
        dt = (timezone.now() + timezone.timedelta(days=14)).isoformat()
        res = s["owner_client"].post(
            "/api/v1/things/",
            {
                "type": "EVENT_THING",
                "headline": "New Event",
                "collection_code": s["collection"].code,
                "event_date": dt,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["type"] == "EVENT_THING"
        assert res.data["event_date"] is not None

    def test_create_event_without_date(self, event_setup):
        s = event_setup
        res = s["owner_client"].post(
            "/api/v1/things/",
            {
                "type": "EVENT_THING",
                "headline": "Casual meetup",
                "collection_code": s["collection"].code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["event_date"] is None


@pytest.mark.django_db
class TestEventSerializer:
    def test_attendee_count_in_serializer(self, event_setup):
        s = event_setup
        s["event"].deal.add(s["invitee"])
        res = s["invitee_client"].get(f"/api/v1/things/{s['event'].code}/")
        assert res.status_code == 200
        assert res.data["attendee_count"] == 1
        assert res.data["event_date"] is not None

    def test_attendee_count_null_for_non_event(self, event_setup):
        s = event_setup
        gift = Thing.objects.create(
            code="EVGF02", type="GIFT_THING", owner=s["owner"], headline="Gift"
        )
        s["collection"].things.add(gift)
        res = s["owner_client"].get(f"/api/v1/things/{gift.code}/")
        assert res.status_code == 200
        assert res.data["attendee_count"] is None


class TestEventAttendEmail:
    def test_email_sent_on_attend(self, event_setup):
        s = event_setup
        with patch("core.views.events.send_event_attend_email") as mock_email:
            s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        mock_email.assert_called_once_with(
            attendee_name="Invitee",
            thing_headline="Reading Session",
            event_date=s["event"].event_date,
            owner_email="owner@test.com",
            attending=True,
        )

    def test_email_sent_on_cancel_attendance(self, event_setup):
        s = event_setup
        s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        with patch("core.views.events.send_event_attend_email") as mock_email:
            s["invitee_client"].post(f"/api/v1/things/{s['event'].code}/attend/")
        mock_email.assert_called_once_with(
            attendee_name="Invitee",
            thing_headline="Reading Session",
            event_date=s["event"].event_date,
            owner_email="owner@test.com",
            attending=False,
        )

    def test_email_uses_email_when_no_name(self, event_setup):
        s = event_setup
        nameless = User.objects.create(code="EVNM01", email="nameless@test.com", name="")
        s["collection"].invites.add(nameless)
        client = APIClient()
        client.force_authenticate(user=nameless)
        with patch("core.views.events.send_event_attend_email") as mock_email:
            client.post(f"/api/v1/things/{s['event'].code}/attend/")
        mock_email.assert_called_once_with(
            attendee_name="nameless@test.com",
            thing_headline="Reading Session",
            event_date=s["event"].event_date,
            owner_email="owner@test.com",
            attending=True,
        )
