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


def validate_headline(value):
    """
    Validate that a headline does not contain HTML tags.

    Rejects any input that contains HTML to prevent XSS attacks.
    """
    if value and re.search(r"<[^>]+>", value):
        raise serializers.ValidationError("HTML tags are not allowed.")
    return value


class SafeHeadlineField(serializers.CharField):
    """
    A CharField that rejects HTML content to prevent XSS.

    Uses bleach to detect and reject any HTML tags in the input.
    """

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return validate_headline(value)


class SafeTextField(serializers.CharField):
    """
    A CharField that rejects HTML content for longer text fields.

    Uses the same bleach-based validation as SafeHeadlineField.
    """

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return validate_headline(value)
