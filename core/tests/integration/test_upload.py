"""
Integration tests for the Cloudinary signed-upload endpoint.

CloudinarySignatureView only computes an HMAC signature locally (no network
call to Cloudinary), so these run against whatever CLOUDINARY_URL is
configured (CI sets a fake one) without mocking.
"""

import pytest

URL = "/api/v1/upload/signature/"


@pytest.mark.django_db
class TestCloudinarySignatureView:
    def test_anonymous_is_unauthorized(self, api_client):
        res = api_client.post(URL, {"folder": "oiueei/things"}, format="json")
        assert res.status_code == 401

    def test_valid_folder_is_echoed(self, authenticated_client):
        res = authenticated_client.post(URL, {"folder": "oiueei/things"}, format="json")
        assert res.status_code == 200
        assert res.data["folder"] == "oiueei/things"

    def test_disallowed_folder_falls_back_to_users(self, authenticated_client):
        res = authenticated_client.post(URL, {"folder": "../../etc"}, format="json")
        assert res.status_code == 200
        assert res.data["folder"] == "oiueei/users"

    def test_missing_folder_falls_back_to_users(self, authenticated_client):
        res = authenticated_client.post(URL, {}, format="json")
        assert res.status_code == 200
        assert res.data["folder"] == "oiueei/users"

    def test_response_contains_signed_upload_params(self, authenticated_client):
        res = authenticated_client.post(URL, {"folder": "oiueei/collections"}, format="json")
        assert res.status_code == 200
        assert res.data["signature"]
        assert res.data["public_id"]
        assert res.data["allowed_formats"] == "jpg,jpeg,png,webp,gif,heic,heif,avif,bmp,tif,tiff"
        assert res.data["resource_type"] == "image"
        assert "timestamp" in res.data
        assert "api_key" in res.data
        assert "cloud_name" in res.data
