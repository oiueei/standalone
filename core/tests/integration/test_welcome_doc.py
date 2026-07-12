"""
Collection welcome & rules PDF (O4): uploaded by the owner, emailed once as a link
to every member the first time they join.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from core.models import RSVP, Collection, User

POP_IN_URL = "/api/v1/auth/pop-in/"
SIGNATURE_URL = "/api/v1/upload/signature/"

DOC_ID = "oiueei/collections/welcome-doc-1"


def _verify(rsvp):
    return APIClient().get(f"/api/v1/auth/verify/{rsvp.token}/")


def _doc_emails():
    """The welcome-doc emails in the outbox — the ones carrying the PDF link.

    Not filtered by subject: the join magic-link subject also names the collection.
    """
    return [m for m in mail.outbox if DOC_ID in m.body]


def _invite_rsvp(user, collection):
    return RSVP.objects.create(
        user_code=user,
        user_email=user.email,
        action=RSVP.Action.COLLECTION_INVITE,
        target_code=collection.code,
    )


@pytest.mark.django_db
class TestWelcomeDocOnJoin:
    def test_accepting_an_invitation_sends_the_document(self, user2, collection):
        collection.welcome_doc = DOC_ID
        collection.save()

        _verify(_invite_rsvp(user2, collection))

        sent = _doc_emails()
        assert len(sent) == 1
        assert collection.headline in sent[0].subject
        assert sent[0].to == [user2.email]

    def test_no_document_means_no_email(self, user2, collection):
        assert collection.welcome_doc == ""

        _verify(_invite_rsvp(user2, collection))

        assert _doc_emails() == []

    def test_rejoining_does_not_resend(self, api_client, collection):
        # Login-to-act on a PUBLIC collection re-runs the (idempotent) M2M add on
        # every pop-in, so an existing member must not get the document again.
        collection.welcome_doc = DOC_ID
        collection.visibility = Collection.Visibility.PUBLIC
        collection.save()

        api_client.post(
            POP_IN_URL,
            {"email": "joiner@test.com", "collection_code": collection.code},
            format="json",
        )
        assert len(_doc_emails()) == 1

        api_client.post(
            POP_IN_URL,
            {"email": "joiner@test.com", "collection_code": collection.code},
            format="json",
        )

        assert len(_doc_emails()) == 1
        assert collection.invites.filter(email="joiner@test.com").exists()

    def test_share_token_join_sends_the_document(self, api_client, collection):
        collection.welcome_doc = DOC_ID
        collection.share_token = "sharetoken1234567890ab"
        collection.save()

        api_client.post(
            POP_IN_URL,
            {"email": "shared@test.com", "share_token": collection.share_token},
            format="json",
        )

        sent = _doc_emails()
        assert len(sent) == 1
        assert sent[0].to == ["shared@test.com"]
        assert User.objects.filter(email="shared@test.com").exists()


@pytest.mark.django_db
class TestDocumentSignature:
    def test_document_mode_signs_pdf_only_and_a_size_cap(self, authenticated_client):
        res = authenticated_client.post(
            SIGNATURE_URL,
            {"folder": "oiueei/collections", "kind": "document"},
            format="json",
        )

        assert res.status_code == 200
        assert res.data["allowed_formats"] == "pdf"
        assert res.data["max_file_size"] == 5 * 1024 * 1024
        # A PDF is a page-based image to Cloudinary — same resource type as a photo.
        assert res.data["resource_type"] == "image"

    def test_image_mode_is_unchanged(self, authenticated_client):
        res = authenticated_client.post(SIGNATURE_URL, {"folder": "oiueei/things"}, format="json")

        assert res.status_code == 200
        assert "pdf" not in res.data["allowed_formats"]
        assert "max_file_size" not in res.data
        assert res.data["resource_type"] == "image"

    def test_an_unknown_kind_falls_back_to_an_image_upload(self, authenticated_client):
        res = authenticated_client.post(
            SIGNATURE_URL,
            {"folder": "oiueei/collections", "kind": "executable"},
            format="json",
        )

        assert res.status_code == 200
        assert "pdf" not in res.data["allowed_formats"]
        assert "max_file_size" not in res.data


@pytest.mark.django_db
class TestWelcomeDocField:
    def test_owner_can_set_and_read_back_the_document(self, authenticated_client, collection):
        res = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/",
            {"welcome_doc": DOC_ID},
            format="json",
        )
        assert res.status_code == 200

        detail = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert detail.data["welcome_doc"] == DOC_ID
        # Delivered as a .pdf URL — no f_auto/q_auto photo transformations.
        assert detail.data["welcome_doc_url"].endswith(".pdf")

    def test_a_path_traversing_id_is_rejected(self, authenticated_client, collection):
        res = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/",
            {"welcome_doc": "../../etc/passwd"},
            format="json",
        )

        assert res.status_code == 400
