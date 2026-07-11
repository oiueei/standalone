"""EMAIL_LANGUAGE: the per-deployment language for all outbound email.

The standalone repo defaults to English; www.oiueei.com sets EMAIL_LANGUAGE=es.
These tests pin the default, the Spanish deployment, the unknown-code fallback,
and the en/es catalogue parity (the email analogue of i18nParity.test.js).
"""

import pytest
from django.core import mail
from django.test import override_settings

from core.services import email_service
from core.services.email_texts import T, en, es


@pytest.mark.django_db
class TestEmailLanguage:
    def test_default_is_english(self):
        email_service.send_magic_link_email("a@example.com", "http://x/verify/tok")
        assert mail.outbox[0].subject == "Hello, welcome to OIUEEI!"
        assert "Click here to sign in" in mail.outbox[0].body

    @override_settings(EMAIL_LANGUAGE="es")
    def test_spanish_deployment(self):
        email_service.send_magic_link_email("a@example.com", "http://x/verify/tok")
        assert mail.outbox[0].subject == "¡Hola, te damos la bienvenida a OIUEEI!"
        assert "iniciar sesión" in mail.outbox[0].body
        html = mail.outbox[0].alternatives[0][0]
        assert "Iniciar sesión" in html

    @override_settings(EMAIL_LANGUAGE="xx")
    def test_unknown_language_falls_back_to_english(self):
        email_service.send_magic_link_email("a@example.com", "http://x/verify/tok")
        assert mail.outbox[0].subject == "Hello, welcome to OIUEEI!"

    @override_settings(EMAIL_LANGUAGE="es")
    def test_footer_is_translated_on_activity_emails(self):
        email_service.send_faq_answer_email("Lala", "Tienda", "¿Sigue?", "Sí", "q@example.com")
        assert "Gestiona tus preferencias de correo" in mail.outbox[0].body

    @override_settings(EMAIL_LANGUAGE="es")
    def test_interpolated_decision_email_in_spanish(self):
        class FakeBooking:
            start_date = None
            end_date = None
            requester_email = "r@example.com"

        class FakeThing:
            headline = "Taladro"

        email_service.send_booking_decision_email(FakeBooking(), FakeThing(), accepted=True)
        assert mail.outbox[0].subject == "Tenemos noticias"
        assert "ha sido confirmada" in mail.outbox[0].body
        assert "Taladro" in mail.outbox[0].body


class TestCatalogueParity:
    def test_es_covers_exactly_the_en_keys(self):
        assert set(es.TEXTS) == set(en.TEXTS)

    def test_placeholders_match_between_languages(self):
        # A translation must keep every {placeholder} its English source has —
        # otherwise .format() raises at send time.
        import string

        fmt = string.Formatter()

        def fields(template):
            return {name for _, name, _, _ in fmt.parse(template) if name}

        mismatched = [key for key in en.TEXTS if fields(en.TEXTS[key]) != fields(es.TEXTS[key])]
        assert mismatched == []

    def test_T_reads_settings_lazily(self):
        with override_settings(EMAIL_LANGUAGE="es"):
            assert T("magic_cta") == "Iniciar sesión"
        with override_settings(EMAIL_LANGUAGE="en"):
            assert T("magic_cta") == "Sign in"
