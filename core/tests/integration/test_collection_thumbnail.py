"""
Integration tests for Collection thumbnail field.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, User


def get_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def owner(db):
    return User.objects.create(code="THB001", email="owner@example.com", name="Owner")


@pytest.fixture
def collection(db, owner):
    return Collection.objects.create(
        code="THBC01", owner=owner, headline="Thumbnail Test Collection"
    )


@pytest.mark.django_db
def test_create_collection_with_thumbnail(owner):
    client = get_client(owner)
    res = client.post(
        "/api/v1/collections/",
        {"headline": "With Photo", "thumbnail": "oiueei/collections/abc123"},
        format="json",
    )
    assert res.status_code == 201
    data = res.json()
    assert data["thumbnail"] == "oiueei/collections/abc123"
    assert data["thumbnail_url"] is not None


@pytest.mark.django_db
def test_create_collection_without_thumbnail(owner):
    client = get_client(owner)
    res = client.post(
        "/api/v1/collections/",
        {"headline": "No Photo"},
        format="json",
    )
    assert res.status_code == 201
    data = res.json()
    assert data["thumbnail"] == ""
    assert data["thumbnail_url"] is None


@pytest.mark.django_db
def test_update_collection_thumbnail(owner, collection):
    client = get_client(owner)
    res = client.patch(
        f"/api/v1/collections/{collection.code}/",
        {"thumbnail": "oiueei/collections/xyz999"},
        format="json",
    )
    assert res.status_code == 200
    collection.refresh_from_db()
    assert collection.thumbnail == "oiueei/collections/xyz999"


@pytest.mark.django_db
def test_clear_collection_thumbnail(owner, collection):
    collection.thumbnail = "oiueei/collections/abc123"
    collection.save()
    client = get_client(owner)
    res = client.patch(
        f"/api/v1/collections/{collection.code}/",
        {"thumbnail": ""},
        format="json",
    )
    assert res.status_code == 200
    collection.refresh_from_db()
    assert collection.thumbnail == ""


@pytest.mark.django_db
def test_collection_detail_exposes_thumbnail_url(owner, collection):
    collection.thumbnail = "oiueei/collections/abc123"
    collection.save()
    client = get_client(owner)
    res = client.get(f"/api/v1/collections/{collection.code}/")
    assert res.status_code == 200
    data = res.json()
    assert "thumbnail_url" in data
    assert data["thumbnail_url"] is not None


@pytest.mark.django_db
def test_thumbnail_rejects_invalid_id(owner):
    client = get_client(owner)
    res = client.post(
        "/api/v1/collections/",
        {"headline": "Bad", "thumbnail": "<script>bad</script>"},
        format="json",
    )
    assert res.status_code == 400
