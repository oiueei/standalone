"""
Custom validators and fields for OIUEEI.

Provides secure validation for user inputs including:
- Image IDs (alphanumeric only)
- Headlines (no HTML/XSS)
- Owner content that may carry one text per language (the ``Localized*`` fields)
"""

import re

from rest_framework import serializers

from core.utils import parse_localized


def validate_image_id(value):
    """
    Validate that a Cloudinary public_id contains only safe characters.

    Allows letters, numbers, underscores, hyphens, and forward slashes
    (needed for folder-prefixed public_ids such as oiueei/things/abc123).
    Rejects double slashes, leading/trailing slashes, and any other characters
    to prevent path traversal and injection attacks.
    """
    if value:
        if not re.match(r"^[a-zA-Z0-9_/.-]+$", value):
            raise serializers.ValidationError(
                "Image ID can only contain letters, numbers, underscores, "
                "hyphens, dots, and forward slashes."
            )
        if "//" in value or value.startswith("/") or value.endswith("/"):
            raise serializers.ValidationError("Image ID contains invalid slash usage.")
        if ".." in value:
            raise serializers.ValidationError("Image ID contains path traversal sequence.")
    return value


class ImageIdField(serializers.CharField):
    """
    A CharField that validates Cloudinary public_ids.

    Accepts folder-prefixed IDs (e.g. oiueei/things/abc123) as well as
    plain IDs. Prevents path traversal and injection attacks.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 255)
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_blank", True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return validate_image_id(value)


def _reject_html_and_unsafe_schemes(value):
    """
    Shared write-path guard for user-supplied text (defence-in-depth).

    Output XSS is already handled by React's escaping, the frontend Markdown
    URL sanitiser, and email autoescaping; these checks simply stop obvious
    markup from reaching storage in the first place. No HTML-sanitisation
    library is used — plain rejection keeps the dependency surface minimal.

    Rejects:
    - HTML tags (``<...>``), which also covers autolinks like ``<javascript:...>``.
    - Dangerous URL schemes in Markdown links, e.g. ``[x](javascript:...)``.
    """
    if re.search(r"<[^>]+>", value):
        raise serializers.ValidationError("HTML tags are not allowed.")
    if re.search(r"]\(\s*(?:javascript|data|vbscript):", value, re.IGNORECASE):
        raise serializers.ValidationError("Unsafe link scheme is not allowed.")


def validate_headline(value):
    """
    Validate a single-line headline.

    Rejects HTML, unsafe link schemes, and line breaks. Line breaks matter
    because headlines flow into email Subject lines, where a raw CR/LF would
    raise Django's ``BadHeaderError`` (header-injection guard) — see
    ``core.services.email_service._send``.
    """
    if value:
        _reject_html_and_unsafe_schemes(value)
        if "\r" in value or "\n" in value:
            raise serializers.ValidationError("Line breaks are not allowed.")
    return value


def validate_text(value):
    """
    Validate a multi-line text field (Markdown allowed).

    Same HTML / unsafe-scheme guards as ``validate_headline``, but permits line
    breaks so Markdown paragraphs and lists survive (e.g. the User ``about`` bio).
    """
    if value:
        _reject_html_and_unsafe_schemes(value)
    return value


class SafeHeadlineField(serializers.CharField):
    """A single-line CharField that rejects HTML, unsafe link schemes and line breaks."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return validate_headline(value)


class SafeTextField(serializers.CharField):
    """
    A multi-line CharField (Markdown) that rejects HTML and unsafe link schemes.

    Line breaks are permitted. Used for longer text such as the User ``about`` bio.
    """

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return validate_text(value)


# How much room the *column* gives an owner-localized value: the same text in
# every language OIUEEI speaks (3 × the visible limit) plus the JSON scaffolding.
# The visible limit — what one language may say — stays what it always was and is
# what the field is constructed with. Tags live in a JSONField, so their storage
# cap is ours to pick rather than a column width.
LOCALIZED_HEADLINE_STORAGE = 256
LOCALIZED_TEXT_STORAGE = 1024
LOCALIZED_TAG_STORAGE = 160


def _validate_localized(value, visible_max_length, guard):
    """Validate a value the owner may have written as a ``{lang: text}`` map.

    Plain text keeps exactly the limit it always had. A localized map is checked
    **per language**: each text runs through the same HTML / unsafe-scheme (and,
    for headlines, line-break) guard as a plain value would, and each must fit the
    visible limit on its own — three languages don't buy three times the length.

    The *raw* string is guarded too (the field's own `Safe*` `to_internal_value`
    ran first, and its `max_length` is the storage cap), so markup can't hide in a
    key, and a map whose JSON scaffolding overflows the column is a 400 rather
    than a PostgreSQL `DataError` at write time — SQLite would let it through
    locally (see the max_length note in the root CLAUDE.md).
    """
    localized = parse_localized(value)
    if localized is None:
        if len(value) > visible_max_length:
            raise serializers.ValidationError(
                f"Ensure this field has no more than {visible_max_length} characters."
            )
        return value
    for lang, text in localized.items():
        guard(text)
        if len(text) > visible_max_length:
            raise serializers.ValidationError(
                f"The {lang} text is longer than {visible_max_length} characters."
            )
    return value


class LocalizedHeadlineField(SafeHeadlineField):
    """A headline (or tag label) the owner may write as a ``{lang: text}`` map.

    ``max_length`` is what one language may say; the column is wide enough for all
    three. A multi-line (pretty-printed) map is rejected like any other headline
    with a line break in it — headlines flow into email Subject lines — so the map
    must be written on one line, which is how the form's example shows it.
    """

    def __init__(self, max_length, storage_max_length=LOCALIZED_HEADLINE_STORAGE, **kwargs):
        self.visible_max_length = max_length
        super().__init__(max_length=storage_max_length, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return _validate_localized(value, self.visible_max_length, validate_headline)


class LocalizedTextField(SafeTextField):
    """A description the owner may write as a ``{lang: text}`` map (Markdown allowed)."""

    def __init__(self, max_length, storage_max_length=LOCALIZED_TEXT_STORAGE, **kwargs):
        self.visible_max_length = max_length
        super().__init__(max_length=storage_max_length, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return _validate_localized(value, self.visible_max_length, validate_text)


# Characters a spreadsheet treats as the start of a formula (CSV injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def reject_spreadsheet_formula(value):
    """
    Reject text whose first non-space character would make a spreadsheet execute
    it as a formula if the data were ever exported to CSV (CSV injection).

    Applied to free-text fields imported via the bulk CSV upload (F-9): a row is
    rejected (so the user fixes the source) rather than silently mangled. The
    existing ``Safe*`` fields already strip HTML and line breaks; this adds the
    leading ``= + - @`` guard on top.
    """
    if value and value.lstrip()[:1] in _FORMULA_PREFIXES:
        raise serializers.ValidationError(
            "This field cannot start with =, +, - or @ (spreadsheet formula injection)."
        )
    return value
