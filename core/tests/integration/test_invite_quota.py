"""
Integration tests for the shared daily invitation-email quota.

The per-view rate limits count *requests*, so one bulk request could still fan
out 100 emails — the quota counts the emails themselves, shared between the
single and bulk invite endpoints (see INVITE_EMAILS_PER_DAY in
core/views/collections.py). It follows RATELIMIT_ENABLE — off in the test
settings — so these tests switch it on with a local-memory cache, like
test_ratelimit.py does.
"""

from unittest.mock import patch

from django.core.cache import caches
from django.test import override_settings

from core.models import RSVP, User

SINGLE_URL = "/api/v1/collections/{code}/invite/"
BULK_URL = "/api/v1/collections/{code}/invite/bulk/"

QUOTA_SETTINGS = {
    "RATELIMIT_ENABLE": True,
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "invite-quota-test",
        }
    },
}


def _invite_rsvp_count(collection):
    return RSVP.objects.filter(
        target_code=collection.code, action=RSVP.Action.COLLECTION_INVITE
    ).count()


@override_settings(**QUOTA_SETTINGS, INVITE_EMAILS_PER_DAY=2)
@patch("core.views.collections.send_collection_invite_email")
def test_single_invite_blocks_after_daily_cap(mock_send, authenticated_client, collection):
    caches["default"].clear()
    for email in ("a@example.com", "b@example.com"):
        res = authenticated_client.post(
            SINGLE_URL.format(code=collection.code), {"email": email}, format="json"
        )
        assert res.status_code == 200

    res = authenticated_client.post(
        SINGLE_URL.format(code=collection.code), {"email": "c@example.com"}, format="json"
    )
    assert res.status_code == 429
    assert "error" in res.data
    assert mock_send.call_count == 2
    # The blocked request created neither RSVPs nor a User row.
    assert _invite_rsvp_count(collection) == 2
    assert not User.objects.filter(email="c@example.com").exists()


@override_settings(**QUOTA_SETTINGS, INVITE_EMAILS_PER_DAY=3)
@patch("core.views.collections.send_collection_invite_email")
def test_bulk_invite_caps_batch_and_reports_daily_limit(
    mock_send, authenticated_client, collection
):
    caches["default"].clear()
    invites = [{"email": f"u{i}@example.com"} for i in range(5)]
    res = authenticated_client.post(
        BULK_URL.format(code=collection.code), {"invites": invites}, format="json"
    )
    assert res.status_code == 200
    assert res.data["invited"] == 3
    assert [s["reason"] for s in res.data["skipped"]] == ["daily_limit", "daily_limit"]
    assert {s["email"] for s in res.data["skipped"]} == {"u3@example.com", "u4@example.com"}
    assert mock_send.call_count == 3
    assert _invite_rsvp_count(collection) == 3
    # Quota-skipped rows never reached get_or_create.
    assert not User.objects.filter(email="u3@example.com").exists()


@override_settings(**QUOTA_SETTINGS, INVITE_EMAILS_PER_DAY=2)
@patch("core.views.collections.send_collection_invite_email")
def test_quota_is_shared_between_single_and_bulk(mock_send, authenticated_client, collection):
    caches["default"].clear()
    res = authenticated_client.post(
        SINGLE_URL.format(code=collection.code), {"email": "one@example.com"}, format="json"
    )
    assert res.status_code == 200

    invites = [{"email": "two@example.com"}, {"email": "three@example.com"}]
    res = authenticated_client.post(
        BULK_URL.format(code=collection.code), {"invites": invites}, format="json"
    )
    assert res.status_code == 200
    assert res.data["invited"] == 1
    assert res.data["skipped"] == [{"email": "three@example.com", "reason": "daily_limit"}]
    assert mock_send.call_count == 2


@override_settings(**QUOTA_SETTINGS, INVITE_EMAILS_PER_DAY=1)
@patch("core.views.collections.send_collection_invite_email")
def test_bulk_invite_blocks_outright_when_quota_exhausted(
    mock_send, authenticated_client, collection
):
    caches["default"].clear()
    res = authenticated_client.post(
        SINGLE_URL.format(code=collection.code), {"email": "first@example.com"}, format="json"
    )
    assert res.status_code == 200

    res = authenticated_client.post(
        BULK_URL.format(code=collection.code),
        {"invites": [{"email": "x@example.com"}]},
        format="json",
    )
    assert res.status_code == 429
    assert "error" in res.data
    assert mock_send.call_count == 1


@override_settings(INVITE_EMAILS_PER_DAY=1)
@patch("core.views.collections.send_collection_invite_email")
def test_quota_follows_the_ratelimit_switch(mock_send, authenticated_client, collection):
    """RATELIMIT_ENABLE=False (the dev/test default) disables the quota too —
    same switch the django-ratelimit decorators read, so local development
    never trips an abuse guard."""
    for email in ("a@example.com", "b@example.com"):
        res = authenticated_client.post(
            SINGLE_URL.format(code=collection.code), {"email": email}, format="json"
        )
        assert res.status_code == 200
    assert mock_send.call_count == 2
