"""
Integration tests for collection-defined tags and thing tag assignment.

Owner defines a tag vocabulary on a collection; things in that collection may be
tagged with a subset. Removing a tag from the collection cascade-strips it from
its things.
"""

import pytest


@pytest.mark.django_db
class TestCollectionTags:
    def test_create_with_tags(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Tagged", "tags": ["Vintage", "Kitchen"]},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["tags"] == ["Vintage", "Kitchen"]

    def test_tags_normalized_trim_and_dedupe(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Norm", "tags": [" Vintage ", "vintage", "Kitchen"]},
            format="json",
        )
        assert res.status_code == 201
        # trimmed + case-insensitive dedupe (first wins)
        assert res.data["tags"] == ["Vintage", "Kitchen"]

    def test_reject_more_than_12(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Too many", "tags": [f"t{i}" for i in range(13)]},
            format="json",
        )
        assert res.status_code == 400

    def test_reject_html(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "XSS", "tags": ["<b>bad</b>"]},
            format="json",
        )
        assert res.status_code == 400

    def test_update_tags(self, authenticated_client, collection):
        res = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/",
            {"tags": ["Alpha", "Beta"]},
            format="json",
        )
        assert res.status_code == 200
        collection.refresh_from_db()
        assert collection.tags == ["Alpha", "Beta"]

    def test_removing_tag_cascade_strips_from_things(self, authenticated_client, collection, thing):
        collection.tags = ["Alpha", "Beta"]
        collection.save(update_fields=["tags"])
        # tag the thing with both (thing is in `collection` via the fixture)
        r1 = authenticated_client.patch(
            f"/api/v1/things/{thing.code}/", {"tags": ["Alpha", "Beta"]}, format="json"
        )
        assert r1.status_code == 200
        # owner removes "Beta" from the collection vocabulary
        r2 = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/", {"tags": ["Alpha"]}, format="json"
        )
        assert r2.status_code == 200
        thing.refresh_from_db()
        assert thing.tags == ["Alpha"]

    def test_removing_tag_cascade_strips_across_multiple_things(
        self, authenticated_client, collection
    ):
        """The cascade bulk-updates every affected thing and leaves the rest
        untouched (guards the atomic bulk_update path)."""
        from core.models import Thing

        collection.tags = ["Alpha", "Beta"]
        collection.save(update_fields=["tags"])
        t1 = Thing.objects.create(
            code="TAGML1",
            type="GIFT_THING",
            owner=collection.owner,
            headline="One",
            tags=["Alpha", "Beta"],
        )
        t2 = Thing.objects.create(
            code="TAGML2",
            type="GIFT_THING",
            owner=collection.owner,
            headline="Two",
            tags=["Beta"],
        )
        t3 = Thing.objects.create(
            code="TAGML3",
            type="GIFT_THING",
            owner=collection.owner,
            headline="Three",
            tags=["Alpha"],
        )
        collection.things.add(t1, t2, t3)

        r = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/", {"tags": ["Alpha"]}, format="json"
        )
        assert r.status_code == 200

        t1.refresh_from_db()
        t2.refresh_from_db()
        t3.refresh_from_db()
        assert t1.tags == ["Alpha"]  # Beta stripped
        assert t2.tags == []  # Beta stripped
        assert t3.tags == ["Alpha"]  # never had Beta — untouched


@pytest.mark.django_db
class TestThingTags:
    def test_create_with_valid_tag(self, authenticated_client, collection):
        collection.tags = ["Alpha", "Beta"]
        collection.save(update_fields=["tags"])
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Tagged thing",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "tags": ["Alpha"],
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["tags"] == ["Alpha"]

    def test_create_with_tag_not_in_collection(self, authenticated_client, collection):
        collection.tags = ["Alpha"]
        collection.save(update_fields=["tags"])
        res = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Bad tag",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "tags": ["Zzz"],
            },
            format="json",
        )
        assert res.status_code == 400

    def test_create_with_tags_but_no_collection(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/things/",
            {"headline": "No collection", "type": "GIFT_THING", "tags": ["X"]},
            format="json",
        )
        assert res.status_code == 400

    def test_update_thing_tags_subset(self, authenticated_client, collection, thing):
        collection.tags = ["Alpha", "Beta"]
        collection.save(update_fields=["tags"])
        ok = authenticated_client.patch(
            f"/api/v1/things/{thing.code}/", {"tags": ["Beta"]}, format="json"
        )
        assert ok.status_code == 200
        thing.refresh_from_db()
        assert thing.tags == ["Beta"]
        bad = authenticated_client.patch(
            f"/api/v1/things/{thing.code}/", {"tags": ["Nope"]}, format="json"
        )
        assert bad.status_code == 400

    def test_tags_and_collection_tags_exposed(self, authenticated_client, collection, thing):
        collection.tags = ["Alpha", "Beta"]
        collection.save(update_fields=["tags"])
        thing.tags = ["Alpha"]
        thing.save(update_fields=["tags"])
        res = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert res.status_code == 200
        assert res.data["tags"] == ["Alpha"]
        assert set(res.data["collection_tags"]) == {"Alpha", "Beta"}

    def test_tags_on_collection_card(self, authenticated_client, collection, thing):
        collection.tags = ["Alpha"]
        collection.save(update_fields=["tags"])
        thing.tags = ["Alpha"]
        thing.save(update_fields=["tags"])
        res = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert res.status_code == 200
        card = next(c for c in res.data["things"] if c["code"] == thing.code)
        assert card["tags"] == ["Alpha"]
