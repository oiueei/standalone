"""
Integration tests for collection broadcast endpoint.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, User


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
            {"subject": "Meeting tonight", "message": "Bring snacks please"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["recipients"] == 2
        assert len(mail.outbox) == 2

        # Check email content
        email = mail.outbox[0]
        assert "[Broadcast Club]" in email.subject
        assert "Meeting tonight" in email.subject
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
        """Broadcast without required fields returns 400."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "Hello"},
            format="json",
        )
        assert resp.status_code == 400

    def test_broadcast_html_rejected(self, broadcast_setup):
        """HTML tags in subject/message are rejected by SafeHeadlineField/SafeTextField."""
        resp = broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "<script>alert(1)</script>", "message": "Normal message"},
            format="json",
        )
        assert resp.status_code == 400

    def test_broadcast_email_content(self, broadcast_setup):
        """Broadcast email includes owner name, collection name, and message."""
        broadcast_setup["owner_client"].post(
            URL.format(broadcast_setup["collection"].code),
            {"subject": "Update", "message": "New items added"},
            format="json",
        )
        assert len(mail.outbox) == 2
        email = mail.outbox[0]
        # Plain text body
        assert "Owner" in email.body
        assert "Broadcast Club" in email.body
        assert "New items added" in email.body
        # HTML alternative
        html = email.alternatives[0][0]
        assert "Owner" in html
        assert "Broadcast Club" in html
        assert "New items added" in html

    def test_broadcast_nonexistent_collection(self, broadcast_setup):
        """Broadcast to non-existent collection returns 404."""
        resp = broadcast_setup["owner_client"].post(
            "/api/v1/collections/XXXXXX/broadcast/",
            {"subject": "Hello", "message": "Hi"},
            format="json",
        )
        assert resp.status_code == 404
