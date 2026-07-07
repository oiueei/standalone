"""
Integration tests for bulk-inviting guests to a collection from a CSV.

Covers the best-effort classification (invited vs skipped: invalid / duplicate /
already_member / already_invited), the owner-only gate, the row cap, the optional
name handling (pre-set on new users, HTML dropped), and that one email is sent
per actually-invited address.
"""

from unittest.mock import patch

from django.core import mail
from django.test import override_settings

from core.models import RSVP, User

URL = "/api/v1/collections/{code}/invite/bulk/"


class _SyncThread:
    """Stand-in for threading.Thread that runs its target immediately, so the
    EMAIL_SEND_ASYNC=True path can be tested deterministically without a real
    background thread."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class TestBulkInvite:
    @patch("core.views.collections.send_collection_invite_email")
    def test_invites_new_emails_and_presets_name(self, mock_send, authenticated_client, collection):
        invites = [{"email": "alice@example.com"}, {"email": "BOB@example.com", "name": "Bob"}]
        res = authenticated_client.post(
            URL.format(code=collection.code), {"invites": invites}, format="json"
        )
        assert res.status_code == 200
        assert res.data["invited"] == 2
        assert res.data["skipped"] == []
        assert res.data["total"] == 2
        # An accept + reject RSVP pair per invitee.
        assert (
            RSVP.objects.filter(
                target_code=collection.code, action=RSVP.Action.COLLECTION_INVITE
            ).count()
            == 2
        )
        # Email lower-cased and the optional name pre-set on the new user.
        bob = User.objects.get(email="bob@example.com")
        assert bob.name == "Bob"
        # One invitation email per invited address.
        assert mock_send.call_count == 2

    @patch("core.views.collections.send_collection_invite_email")
    def test_best_effort_classifies_each_row(self, mock_send, authenticated_client, collection):
        member = User.objects.create(code="MEMBR1", email="member@example.com", name="M")
        collection.invites.add(member)
        pending = User.objects.create(code="PEND01", email="pending@example.com")
        RSVP.objects.create(
            user_code=pending,
            user_email=pending.email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=collection.code,
        )
        invites = [
            {"email": "new@example.com"},
            {"email": "new@example.com"},  # duplicate within the batch
            {"email": "notanemail"},  # invalid
            {"email": "member@example.com"},  # already a member
            {"email": "pending@example.com"},  # already invited (pending RSVP)
        ]
        res = authenticated_client.post(
            URL.format(code=collection.code), {"invites": invites}, format="json"
        )
        assert res.status_code == 200
        assert res.data["invited"] == 1
        reasons = {s["email"]: s["reason"] for s in res.data["skipped"]}
        assert reasons["new@example.com"] == "duplicate"
        assert reasons["notanemail"] == "invalid"
        assert reasons["member@example.com"] == "already_member"
        assert reasons["pending@example.com"] == "already_invited"
        assert mock_send.call_count == 1

    @patch("core.views.collections.send_collection_invite_email")
    def test_html_name_is_dropped_but_address_still_invited(
        self, mock_send, authenticated_client, collection
    ):
        res = authenticated_client.post(
            URL.format(code=collection.code),
            {"invites": [{"email": "c@example.com", "name": "<script>x</script>"}]},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["invited"] == 1
        carol = User.objects.get(email="c@example.com")
        assert not carol.name  # malformed name dropped, not stored
        assert mock_send.call_count == 1

    def test_non_owner_is_forbidden(self, authenticated_client2, collection):
        res = authenticated_client2.post(
            URL.format(code=collection.code),
            {"invites": [{"email": "x@example.com"}]},
            format="json",
        )
        assert res.status_code == 403
        assert not RSVP.objects.filter(target_code=collection.code).exists()

    def test_too_many_rows_rejected(self, authenticated_client, collection):
        invites = [{"email": f"u{i}@example.com"} for i in range(101)]
        res = authenticated_client.post(
            URL.format(code=collection.code), {"invites": invites}, format="json"
        )
        assert res.status_code == 400
        assert not RSVP.objects.filter(target_code=collection.code).exists()

    def test_empty_list_rejected(self, authenticated_client, collection):
        res = authenticated_client.post(
            URL.format(code=collection.code), {"invites": []}, format="json"
        )
        assert res.status_code == 400

    @override_settings(EMAIL_SEND_ASYNC=True)
    def test_sends_emails_on_daemon_thread_when_email_send_async(
        self, authenticated_client, collection
    ):
        """_send_bulk_invites's EMAIL_SEND_ASYNC=True branch (production) was
        never exercised — tests always ran with it off."""
        mail.outbox.clear()
        with patch("core.views.collections.threading.Thread", _SyncThread):
            res = authenticated_client.post(
                URL.format(code=collection.code),
                {"invites": [{"email": "async@example.com"}]},
                format="json",
            )
        assert res.status_code == 200
        assert res.data["invited"] == 1
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["async@example.com"]
