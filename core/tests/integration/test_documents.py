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

    def test_owner_sees_raw_documents(self, auth_client, thing_with_docs):
        res = auth_client.get(f"/api/v1/things/{thing_with_docs.code}/")
        assert res.status_code == 200
        assert res.data["documents"] is not None
        assert res.data["documents"][0]["public_id"] == "oiueei/documents/abc123"

    def test_raw_documents_are_owner_only(self, api_client, thing_with_docs, collection, user2):
        """A non-owner viewer gets the gated download links but never the raw
        documents array — exposing public_ids would let them rebuild an eternal
        URL for legacy public documents (M2)."""
        collection.invites.add(user2)
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        res = api_client.get(f"/api/v1/things/{thing_with_docs.code}/")
        assert res.status_code == 200
        assert res.data["documents"] is None
        assert len(res.data["document_urls"]) == 2


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
        mock_send.assert_called_once_with(user2.email, thing_with_docs)

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
        # resource_type is derived from the folder, never trusted from the client.
        assert res.data["resource_type"] == "image"

    def test_signature_binds_server_chosen_public_id_and_formats(self, auth_client):
        """M1: public_id is generated server-side and allowed_formats/type are
        signed, so the client cannot choose them. The signature must cover exactly
        those parameters."""
        import cloudinary

        res = auth_client.post(
            "/api/v1/upload/signature/", {"folder": "oiueei/documents"}, format="json"
        )
        assert res.status_code == 200
        data = res.data
        # Server-generated id (the client never supplied one) and the document
        # format allowlist + private delivery type.
        assert data["public_id"] and len(data["public_id"]) >= 16
        assert data["resource_type"] == "raw"
        assert data["allowed_formats"] == "pdf,doc,docx,xls,xlsx,md"
        assert data["type"] == "authenticated"
        # The signature must be over exactly the signed parameter set.
        params = {
            "allowed_formats": data["allowed_formats"],
            "folder": data["folder"],
            "public_id": data["public_id"],
            "timestamp": data["timestamp"],
            "type": data["type"],
        }
        expected = cloudinary.utils.api_sign_request(params, cloudinary.config().api_secret)
        assert data["signature"] == expected

    def test_image_folder_excludes_svg_and_is_public(self, auth_client):
        res = auth_client.post(
            "/api/v1/upload/signature/", {"folder": "oiueei/things"}, format="json"
        )
        assert res.status_code == 200
        # Raster photo formats only — SVG (script-bearing) must not be allowed.
        assert "svg" not in res.data["allowed_formats"]
        assert "png" in res.data["allowed_formats"]
        # Images stay public uploads (displayed in <img>), so no private type.
        assert "type" not in res.data

    def test_each_signature_has_a_unique_public_id(self, auth_client):
        ids = set()
        for _ in range(3):
            res = auth_client.post(
                "/api/v1/upload/signature/", {"folder": "oiueei/documents"}, format="json"
            )
            ids.add(res.data["public_id"])
        assert len(ids) == 3


# --- Signed, gated document download (M2) ---


class TestDocumentDownload:
    def _authenticate(self, api_client, who):
        refresh = RefreshToken.for_user(who)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return api_client

    def test_owner_download_redirects_to_signed_expiring_url(self, auth_client, thing_with_docs):
        res = auth_client.get(f"/api/v1/things/{thing_with_docs.code}/documents/0/download/")
        assert res.status_code == 302
        location = res["Location"]
        # A signed, expiring Cloudinary download URL — never an eternal delivery URL.
        assert "api.cloudinary.com" in location and "/raw/download" in location
        assert "expires_at=" in location
        assert "signature=" in location

    def test_api_created_document_is_authenticated(self, auth_client, collection):
        """Documents created through the API are stamped type=authenticated, so
        their signed download URL is for the private (authenticated) asset."""
        create = auth_client.post(
            "/api/v1/things/",
            {
                "headline": "Authed Doc",
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
        assert create.status_code == 201
        code = create.data["code"]
        res = auth_client.get(f"/api/v1/things/{code}/documents/0/download/")
        assert res.status_code == 302
        assert "type=authenticated" in res["Location"]

    def test_document_urls_point_at_the_gated_endpoint(self, auth_client, thing_with_docs):
        res = auth_client.get(f"/api/v1/things/{thing_with_docs.code}/")
        assert res.status_code == 200
        urls = res.data["document_urls"]
        assert len(urls) == 2
        for index, entry in enumerate(urls):
            assert entry["url"] == (
                f"/api/v1/things/{thing_with_docs.code}/documents/{index}/download/"
            )
            # No raw Cloudinary URL is ever exposed in the serialised payload.
            assert "cloudinary.com" not in entry["url"]

    def test_download_out_of_range_returns_404(self, auth_client, thing_with_docs):
        res = auth_client.get(f"/api/v1/things/{thing_with_docs.code}/documents/9/download/")
        assert res.status_code == 404

    def test_download_with_no_documents_returns_404(self, auth_client, thing):
        res = auth_client.get(f"/api/v1/things/{thing.code}/documents/0/download/")
        assert res.status_code == 404

    def test_non_viewer_is_forbidden(self, api_client, thing_with_docs, user2):
        client = self._authenticate(api_client, user2)
        res = client.get(f"/api/v1/things/{thing_with_docs.code}/documents/0/download/")
        assert res.status_code == 403

    def test_download_requires_authentication(self, api_client, thing_with_docs):
        res = api_client.get(f"/api/v1/things/{thing_with_docs.code}/documents/0/download/")
        assert res.status_code in (401, 403)
