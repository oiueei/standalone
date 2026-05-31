"""Unit tests for email service resilience.

A failing/slow SMTP provider must never propagate out of the email layer:
user actions whose DB work has already committed must not 500, and
multi-recipient loops must not abort on one bad recipient.
"""

import smtplib
from unittest.mock import patch

from core.services import email_service


def test_send_returns_false_on_smtp_error():
    """_send swallows an SMTP error and reports failure instead of raising."""
    with patch(
        "core.services.email_service.send_mail",
        side_effect=smtplib.SMTPException("provider down"),
    ):
        result = email_service._send(
            "nobody@example.com",
            "Subject",
            "plain",
            "<p>html</p>",
            email_service.CATEGORY_MANDATORY,
        )
    assert result is False


def test_send_returns_false_on_socket_error():
    """A socket-level error (timeout/connection) is also swallowed."""
    with patch(
        "core.services.email_service.send_mail",
        side_effect=OSError("connection refused"),
    ):
        result = email_service._send(
            "nobody@example.com",
            "Subject",
            "plain",
            "<p>html</p>",
            email_service.CATEGORY_MANDATORY,
        )
    assert result is False


def test_public_send_does_not_raise_when_provider_is_down():
    """A mandatory email (magic link) must not raise when SMTP fails — the
    sign-in action it backs must not 500 because mail is temporarily down."""
    with patch(
        "core.services.email_service.send_mail",
        side_effect=smtplib.SMTPException("down"),
    ):
        email_service.send_magic_link_email("nobody@example.com", "https://x/verify/ABC123")
