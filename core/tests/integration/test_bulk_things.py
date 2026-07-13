"""
Integration tests for CSV bulk-add of things (F-9 / Fase 15b).

Covers the atomic batch create, the CSV-injection guard, all-or-nothing
rollback, the per-collection authorisation gate, and the input bounds.
"""

import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Thing
from core.models.event import Event

URL = "/api/v1/collections/{code}/things/bulk/"


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated client for the collection owner."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


class TestBulkCreate:
    def test_creates_all_rows_atomically(self, auth_client, collection):
        rows = [
            {"type": "GIFT_THING", "headline": "Row one"},
            {"type": "GIFT_THING", "headline": "Row two", "description": "Nice and handy"},
            {"type": "SELL_THING", "headline": "Row three", "fee": "9.99", "location": "Bilbao"},
        ]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 201
        assert res.data["created"] == 3
        assert len(res.data["codes"]) == 3
        assert collection.things.count() == 3
        third = Thing.objects.get(code=res.data["codes"][2])
        assert third.headline == "Row three"
        assert str(third.fee) == "9.99"
        assert third.owner_id == collection.owner_id

    def test_rejects_csv_formula_injection_in_headline(self, auth_client, collection):
        rows = [
            {"type": "GIFT_THING", "headline": "Fine one"},
            {"type": "GIFT_THING", "headline": "=SUM(1+1)"},
        ]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 400
        assert res.data["errors"][0]["row"] == 1
        # All-or-nothing: the valid row is not created either.
        assert collection.things.count() == 0

    @pytest.mark.parametrize("field,value", [("description", "@cmd"), ("location", "+1+1")])
    def test_rejects_formula_in_other_text_fields(self, auth_client, collection, field, value):
        res = auth_client.post(
            URL.format(code=collection.code),
            {"rows": [{"type": "GIFT_THING", "headline": "ok", field: value}]},
            format="json",
        )
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_one_invalid_row_rolls_back_the_whole_batch(self, auth_client, collection):
        rows = [
            {"type": "GIFT_THING", "headline": "Valid row"},
            {"type": "GIFT_THING"},  # missing required headline
        ]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_rejects_html_in_headline(self, auth_client, collection):
        res = auth_client.post(
            URL.format(code=collection.code),
            {"rows": [{"type": "GIFT_THING", "headline": "<script>x</script>"}]},
            format="json",
        )
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_rejects_type_invalid_for_collection(self, auth_client, collection):
        # WISH_THING is community-only; this collection is proprietary.
        res = auth_client.post(
            URL.format(code=collection.code),
            {"rows": [{"type": "WISH_THING", "headline": "I wish"}]},
            format="json",
        )
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_empty_rows_rejected(self, auth_client, collection):
        res = auth_client.post(URL.format(code=collection.code), {"rows": []}, format="json")
        assert res.status_code == 400

    def test_too_many_rows_rejected(self, auth_client, collection):
        rows = [{"type": "GIFT_THING", "headline": f"Item {i}"} for i in range(101)]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_non_member_is_forbidden(self, api_client, collection, user2):
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        res = api_client.post(
            URL.format(code=collection.code),
            {"rows": [{"type": "GIFT_THING", "headline": "x"}]},
            format="json",
        )
        assert res.status_code == 403
        assert collection.things.count() == 0

    def test_requires_authentication(self, api_client, collection):
        res = api_client.post(
            URL.format(code=collection.code),
            {"rows": [{"type": "GIFT_THING", "headline": "x"}]},
            format="json",
        )
        assert res.status_code in (401, 403)

    def test_non_dict_body_is_rejected_not_500(self, auth_client, collection):
        # A top-level JSON array (instead of {"rows": [...]}) must 400, not crash.
        res = auth_client.post(
            URL.format(code=collection.code),
            [{"type": "GIFT_THING", "headline": "x"}],
            format="json",
        )
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_wish_things_cannot_be_bulk_imported(self, auth_client, user):
        from core.models import Collection

        community = Collection.objects.create(
            code="COMM01", owner=user, headline="Community", mode="COMMUNITY"
        )
        res = auth_client.post(
            URL.format(code=community.code),
            {"rows": [{"type": "WISH_THING", "headline": "I wish for peace"}]},
            format="json",
        )
        assert res.status_code == 400
        assert "type" in res.data["errors"][0]["errors"]
        assert community.things.count() == 0

    def test_imports_tags_from_collection_vocabulary(self, auth_client, collection):
        collection.tags = ["Books", "Toys"]
        collection.save(update_fields=["tags"])
        rows = [{"type": "GIFT_THING", "headline": "Tagged", "tags": ["Books"]}]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 201
        thing = Thing.objects.get(code=res.data["codes"][0])
        assert thing.tags == ["Books"]

    def test_rejects_tag_not_in_collection_vocabulary(self, auth_client, collection):
        collection.tags = ["Books"]
        collection.save(update_fields=["tags"])
        rows = [{"type": "GIFT_THING", "headline": "Bad tag", "tags": ["Undefined"]}]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 400
        assert "tags" in res.data["errors"][0]["errors"]
        assert collection.things.count() == 0

    def test_imports_thumbnail_public_id(self, auth_client, collection):
        # The ZIP path uploads images to Cloudinary client-side and sends the
        # resulting public_id here as `thumbnail`.
        rows = [
            {"type": "GIFT_THING", "headline": "With photo", "thumbnail": "oiueei/things/abc123"}
        ]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 201
        thing = Thing.objects.get(code=res.data["codes"][0])
        assert thing.thumbnail == "oiueei/things/abc123"

    def test_rejects_path_traversal_thumbnail(self, auth_client, collection):
        rows = [{"type": "GIFT_THING", "headline": "Evil", "thumbnail": "../../etc/passwd"}]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 400
        assert collection.things.count() == 0

    def test_logs_a_thing_added_event_per_row(self, auth_client, collection):
        rows = [
            {"type": "GIFT_THING", "headline": "Row one"},
            {"type": "GIFT_THING", "headline": "Row two"},
        ]
        res = auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")
        assert res.status_code == 201
        events = Event.objects.filter(kind=Event.Kind.THING_ADDED, collection_code=collection.code)
        assert events.count() == 2
        assert set(events.values_list("thing_code", flat=True)) == set(res.data["codes"])


class TestBulkFeeDecimalComma:
    """Spanish/Catalan spreadsheet exports write decimals as a comma (S9)."""

    def _fee_of(self, auth_client, collection, fee):
        rows = [{"type": "SELL_THING", "headline": "Priced item", "fee": fee}]
        return auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")

    def test_accepts_a_dot_decimal(self, auth_client, collection):
        res = self._fee_of(auth_client, collection, "1.5")
        assert res.status_code == 201
        assert str(Thing.objects.get(code=res.data["codes"][0]).fee) == "1.50"

    def test_accepts_a_comma_decimal(self, auth_client, collection):
        res = self._fee_of(auth_client, collection, "1,5")
        assert res.status_code == 201
        assert str(Thing.objects.get(code=res.data["codes"][0]).fee) == "1.50"

    def test_integers_are_unchanged(self, auth_client, collection):
        res = self._fee_of(auth_client, collection, "10")
        assert res.status_code == 201
        assert str(Thing.objects.get(code=res.data["codes"][0]).fee) == "10.00"

    def test_rejects_dot_then_comma_as_ambiguous(self, auth_client, collection):
        res = self._fee_of(auth_client, collection, "1.234,56")
        assert res.status_code == 400
        assert "Ambiguous" in str(res.data["errors"][0]["errors"]["fee"])
        assert collection.things.count() == 0

    def test_rejects_comma_then_dot_as_ambiguous(self, auth_client, collection):
        res = self._fee_of(auth_client, collection, "1,234.56")
        assert res.status_code == 400
        assert "Ambiguous" in str(res.data["errors"][0]["errors"]["fee"])


class TestBulkTagAlias:
    """A CSV tag may name a localized vocabulary entry in any of its
    languages, not just the byte-identical canonical JSON (S10)."""

    LOCALIZED_TAG = '{"es": "Crianza", "ca": "Criança"}'

    def _tagged(self, auth_client, collection, tags):
        rows = [{"type": "GIFT_THING", "headline": "Tagged", "tags": tags}]
        return auth_client.post(URL.format(code=collection.code), {"rows": rows}, format="json")

    def _set_vocabulary(self, collection, tags):
        collection.tags = tags
        collection.save(update_fields=["tags"])

    def test_an_alias_in_one_language_resolves_to_the_canonical_string(
        self, auth_client, collection
    ):
        self._set_vocabulary(collection, [self.LOCALIZED_TAG])
        res = self._tagged(auth_client, collection, ["Crianza"])
        assert res.status_code == 201
        assert Thing.objects.get(code=res.data["codes"][0]).tags == [self.LOCALIZED_TAG]

    def test_an_alias_in_another_language_also_resolves(self, auth_client, collection):
        self._set_vocabulary(collection, [self.LOCALIZED_TAG])
        res = self._tagged(auth_client, collection, ["Criança"])
        assert res.status_code == 201
        assert Thing.objects.get(code=res.data["codes"][0]).tags == [self.LOCALIZED_TAG]

    def test_an_alias_matches_case_insensitively(self, auth_client, collection):
        self._set_vocabulary(collection, [self.LOCALIZED_TAG])
        res = self._tagged(auth_client, collection, ["criança"])
        assert res.status_code == 201
        assert Thing.objects.get(code=res.data["codes"][0]).tags == [self.LOCALIZED_TAG]

    def test_the_exact_canonical_string_still_works(self, auth_client, collection):
        self._set_vocabulary(collection, [self.LOCALIZED_TAG])
        res = self._tagged(auth_client, collection, [self.LOCALIZED_TAG])
        assert res.status_code == 201
        assert Thing.objects.get(code=res.data["codes"][0]).tags == [self.LOCALIZED_TAG]

    def test_an_unknown_tag_still_fails(self, auth_client, collection):
        self._set_vocabulary(collection, [self.LOCALIZED_TAG])
        res = self._tagged(auth_client, collection, ["Nope"])
        assert res.status_code == 400
        assert "not defined" in str(res.data["errors"][0]["errors"]["tags"])
        assert collection.things.count() == 0

    def test_an_alias_matching_two_entries_is_rejected_as_ambiguous(self, auth_client, collection):
        # Both vocabulary entries carry "Crianza" as their Spanish text.
        self._set_vocabulary(
            collection,
            [self.LOCALIZED_TAG, '{"es": "Crianza", "ca": "Altra"}'],
        )
        res = self._tagged(auth_client, collection, ["Crianza"])
        assert res.status_code == 400
        assert "more than one" in str(res.data["errors"][0]["errors"]["tags"])
        assert collection.things.count() == 0
