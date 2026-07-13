"""
Owner multilingual content (O6): a headline, description or tag label may hold
one text per language as inline JSON — ``{"es": "…", "ca": "…"}``.

The parse is the whole feature, so it is pinned hard: everything it does *not*
recognise renders verbatim to every reader, which is what keeps the trick free
for the 99% of owners who never use it (an owner writing about JSON in a
description must not have it swallowed).
"""

import pytest
from rest_framework import serializers

from core.utils import parse_localized, resolve_localized
from core.validators import LocalizedHeadlineField, LocalizedTextField


class TestParseLocalized:
    def test_a_map_of_languages_is_localized_content(self):
        assert parse_localized('{"es": "Las cosas de mamá", "ca": "Les coses de mama"}') == {
            "es": "Las cosas de mamá",
            "ca": "Les coses de mama",
        }

    def test_one_language_is_enough(self):
        assert parse_localized('{"ca": "Les coses"}') == {"ca": "Les coses"}

    def test_surrounding_whitespace_is_tolerated(self):
        # A pasted example usually carries some.
        assert parse_localized('  {"es": "Hola"}\n') == {"es": "Hola"}

    def test_plain_text_is_not_localized_content(self):
        assert parse_localized("Las cosas de mamá") is None

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "{",
            "{not json}",
            '["es", "ca"]',  # a list, not a map
            "{}",  # no language at all
            '{"es": "Hola", "fr": "Salut"}',  # a language OIUEEI doesn't speak
            '{"es": ""}',  # an empty text is not a translation
            '{"es": "   "}',
            '{"es": 42}',  # not a string
            '{"es": {"nested": "no"}}',
        ],
    )
    def test_anything_else_renders_verbatim(self, value):
        assert parse_localized(value) is None

    def test_a_non_string_is_not_localized_content(self):
        assert parse_localized(None) is None
        assert parse_localized(42) is None


class TestResolveLocalized:
    def test_plain_text_comes_back_untouched(self):
        assert resolve_localized("Las cosas de mamá", "ca") == "Las cosas de mamá"

    def test_the_reader_gets_their_own_language(self):
        value = '{"es": "Las cosas", "ca": "Les coses", "en": "The things"}'
        assert resolve_localized(value, "ca") == "Les coses"
        assert resolve_localized(value, "en") == "The things"

    def test_a_language_the_owner_didnt_write_falls_back_to_spanish(self):
        assert resolve_localized('{"es": "Las cosas", "ca": "Les coses"}', "en") == "Las cosas"

    def test_without_spanish_the_first_language_written_answers(self):
        # Words beat raw JSON, always.
        assert resolve_localized('{"ca": "Les coses", "en": "The things"}', "fr") == "Les coses"

    def test_no_language_asked_still_resolves(self):
        assert resolve_localized('{"ca": "Les coses"}') == "Les coses"


class TestLocalizedFields:
    """The server is the real guard: SQLite doesn't enforce max_length, PostgreSQL does."""

    def test_a_headline_accepts_plain_text_at_the_visible_limit(self):
        field = LocalizedHeadlineField(max_length=64)
        assert field.run_validation("a" * 64) == "a" * 64

    def test_a_plain_headline_over_the_visible_limit_is_rejected(self):
        field = LocalizedHeadlineField(max_length=64)
        with pytest.raises(serializers.ValidationError):
            field.run_validation("a" * 65)

    def test_a_localized_headline_is_stored_as_written(self):
        field = LocalizedHeadlineField(max_length=64)
        value = '{"es": "Las cosas de mamá", "ca": "Les coses de mama"}'
        assert field.run_validation(value) == value

    def test_each_language_gets_the_visible_limit_not_three_times_it(self):
        field = LocalizedHeadlineField(max_length=64)
        long_one = "a" * 65
        with pytest.raises(serializers.ValidationError) as exc:
            field.run_validation('{"es": "corto", "ca": "%s"}' % long_one)
        assert "ca" in str(exc.value)

    def test_three_languages_at_the_limit_still_fit_the_column(self):
        field = LocalizedHeadlineField(max_length=64)
        text = "a" * 64
        value = '{"es": "%s", "ca": "%s", "en": "%s"}' % (text, text, text)
        assert field.run_validation(value) == value

    def test_html_inside_one_language_is_rejected(self):
        field = LocalizedHeadlineField(max_length=64)
        with pytest.raises(serializers.ValidationError):
            field.run_validation('{"es": "Hola", "ca": "<script>alert(1)</script>"}')

    def test_a_multi_line_headline_is_rejected_even_as_a_map(self):
        # Headlines flow into email Subject lines — no CR/LF, pretty-printed or not.
        field = LocalizedHeadlineField(max_length=64)
        with pytest.raises(serializers.ValidationError):
            field.run_validation('{\n  "es": "Hola"\n}')

    def test_a_description_may_span_lines_like_any_markdown(self):
        field = LocalizedTextField(max_length=256)
        value = '{\n  "es": "Hola",\n  "ca": "Hola"\n}'
        assert field.run_validation(value) == value

    def test_an_unsafe_link_scheme_inside_one_language_is_rejected(self):
        field = LocalizedTextField(max_length=256)
        with pytest.raises(serializers.ValidationError):
            field.run_validation('{"es": "[x](javascript:alert(1))"}')

    def test_a_tag_label_caps_each_language_at_its_own_limit(self):
        field = LocalizedHeadlineField(max_length=32, storage_max_length=160)
        assert field.run_validation('{"es": "Juguetes", "ca": "Joguines"}')
        with pytest.raises(serializers.ValidationError):
            field.run_validation('{"es": "%s"}' % ("j" * 33))
