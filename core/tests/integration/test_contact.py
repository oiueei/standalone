"""The contact form (support channel): anonymous on purpose — the person who
most needs it is the one who can't log in. Fixed recipient (the operator), the
sender's address as Reply-To, per-IP rate limit."""

import pytest
from django.core import mail

CONTACT_URL = "/api/v1/contact/"


@pytest.mark.django_db
class TestContactForm:
    def test_anonymous_message_reaches_the_operator_with_reply_to(self, api_client, settings):
        settings.DEFAULT_FROM_EMAIL = "operator@example.com"
        response = api_client.post(
            CONTACT_URL,
            {"name": "Napoleón", "email": "nappy@example.com", "message": "No puedo entrar."},
            format="json",
        )
        assert response.status_code == 200
        assert len(mail.outbox) == 1
        sent = mail.outbox[0]
        assert sent.to == ["operator@example.com"]
        assert sent.reply_to == ["nappy@example.com"]
        assert "No puedo entrar." in sent.body
        assert "Napoleón" in sent.subject

    def test_name_is_optional_email_is_the_fallback_sender(self, api_client):
        response = api_client.post(
            CONTACT_URL, {"email": "quiet@example.com", "message": "Hola."}, format="json"
        )
        assert response.status_code == 200
        assert "quiet@example.com" in mail.outbox[0].subject

    def test_collab_kind_labels_the_subject_differently(self, api_client):
        api_client.post(
            CONTACT_URL,
            {"email": "dev@example.com", "message": "I design.", "kind": "collab"},
            format="json",
        )
        assert "collaboration" in mail.outbox[0].subject.lower()

    def test_message_and_valid_email_are_required(self, api_client):
        assert api_client.post(CONTACT_URL, {"email": "a@b.com"}, format="json").status_code == 400
        assert (
            api_client.post(
                CONTACT_URL, {"email": "not-an-email", "message": "x"}, format="json"
            ).status_code
            == 400
        )
        assert len(mail.outbox) == 0

    def test_html_in_the_message_is_rejected(self, api_client):
        response = api_client.post(
            CONTACT_URL,
            {"email": "a@b.com", "message": "<script>alert(1)</script>"},
            format="json",
        )
        assert response.status_code == 400
        assert len(mail.outbox) == 0
