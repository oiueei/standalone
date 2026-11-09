"""The emails a member gets about a loan in a network carry the pickup point.

Acceptance and the pickup and return reminders name the entity that lends ("Cooperativa
La Fusteria has accepted your loan") and say where and when: name, address, hours and
contact, escaped. When the founder declines a request on another entity's thing (the
rescue) it is the network that declines, not the entity, who did not decide.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, NetworkPoint, User
from core.tests.factories import BookingPeriodFactory, CollectionFactory, ThingFactory

LEND, RENT = "LEND_THING", "RENT_THING"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


def html_of(message):
    return message.alternatives[0][0]


@pytest.fixture
def net(db):
    founder, lele, lolo = _user("FOUN01", "Lala"), _user("ENTA01", "Lele"), _user("ASKR01", "Lolo")
    group = CollectionFactory(
        owner=founder,
        mode=Collection.Mode.NETWORK,
        headline="Red del barrio",
        allowed_thing_types=[LEND, RENT],
        email_note="the network's note",
    )
    group.invites.add(lele, lolo)
    group.co_owners.add(lele)
    thing = ThingFactory(owner=lele, type=LEND, headline="Cordless drill")
    group.things.add(thing)
    return {"group": group, "thing": thing, "founder": founder, "lele": lele, "lolo": lolo}


def a_point(net, **extra):
    values = {
        "entity_name": "Cooperativa La Fusteria",
        "address": "Carrer Major 4",
        "hours_note": "martes y jueves de 18 a 20",
        "contact": "93 000 00 00",
        **extra,
    }
    return NetworkPoint.objects.create(collection=net["group"], user=net["lele"], **values)


def pending(net, **extra):
    today = timezone.localdate()
    return BookingPeriodFactory(
        thing_code=net["thing"],
        requester_code=net["lolo"],
        owner_code=net["lele"],
        thing_type=LEND,
        start_date=today + timedelta(days=3),
        end_date=today + timedelta(days=6),
        **extra,
    )


def decide(net, who, verb, booking):
    mail.outbox.clear()
    return client_for(net[who]).post(f"/api/v1/bookings/{booking.code}/{verb}/")


def to_requester():
    [message] = [m for m in mail.outbox if m.to == ["lolo@your-domain.test"]]
    return message


class TestAcceptance:
    def test_the_entity_accepts_and_says_where_and_when(self, net):
        a_point(net)

        decide(net, "lele", "accept", pending(net))

        message = to_requester()
        for text in (message.body, html_of(message)):
            assert "Cooperativa La Fusteria has accepted your loan request" in text
            assert "Carrer Major 4" in text
            assert "martes y jueves de 18 a 20" in text
            assert "93 000 00 00" in text

    def test_the_contact_is_escaped_and_never_a_link(self, net):
        a_point(net, contact="<script>x</script> www.example.org")

        decide(net, "lele", "accept", pending(net))

        html = html_of(to_requester())
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;x&lt;/script&gt; www.example.org" in html
        assert 'href="http://www.example.org' not in html
        assert 'href="www.example.org' not in html

    def test_a_dinamizador_with_no_point_is_named_by_their_own_name(self, net):
        decide(net, "lele", "accept", pending(net))

        message = to_requester()
        assert "Lele has accepted your loan request" in message.body
        assert "Pickup point" not in message.body

    def test_the_entitys_email_note_wins_and_the_networks_is_the_fallback(self, net):
        a_point(net, email_note="the entity's note")
        decide(net, "lele", "accept", pending(net))
        assert "the entity's note" in to_requester().body
        assert "the network's note" not in to_requester().body

        NetworkPoint.objects.update(email_note="")
        decide(net, "lele", "accept", pending(net))
        assert "the network's note" in to_requester().body

    def test_a_refusal_by_the_entity_names_it_and_carries_no_pickup_details(self, net):
        a_point(net)

        decide(net, "lele", "reject", pending(net))

        message = to_requester()
        assert "Cooperativa La Fusteria has declined your loan request" in message.body
        assert "Carrer Major 4" not in message.body


class TestTheRescue:
    def test_the_network_declines_when_the_founder_declines_an_entitys_request(self, net):
        a_point(net)

        res = decide(net, "founder", "reject", pending(net))

        assert res.status_code == 200
        message = to_requester()
        assert "Red del barrio has declined your loan request" in message.body
        assert "Cooperativa La Fusteria" not in message.body
        assert "Cooperativa La Fusteria" not in html_of(message)

    def test_the_founders_own_things_are_declined_in_the_name_of_their_own_point(self, net):
        point = NetworkPoint.objects.create(
            collection=net["group"], user=net["founder"], entity_name="Federación"
        )
        thing = ThingFactory(owner=net["founder"], type=LEND, headline="Saw")
        net["group"].things.add(thing)
        today = timezone.localdate()
        booking = BookingPeriodFactory(
            thing_code=thing,
            requester_code=net["lolo"],
            owner_code=net["founder"],
            thing_type=LEND,
            start_date=today + timedelta(days=3),
            end_date=today + timedelta(days=6),
        )

        decide(net, "founder", "reject", booking)

        assert f"{point.entity_name} has declined your loan request" in to_requester().body


class TestReminders:
    def accepted(self, net, *, start, end):
        return BookingPeriodFactory(
            thing_code=net["thing"],
            requester_code=net["lolo"],
            owner_code=net["lele"],
            thing_type=LEND,
            status="ACCEPTED",
            start_date=start,
            end_date=end,
        )

    def test_the_pickup_reminder_to_the_borrower_names_the_entity_and_the_point(self, net):
        a_point(net)
        today = timezone.localdate()
        self.accepted(net, start=today + timedelta(days=1), end=today + timedelta(days=8))
        mail.outbox.clear()

        call_command("send_reminders")

        [message] = [m for m in mail.outbox if m.to == ["lolo@your-domain.test"]]
        assert "Cooperativa La Fusteria" in message.body
        assert "Carrer Major 4" in message.body
        assert "martes y jueves de 18 a 20" in html_of(message)
        assert "93 000 00 00" in html_of(message)

    def test_the_return_reminder_to_the_borrower_names_the_entity_and_the_point(self, net):
        a_point(net)
        today = timezone.localdate()
        self.accepted(net, start=today - timedelta(days=6), end=today + timedelta(days=1))
        mail.outbox.clear()

        call_command("send_reminders")

        [message] = [m for m in mail.outbox if m.to == ["lolo@your-domain.test"]]
        assert "Cooperativa La Fusteria" in message.body
        assert "Carrer Major 4" in message.body

    def test_without_a_point_the_reminder_names_the_dinamizador_and_adds_nothing(self, net):
        today = timezone.localdate()
        self.accepted(net, start=today + timedelta(days=1), end=today + timedelta(days=8))
        mail.outbox.clear()

        call_command("send_reminders")

        [message] = [m for m in mail.outbox if m.to == ["lolo@your-domain.test"]]
        assert "Lele" in message.body
        assert "Pickup point" not in message.body

    def test_outside_a_network_the_reminder_is_what_it_was(self, db):
        founder, lolo = _user("FOUN01", "Lala"), _user("ASKR01", "Lolo")
        group = CollectionFactory(
            owner=founder, mode=Collection.Mode.PROPRIETARY, allowed_thing_types=[LEND, RENT]
        )
        group.invites.add(lolo)
        thing = ThingFactory(owner=founder, type=LEND)
        group.things.add(thing)
        NetworkPoint.objects.create(collection=group, user=founder, entity_name="Ghost entity")
        today = timezone.localdate()
        BookingPeriodFactory(
            thing_code=thing,
            requester_code=lolo,
            owner_code=founder,
            thing_type=LEND,
            status="ACCEPTED",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=8),
        )
        mail.outbox.clear()

        call_command("send_reminders")

        [message] = [m for m in mail.outbox if m.to == ["lolo@your-domain.test"]]
        assert "Ghost entity" not in message.body
        assert "Lala" in message.body


class TestReminderQueryBudget:
    def _loans_due_tomorrow(self, net, n):
        today = timezone.localdate()
        for _ in range(n):
            thing = ThingFactory(owner=net["lele"], type=LEND)
            net["group"].things.add(thing)
            BookingPeriodFactory(
                thing_code=thing,
                requester_code=net["lolo"],
                owner_code=net["lele"],
                thing_type=LEND,
                status="ACCEPTED",
                start_date=today - timedelta(days=6),
                end_date=today + timedelta(days=1),
            )

    def _point_queries(self):
        mail.outbox.clear()
        with CaptureQueriesContext(connection) as queries:
            call_command("send_reminders")
        return [q["sql"] for q in queries if "network_points" in q["sql"]]

    def test_the_pickup_points_are_read_once_however_many_loans_are_due(self, net):
        a_point(net)
        self._loans_due_tomorrow(net, 2)
        few = self._point_queries()
        self._loans_due_tomorrow(net, 3)
        many = self._point_queries()

        assert len(mail.outbox) >= 5
        assert len(many) == len(few), f"{len(few)} point reads for 2 loans, {len(many)} for 5"


class TestTheRequestReceived:
    def test_the_confirmation_to_the_requester_carries_the_entitys_note(self, net):
        a_point(net, email_note="the entity's note")
        today = timezone.localdate()
        mail.outbox.clear()

        client_for(net["lolo"]).post(
            f"/api/v1/things/{net['thing'].code}/request/",
            {
                "start_date": str(today + timedelta(days=3)),
                "end_date": str(today + timedelta(days=6)),
                "collection_code": net["group"].code,
            },
            format="json",
        )

        message = to_requester()
        assert "the entity's note" in message.body
        assert "the network's note" not in message.body
