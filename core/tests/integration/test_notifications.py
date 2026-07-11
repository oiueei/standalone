"""
Integration tests for notification preferences and in-app inbox notifications.

Covers:
- _should_send helper: mandatory always on, activity/news respect user prefs,
  unknown email defaults to send.
- Representative Cat. 2 email (send_booking_decision_email) skips when notify_activity=False.
- Representative Cat. 3 email (send_digest_email) skips when notify_news=False.
- Cat. 1 email (send_magic_link_email) always sent regardless of prefs.
- PATCH /api/v1/users/{code}/ accepts notify_activity / notify_news.
- Token endpoint GET/PATCH round-trip; rejects invalid tokens.
- InAppNotification created for all user-action-triggered events.
"""

from unittest.mock import patch

import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import FAQ, RSVP, BookingPeriod, Collection, Thing, User
from core.models.notification import InAppNotification
from core.services.email_service import (
    CATEGORY_ACTIVITY,
    CATEGORY_MANDATORY,
    CATEGORY_NEWS,
    _should_send,
    make_notifications_token,
    send_booking_decision_email,
    send_booking_unavailable_email,
    send_digest_email,
    send_invite_rejected_email,
    send_magic_link_email,
)


@pytest.fixture
def noti_user(db):
    return User.objects.create(
        code="NOTI01", email="noti1@test.com", name="Prefs User", notify_news=True
    )


def test_new_user_defaults_news_off_activity_on(db):
    """DESIGN §6: news (Cat. 3) is opt-in — a brand-new user starts opted out,
    while transactional activity (Cat. 2) stays on."""
    fresh = User.objects.create(code="NEW01", email="new@test.com", name="Fresh")
    assert fresh.notify_news is False
    assert fresh.notify_activity is True


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


def test_booking_unavailable_email_content(db, noti_user):
    """Previously only asserted through a mock in test_share_transfer.py — never
    verified a real message actually reached mail.outbox with the right content."""
    owner = User.objects.create(code="OWN002", email="owner2@test.com", name="Owner Two")
    thing = Thing.objects.create(code="THG002", owner=owner, headline="Popular Item")
    booking = BookingPeriod.objects.create(
        code="BKG002",
        thing_code=thing,
        requester_code=noti_user,
        requester_email=noti_user.email,
        owner_code=owner,
        status="REJECTED",
    )
    mail.outbox.clear()
    send_booking_unavailable_email(booking, thing)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [noti_user.email]
    assert "Popular Item" in mail.outbox[0].body
    assert "Popular Item" in mail.outbox[0].alternatives[0][0]


def test_invite_rejected_email_content(db):
    """Previously only asserted through mocks in test_views.py/test_notifications.py
    — never verified a real message reached mail.outbox with the right content."""
    mail.outbox.clear()
    send_invite_rejected_email("Jamie", "Book Club", "owner3@test.com")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["owner3@test.com"]
    assert "Jamie" in mail.outbox[0].body
    assert "Book Club" in mail.outbox[0].body


def test_news_email_skipped_when_opted_out(db, noti_user):
    second = User.objects.create(
        code="NOTI02", email="noti2@test.com", name="Second", notify_news=True
    )
    noti_user.notify_news = False
    noti_user.save()
    mail.outbox.clear()

    send_digest_email("Club", "COLL01", ["Thing A"], [noti_user.email, second.email])
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
    token = make_notifications_token(noti_user)

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


def test_notifications_token_is_salt_scoped(db, noti_user):
    """L3: the prefs token is a TimestampSigner signature scoped to the
    'notifications-prefs' salt — a valid one resolves to the user, but a
    signature minted with another salt (or garbage) is rejected."""
    from django.core.signing import TimestampSigner

    from core.services.email_service import verify_notifications_token

    assert verify_notifications_token(make_notifications_token(noti_user)) == noti_user.code
    # Same payload, different salt → not a valid prefs token here.
    other = TimestampSigner(salt="something-else").sign(noti_user.code)
    assert verify_notifications_token(other) is None
    assert verify_notifications_token("garbage") is None


# ---------------------------------------------------------------------------
# InAppNotification creation tests
# ---------------------------------------------------------------------------


def _make_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def _make_booking(owner, requester, thing, thing_type="GIFT_THING"):
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing_type,
        requester_code=requester,
        requester_email=requester.email,
        owner_code=owner,
        status="PENDING",
    )


@pytest.fixture
def two_users(db):
    owner = User.objects.create(code="OWN001", email="owner@test.com", name="Owner")
    requester = User.objects.create(code="REQ001", email="requester@test.com", name="Requester")
    return owner, requester


@pytest.fixture
def thing_with_collection(db, two_users):
    owner, requester = two_users
    thing = Thing.objects.create(code="THG001", owner=owner, headline="My Thing", type="GIFT_THING")
    collection = Collection.objects.create(code="COL001", owner=owner, headline="My Collection")
    collection.things.add(thing)
    collection.invites.add(requester)
    return thing, collection


@pytest.mark.django_db
def test_booking_accept_via_api_creates_in_app_notification(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    booking = _make_booking(owner, requester, thing)
    client = _make_client(owner)

    with patch("core.services.email_service.send_booking_decision_email"):
        resp = client.post(f"/api/v1/bookings/{booking.code}/accept/")

    assert resp.status_code == status.HTTP_200_OK
    notif = InAppNotification.objects.get(
        user=requester, type=InAppNotification.Type.BOOKING_ACCEPTED
    )
    assert notif.payload["thing_headline"] == thing.headline
    assert notif.payload["owner_name"] == owner.name


@pytest.mark.django_db
def test_booking_reject_via_api_creates_in_app_notification(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    booking = _make_booking(owner, requester, thing)
    client = _make_client(owner)

    with patch("core.services.email_service.send_booking_decision_email"):
        resp = client.post(f"/api/v1/bookings/{booking.code}/reject/")

    assert resp.status_code == status.HTTP_200_OK
    notif = InAppNotification.objects.get(
        user=requester, type=InAppNotification.Type.BOOKING_REJECTED
    )
    assert notif.payload["thing_headline"] == thing.headline


@pytest.mark.django_db
def test_booking_accept_via_rsvp_creates_in_app_notification(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    booking = _make_booking(owner, requester, thing)
    rsvp = RSVP.objects.create(
        user_code=owner,
        user_email=owner.email,
        action="BOOKING_ACCEPT",
        target_code=booking.code,
    )
    client = APIClient()

    with patch("core.services.email_service.send_booking_decision_email"):
        resp = client.post(f"/api/v1/auth/verify/{rsvp.token}/")

    assert resp.status_code == status.HTTP_200_OK
    assert InAppNotification.objects.filter(
        user=requester, type=InAppNotification.Type.BOOKING_ACCEPTED
    ).exists()


@pytest.mark.django_db
def test_booking_request_creates_in_app_notification_for_owner(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    client = _make_client(requester)

    with (
        patch("core.services.email_service.send_booking_request_email"),
        patch("core.services.email_service.send_booking_confirmation_email"),
    ):
        resp = client.post(f"/api/v1/things/{thing.code}/request/", {}, format="json")

    assert resp.status_code == status.HTTP_201_CREATED
    notif = InAppNotification.objects.get(user=owner, type=InAppNotification.Type.BOOKING_REQUESTED)
    assert notif.payload["thing_headline"] == thing.headline
    assert notif.payload["requester_name"] == requester.name


@pytest.mark.django_db
def test_faq_question_creates_in_app_notification_for_owner(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    client = _make_client(requester)

    with patch("core.views.faq.send_faq_question_email"):
        resp = client.post(
            f"/api/v1/things/{thing.code}/faq/", {"question": "Is this available?"}, format="json"
        )

    assert resp.status_code == status.HTTP_201_CREATED
    notif = InAppNotification.objects.get(user=owner, type=InAppNotification.Type.FAQ_QUESTION)
    assert notif.payload["thing_headline"] == thing.headline
    assert notif.payload["questioner_name"] == requester.name


@pytest.mark.django_db
def test_faq_answer_creates_in_app_notification_for_questioner(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    faq = FAQ.objects.create(
        code="FAQ001",
        thing=thing,
        questioner=requester,
        question="Is this available?",
    )
    client = _make_client(owner)

    with patch("core.views.faq.send_faq_answer_email"):
        resp = client.post(f"/api/v1/faq/{faq.code}/answer/", {"answer": "Yes!"}, format="json")

    assert resp.status_code == status.HTTP_200_OK
    notif = InAppNotification.objects.get(user=requester, type=InAppNotification.Type.FAQ_ANSWERED)
    assert notif.payload["thing_headline"] == thing.headline


@pytest.mark.django_db
def test_faq_hide_creates_in_app_notification_for_questioner(two_users, thing_with_collection):
    owner, requester = two_users
    thing, _ = thing_with_collection
    faq = FAQ.objects.create(
        code="FAQ002",
        thing=thing,
        questioner=requester,
        question="Is this available?",
    )
    client = _make_client(owner)

    with patch("core.views.faq.send_faq_hide_email"):
        resp = client.post(f"/api/v1/faq/{faq.code}/hide/")

    assert resp.status_code == status.HTTP_200_OK
    notif = InAppNotification.objects.get(user=requester, type=InAppNotification.Type.FAQ_HIDDEN)
    assert notif.payload["thing_headline"] == thing.headline


@pytest.mark.django_db
def test_invite_rejected_creates_in_app_notification_for_owner(two_users):
    owner, invitee = two_users
    collection = Collection.objects.create(code="COL003", owner=owner, headline="My Collection")
    rsvp = RSVP.objects.create(
        user_code=invitee,
        user_email=invitee.email,
        action="COLLECTION_REJECT",
        target_code=collection.code,
    )
    client = APIClient()

    with patch("core.views.auth.send_invite_rejected_email"):
        resp = client.get(f"/api/v1/auth/verify/{rsvp.token}/")

    assert resp.status_code == status.HTTP_200_OK
    notif = InAppNotification.objects.get(user=owner, type=InAppNotification.Type.INVITE_REJECTED)
    assert notif.payload["collection_headline"] == collection.headline
    assert notif.payload["invitee_name"] == invitee.name


@pytest.mark.django_db
def test_collection_revoke_creates_in_app_notification_for_removed_user(two_users):
    owner, invitee = two_users
    collection = Collection.objects.create(code="COL004", owner=owner, headline="My Collection")
    collection.invites.add(invitee)
    client = _make_client(owner)

    with patch("core.views.collections.send_collection_revoke_email"):
        resp = client.delete(
            f"/api/v1/collections/{collection.code}/invite/",
            {"user_code": invitee.code},
            format="json",
        )

    assert resp.status_code == status.HTTP_200_OK
    notif = InAppNotification.objects.get(
        user=invitee, type=InAppNotification.Type.COLLECTION_REVOKED
    )
    assert notif.payload["collection_headline"] == collection.headline


# ---------------------------------------------------------------------------
# Inbox endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_inbox_get_returns_notifications_for_authenticated_user(two_users):
    owner, requester = two_users
    InAppNotification.objects.create(
        code="NTF001",
        user=owner,
        type=InAppNotification.Type.BOOKING_ACCEPTED,
        payload={"thing_headline": "Widget"},
    )
    InAppNotification.objects.create(
        code="NTF002",
        user=requester,
        type=InAppNotification.Type.BOOKING_REJECTED,
        payload={"thing_headline": "Gadget"},
    )
    client = _make_client(owner)

    resp = client.get("/api/v1/inbox/")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.data) == 1
    assert resp.data[0]["code"] == "NTF001"
    assert resp.data[0]["type"] == InAppNotification.Type.BOOKING_ACCEPTED
    assert resp.data[0]["payload"]["thing_headline"] == "Widget"


@pytest.mark.django_db
def test_inbox_get_returns_empty_list_when_no_notifications(two_users):
    owner, _ = two_users
    client = _make_client(owner)

    resp = client.get("/api/v1/inbox/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data == []


@pytest.mark.django_db
def test_inbox_get_requires_authentication():
    client = APIClient()
    resp = client.get("/api/v1/inbox/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_inbox_delete_removes_notification(two_users):
    owner, _ = two_users
    notif = InAppNotification.objects.create(
        code="NTF003",
        user=owner,
        type=InAppNotification.Type.BOOKING_ACCEPTED,
        payload={},
    )
    client = _make_client(owner)

    resp = client.delete(f"/api/v1/inbox/{notif.code}/")

    assert resp.status_code == 204
    assert not InAppNotification.objects.filter(code="NTF003").exists()


@pytest.mark.django_db
def test_inbox_delete_cannot_remove_other_users_notification(two_users):
    owner, requester = two_users
    notif = InAppNotification.objects.create(
        code="NTF004",
        user=owner,
        type=InAppNotification.Type.BOOKING_ACCEPTED,
        payload={},
    )
    client = _make_client(requester)

    resp = client.delete(f"/api/v1/inbox/{notif.code}/")

    assert resp.status_code == 404
    assert InAppNotification.objects.filter(code="NTF004").exists()


@pytest.mark.django_db
def test_inbox_delete_nonexistent_notification_returns_404(two_users):
    owner, _ = two_users
    client = _make_client(owner)

    resp = client.delete("/api/v1/inbox/ZZZZZZ/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_inbox_get_on_item_route_returns_405_not_500(two_users):
    # GET /inbox/{code}/ is not a feature (only the collection is listable). The
    # crossed route must return a clean 405, not a TypeError-driven 500.
    owner, _ = two_users
    client = _make_client(owner)

    resp = client.get("/api/v1/inbox/ANYCOD/")

    assert resp.status_code == 405


@pytest.mark.django_db
def test_inbox_delete_on_collection_route_returns_405_not_500(two_users):
    # DELETE /inbox/ has no target notification — a clean 405, not a 500.
    owner, _ = two_users
    client = _make_client(owner)

    resp = client.delete("/api/v1/inbox/")

    assert resp.status_code == 405
