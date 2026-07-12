"""EMAIL_LANGUAGE: the per-deployment language for all outbound email.

The standalone repo defaults to English; www.oiueei.com sets EMAIL_LANGUAGE=es.
These tests pin the default, the Spanish deployment, the unknown-code fallback,
and the en/{es,ca} catalogue parity (the email analogue of i18nParity.test.js).
"""

import string

import pytest
from django.core import mail
from django.test import override_settings

from core.models import Collection, User
from core.services import email_service
from core.services.email_texts import T, ca, en, es


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
        class FakeCollections:
            def first(self):
                return None

        class FakeThing:
            headline = "Tienda"
            code = "THG123"
            collections = FakeCollections()

        email_service.send_faq_answer_email("Lala", FakeThing(), "¿Sigue?", "Sí", "q@example.com")
        assert "Gestiona tus preferencias de correo" in mail.outbox[0].body
        # The thing headline is now the link label in both formats.
        assert "Tienda" in mail.outbox[0].body
        assert "Tienda" in mail.outbox[0].alternatives[0][0]

    @override_settings(EMAIL_LANGUAGE="es")
    def test_interpolated_decision_email_in_spanish(self):
        class FakeBooking:
            start_date = None
            end_date = None
            requester_email = "r@example.com"

        class FakeThing:
            headline = "Taladro"
            type = "SELL_THING"

        email_service.send_booking_decision_email(FakeBooking(), FakeThing(), accepted=True)
        assert mail.outbox[0].subject == "Tenemos noticias"
        assert "ha sido confirmada" in mail.outbox[0].body
        assert "compra" in mail.outbox[0].body
        assert "Taladro" in mail.outbox[0].body

    def _send_sell_confirmation(self):
        """Send a SELL confirmation and return the resulting mailbox message."""

        class FakeOwner:
            display_name = "Lala"

        class FakeCollections:
            def first(self):
                return None

        class FakeThing:
            headline = "Drill"
            code = "THG123"
            type = "SELL_THING"
            owner = FakeOwner()
            collections = FakeCollections()

        class FakeBooking:
            start_date = None
            end_date = None

        class FakeRequester:
            email = "r@example.com"

        mail.outbox.clear()
        email_service.send_booking_confirmation_email(FakeRequester(), FakeThing(), FakeBooking())
        return mail.outbox[0]

    def test_confirmation_carries_per_type_action_noun(self):
        # A SELL confirmation must name the type's action noun — "compra" in the
        # Spanish deployment, "purchase" in English — in both subject and body.
        with override_settings(EMAIL_LANGUAGE="es"):
            msg = self._send_sell_confirmation()
            assert "compra" in msg.subject
            assert "compra" in msg.body
        with override_settings(EMAIL_LANGUAGE="en"):
            msg = self._send_sell_confirmation()
            assert "purchase" in msg.subject
            assert "purchase" in msg.body


# Catalogues that must mirror the en reference (keys, placeholders, viral shape).
OTHER_CATALOGUES = [es, ca]


class TestCatalogueParity:
    @pytest.mark.parametrize("catalogue", OTHER_CATALOGUES, ids=["es", "ca"])
    def test_covers_exactly_the_en_keys(self, catalogue):
        assert set(catalogue.TEXTS) == set(en.TEXTS)

    @pytest.mark.parametrize("catalogue", OTHER_CATALOGUES, ids=["es", "ca"])
    def test_placeholders_match_en(self, catalogue):
        # A translation must keep every {placeholder} its English source has —
        # otherwise .format() raises at send time.
        fmt = string.Formatter()

        def fields(template):
            return {name for _, name, _, _ in fmt.parse(template) if name}

        mismatched = [k for k in en.TEXTS if fields(en.TEXTS[k]) != fields(catalogue.TEXTS[k])]
        assert mismatched == []

    @pytest.mark.parametrize("catalogue", OTHER_CATALOGUES, ids=["es", "ca"])
    def test_viral_lines_shape_matches_en(self, catalogue):
        # VIRAL_LINES must have the same length and the same dict keys in every
        # catalogue (the analogue of the TEXTS parity above).
        assert len(en.VIRAL_LINES) == len(catalogue.VIRAL_LINES)
        assert len(en.VIRAL_LINES) > 0
        keys = {frozenset(d) for d in en.VIRAL_LINES} | {
            frozenset(d) for d in catalogue.VIRAL_LINES
        }
        assert keys == {frozenset({"text", "cta"})}

    def test_T_reads_settings_lazily(self):
        with override_settings(EMAIL_LANGUAGE="es"):
            assert T("magic_cta") == "Iniciar sesión"
        with override_settings(EMAIL_LANGUAGE="en"):
            assert T("magic_cta") == "Sign in"
        with override_settings(EMAIL_LANGUAGE="ca"):
            assert T("magic_cta") == "Iniciar sessió"

    @override_settings(EMAIL_LANGUAGE="ca")
    def test_ca_smoke(self):
        # The Catalan catalogue is wired end-to-end via the lazy import.
        email_service.send_magic_link_email("a@example.com", "http://x/verify/tok")
        assert mail.outbox[0].subject == "Hola, et donem la benvinguda a OIUEEI!"
        assert "iniciar sessió" in mail.outbox[0].body


@pytest.mark.django_db
class TestViralLine:
    """The growth CTA appended above the preferences footer (S3)."""

    def _thing(self):
        class FakeCollections:
            def first(self):
                return None

        class FakeThing:
            headline = "Taladro"
            code = "THG123"
            collections = FakeCollections()

        return FakeThing()

    def test_line_present_for_non_owner(self):
        # A registered user with no collection is exactly the target audience.
        u = User.objects.create(code="GUEST1", email="guest@test.com", name="Guest")
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", u.email)
        assert "/collections/new" in mail.outbox[0].body
        assert "/collections/new" in mail.outbox[0].alternatives[0][0]

    def test_line_absent_for_collection_owner(self):
        owner = User.objects.create(code="OWNR1", email="owner@test.com", name="Owner")
        Collection.objects.create(code="OWNC1", owner=owner, headline="Mine", status="ACTIVE")
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", owner.email)
        assert "/collections/new" not in mail.outbox[0].body

    def test_line_absent_on_magic_link(self):
        u = User.objects.create(code="GUEST2", email="magic@test.com", name="Guest")
        mail.outbox.clear()
        email_service.send_magic_link_email(u.email, "http://x/verify/tok")
        assert "/collections/new" not in mail.outbox[0].body

    def test_footer_still_after_viral_line(self):
        u = User.objects.create(code="GUEST3", email="foot@test.com", name="Guest")
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", u.email)
        body = mail.outbox[0].body
        # Viral CTA appears before the preferences footer (footer always last).
        assert body.index("/collections/new") < body.index("Manage your email preferences")
