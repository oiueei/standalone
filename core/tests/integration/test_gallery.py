"""
Integration tests for the multi-photo `gallery` field on Things ("Image pagination").
The cover `thumbnail` is unchanged; `gallery` holds additional ordered photos.
"""

import pytest

from core.models import Thing


@pytest.mark.django_db
class TestGalleryCreate:
    def test_create_with_gallery(self, authenticated_client, collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "With gallery",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "gallery": ["oiueei/things/a1", "oiueei/things/b2"],
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["gallery"] == ["oiueei/things/a1", "oiueei/things/b2"]
        assert len(res.data["gallery_urls"]) == 2

    def test_create_without_gallery_defaults_empty(self, authenticated_client, collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {"headline": "No gallery", "type": "GIFT_THING", "collection_code": collection.code},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["gallery"] == []
        assert res.data["gallery_urls"] == []

    def test_reject_more_than_8(self, authenticated_client, collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Too many",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "gallery": [f"oiueei/things/p{i}" for i in range(9)],
            },
            format="json",
        )
        assert res.status_code == 400

    def test_reject_path_traversal(self, authenticated_client, collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Traversal",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "gallery": ["../../../etc/passwd"],
            },
            format="json",
        )
        assert res.status_code == 400


@pytest.mark.django_db
class TestGalleryUpdate:
    def test_update_gallery(self, authenticated_client, thing):
        res = authenticated_client.patch(
            f"/api/v1/things/{thing.code}/",
            {"gallery": ["oiueei/things/new1"]},
            format="json",
        )
        assert res.status_code == 200
        thing.refresh_from_db()
        assert thing.gallery == ["oiueei/things/new1"]

    def test_clear_gallery(self, authenticated_client, thing):
        thing.gallery = ["oiueei/things/x1", "oiueei/things/x2"]
        thing.save(update_fields=["gallery"])
        res = authenticated_client.patch(
            f"/api/v1/things/{thing.code}/",
            {"gallery": []},
            format="json",
        )
        assert res.status_code == 200
        thing.refresh_from_db()
        assert thing.gallery == []


@pytest.mark.django_db
class TestGalleryUrls:
    def test_gallery_urls_in_response(self, authenticated_client, thing):
        thing.gallery = ["oiueei/things/g1", "oiueei/things/g2", "oiueei/things/g3"]
        thing.save(update_fields=["gallery"])
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert len(res.data["gallery_urls"]) == 3

    def test_empty_gallery_returns_empty_list(self, authenticated_client, thing):
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert res.data["gallery_urls"] == []

    def test_gallery_is_things_only_default_list(self, thing):
        # The model default is an (empty) list, never None — so URL building never
        # has to guard against None.
        assert Thing.objects.get(code=thing.code).gallery == []

    def test_collection_card_exposes_gallery_urls(self, authenticated_client, thing, collection):
        # The collection-grid cards (CollectionThingSummarySerializer) expose
        # gallery_urls so ThingLinkbox can show the carousel.
        thing.gallery = ["oiueei/things/g1", "oiueei/things/g2"]
        thing.save(update_fields=["gallery"])
        res = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert res.status_code == 200
        card = next(c for c in res.data["things"] if c["code"] == thing.code)
        assert len(card["gallery_urls"]) == 2
