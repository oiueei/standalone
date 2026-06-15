"""
Unit tests for OIUEEI validators.
"""

import pytest
from rest_framework import serializers

from core.validators import (
    ImageIdField,
    SafeHeadlineField,
    SafeTextField,
    validate_headline,
    validate_image_id,
    validate_text,
)


class TestValidateImageId:
    """Tests for validate_image_id function."""

    def test_valid_alphanumeric(self):
        """Should accept alphanumeric characters."""
        assert validate_image_id("abc123") == "abc123"
        assert validate_image_id("ABC123") == "ABC123"
        assert validate_image_id("ABCDEF") == "ABCDEF"
        assert validate_image_id("123456") == "123456"

    def test_valid_with_underscores(self):
        """Should accept underscores."""
        assert validate_image_id("abc_123") == "abc_123"
        assert validate_image_id("_test_") == "_test_"

    def test_valid_with_hyphens(self):
        """Should accept hyphens."""
        assert validate_image_id("abc-123") == "abc-123"
        assert validate_image_id("-test-") == "-test-"

    def test_valid_mixed(self):
        """Should accept mix of valid characters."""
        assert validate_image_id("abc_123-XYZ") == "abc_123-XYZ"

    def test_empty_value_allowed(self):
        """Should accept empty values."""
        assert validate_image_id("") == ""
        assert validate_image_id(None) is None

    def test_invalid_with_html(self):
        """Should reject HTML tags."""
        with pytest.raises(serializers.ValidationError):
            validate_image_id("<script>alert(1)</script>")

    def test_invalid_with_path_traversal(self):
        """Should reject path traversal attempts."""
        with pytest.raises(serializers.ValidationError):
            validate_image_id("../etc/passwd")
        with pytest.raises(serializers.ValidationError):
            validate_image_id("..\\windows\\system32")

    def test_invalid_with_spaces(self):
        """Should reject spaces."""
        with pytest.raises(serializers.ValidationError):
            validate_image_id("abc 123")

    def test_invalid_with_special_chars(self):
        """Should reject special characters."""
        with pytest.raises(serializers.ValidationError):
            validate_image_id("abc@123")
        with pytest.raises(serializers.ValidationError):
            validate_image_id("abc#123")
        with pytest.raises(serializers.ValidationError):
            validate_image_id("abc$123")


class TestImageIdField:
    """Tests for ImageIdField serializer field."""

    def test_valid_value(self):
        """Should accept valid image IDs."""
        field = ImageIdField()
        assert field.to_internal_value("abc123") == "abc123"

    def test_max_length_default(self):
        """Should have default max_length of 255 (folder-prefixed Cloudinary IDs)."""
        field = ImageIdField()
        assert field.max_length == 255

    def test_not_required_by_default(self):
        """Should not be required by default."""
        field = ImageIdField()
        assert field.required is False

    def test_invalid_value_raises(self):
        """Should raise on invalid input."""
        field = ImageIdField()
        with pytest.raises(serializers.ValidationError):
            field.to_internal_value("<script>")


class TestValidateHeadline:
    """Tests for validate_headline function."""

    def test_valid_plain_text(self):
        """Should accept plain text."""
        assert validate_headline("Hello World") == "Hello World"
        assert validate_headline("My Collection 2024") == "My Collection 2024"

    def test_valid_with_punctuation(self):
        """Should accept punctuation."""
        assert validate_headline("Hello, World!") == "Hello, World!"
        assert validate_headline("What's up?") == "What's up?"

    def test_valid_with_unicode(self):
        """Should accept unicode characters."""
        assert validate_headline("Boda de Maria") == "Boda de Maria"

    def test_empty_value_allowed(self):
        """Should accept empty values."""
        assert validate_headline("") == ""
        assert validate_headline(None) is None

    def test_invalid_with_script_tags(self):
        """Should reject script tags."""
        with pytest.raises(serializers.ValidationError):
            validate_headline("<script>alert(1)</script>")

    def test_invalid_with_html_tags(self):
        """Should reject any HTML tags."""
        with pytest.raises(serializers.ValidationError):
            validate_headline("<b>Bold</b>")
        with pytest.raises(serializers.ValidationError):
            validate_headline("<a href='bad'>Link</a>")
        with pytest.raises(serializers.ValidationError):
            validate_headline("<img src=x onerror=alert(1)>")

    def test_invalid_with_event_handlers(self):
        """Should reject event handler attempts."""
        with pytest.raises(serializers.ValidationError):
            validate_headline('<div onmouseover="alert(1)">')

    def test_invalid_with_line_breaks(self):
        """Should reject CR/LF (header-injection guard for email subjects)."""
        with pytest.raises(serializers.ValidationError):
            validate_headline("Hello\r\nBcc: victim@example.com")
        with pytest.raises(serializers.ValidationError):
            validate_headline("Line one\nLine two")

    def test_invalid_with_unsafe_link_scheme(self):
        """Should reject dangerous URL schemes in Markdown links."""
        with pytest.raises(serializers.ValidationError):
            validate_headline("[click](javascript:alert(1))")
        with pytest.raises(serializers.ValidationError):
            validate_headline("[x](data:text/plain,hello)")


class TestValidateText:
    """Tests for validate_text (multi-line Markdown fields)."""

    def test_allows_newlines(self):
        """Should permit line breaks (Markdown paragraphs/lists)."""
        assert validate_text("a\nb\nc") == "a\nb\nc"

    def test_allows_safe_markdown_links(self):
        """Should permit http(s) Markdown links."""
        value = "See [my site](https://example.org/path?q=1)"
        assert validate_text(value) == value

    def test_rejects_html(self):
        """Should reject raw HTML tags."""
        with pytest.raises(serializers.ValidationError):
            validate_text("<script>alert(1)</script>")

    def test_rejects_unsafe_scheme(self):
        """Should reject dangerous URL schemes in Markdown links."""
        with pytest.raises(serializers.ValidationError):
            validate_text("[x](javascript:alert(1))")

    def test_empty_value_allowed(self):
        """Should accept empty values."""
        assert validate_text("") == ""
        assert validate_text(None) is None


class TestSafeHeadlineField:
    """Tests for SafeHeadlineField serializer field."""

    def test_valid_value(self):
        """Should accept valid headlines."""
        field = SafeHeadlineField()
        assert field.to_internal_value("My Collection") == "My Collection"

    def test_invalid_value_raises(self):
        """Should raise on HTML input."""
        field = SafeHeadlineField()
        with pytest.raises(serializers.ValidationError):
            field.to_internal_value("<script>bad</script>")


class TestSafeTextField:
    """Tests for SafeTextField serializer field (used by the User `about` Markdown bio)."""

    def test_accepts_multiline_markdown(self):
        """Should accept multi-line Markdown (newlines, bold, list dashes, links)."""
        field = SafeTextField(max_length=2000)
        value = "Contact me at [my site](https://example.com)\n- one\n- two\n**bold**"
        assert field.to_internal_value(value) == value

    def test_empty_value_allowed(self):
        field = SafeTextField(allow_blank=True)
        assert field.to_internal_value("") == ""

    def test_invalid_with_html(self):
        """Should reject raw HTML tags (XSS guard) while permitting Markdown."""
        field = SafeTextField()
        with pytest.raises(serializers.ValidationError):
            field.to_internal_value("<script>alert(1)</script>")
        with pytest.raises(serializers.ValidationError):
            field.to_internal_value("<iframe src=x></iframe>")

    def test_invalid_with_unsafe_link_scheme(self):
        """Should reject dangerous URL schemes in Markdown links."""
        field = SafeTextField()
        with pytest.raises(serializers.ValidationError):
            field.to_internal_value("[click me](javascript:alert(document.cookie))")

    def test_allows_newlines_with_safe_links(self):
        """Multi-line Markdown plus http(s) links must pass."""
        field = SafeTextField(max_length=2000)
        value = "Para 1\n\nPara 2 with [a link](https://example.org/path?q=1)"
        assert field.to_internal_value(value) == value
