"""Integration tests: the Event log is written at each instrumented call site.

Fixtures build their objects through the ORM (not the API), so the ``events`` table
starts empty in every test and exact counts can be asserted.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, BookingPeriod, Collection, Event, User


def client_for(user):
    """A dedicated authenticated client — the conftest ``authenticated_client``/
    ``authenticated_client2`` share one APIClient, so owner+guest flows need
    separate instances."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db
class TestCollectionEvents:
    def test_create_collection_logs_event(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/v1/collections/", {"headline": "Tracked"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        event = Event.objects.get(kind=Event.Kind.COLLECTION_CREATED)
        assert event.actor_code == user.code
        assert event.collection_code == response.data["code"]

    def test_delete_collection_logs_event(self, authenticated_client, user, collection):
        code = collection.code
        response = authenticated_client.delete(f"/api/v1/collections/{code}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        event = Event.objects.get(kind=Event.Kind.COLLECTION_DELETED)
        assert event.actor_code == user.code
        assert event.collection_code == code


@pytest.mark.django_db
class TestThingEvents:
    def test_add_thing_logs_event(self, authenticated_client, user, collection):
        response = authenticated_client.post(
            "/api/v1/things/",
            {"headline": "Widget", "type": "GIFT_THING", "collection_code": collection.code},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        event = Event.objects.get(kind=Event.Kind.THING_ADDED)
        assert event.actor_code == user.code
        assert event.collection_code == collection.code
        assert event.thing_code == response.data["code"]
        assert event.thing_type == "GIFT_THING"

    def test_delete_thing_logs_event(self, authenticated_client, user, thing):
        code, ttype = thing.code, thing.type
        response = authenticated_client.delete(f"/api/v1/things/{code}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        event = Event.objects.get(kind=Event.Kind.THING_REMOVED)
        assert event.actor_code == user.code
        assert event.thing_code == code
        assert event.thing_type == ttype


@pytest.mark.django_db
class TestMembershipEvents:
    def test_invite_new_email_logs_user_joined(self, authenticated_client, collection):
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/invite/",
            {"email": "brandnew@test.com"},
            format="json",
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        new_user = User.objects.get(email="brandnew@test.com")
        assert Event.objects.filter(kind=Event.Kind.USER_JOINED, actor_code=new_user.code).exists()

    def test_accept_invite_logs_member_joined(self, api_client, user2, collection):
        rsvp = RSVP.objects.create(
            user_code=user2,
            user_email=user2.email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=collection.code,
        )
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert response.status_code == status.HTTP_200_OK
        event = Event.objects.get(kind=Event.Kind.MEMBER_JOINED)
        assert event.actor_code == user2.code
        assert event.collection_code == collection.code

    def test_leave_collection_logs_member_left(self, authenticated_client2, user2, collection):
        collection.invites.add(user2)
        response = authenticated_client2.post(f"/api/v1/collections/{collection.code}/leave/")
        assert response.status_code == status.HTTP_200_OK
        event = Event.objects.get(kind=Event.Kind.MEMBER_LEFT)
        assert event.actor_code == user2.code
        assert event.collection_code == collection.code

    def test_popin_logs_user_joined_and_member_joined(self, api_client, user):
        onboarding = Collection.objects.create(
            code="ONBRD1", owner=user, headline="Welcome", is_onboarding=True
        )
        response = api_client.post(
            "/api/v1/auth/pop-in/", {"email": "popin@test.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        new_user = User.objects.get(email="popin@test.com")
        assert Event.objects.filter(kind=Event.Kind.USER_JOINED, actor_code=new_user.code).exists()
        assert Event.objects.filter(
            kind=Event.Kind.MEMBER_JOINED,
            actor_code=new_user.code,
            collection_code=onboarding.code,
        ).exists()


@pytest.mark.django_db
class TestFAQEvent:
    def test_ask_faq_logs_event(self, authenticated_client2, user2, thing, collection):
        collection.invites.add(user2)
        response = authenticated_client2.post(
            f"/api/v1/things/{thing.code}/faq/",
            {"question": "Is it available?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        event = Event.objects.get(kind=Event.Kind.FAQ_ASKED)
        assert event.actor_code == user2.code
        assert event.thing_code == thing.code


@pytest.mark.django_db
class TestHoldEvents:
    def test_request_and_accept_hold_log_events(self, user, user2, thing, collection):
        collection.invites.add(user2)
        owner_client, guest_client = client_for(user), client_for(user2)

        # Guest requests a hold on the GIFT thing.
        req = guest_client.post(f"/api/v1/things/{thing.code}/request/")
        assert req.status_code == status.HTTP_200_OK
        requested = Event.objects.get(kind=Event.Kind.HOLD_REQUESTED)
        assert requested.actor_code == user2.code
        assert requested.thing_code == thing.code
        assert requested.thing_type == "GIFT_THING"

        # Owner accepts it.
        booking = BookingPeriod.objects.get(thing_code=thing, requester_code=user2)
        acc = owner_client.post(f"/api/v1/bookings/{booking.code}/accept/")
        assert acc.status_code == status.HTTP_200_OK
        accepted = Event.objects.get(kind=Event.Kind.HOLD_ACCEPTED)
        assert accepted.actor_code == user2.code
        assert accepted.thing_code == thing.code

    def test_reject_hold_logs_no_accepted_event(self, user, user2, thing, collection):
        collection.invites.add(user2)
        owner_client, guest_client = client_for(user), client_for(user2)

        guest_client.post(f"/api/v1/things/{thing.code}/request/")
        booking = BookingPeriod.objects.get(thing_code=thing, requester_code=user2)
        rej = owner_client.post(f"/api/v1/bookings/{booking.code}/reject/")
        assert rej.status_code == status.HTTP_200_OK
        assert Event.objects.filter(kind=Event.Kind.HOLD_REQUESTED).count() == 1
        assert Event.objects.filter(kind=Event.Kind.HOLD_ACCEPTED).count() == 0
