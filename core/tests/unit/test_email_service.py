"""Unit tests for email service resilience.

A failing/slow SMTP provider must never propagate out of the email layer:
user actions whose DB work has already committed must not 500, and
multi-recipient loops must not abort on one bad recipient.
"""

import smtplib
from unittest.mock import patch

import pytest
from django.core import mail

from core.services import email_service


def test_send_returns_false_on_smtp_error():
    """_send swallows an SMTP error and reports failure instead of raising."""
    with patch(
        "core.services.email_service.EmailMultiAlternatives.send",
        side_effect=smtplib.SMTPException("provider down"),
    ):
        result = email_service._send(
            "nobody@example.com",
            "Subject",
            "plain",
            "<p>html</p>",
            email_service.CATEGORY_MANDATORY,
            include_viral=False,
        )
    assert result is False


def test_send_returns_false_on_socket_error():
    """A socket-level error (timeout/connection) is also swallowed."""
    with patch(
        "core.services.email_service.EmailMultiAlternatives.send",
        side_effect=OSError("connection refused"),
    ):
        result = email_service._send(
            "nobody@example.com",
            "Subject",
            "plain",
            "<p>html</p>",
            email_service.CATEGORY_MANDATORY,
            include_viral=False,
        )
    assert result is False


def test_public_send_does_not_raise_when_provider_is_down():
    """A mandatory email (magic link) must not raise when SMTP fails — the
    sign-in action it backs must not 500 because mail is temporarily down."""
    with patch(
        "core.services.email_service.EmailMultiAlternatives.send",
        side_effect=smtplib.SMTPException("down"),
    ):
        email_service.send_magic_link_email("nobody@example.com", "https://x/verify/ABC123")


@pytest.mark.django_db
def test_html_email_embeds_logo_inline():
    """An activity email carries the OIUEEI logo as a CID attachment (S5): one
    inline image attachment on the message, referenced from the HTML
    alternative, plain-text body untouched."""
    email_service.send_invite_rejected_email("Ana", "Ropa de invierno", "owner@example.com")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert len(msg.attachments) == 1
    assert msg.attachments[0]["Content-ID"] == "<oiueei-logo>"
    assert msg.attachments[0]["Content-Disposition"].startswith("inline")
    html_body = msg.alternatives[0][0]
    assert "cid:oiueei-logo" in html_body
    assert "cid:oiueei-logo" not in msg.body
