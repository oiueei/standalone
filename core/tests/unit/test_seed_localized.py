"""The multilingual demo seed (one seeding serves every reader — O6).

Collection/thing headlines, descriptions and tag labels are seeded as localized
``{"es": …, "ca": …, "en": …}`` maps built from ALL the language files;
``--lang`` only picks the language of the plain-column text (user bios, FAQs,
wish responses). These tests pin the merge, the parity between language files
(the seed analogue of ``i18nParity``), the per-language length limits the
serializers would otherwise enforce, and the raw-string tag consistency the
subset check depends on.
"""

from importlib import import_module

import pytest
from django.core.management import call_command

from core.management.commands.seed_data import common
from core.management.commands.seed_demo import (
    _MERGE_KEYS,
    SUPPORTED_LANGS,
    _localize,
    load_seed_data,
)
from core.models import Collection, Thing
from core.utils import parse_localized, resolve_localized

LANG_MODULES = {
    code: import_module(f"core.management.commands.seed_data.{code}") for code in SUPPORTED_LANGS
}

# Visible (per-language) and storage caps — mirror the Localized* serializer fields.
HEADLINE_LIMIT, HEADLINE_STORAGE = 64, 256
DESCRIPTION_LIMIT, DESCRIPTION_STORAGE = 256, 1024
TAG_LIMIT, TAG_STORAGE = 32, 160


class TestLocalize:
    def test_identical_variants_stay_a_plain_string(self):
        assert _localize({"es": "Arduino", "ca": "Arduino", "en": "Arduino"}) == "Arduino"

    def test_distinct_variants_become_a_strict_map(self):
        value = _localize({"es": "Cocina", "ca": "Cuina", "en": "Kitchen"})
        assert parse_localized(value) == {"es": "Cocina", "ca": "Cuina", "en": "Kitchen"}

    def test_missing_variants_are_dropped_not_stored_empty(self):
        value = _localize({"es": "Hola", "ca": "", "en": "Hi"})
        assert parse_localized(value) == {"es": "Hola", "en": "Hi"}

    def test_all_empty_is_empty(self):
        assert _localize({"es": "", "ca": "", "en": ""}) == ""


class TestSeedFileParity:
    """Every language file must translate the same rows and the same fields."""

    @pytest.mark.parametrize("entity", ["USERS", "COLLECTIONS", "THINGS", "FAQS"])
    def test_same_rows_and_fields_in_every_language(self, entity):
        key = _MERGE_KEYS[entity]
        reference = {row[key]: set(row) for row in getattr(LANG_MODULES["en"], entity)}
        for code in SUPPORTED_LANGS:
            rows = {row[key]: set(row) for row in getattr(LANG_MODULES[code], entity)}
            assert rows.keys() == reference.keys(), f"{code}.{entity} rows differ from en"
            for row_key, fields in rows.items():
                assert fields == reference[row_key], f"{code}.{entity}[{row_key}] fields differ"

    def test_per_language_texts_fit_the_visible_limits(self):
        for code, module in LANG_MODULES.items():
            for row in module.COLLECTIONS + module.THINGS:
                assert len(row.get("headline", "")) <= HEADLINE_LIMIT, (code, row)
                assert len(row.get("description", "")) <= DESCRIPTION_LIMIT, (code, row)
            for row in module.USERS:
                assert len(row.get("headline", "")) <= HEADLINE_LIMIT, (code, row)
            for row in module.FAQS:
                assert len(row["question"]) <= 64 and len(row["answer"]) <= 256, (code, row)


class TestMergedSeedData:
    def test_collection_text_resolves_per_reader_language(self):
        data = load_seed_data("en")
        headline = next(c for c in data.COLLECTIONS if c["code"] == "l1l1C1")["headline"]
        assert parse_localized(headline) is not None
        for code in SUPPORTED_LANGS:
            expected = next(
                c for c in getattr(LANG_MODULES[code], "COLLECTIONS") if c["code"] == "l1l1C1"
            )["headline"]
            assert resolve_localized(headline, code) == expected

    def test_language_neutral_thing_stays_plain(self):
        # "Arduino Nano 33 BLE" reads the same in every language file.
        data = load_seed_data("en")
        headline = next(t for t in data.THINGS if t["code"] == "L3L305")["headline"]
        assert headline == "Arduino Nano 33 BLE"
        assert parse_localized(headline) is None

    def test_merged_values_fit_the_storage_columns(self):
        data = load_seed_data("en")
        for row in data.COLLECTIONS:
            assert len(row["headline"]) <= HEADLINE_STORAGE, row["code"]
            assert len(row["description"]) <= DESCRIPTION_STORAGE, row["code"]
            for tag in row.get("tags", []):
                assert len(tag) <= TAG_STORAGE, (row["code"], tag)
        for row in data.THINGS:
            assert len(row["headline"]) <= HEADLINE_STORAGE, row["code"]
            assert len(row["description"]) <= DESCRIPTION_STORAGE, row["code"]

    def test_tag_labels_fit_the_per_language_limit(self):
        for row in common.COLLECTIONS:
            for tag in row.get("tags", []):
                texts = parse_localized(tag)
                for text in (texts or {tag: tag}).values():
                    assert len(text) <= TAG_LIMIT, tag

    def test_thing_tags_are_a_raw_string_subset_of_their_collection_vocabulary(self):
        # The subset check in production compares RAW strings — a thing tag must
        # be byte-identical to a vocabulary entry (the constants in common.py).
        vocab = {c["code"]: set(c.get("tags", [])) for c in common.COLLECTIONS}
        for thing in common.THINGS:
            for col_code in thing.get("collections", []):
                for tag in thing.get("tags", []):
                    assert tag in vocab[col_code], (thing["code"], tag)


@pytest.mark.django_db
class TestSeedCommand:
    def test_seeds_localized_maps_and_is_idempotent(self):
        call_command("seed_demo", lang="ca", verbosity=0)
        call_command("seed_demo", lang="ca", verbosity=0)  # idempotent re-run

        collection = Collection.objects.get(code="l1l1C1")
        assert resolve_localized(collection.headline, "ca").startswith("Préstecs de la Lili")
        assert resolve_localized(collection.headline, "es").startswith("Préstamos de Lili")
        assert resolve_localized(collection.headline, "en")  # English present too

        thing = Thing.objects.get(code="l1l101")
        assert parse_localized(thing.headline) is not None
        # The thing's tag is the same raw string as the vocabulary entry.
        assert set(thing.tags) <= set(collection.tags)

        # Non-localizable text followed --lang=ca.
        faq = thing.owner.asked_faqs.model.objects.filter(thing_id="La1a01").first()
        assert faq is not None and faq.question == "Puc recollir-ho a final de mes?"
