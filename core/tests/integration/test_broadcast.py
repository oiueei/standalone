"""
Integration tests for collection broadcast endpoint.
"""

from unittest.mock import patch

import pytest
from django.core import mail
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, User
from core.services.email_service import send_broadcast_email


@pytest.fixture
def broadcast_setup(db):
    """Create owner, invitees, and collection for broadcast tests."""
    owner = User.objects.create(code="BROWN1", email="browner@test.com", name="Owner")
    invitee1 = User.objects.create(code="BRINV1", email="brinv1@test.com", name="Invitee One")
    invitee2 = User.objects.create(code="BRINV2", email="brinv2@test.com", name="Invitee Two")
    stranger = User.objects.create(code="BRSTR1", email="brstr@test.com", name="Stranger")

    collection = Collection.objects.create(code="BRCOL1", owner=owner, headline="Broadcast Club")
    collection.invites.add(invitee1, invitee2)

    empty_collection = Collection.objects.create(code="BRCOL2", owner=owner, headline="Empty Club")

    owner_client = APIClient()
    owner_token = RefreshToken.for_user(owner)
    owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token.access_token}")

    invitee_client = APIClient()
    invitee_token = RefreshToken.for_user(invitee1)
    invitee_client.credentials(HTTP_AUTHORIZATION=f"Bearer {invitee_token.access_token}")

    stranger_client = APIClient()
    stranger_token = RefreshToken.for_user(stranger)
    stranger_client.credentials(HTTP_AUTHORIZATION=f"Bearer {stranger_token.access_token}")

    return {
        "owner": owner,
        "invitee1": invitee1,
        "invitee2": invitee2,
        "stranger": stranger,
        "collection": collection,
        "empty_collection": empty_collection,
        "owner_client": owner_client,
        "invitee_client": invitee_client,
        "stranger_client": stranger_client,
    }


URL = "/api/v1/collections/{}/broadcast/"


@pytest.mark.django_db
class TestCollectionBroadcast:
    def test_owner_can_broadcast(self, broadcast_setup):
        """Owner sends broadcast to all invitees."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"message": "Bring snacks please"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["recipients"] == 2
        assert len(mail.outbox) == 2

        # Subject is auto-generated as "Hey! {collection}" (no user-provided subject)
        email = mail.outbox[0]
        assert email.subject == "Hey! Broadcast Club"
        assert email.reply_to == ["browner@test.com"]

    def test_invitee_cannot_broadcast(self, broadcast_setup):
        """Only the owner can send broadcasts."""
        resp = broadcast_setup["invitee_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "Hello", "message": "Hi everyone"},
            format="json",
        )
        assert resp.status_code == 403

    def test_stranger_cannot_broadcast(self, broadcast_setup):
        """Unrelated users cannot broadcast."""
        resp = broadcast_setup["stranger_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "Hello", "message": "Hi everyone"},
            format="json",
        )
        assert resp.status_code == 403

    def test_broadcast_empty_collection(self, broadcast_setup):
        """Broadcast to collection with no invitees returns 400."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["empty_collection"].code),
            {"subject": "Hello", "message": "Anyone there?"},
            format="json",
        )
        assert resp.status_code == 400
        assert "No invitees" in resp.data["error"]

    def test_broadcast_missing_fields(self, broadcast_setup):
        """Broadcast without a message returns 400."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {},
            format="json",
        )
        assert resp.status_code == 400

    def test_broadcast_html_rejected(self, broadcast_setup):
        """HTML tags in the message are rejected by SafeTextField."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"message": "<script>alert(1)</script>"},
            format="json",
        )
        assert resp.status_code == 400

    def test_broadcast_email_content(self, broadcast_setup):
        """Broadcast email includes owner name, collection name, and message."""
        broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"message": "New items added"},
            format="json",
        )
        assert len(mail.outbox) == 2
        email = mail.outbox[0]
        # Plain text body
        assert "Owner" in email.body
        assert "Broadcast Club" in email.body
        assert "New items added" in email.body
        # Link to the collection that originated the message
        collection_path = f"/collections/{broadcast_setup['collection'].code}"
        assert collection_path in email.body
        # HTML alternative
        html = email.alternatives[0][0]
        assert "Owner" in html
        assert "Broadcast Club" in html
        assert "New items added" in html
        assert collection_path in html

    def test_broadcast_nonexistent_collection(self, broadcast_setup):
        """Broadcast to non-existent collection returns 404."""
        resp = broadcast_setup["owner_client"].post(
            "/api/v1/collections/XXXXXX/broadcast/",
            {"subject": "Hello", "message": "Hi"},
            format="json",
        )
        assert resp.status_code == 404

    def test_broadcast_sends_off_the_request_thread_in_production(self, broadcast_setup):
        """With EMAIL_SEND_ASYNC on, the send is dispatched to a daemon thread so a
        large group can't stall the response past Heroku's 30s window (H12) — yet
        every invitee still gets the email."""

        class _InlineThread:
            """Run the target synchronously so the test stays deterministic."""

            def __init__(self, target=None, daemon=None, **kwargs):
                self._target = target
                self.daemon = daemon

            def start(self):
                self._target()

        with override_settings(EMAIL_SEND_ASYNC=True):
            with patch("core.views.collections.threading.Thread", _InlineThread):
                resp = broadcast_setup["owner_client"].post(
                    URL.format(broadcast_setup["collection"].code),
                    {"message": "Async hello"},
                    format="json",
                )
        assert resp.status_code == 200
        assert resp.data["recipients"] == 2
        assert len(mail.outbox) == 2

    def test_broadcast_user_lookups_are_bulked_not_per_recipient(self):
        """CODE B2: a broadcast resolves recipient prefs + footer tokens with two
        bulk User queries (``_filter_recipients`` + ``_lookup_users``), never a
        ``_lookup_user`` per recipient. The query count must be constant in the
        number of recipients — adding invitees adds zero queries."""
        owner = User.objects.create(code="BRBKO1", email="brbko@test.com", name="Owner")
        first = [
            User.objects.create(code=f"BRBK0{i}", email=f"brbk{i}@test.com", name=f"Inv{i}")
            for i in range(1, 3)
        ]

        with CaptureQueriesContext(connection) as small:
            send_broadcast_email(
                "Owner", owner.email, "Club", "BRBKCL", "hi", [u.email for u in first]
            )
        assert len(mail.outbox) == 2

        rest = [
            User.objects.create(code=f"BRBK0{i}", email=f"brbk{i}@test.com", name=f"Inv{i}")
            for i in range(3, 7)
        ]
        with CaptureQueriesContext(connection) as big:
            send_broadcast_email(
                "Owner",
                owner.email,
                "Club",
                "BRBKCL",
                "hi",
                [u.email for u in first + rest],
            )
        assert len(mail.outbox) == 8  # 2 from the first send + 6 here

        assert len(big) == len(small), (
            f"N+1 in broadcast send: {len(small)} queries for 2 recipients vs "
            f"{len(big)} for 6 — _lookup_user is firing per recipient"
        )
