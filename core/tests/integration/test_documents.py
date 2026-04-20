"""
Integration tests for document attachments on Things (F11).
"""

from unittest.mock import patch

import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Thing
from core.models.booking import BookingPeriod
from core.services.booking_service import accept_booking


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated client for the thing owner."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def thing_with_docs(db, user, collection):
    """Create a thing with documents attached."""
    t = Thing.objects.create(
        code="DOC001",
        type="GIFT_THING",
        owner=user,
        headline="Thing With Docs",
        documents=[
            {
                "public_id": "oiueei/documents/abc123",
                "filename": "manual.pdf",
                "content_type": "application/pdf",
            },
            {
                "public_id": "oiueei/documents/def456",
                "filename": "notes.md",
                "content_type": "text/markdown",
            },
        ],
    )
    collection.things.add(t)
    return t


# --- Serializer validation tests ---


class TestDocumentSerializer:
    def test_create_thing_with_valid_documents(self, auth_client, collection):
        res = auth_client.post(
            "/api/v1/things/",
            {
                "headline": "With Docs",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "documents": [
                    {
                        "public_id": "oiueei/documents/abc123",
                        "filename": "manual.pdf",
                        "content_type": "application/pdf",
                    }
                ],
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["documents"] is not None
        assert len(res.data["documents"]) == 1

    def test_create_thing_with_no_documents(self, auth_client, collection):
        res = auth_client.post(
            "/api/v1/things/",
            {
                "headline": "No Docs",
                "type": "GIFT_THING",
                "collection_code": collection.code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["documents"] is None

    def test_reject_invalid_content_type(self, auth_client, collection):
        res = auth_client.post(
            "/api/v1/things/",
            {
                "headline": "Bad Type",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "documents": [
                    {
                        "public_id": "oiueei/documents/abc123",
                        "filename": "virus.exe",
                        "content_type": "application/x-msdownload",
                    }
                ],
            },
            format="json",
        )
        assert res.status_code == 400

    def test_reject_more_than_5_documents(self, auth_client, collection):
        docs = [
            {
                "public_id": f"oiueei/documents/doc{i}",
                "filename": f"file{i}.pdf",
                "content_type": "application/pdf",
            }
            for i in range(6)
        ]
        res = auth_client.post(
            "/api/v1/things/",
            {
                "headline": "Too Many",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "documents": docs,
            },
            format="json",
        )
        assert res.status_code == 400

    def test_reject_path_traversal_in_public_id(self, auth_client, collection):
        res = auth_client.post(
            "/api/v1/things/",
            {
                "headline": "Traversal",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "documents": [
                    {
                        "public_id": "../../../etc/passwd",
                        "filename": "hack.pdf",
                        "content_type": "application/pdf",
                    }
                ],
            },
            format="json",
        )
        assert res.status_code == 400


# --- Read serializer tests ---


class TestDocumentUrls:
    def test_document_urls_in_response(self, auth_client, thing_with_docs):
        res = auth_client.get(f"/api/v1/things/{thing_with_docs.code}/")
        assert res.status_code == 200
        assert len(res.data["document_urls"]) == 2
        assert res.data["document_urls"][0]["filename"] == "manual.pdf"
        assert "url" in res.data["document_urls"][0]

    def test_empty_documents_returns_empty_list(self, auth_client, thing):
        res = auth_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert res.data["document_urls"] == []


# --- Update tests ---


class TestDocumentUpdate:
    def test_update_thing_with_documents(self, auth_client, thing):
        res = auth_client.patch(
            f"/api/v1/things/{thing.code}/",
            {
                "documents": [
                    {
                        "public_id": "oiueei/documents/new123",
                        "filename": "new.pdf",
                        "content_type": "application/pdf",
                    }
                ],
            },
            format="json",
        )
        assert res.status_code == 200
        thing.refresh_from_db()
        assert len(thing.documents) == 1

    def test_clear_documents(self, auth_client, thing_with_docs):
        res = auth_client.patch(
            f"/api/v1/things/{thing_with_docs.code}/",
            {"documents": []},
            format="json",
        )
        assert res.status_code == 200
        thing_with_docs.refresh_from_db()
        assert thing_with_docs.documents == []


# --- Booking acceptance triggers documents email ---


class TestDocumentsEmail:
    @patch("core.services.email_service.send_documents_email")
    def test_accept_booking_sends_documents_email(self, mock_send, thing_with_docs, user, user2):
        booking = BookingPeriod.objects.create(
            thing_code=thing_with_docs,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        accept_booking(booking)
        mock_send.assert_called_once_with(
            user2.email,
            thing_with_docs.headline,
            thing_with_docs.documents,
        )

    @patch("core.services.email_service.send_documents_email")
    def test_accept_booking_no_documents_no_email(self, mock_send, thing, user, user2):
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        accept_booking(booking)
        mock_send.assert_not_called()


# --- Upload view tests ---


class TestUploadSignature:
    def test_documents_folder_allowed(self, auth_client):
        res = auth_client.post(
            "/api/v1/upload/signature/",
            {"folder": "oiueei/documents", "resource_type": "raw"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["folder"] == "oiueei/documents"
        assert res.data["resource_type"] == "raw"

    def test_invalid_resource_type_falls_back(self, auth_client):
        res = auth_client.post(
            "/api/v1/upload/signature/",
            {"folder": "oiueei/things", "resource_type": "video"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["resource_type"] == "image"
