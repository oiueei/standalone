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

from core.models import RSVP, Collection, InAppNotification, User
from core.services.email_service import send_broadcast_email
from core.services.invitation_service import deliver_invitation


@pytest.fixture
def broadcast_setup(db):
    """Create owner, invitees, and collection for broadcast tests."""
    owner = User.objects.create(code="BROWN1", email="lala@your-domain.test", name="Owner")
    invitee1 = User.objects.create(
        code="BRINV1", email="lala1@your-domain.test", name="Invitee One"
    )
    invitee2 = User.objects.create(code="BRINV2", email="lele@your-domain.test", name="Invitee Two")
    stranger = User.objects.create(code="BRSTR1", email="lili@your-domain.test", name="Stranger")

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
        assert email.reply_to == ["lala@your-domain.test"]

    def test_broadcast_skips_an_invitation_nobody_has_accepted(self, broadcast_setup):
        """A pending invitation is not membership: the group's message reaches
        the confirmed members and neither mails nor notifies the invited address."""
        collection = broadcast_setup["collection"]
        deliver_invitation(collection, "pending@your-domain.test", "Owner")
        pending = User.objects.get(email="pending@your-domain.test")
        assert RSVP.objects.filter(user_code=pending, target_code=collection.code).exists()
        mail.outbox.clear()

        resp = broadcast_setup["owner_client"].post(
            URL.format(collection.code), {"message": "Bring snacks please"}, format="json"
        )

        assert resp.status_code == 200
        assert resp.data["recipients"] == 2
        recipients = {addr for m in mail.outbox for addr in m.to}
        assert recipients == {"lala1@your-domain.test", "lele@your-domain.test"}
        assert not InAppNotification.objects.filter(
            user=pending, type=InAppNotification.Type.BROADCAST
        ).exists()
        assert InAppNotification.objects.filter(
            user=broadcast_setup["invitee1"], type=InAppNotification.Type.BROADCAST
        ).exists()

    def test_invitee_cannot_broadcast(self, broadcast_setup):
        """Only the owner can send broadcasts — and a denial sends nothing."""
        resp = broadcast_setup["invitee_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "Hello", "message": "Hi everyone"},
            format="json",
        )
        assert resp.status_code == 403
        assert len(mail.outbox) == 0

    def test_stranger_cannot_broadcast(self, broadcast_setup):
        """Unrelated users cannot broadcast — and a denial sends nothing."""
        resp = broadcast_setup["stranger_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "Hello", "message": "Hi everyone"},
            format="json",
        )
        assert resp.status_code == 403
        assert len(mail.outbox) == 0

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
        assert len(mail.outbox) == 0

    def test_broadcast_html_rejected(self, broadcast_setup):
        """HTML tags in the message are rejected by SafeTextField."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"message": "<script>alert(1)</script>"},
            format="json",
        )
        assert resp.status_code == 400
        assert len(mail.outbox) == 0

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
        collection_path = f"/stall/{broadcast_setup['collection'].code}"
        assert collection_path in email.body
        # HTML alternative
        html = email.alternatives[0][0]
        assert "Owner" in html
        assert "Broadcast Club" in html
        assert "New items added" in html
        assert collection_path in html

    def test_broadcast_link_opens_the_group_without_presuming_a_plea(self, broadcast_setup):
        """The link under a group message says where it goes — "Open the group" —
        in both halves of the email. It used to read "I can help!", a leftover of
        the WISH_THING call-for-help flow that shipped under every broadcast
        whatever it said ("the workshop is shut on Monday" → "I can help!")."""
        broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"message": "The workshop is shut on Monday"},
            format="json",
        )
        email = mail.outbox[0]
        html = email.alternatives[0][0]
        collection_path = f"/stall/{broadcast_setup['collection'].code}"
        labelled_url = email.body.split("Open the group: ", 1)[1].split()[0]
        assert labelled_url.endswith(collection_path)
        assert "Open the group</a>" in html
        for part in (email.body, html):
            assert "I can help" not in part

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
        """A broadcast resolves recipient prefs + footer tokens with two
        bulk User queries (``_filter_recipients`` + ``_lookup_users``), never a
        ``_lookup_user`` per recipient. The query count must be constant in the
        number of recipients — adding invitees adds zero queries."""
        owner = User.objects.create(code="BRBKO1", email="lolo@your-domain.test", name="Owner")
        first = [
            User.objects.create(code=f"BRBK0{i}", email=f"lala{i}@your-domain.test", name=f"Inv{i}")
            for i in range(1, 3)
        ]

        with CaptureQueriesContext(connection) as small:
            send_broadcast_email(
                "Owner", owner.email, "Club", "BRBKCL", "hi", [u.email for u in first]
            )
        assert len(mail.outbox) == 2

        rest = [
            User.objects.create(code=f"BRBK0{i}", email=f"lala{i}@your-domain.test", name=f"Inv{i}")
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
