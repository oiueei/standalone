"""
Custom validators and fields for OIUEEI.

Provides secure validation for user inputs including:
- Image IDs (alphanumeric only)
- Headlines (no HTML/XSS)
"""

import re

from rest_framework import serializers


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
