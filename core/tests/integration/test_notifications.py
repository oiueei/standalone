"""
Integration tests for notification preferences.

Covers:
- _should_send helper: mandatory always on, activity/news respect user prefs, unknown email defaults to send.
- Representative Cat. 2 email (send_booking_decision_email) skips when notify_activity=False.
- Representative Cat. 3 email (send_digest_email) skips when notify_news=False.
- Cat. 1 email (send_magic_link_email) always sent regardless of prefs.
- PATCH /api/v1/users/{code}/ accepts notify_activity / notify_news.
- Token endpoint GET/PATCH round-trip; rejects invalid tokens.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.services.email_service import (
    CATEGORY_ACTIVITY,
    CATEGORY_MANDATORY,
    CATEGORY_NEWS,
    _should_send,
    make_notifications_token,
    send_booking_decision_email,
    send_digest_email,
    send_magic_link_email,
)


@pytest.fixture
def noti_user(db):
    return User.objects.create(code="NOTI01", email="noti1@test.com", name="Prefs User")


def test_should_send_mandatory_always_true(db, noti_user):
    noti_user.notify_activity = False
    noti_user.notify_news = False
    noti_user.save()
    assert _should_send(noti_user.email, CATEGORY_MANDATORY) is True


def test_should_send_respects_activity_and_news(db, noti_user):
    noti_user.notify_activity = False
    noti_user.notify_news = True
    noti_user.save()
    assert _should_send(noti_user.email, CATEGORY_ACTIVITY) is False
    assert _should_send(noti_user.email, CATEGORY_NEWS) is True


def test_should_send_unknown_email_defaults_to_true(db):
    assert _should_send("stranger@nowhere.test", CATEGORY_ACTIVITY) is True
    assert _should_send("stranger@nowhere.test", CATEGORY_NEWS) is True


def test_magic_link_always_sent_even_when_opted_out(db, noti_user):
    noti_user.notify_activity = False
    noti_user.notify_news = False
    noti_user.save()
    mail.outbox.clear()
    send_magic_link_email(noti_user.email, "http://example.com/magic/ABC123")
    assert len(mail.outbox) == 1


def test_activity_email_skipped_when_opted_out(db, noti_user):
    owner = User.objects.create(code="OWN001", email="owner@test.com", name="Owner")
    collection = Collection.objects.create(code="COL001", owner=owner, headline="Club")
    thing = Thing.objects.create(code="THG001", owner=owner, headline="Item")
    collection.things.add(thing)
    booking = BookingPeriod.objects.create(
        code="BKG001",
        thing_code=thing,
        requester_code=noti_user,
        requester_email=noti_user.email,
        owner_code=owner,
        status="ACCEPTED",
    )

    noti_user.notify_activity = False
    noti_user.save()
    mail.outbox.clear()
    send_booking_decision_email(booking, thing, accepted=True)
    assert len(mail.outbox) == 0

    noti_user.notify_activity = True
    noti_user.save()
    send_booking_decision_email(booking, thing, accepted=True)
    assert len(mail.outbox) == 1


def test_news_email_skipped_when_opted_out(db, noti_user):
    second = User.objects.create(code="NOTI02", email="noti2@test.com", name="Second")
    noti_user.notify_news = False
    noti_user.save()
    mail.outbox.clear()

    send_digest_email("Club", ["Thing A"], [noti_user.email, second.email])
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [second.email]


def test_patch_me_updates_prefs(db, noti_user):
    client = APIClient()
    token = RefreshToken.for_user(noti_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    resp = client.put(
        f"/api/v1/users/{noti_user.code}/",
        {"notify_activity": False, "notify_news": False},
        format="json",
    )
    assert resp.status_code == 200
    noti_user.refresh_from_db()
    assert noti_user.notify_activity is False
    assert noti_user.notify_news is False


def test_notifications_token_endpoint_round_trip(db, noti_user):
    client = APIClient()
    token = make_notifications_token(noti_user.code)

    resp = client.get(f"/api/v1/notifications/token/{token}/")
    assert resp.status_code == 200
    assert resp.json() == {"notify_activity": True, "notify_news": True}

    resp = client.patch(
        f"/api/v1/notifications/token/{token}/",
        {"notify_news": False},
        format="json",
    )
    assert resp.status_code == 200
    noti_user.refresh_from_db()
    assert noti_user.notify_news is False
    assert noti_user.notify_activity is True


def test_notifications_token_rejects_invalid(db):
    client = APIClient()
    resp = client.get("/api/v1/notifications/token/not-a-real-token/")
    assert resp.status_code == 401
