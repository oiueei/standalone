"""Send one sample of every email OIUEEI can send to an address you choose.

    python manage.py send_test_emails --to lulu@your-domain.test
    python manage.py send_test_emails --to lulu@your-domain.test --lang ca --only booking
    python manage.py send_test_emails --list

Why it exists: an email is the one part of the product that cannot be looked at
in a browser or a test — the client decides how it draws (Apple Mail ignored a
logo's size that Gmail honoured; some clients strip buttons), so it has to be
opened in the client. This sends the real builders, with realistic sample data,
so that can be done for every email in one sitting.

**It can only ever mail the address you pass.** Every message is rewritten on its
way out — recipient forced to ``--to``, Cc/Bcc dropped — so it does not matter how
a builder works out its recipients (the capacity alarm mails the superusers, the
contact form the operator): none of it can reach anyone else. Each subject is
prefixed ``[TEST 07/37 booking_request]`` so the messages sort and tell
themselves apart.

**It leaves nothing behind.** The sample users, collections, things and bookings
are created inside a transaction that is rolled back at the end. That includes
``--to`` itself: if it already belongs to a real account, that account is used —
with its language and notification preferences overridden for the run — and
restored by the rollback, so the emails render as any recipient would see them
(footer link, opt-outs off) whoever you are.

**The buttons are decoys.** The links point at the deployment's real address but
carry sample tokens, so they will not do anything when clicked. What is being
tested is how the message looks and reads, not what its links do.

Sending for real (an SMTP backend) needs ``--yes``, so a typo in ``--to`` cannot
send 37 emails by accident; the console backend needs nothing.
"""

import time
from dataclasses import dataclass
from datetime import date, timedelta
from datetime import time as dtime
from typing import Callable

from django.conf import settings
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings

from core.models import BookingPeriod, Collection, NetworkPoint, Thing, User
from core.services import email_service as es

LANGS = ("es", "ca", "en")

# Backends that put nothing on the wire: no confirmation needed for these.
HARMLESS_BACKENDS = ("console", "locmem", "filebased", "dummy")


class TestSendBackend(BaseEmailBackend):
    """Wraps the real backend and rewrites every message on the way out: one
    recipient, no Cc/Bcc, a tagged subject. The real backend's dotted path, the
    address and the current label are class attributes because Django builds a
    fresh backend instance per connection."""

    __test__ = False  # pytest: not a test class, despite the name

    real_backend = None
    target = None
    label = ""

    def send_messages(self, email_messages):
        for message in email_messages:
            message.subject = f"[TEST {self.label}] {message.subject}"
            message.to = [self.target]
            message.cc = []
            message.bcc = []
        real = mail.get_connection(self.real_backend, fail_silently=self.fail_silently)
        return real.send_messages(email_messages) or 0


@dataclass(frozen=True)
class Sample:
    """One email to send: its name, the ``email_service`` function it exercises
    (so a test can prove none is missing) and how to call it."""

    name: str
    covers: str
    send: Callable


SAMPLES = []


def sample(name, covers):
    def register(fn):
        SAMPLES.append(Sample(name, covers, fn))
        return fn

    return register


class World:
    """The sample data every builder draws on, created once per language."""

    def __init__(self, to, lang):
        self.to = to
        self.lang = lang
        today = date.today()
        self.start = today + timedelta(days=7)
        self.end = today + timedelta(days=10)

        # The recipient. An existing account is used as it is (and put back by the
        # rollback); a new address gets a throwaway one. Either way the language
        # and the notification switches are forced, so what arrives is what a
        # fresh recipient would get and not whatever this account happened to set.
        self.me, _ = User.objects.get_or_create(email=to, defaults={"name": "Tú"})
        self.me.language = lang
        self.me.notify_activity = True
        self.me.notify_news = True
        self.me.save()

        # Lala and Lele, at addresses `seed_demo` never makes (it makes lala@ and lele@
        # at SEED_EMAIL_DOMAIN, and an address is unique). Created, never looked up: a
        # real demo account would lend the samples its language and switches.
        self.owner = User.objects.create(email="lala.sample@your-domain.test", name="Lala")
        self.member = User.objects.create(email="lele.sample@your-domain.test", name="Lele")

        pickup_note = (
            "**Cómo recoger:** pásate el domingo entre las 11 y las 13 h. "
            "Pregunta por Lala en el patio."
        )
        # A stall and a library, one kind each: a collection holds one kind of thing,
        # and the links of the emails carry its address, /{kind}/{code}.
        self.collection = Collection.objects.create(
            owner=self.owner,
            kind=Collection.Kind.STALL,
            headline="Chalmercadillo",
            description="El mercadillo de los domingos en el patio.",
            language=lang,
            allowed_thing_types=[Thing.Type.GIFT_THING, Thing.Type.SELL_THING],
            email_note=pickup_note,
        )
        self.collection.invites.add(self.me, self.member)
        self.library = Collection.objects.create(
            owner=self.owner,
            kind=Collection.Kind.LIBRARY,
            headline="Biblioteca de herramientas",
            language=lang,
            allowed_thing_types=[Thing.Type.LEND_THING, Thing.Type.RENT_THING],
            email_note=pickup_note,
        )
        self.library.invites.add(self.me, self.member)
        # A network: Lele answers for an entity with a pickup point of its own, and
        # Lala, the founder, may decline a request on his things as the network.
        self.network = Collection.objects.create(
            owner=self.owner,
            kind=Collection.Kind.LIBRARY,
            mode=Collection.Mode.NETWORK,
            headline="Red de bibliotecas del barrio",
            language=lang,
            allowed_thing_types=[Thing.Type.LEND_THING, Thing.Type.RENT_THING],
            email_note="**Trae el carné** de la red cuando vengas a recoger.",
        )
        self.network.invites.add(self.me, self.member)
        self.network.co_owners.add(self.member)
        NetworkPoint.objects.create(
            collection=self.network,
            user=self.member,
            entity_name="Cooperativa La Fusteria",
            address="Carrer Major 4",
            hours_note="martes y jueves de 18 a 20",
            contact="93 000 00 00",
        )

        self.gift = self._thing(Thing.Type.GIFT_THING, "Silla de madera")
        self.lend = self._thing(
            Thing.Type.LEND_THING, "Escalera de mano", location="Planta baja", home=self.library
        )

        self.net_lend = Thing.objects.create(
            type=Thing.Type.LEND_THING, owner=self.member, headline="Taladro"
        )
        self.network.things.add(self.net_lend)

        self.rooms = Collection.objects.create(
            owner=self.owner,
            kind=Collection.Kind.SHED,
            headline="Sala polivalente",
            language=lang,
            allowed_thing_types=[Thing.Type.RESERVE_THING],
            # So the reservation-confirmation samples show what the owner's
            # own note (request_info.EmailNote) actually looks like inline,
            # not just the collection with none set.
            email_note=(
                "**Antes de venir:** la llave está en portería, pide la de "
                "la sala polivalente. Deja la sala como la encontraste."
            ),
        )
        self.reserve = Thing.objects.create(
            type=Thing.Type.RESERVE_THING,
            owner=self.owner,
            headline="Sala polivalente",
            location="Planta 1, sala 2",
            fee="5.00",
        )
        self.rooms.things.add(self.reserve)

    def _thing(self, kind, headline, home=None, **extra):
        thing = Thing.objects.create(type=kind, owner=self.owner, headline=headline, **extra)
        (home or self.collection).things.add(thing)
        return thing

    def link(self, path):
        """A link on the deployment's own address with a sample token: it looks
        right and does nothing."""
        return f"{es._frontend_base_url()}/{path}/SAMPLE"

    def booking(self, thing, requester, *, dated=True, times=False, accepted=False, owner=None):
        kwargs = {}
        if dated:
            kwargs.update(start_date=self.start, end_date=self.end)
        if times:
            kwargs.update(
                start_date=self.start,
                end_date=self.start + timedelta(days=1),
                start_time=dtime(11, 0),
                end_time=dtime(13, 0),
            )
        return BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner or self.owner,
            status=BookingPeriod.Status.ACCEPTED if accepted else BookingPeriod.Status.PENDING,
            **kwargs,
        )


# --- Category 1: mandatory ---------------------------------------------------------


@sample("magic_link", "send_magic_link_email")
def _(w):
    es.send_magic_link_email(w.to, w.link("verify"), lang=w.lang)


@sample("magic_link_joining_a_group", "send_magic_link_email")
def _(w):
    es.send_magic_link_email(
        w.to, w.link("verify"), collection_headline="Chalmercadillo", lang=w.lang
    )


@sample("collection_invite", "send_collection_invite_email")
def _(w):
    es.send_collection_invite_email(
        "Lala", "Chalmercadillo", w.to, w.link("rsvp"), w.link("rsvp"), collection=w.collection
    )


@sample("collection_invite_recommended", "send_collection_invite_email")
def _(w):
    es.send_collection_invite_email(
        "Lala",
        "Chalmercadillo",
        w.to,
        w.link("rsvp"),
        w.link("rsvp"),
        collection=w.collection,
        proposer_name="Lele",
    )


@sample("collection_welcome_doc", "send_collection_welcome_doc_email")
def _(w):
    es.send_collection_welcome_doc_email(
        "Chalmercadillo", f"{es._frontend_base_url()}/normas.pdf", w.to, collection=w.collection
    )


@sample("collection_revoke", "send_collection_revoke_email")
def _(w):
    es.send_collection_revoke_email("Lala", "Chalmercadillo", w.to, collection=w.collection)


@sample("collection_revoke_with_things", "send_collection_revoke_email")
def _(w):
    es.send_collection_revoke_email(
        "Lala",
        "Chalmercadillo",
        w.to,
        collection=w.collection,
        things=["Taladro", "Escalera de mano"],
    )


@sample("thing_withdrawn_asked", "send_thing_withdrawn_email")
def _(w):
    es.send_thing_withdrawn_email("Escalera de mano", "Chalmercadillo", w.to, holding=False)


@sample("thing_withdrawn_holding_in_a_network", "send_thing_withdrawn_email")
def _(w):
    es.send_thing_withdrawn_email(
        "Taladro",
        "Red de bibliotecas del barrio",
        w.to,
        holding=True,
        collection=w.network,
        point=w.network.point_for(w.member.code),
    )


@sample("thing_left_asked", "send_thing_left_with_owner_email")
def _(w):
    es.send_thing_left_with_owner_email(
        "Taladro", "Chalmercadillo", w.to, holding=False, collection=w.collection
    )


@sample("thing_left_holding", "send_thing_left_with_owner_email")
def _(w):
    es.send_thing_left_with_owner_email(
        "Taladro", "Chalmercadillo", w.to, holding=True, collection=w.collection
    )


@sample("account_delete", "send_account_delete_email")
def _(w):
    es.send_account_delete_email(w.me, w.link("verify"))


@sample("inactivity_will_delete", "send_inactivity_warning_email")
def _(w):
    es.send_inactivity_warning_email(w.me, months=24, days=30, will_delete=True)


@sample("inactivity_account_kept", "send_inactivity_warning_email")
def _(w):
    es.send_inactivity_warning_email(w.me, months=24, days=30, will_delete=False)


# --- Category 2: activity ----------------------------------------------------------


@sample("invitation_proposal", "send_invitation_proposal_email")
def _(w):
    es.send_invitation_proposal_email(
        w.to,
        "Lele",
        "Chalmercadillo",
        "lili@your-domain.test",
        "Vive en mi escalera y le encantaría participar.",
        w.link("rsvp"),
        w.link("rsvp"),
        collection=w.collection,
    )


@sample("proposal_declined", "send_proposal_declined_email")
def _(w):
    es.send_proposal_declined_email(
        w.to, "Lala", "Chalmercadillo", "lili@your-domain.test", collection=w.collection
    )


@sample("invite_rejected", "send_invite_rejected_email")
def _(w):
    es.send_invite_rejected_email("Lele", "Chalmercadillo", w.to, collection=w.collection)


@sample("booking_request", "send_booking_request_email")
def _(w):
    es.send_booking_request_email(
        w.member, w.lend, w.booking(w.lend, w.member), w.to, w.link("rsvp"), w.link("rsvp")
    )


@sample("booking_request_gift", "send_booking_request_email")
def _(w):
    es.send_booking_request_email(
        w.member,
        w.gift,
        w.booking(w.gift, w.member, dated=False),
        w.to,
        w.link("rsvp"),
        w.link("rsvp"),
    )


@sample("booking_confirmed", "send_booking_decision_email")
def _(w):
    es.send_booking_decision_email(
        w.booking(w.lend, w.me, accepted=True), w.lend, accepted=True, collection=w.library
    )


@sample("booking_declined", "send_booking_decision_email")
def _(w):
    es.send_booking_decision_email(
        w.booking(w.lend, w.me), w.lend, accepted=False, collection=w.library
    )


@sample("network_booking_confirmed", "send_booking_decision_email")
def _(w):
    es.send_booking_decision_email(
        w.booking(w.net_lend, w.me, accepted=True, owner=w.member),
        w.net_lend,
        accepted=True,
        collection=w.network,
        decided_by=w.member,
    )


@sample("network_booking_declined_by_the_network", "send_booking_decision_email")
def _(w):
    es.send_booking_decision_email(
        w.booking(w.net_lend, w.me, owner=w.member),
        w.net_lend,
        accepted=False,
        collection=w.network,
        decided_by=w.owner,
    )


@sample("booking_confirmation", "send_booking_confirmation_email")
def _(w):
    es.send_booking_confirmation_email(
        w.me, w.lend, w.booking(w.lend, w.me, accepted=True), collection=w.library
    )


@sample("faq_question", "send_faq_question_email")
def _(w):
    es.send_faq_question_email("Lele", w.gift, "¿Sigue disponible?", w.to)


@sample("faq_answer", "send_faq_answer_email")
def _(w):
    es.send_faq_answer_email("Lala", w.gift, "¿Sigue disponible?", "Sí, ven a por ella.", w.to)


@sample("faq_answered_to_team", "send_faq_answered_to_team_email")
def _(w):
    es.send_faq_answered_to_team_email(
        "Lala", w.gift, "¿Sigue disponible?", "Sí, ven a por ella.", w.to
    )


@sample("faq_hide", "send_faq_hide_email")
def _(w):
    es.send_faq_hide_email("Lala", w.gift, "¿Sigue disponible?", w.to)


@sample("faq_hidden_to_team", "send_faq_hidden_to_team_email")
def _(w):
    es.send_faq_hidden_to_team_email("Lala", w.gift, "¿Sigue disponible?", w.to)


@sample("thing_reported", "send_thing_reported_email")
def _(w):
    es.send_thing_reported_email(w.gift, w.to)


@sample("thing_hidden_by_founder", "send_thing_hidden_by_founder_email")
def _(w):
    es.send_thing_hidden_by_founder_email(w.gift, w.owner, w.collection.headline, w.to)


@sample("return_reminder_to_owner", "send_return_reminder_email")
def _(w):
    es.send_return_reminder_email("Lele", w.lend, w.end, w.to)


@sample("return_due_to_borrower", "send_return_due_email")
def _(w):
    es.send_return_due_email("Lala", w.lend, w.end, w.to)


@sample("network_return_due_to_borrower", "send_return_due_email")
def _(w):
    es.send_return_due_email("Lele", w.net_lend, w.end, w.to)


@sample("network_pickup_due_to_borrower", "send_pickup_due_email")
def _(w):
    es.send_pickup_due_email("Lele", w.net_lend, w.start, w.to)


@sample("pickup_due_to_borrower", "send_pickup_due_email")
def _(w):
    es.send_pickup_due_email("Lala", w.lend, w.start, w.to)


@sample("pickup_reminder_to_owner", "send_pickup_reminder_email")
def _(w):
    es.send_pickup_reminder_email("Lele", w.lend, w.start, w.to)


@sample("return_overdue_to_borrower", "send_return_overdue_email")
def _(w):
    es.send_return_overdue_email(w.me, w.lend, w.end, w.to)


@sample("reservation_confirmed", "send_reservation_confirmed_email")
def _(w):
    es.send_reservation_confirmed_email(
        w.me, w.reserve, w.booking(w.reserve, w.me, accepted=True), collection=w.rooms
    )


@sample("reservation_confirmed_hourly", "send_reservation_confirmed_email")
def _(w):
    es.send_reservation_confirmed_email(
        w.me,
        w.reserve,
        w.booking(w.reserve, w.me, dated=False, times=True, accepted=True),
        collection=w.rooms,
    )


@sample("reservation_notice_to_owner", "send_reservation_notice_email")
def _(w):
    booking = w.booking(w.reserve, w.member, accepted=True)
    # The sample shows the line that says a number was left, never the number.
    booking.contact_phone = "600 000 000"
    es.send_reservation_notice_email(w.to, w.member, w.reserve, booking, collection=w.rooms)


@sample("reservation_cancelled_by_owner", "send_reservation_cancelled_email")
def _(w):
    es.send_reservation_cancelled_email(
        w.to, "Lala", w.reserve, w.booking(w.reserve, w.me), cancelled_by_owner=True
    )


@sample("reservation_cancelled_by_guest", "send_reservation_cancelled_email")
def _(w):
    es.send_reservation_cancelled_email(
        w.to, "Lele", w.reserve, w.booking(w.reserve, w.member), cancelled_by_owner=False
    )


@sample("reservation_cancel_confirmation_self", "send_reservation_cancel_confirmation_email")
def _(w):
    es.send_reservation_cancel_confirmation_email(
        w.to, w.reserve, w.booking(w.reserve, w.me, accepted=True), is_own_reservation=True
    )


@sample("reservation_cancel_confirmation_other", "send_reservation_cancel_confirmation_email")
def _(w):
    es.send_reservation_cancel_confirmation_email(
        w.owner.email,
        w.reserve,
        w.booking(w.reserve, w.member, accepted=True),
        is_own_reservation=False,
        member_name=w.member.name,
    )


@sample("reservation_reminder", "send_reservation_reminder_email")
def _(w):
    es.send_reservation_reminder_email(w.to, w.reserve, w.booking(w.reserve, w.me, accepted=True))


@sample("email_note_test", "send_email_note_test_email")
def _(w):
    es.send_email_note_test_email(w.me, w.collection, w.collection.email_note)


@sample("broadcast", "send_broadcast_email")
def _(w):
    es.send_broadcast_email(
        "Lala",
        w.owner.email,
        "Chalmercadillo",
        w.collection.code,
        "Este domingo hay mercadillo doble: traed lo que os sobre.",
        [w.to],
        collection=w.collection,
    )


@sample("join-summary", "send_join_summary_email")
def _(w):
    es.send_join_summary_email(w.collection, w.me, ["Lala", "lele@your-domain.test", "Lolo"])


@sample("join-summary-many", "send_join_summary_email")
def _(w):
    # Twelve people, some without a name: the list closes with "and 2 more" and the
    # nameless ones are listed by their address.
    names = [
        "Lala",
        "lele@your-domain.test",
        "Lele",
        "Lili",
        "lili@your-domain.test",
        "Lolo",
        "Lulu",
        "Lola",
        "lola@your-domain.test",
        "Lalo",
        "Lila",
        "Lilo",
    ]
    es.send_join_summary_email(w.collection, w.me, names)


# --- Category 3: news --------------------------------------------------------------


@sample("digest", "send_digest_email")
def _(w):
    es.send_digest_email(
        "Chalmercadillo",
        w.collection.code,
        ["Silla de madera", "Escalera de mano"],
        [w.to],
        collection=w.collection,
        new_members=3,
    )


# --- Operator mail -----------------------------------------------------------------


@sample("contact_form", "send_contact_email")
def _(w):
    es.send_contact_email("Lele", "lele@your-domain.test", "No consigo entrar en mi cuenta.")


@sample("collaboration_form", "send_contact_email")
def _(w):
    es.send_contact_email(
        "Lele", "lele@your-domain.test", "Me gustaría colaborar con el diseño.", kind="collab"
    )


@sample("capacity_alarm", "send_collection_capacity_alarm")
def _(w):
    es.send_collection_capacity_alarm(w.collection, "things", 5000, 4000)


class Command(BaseCommand):
    help = "Send one sample of every email to an address you choose (see the module docstring)."

    def add_arguments(self, parser):
        parser.add_argument("--to", help="The one address every sample is sent to. Required.")
        parser.add_argument(
            "--lang",
            default="es",
            choices=LANGS + ("all",),
            help="Language of the samples; 'all' sends every email in es, ca and en (default es).",
        )
        parser.add_argument(
            "--only",
            help="Only the samples whose name contains this text (e.g. 'booking', 'invite').",
        )
        parser.add_argument("--list", action="store_true", help="List the samples and stop.")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm a real send (an SMTP backend). Not needed for the console.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Seconds between sends on a real backend, so the provider is not hammered.",
        )

    def handle(self, *args, **opts):
        chosen = [s for s in SAMPLES if not opts["only"] or opts["only"] in s.name]
        if opts["list"]:
            for i, s in enumerate(chosen, 1):
                self.stdout.write(f"{i:>2}  {s.name:<34} {s.covers}")
            self.stdout.write(f"\n{len(chosen)} samples")
            return

        to = (opts["to"] or "").strip()
        if not to or "@" not in to:
            raise CommandError("--to is required: the one address every sample is sent to.")
        if not chosen:
            raise CommandError(f"No sample matches --only {opts['only']!r}. Try --list.")

        langs = LANGS if opts["lang"] == "all" else (opts["lang"],)
        total = len(chosen) * len(langs)
        real_backend = settings.EMAIL_BACKEND
        harmless = any(kind in real_backend for kind in HARMLESS_BACKENDS)
        if not harmless and not opts["yes"]:
            raise CommandError(
                f"This would really send {total} emails to {to} through {real_backend}.\n"
                "Run it again with --yes to confirm."
            )

        self.stdout.write(
            f"Sending {total} sample emails to {to} "
            f"({', '.join(langs)}) through {real_backend.rsplit('.', 2)[-2]}.\n"
        )

        TestSendBackend.real_backend = real_backend
        TestSendBackend.target = to
        sent = 0
        with override_settings(EMAIL_BACKEND=f"{__name__}.TestSendBackend", EMAIL_SEND_ASYNC=False):
            for lang in langs:
                # One rolled-back transaction per language: the data is built for
                # that language and nothing survives it.
                with override_settings(EMAIL_LANGUAGE=lang):
                    sent += self._send_language(chosen, to, lang, total, sent, opts, harmless)
        self.stdout.write(self.style.SUCCESS(f"\nDone: {sent} of {total} emails sent to {to}."))

    def _send_language(self, chosen, to, lang, total, done, opts, harmless):
        sent = 0
        try:
            with transaction.atomic():
                world = World(to, lang)
                for sample_ in chosen:
                    number = done + sent + 1
                    TestSendBackend.label = f"{number:02d}/{total} {lang} {sample_.name}"
                    try:
                        sample_.send(world)
                        sent += 1
                        self.stdout.write(f"  {TestSendBackend.label}")
                    except Exception as exc:  # noqa: BLE001 — report and carry on
                        self.stderr.write(
                            self.style.ERROR(f"  {TestSendBackend.label}  FAILED: {exc!r}")
                        )
                    if not harmless and opts["delay"]:
                        time.sleep(opts["delay"])
                # Nothing of the sample world is kept, the recipient's account
                # (if it has one) included.
                transaction.set_rollback(True)
        finally:
            TestSendBackend.label = ""
        return sent
