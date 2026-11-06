"""EMAIL_LANGUAGE: the per-deployment language for all outbound email.

The standalone repo defaults to English; a deployment may set EMAIL_LANGUAGE=es.
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
        email_service.send_magic_link_email("lili@your-domain.test", "http://x/verify/tok")
        assert mail.outbox[0].subject == "Hello, welcome to OIUEEI!"
        assert "Click the link to sign in" in mail.outbox[0].body

    @override_settings(EMAIL_LANGUAGE="es")
    def test_spanish_deployment(self):
        email_service.send_magic_link_email("lili@your-domain.test", "http://x/verify/tok")
        assert mail.outbox[0].subject == "¡Hola, te damos la bienvenida a OIUEEI!"
        assert "iniciar sesión" in mail.outbox[0].body
        html = mail.outbox[0].alternatives[0][0]
        assert "Iniciar sesión" in html

    @override_settings(EMAIL_LANGUAGE="xx")
    def test_unknown_language_falls_back_to_english(self):
        email_service.send_magic_link_email("lili@your-domain.test", "http://x/verify/tok")
        assert mail.outbox[0].subject == "Hello, welcome to OIUEEI!"

    @override_settings(EMAIL_LANGUAGE="es")
    def test_footer_is_translated_on_activity_emails(self):
        class FakeCollections:
            def first(self):
                return None

            def all(self):
                return []

        class FakeThing:
            headline = "Tienda"
            code = "THG123"
            collections = FakeCollections()

        email_service.send_faq_answer_email(
            "Lala", FakeThing(), "¿Sigue?", "Sí", "lili8@your-domain.test"
        )
        assert "Gestiona tus preferencias de correo" in mail.outbox[0].body
        # The thing headline is now the link label in both formats.
        assert "Tienda" in mail.outbox[0].body
        assert "Tienda" in mail.outbox[0].alternatives[0][0]

    @override_settings(EMAIL_LANGUAGE="es")
    def test_interpolated_decision_email_in_spanish(self):
        class FakeBooking:
            start_date = None
            end_date = None
            quantity = 1
            requester_email = "lala1@your-domain.test"

        class FakeCollections:
            def first(self):
                return None

            def all(self):
                return []

        class FakeThing:
            headline = "Taladro"
            code = "THG123"
            type = "SELL_THING"
            collections = FakeCollections()

        email_service.send_booking_decision_email(FakeBooking(), FakeThing(), accepted=True)
        assert mail.outbox[0].subject == "Tu solicitud está confirmada"
        assert "ha sido confirmada" in mail.outbox[0].body
        assert "compra" in mail.outbox[0].body
        assert "Taladro" in mail.outbox[0].body
        # The decision is the end of the requester's flow, so it has to lead
        # somewhere: the thing, in both formats, translated CTA in the HTML.
        assert "/things/THG123" in mail.outbox[0].body
        html = mail.outbox[0].alternatives[0][0]
        assert "/things/THG123" in html
        assert "Ver la publicación" in html

    @override_settings(EMAIL_LANGUAGE="es")
    def test_decision_subject_tells_the_two_outcomes_apart(self):
        """One subject per decision — the inbox has to be readable without opening."""

        class FakeBooking:
            start_date = None
            end_date = None
            quantity = 1
            requester_email = "lala1@your-domain.test"

        class FakeCollections:
            def first(self):
                return None

            def all(self):
                return []

        class FakeThing:
            headline = "Taladro"
            code = "THG123"
            type = "SELL_THING"
            collections = FakeCollections()

        email_service.send_booking_decision_email(FakeBooking(), FakeThing(), accepted=False)
        assert mail.outbox[0].subject == "Tu solicitud no ha salido adelante"
        # "rechazada", not "cancelada": the manager declined it, nobody cancelled it.
        assert "ha sido rechazada" in mail.outbox[0].body
        assert "cancelada" not in mail.outbox[0].body

    def _send_sell_confirmation(self):
        """Send a SELL confirmation and return the resulting mailbox message."""

        class FakeCollections:
            def first(self):
                return None

            def all(self):
                return []

        class FakeThing:
            headline = "Drill"
            code = "THG123"
            type = "SELL_THING"
            collections = FakeCollections()

        class FakeBooking:
            start_date = None
            end_date = None
            quantity = 1

        class FakeRequester:
            email = "lala1@your-domain.test"

        mail.outbox.clear()
        # `informed` is what the request's fan-out tells the email (how many people it
        # warned); the email no longer names the owner, so the fakes need no owner.
        email_service.send_booking_confirmation_email(
            FakeRequester(), FakeThing(), FakeBooking(), informed=1
        )
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

    def test_every_bookable_type_has_an_action_noun(self):
        # Every type that can reach the shared booking emails needs a noun in
        # the en reference (key parity extends it to es/ca). The decision email
        # is shared — finalize_booking_decision runs for every booking type —
        # so a missing key is a KeyError mid-decision, after the booking has
        # already been accepted and the thing taken out of circulation.
        from core.models import Thing

        missing = [t for t in Thing.Type.values if f"action_noun_{t}" not in en.TEXTS]
        assert missing == []

    @pytest.mark.parametrize("catalogue", OTHER_CATALOGUES, ids=["es", "ca"])
    def test_viral_lines_shape_matches_en(self, catalogue):
        # VIRAL_LINES must have the same length and the same dict keys in every
        # catalogue (the analogue of the TEXTS parity above).
        assert len(en.VIRAL_LINES) == len(catalogue.VIRAL_LINES)
        assert len(en.VIRAL_LINES) > 0
        keys = {frozenset(d) for d in en.VIRAL_LINES} | {
            frozenset(d) for d in catalogue.VIRAL_LINES
        }
        assert keys == {frozenset({"text", "cta", "path"})}

    @pytest.mark.parametrize("catalogue", OTHER_CATALOGUES, ids=["es", "ca"])
    def test_every_viral_line_leads_to_the_same_place_in_every_language(self, catalogue):
        assert [line["path"] for line in en.VIRAL_LINES] == [
            line["path"] for line in catalogue.VIRAL_LINES
        ]

    def test_every_viral_line_leads_to_a_form_the_app_has(self):
        assert {line["path"] for line in en.VIRAL_LINES} <= {
            "/new",
            "/stall/new",
            "/library/new",
            "/shed/new",
        }

    def test_T_reads_settings_lazily(self):
        with override_settings(EMAIL_LANGUAGE="es"):
            assert T("magic_cta") == "Iniciar sesión →"
        with override_settings(EMAIL_LANGUAGE="en"):
            assert T("magic_cta") == "Sign in →"
        with override_settings(EMAIL_LANGUAGE="ca"):
            assert T("magic_cta") == "Iniciar sessió →"

    @override_settings(EMAIL_LANGUAGE="ca")
    def test_ca_smoke(self):
        # The Catalan catalogue is wired end-to-end via the lazy import.
        email_service.send_magic_link_email("lili@your-domain.test", "http://x/verify/tok")
        assert mail.outbox[0].subject == "Hola, et donem la benvinguda a OIUEEI!"
        assert "iniciar sessió" in mail.outbox[0].body


@pytest.mark.django_db
class TestViralLine:
    """The growth CTA appended above the preferences footer."""

    def _thing(self):
        class FakeCollections:
            def first(self):
                return None

            def all(self):
                return []

        class FakeThing:
            headline = "Taladro"
            code = "THG123"
            collections = FakeCollections()

        return FakeThing()

    def test_line_present_for_non_owner(self):
        # A registered user with no collection is exactly the target audience.
        u = User.objects.create(code="GUEST1", email="lele12@your-domain.test", name="Guest")
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", u.email)
        assert "/new" in mail.outbox[0].body
        assert "/new" in mail.outbox[0].alternatives[0][0]

    def test_line_absent_for_collection_owner(self):
        owner = User.objects.create(code="OWNR1", email="lala@your-domain.test", name="Owner")
        Collection.objects.create(code="OWNC1", owner=owner, headline="Mine", status="ACTIVE")
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", owner.email)
        assert "/new" not in mail.outbox[0].body

    def test_line_absent_for_a_co_curator(self):
        """Since 2026-09 a co-curator has the founder's whole reach minus
        deleting the collection, so the invitation to start one is a letter to
        somebody who already runs one. In production (2026-09-28) the FAQ
        notice reached the co-curator WITH the line and the owner without it —
        same email, two curators, one wrongly addressed."""
        founder = User.objects.create(code="OWNR3", email="lala5@your-domain.test", name="Founder")
        co = User.objects.create(code="COOWN1", email="lala2@your-domain.test", name="Co")
        collection = Collection.objects.create(
            code="COCUR1", owner=founder, headline="Ours", status="ACTIVE"
        )
        collection.co_owners.add(co)
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", co.email)
        assert "/new" not in mail.outbox[0].body

    def test_line_absent_for_a_co_curator_in_a_bulk_send(self):
        # The bulk lookup resolves the same flag in one query for the whole
        # list (broadcast is the shape that reaches it) — the suppression must
        # survive that path too, not only the per-recipient lookup.
        founder = User.objects.create(code="OWNR4", email="lala3@your-domain.test", name="Founder")
        co = User.objects.create(code="COOWN2", email="lala4@your-domain.test", name="Co")
        collection = Collection.objects.create(
            code="COCUR2", owner=founder, headline="Ours", status="ACTIVE"
        )
        collection.co_owners.add(co)
        mail.outbox.clear()
        email_service.send_broadcast_email(
            "Founder", founder.email, "Ours", collection.code, "Hello team", [co.email]
        )
        assert len(mail.outbox) == 1
        assert "/new" not in mail.outbox[0].body

    def test_a_plain_member_still_gets_the_line(self):
        # Being IN a collection is not curating one — the rank-and-file member
        # is exactly the audience the growth line addresses.
        owner = User.objects.create(code="OWNR5", email="lala6@your-domain.test", name="Owner")
        member = User.objects.create(code="MEMB1", email="lele@your-domain.test", name="Member")
        collection = Collection.objects.create(
            code="MEMC1", owner=owner, headline="Theirs", status="ACTIVE"
        )
        collection.invites.add(member)
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", member.email)
        assert "/new" in mail.outbox[0].body

    def test_line_present_on_magic_link_for_non_owner(self):
        # The magic link is the one email every user gets, so the growth
        # CTA runs here too now — still gated by collection ownership.
        u = User.objects.create(code="GUEST2", email="lele1@your-domain.test", name="Guest")
        mail.outbox.clear()
        email_service.send_magic_link_email(u.email, "http://x/verify/tok")
        assert "/new" in mail.outbox[0].body

    def test_line_present_on_magic_link_for_unregistered_address(self):
        # Not-yet-registered invitees (JoinView, before the User row exists
        # at send time in some callers) are exactly the growth target too.
        mail.outbox.clear()
        email_service.send_magic_link_email("lili1@your-domain.test", "http://x/verify/tok")
        assert "/new" in mail.outbox[0].body

    def test_line_absent_on_magic_link_for_collection_owner(self):
        owner = User.objects.create(code="OWNR2", email="lala7@your-domain.test", name="Owner")
        Collection.objects.create(code="OWNC2", owner=owner, headline="Mine", status="ACTIVE")
        mail.outbox.clear()
        email_service.send_magic_link_email(owner.email, "http://x/verify/tok")
        assert "/new" not in mail.outbox[0].body

    def test_line_absent_on_an_operator_report(self):
        """Ops mail is never growth copy — it goes to whoever runs the server.

        The capacity alarm is the operator report that remains here; the stats
        summary, which used to be this test's example, is a deployment's own
        concern and left with its command.
        """
        owner = User.objects.create(code="ALRMOW", email="lala8@your-domain.test", name="Owner")
        collection = Collection.objects.create(
            code="ALRMC1", owner=owner, headline="Busy", status="ACTIVE"
        )
        User.objects.create(code="ALRMSU", email="lolo@your-domain.test", is_superuser=True)
        mail.outbox.clear()

        email_service.send_collection_capacity_alarm(collection, "things", 501, 500)

        assert "/new" not in mail.outbox[0].body

    def test_footer_still_after_viral_line(self):
        u = User.objects.create(code="GUEST3", email="lulu@your-domain.test", name="Guest")
        mail.outbox.clear()
        email_service.send_faq_answer_email("Lala", self._thing(), "¿Sigue?", "Sí", u.email)
        body = mail.outbox[0].body
        # Viral CTA appears before the preferences footer (footer always last).
        assert body.index("/new") < body.index("Manage your email preferences")
