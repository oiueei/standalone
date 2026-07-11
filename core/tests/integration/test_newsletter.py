"""
Integration tests for weekly activity newsletter (F14).
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
import time_machine
from django.core.management import call_command
from django.utils import timezone

from core.models import Collection, Thing
from core.models.transfer import ThingTransfer

# Fixed so the fixture data below is deterministically inside the newsletter's
# [monday-7, monday) window regardless of which real-world day the suite runs on
# (a dynamic "next Monday from today" computation put the fixture created
# timestamp exactly at `until` — excluded by `lt` — whenever today already was a
# Monday, making the assertions below pass vacuously).
MONDAY = date(2026, 4, 20)


@pytest.fixture
def share_collection(db, user):
    """Create a COMMUNITY share collection with newsletter enabled."""
    return Collection.objects.create(
        code="SHNEWS",
        owner=user,
        headline="Share Newsletter Collection",
        mode="COMMUNITY",
        is_share=True,
        newsletter_enabled=True,
    )


@pytest.fixture
def non_share_collection(db, user):
    """Create a collection without newsletter."""
    return Collection.objects.create(
        code="NOSHNW",
        owner=user,
        headline="Normal Collection",
        mode="COMMUNITY",
    )


@pytest.fixture
def share_thing_in_collection(db, user, share_collection):
    """Create a SHARE_THING in the share collection, created within the last week."""
    t = Thing.objects.create(
        code="SHNT01",
        type="SHARE_THING",
        owner=user,
        headline="Shared Item One",
    )
    share_collection.things.add(t)
    return t


@pytest.mark.django_db
class TestNewsletterCommand:
    """Tests for the send_digests management command newsletter functionality."""

    @patch("core.management.commands.send_digests.send_newsletter_email")
    def test_newsletter_sent_on_monday(self, mock_send, user, user2, share_collection):
        """Newsletter should be sent on Mondays for share collections."""
        share_collection.invites.add(user2)
        with time_machine.travel(MONDAY):
            t = Thing.objects.create(
                code="NWT001",
                type="SHARE_THING",
                owner=user,
                headline="New Shared Item",
                created=timezone.now() - timedelta(days=1),
            )
            share_collection.things.add(t)

            out = StringIO()
            call_command("send_digests", stdout=out)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["collection_headline"] == "Share Newsletter Collection"
        assert kwargs["emails"] == [user2.email]
        assert kwargs["new_thing_headlines"] == ["New Shared Item"]

    @patch("core.management.commands.send_digests.send_newsletter_email")
    def test_newsletter_skipped_for_non_share(self, mock_send, user, user2, non_share_collection):
        """Newsletter should not be sent for collections without newsletter_enabled."""
        non_share_collection.invites.add(user2)
        with time_machine.travel(MONDAY):
            t = Thing.objects.create(
                code="NWT002",
                type="SHARE_THING",
                owner=user,
                headline="Some Item",
                created=timezone.now() - timedelta(days=1),
            )
            non_share_collection.things.add(t)

            out = StringIO()
            call_command("send_digests", stdout=out)

        mock_send.assert_not_called()

    @patch("core.management.commands.send_digests.send_newsletter_email")
    def test_newsletter_skipped_when_no_activity(self, mock_send, user, user2, share_collection):
        """Newsletter should not be sent when there are no new things or transfers."""
        share_collection.invites.add(user2)
        # No things, no transfers
        with time_machine.travel(MONDAY):
            out = StringIO()
            call_command("send_digests", stdout=out)

        mock_send.assert_not_called()

    @patch("core.management.commands.send_digests.send_newsletter_email")
    def test_newsletter_includes_transfers(self, mock_send, user, user2, share_collection):
        """Newsletter should render a real ownership-change entry alongside the
        new-thing headline."""
        share_collection.invites.add(user2)
        with time_machine.travel(MONDAY):
            t = Thing.objects.create(
                code="NWT003",
                type="SHARE_THING",
                owner=user,
                headline="Transferred Item",
                created=timezone.now() - timedelta(days=1),
            )
            share_collection.things.add(t)
            ThingTransfer.objects.create(
                thing=t,
                from_user=user,
                to_user=user2,
                lent_date=MONDAY - timedelta(days=1),
            )

            out = StringIO()
            call_command("send_digests", stdout=out)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["transfer_entries"] == [
            {
                "date": MONDAY - timedelta(days=1),
                "thing": "Transferred Item",
                "from_name": user.display_name,
                "to_name": user2.display_name,
            }
        ]

    @patch("core.management.commands.send_digests.send_newsletter_email")
    def test_newsletter_skipped_without_invitees(self, mock_send, user, share_collection):
        """Newsletter should not be sent when collection has no invitees."""
        with time_machine.travel(MONDAY):
            t = Thing.objects.create(
                code="NWT004",
                type="SHARE_THING",
                owner=user,
                headline="Lonely Item",
                created=timezone.now() - timedelta(days=1),
            )
            share_collection.things.add(t)

            out = StringIO()
            call_command("send_digests", stdout=out)

        mock_send.assert_not_called()


@pytest.mark.django_db
class TestDigestErrorResilience:
    """A failure sending one collection's digest/newsletter must not abort the
    daily cron — the per-collection try/except logs a warning and continues to
    the next collection (CODE C19). Without that guard a single bad row would
    suppress every later collection's email and 500 the scheduler job."""

    @patch("core.management.commands.send_digests.send_digest_email")
    def test_digest_continues_after_a_collection_fails(self, mock_send, user, user2):
        mock_send.side_effect = [RuntimeError("boom"), None]
        with time_machine.travel(MONDAY):
            for code in ("DGCFA1", "DGCFA2"):
                c = Collection.objects.create(
                    code=code,
                    owner=user,
                    headline=code,
                    digest_frequency=Collection.DigestFrequency.WEEKLY,
                )
                c.invites.add(user2)
                t = Thing.objects.create(
                    code=f"T{code}",
                    type="GIFT_THING",
                    owner=user,
                    headline=code,
                    created=timezone.now() - timedelta(days=1),
                )
                c.things.add(t)

            out, err = StringIO(), StringIO()
            call_command("send_digests", stdout=out, stderr=err)

        # Both collections were attempted despite the first raise — the loop
        # did not abort.
        assert mock_send.call_count == 2
        assert "failed" in err.getvalue()  # the failure was logged, not swallowed silently

    @patch("core.management.commands.send_digests.send_newsletter_email")
    def test_newsletter_continues_after_a_collection_fails(self, mock_send, user, user2):
        mock_send.side_effect = [RuntimeError("boom"), None]
        with time_machine.travel(MONDAY):
            for code in ("NLCFA1", "NLCFA2"):
                c = Collection.objects.create(
                    code=code,
                    owner=user,
                    headline=code,
                    mode="COMMUNITY",
                    is_share=True,
                    newsletter_enabled=True,
                )
                c.invites.add(user2)
                t = Thing.objects.create(
                    code=f"T{code}",
                    type="SHARE_THING",
                    owner=user,
                    headline=code,
                    created=timezone.now() - timedelta(days=1),
                )
                c.things.add(t)

            out, err = StringIO(), StringIO()
            call_command("send_digests", stdout=out, stderr=err)

        assert mock_send.call_count == 2
        assert "failed" in err.getvalue()


@pytest.mark.django_db
class TestDigestLinks:
    """Digest and newsletter emails link directly to the collection page.

    The links point straight to `/collections/{code}` and are never wrapped
    in a redirect or tracking intermediary (see DESIGN.md §9). The tests
    assert both: the direct link is present and no `/digest/` prefix appears.
    """

    def test_digest_email_link_targets_collection_directly(self, db):
        from django.core import mail

        from core.services.email_service import send_digest_email

        mail.outbox.clear()
        send_digest_email(
            collection_headline="Book Club",
            collection_code="ABC123",
            thing_headlines=["Dune"],
            emails=["reader@example.com"],
        )
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        html_body = mail.outbox[0].alternatives[0][0]
        assert "/collections/ABC123" in body
        assert "/collections/ABC123" in html_body
        assert "/digest/" not in body
        assert "/digest/" not in html_body

    def test_newsletter_email_link_targets_collection_directly(self, db):
        from django.core import mail

        from core.services.email_service import send_newsletter_email

        mail.outbox.clear()
        send_newsletter_email(
            collection_headline="Free Library",
            collection_code="XYZ789",
            new_thing_headlines=["A Book"],
            transfer_entries=[],
            emails=["reader@example.com"],
        )
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        html_body = mail.outbox[0].alternatives[0][0]
        assert "/collections/XYZ789" in body
        assert "/collections/XYZ789" in html_body
        assert "/digest/" not in body
        assert "/digest/" not in html_body


@pytest.mark.django_db
class TestNewsletterValidation:
    """Tests for newsletter_enabled validation on collection serializers."""

    def test_cannot_enable_newsletter_without_share(self, authenticated_client):
        """Newsletter requires is_share=True."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Test Collection",
                "mode": "COMMUNITY",
                "is_share": False,
                "newsletter_enabled": True,
            },
            format="json",
        )
        assert response.status_code == 400

    def test_can_enable_newsletter_with_share(self, authenticated_client):
        """Newsletter should work when is_share is True."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Test Collection",
                "mode": "COMMUNITY",
                "is_share": True,
                "newsletter_enabled": True,
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["newsletter_enabled"] is True

    def test_update_disabling_share_clears_newsletter(self, authenticated_client, user):
        """Updating to is_share=False should reject if newsletter_enabled stays True."""
        coll = Collection.objects.create(
            code="UPDNWS",
            owner=user,
            headline="Updatable",
            mode="COMMUNITY",
            is_share=True,
            newsletter_enabled=True,
        )
        response = authenticated_client.patch(
            f"/api/v1/collections/{coll.code}/",
            {"is_share": False},
            format="json",
        )
        # Should fail because newsletter_enabled is still True on the instance
        assert response.status_code == 400
