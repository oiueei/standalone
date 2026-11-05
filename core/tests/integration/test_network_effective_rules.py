"""The rules that govern a thing of a network are its pickup point's over the collection's.

Days: the point's when it set any, else the collection's. Closures: the union. Lengths
(and everything else) the collection's. Conditions (deposit policy, request note, email
note): the point's own, each falling back to the collection's when empty. The server's
refusal, the live availability and the rules the thing's payload carries to the request
page all read the one answer (``Collection.rental_rules_for``).
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, NetworkPoint, User
from core.services.booking_service import resolve_rental_collection
from core.tests.factories import CollectionFactory, ThingFactory

LEND, RENT = "LEND_THING", "RENT_THING"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


def next_weekday(weekday, after=14):
    day = timezone.localdate() + timedelta(days=after)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


@pytest.fixture
def world(db):
    founder, lele, lili, lolo = (
        _user("FOUN01", "Lala"),
        _user("ENTA01", "Lele"),
        _user("ENTB01", "Lili"),
        _user("MEMB01", "Lolo"),
    )
    network = CollectionFactory(
        owner=founder,
        mode=Collection.Mode.NETWORK,
        visibility=Collection.Visibility.PRIVATE,
        allowed_thing_types=[LEND, RENT],
        rental_weekdays=[0, 1, 2, 3, 4],
        rental_durations=[7],
        deposit_policy="network deposit",
        request_info="network request note",
        email_note="network email note",
    )
    network.invites.add(lele, lili, lolo)
    network.co_owners.add(lele, lili)
    leles = ThingFactory(owner=lele, type=LEND)
    lilis = ThingFactory(owner=lili, type=LEND)
    network.things.add(leles, lilis)
    return {
        "network": network,
        "founder": founder,
        "lele": lele,
        "lili": lili,
        "lolo": lolo,
        "leles": leles,
        "lilis": lilis,
    }


def fresh(world):
    return Collection.objects.get(code=world["network"].code)


class TestTheRulesOfAThing:
    def test_without_a_point_a_thing_follows_the_collection_exactly(self, world):
        rules = fresh(world).rental_rules_for("ENTA01")

        assert rules.weekdays == [0, 1, 2, 3, 4]
        assert rules.closed == set()
        assert rules.durations == [7]

    def test_a_point_replaces_the_days_and_adds_its_closures(self, world):
        network = world["network"]
        network.closed_dates = ["2030-12-25"]
        network.save()
        NetworkPoint.objects.create(
            collection=network, user=world["lele"], weekdays=[2], closed_dates=["2030-08-15"]
        )

        mine = fresh(world).rental_rules_for("ENTA01")
        theirs = fresh(world).rental_rules_for("ENTB01")

        assert mine.weekdays == [2]
        assert mine.closed == {date(2030, 12, 25), date(2030, 8, 15)}
        assert mine.durations == [7]
        assert theirs.weekdays == [0, 1, 2, 3, 4]
        assert theirs.closed == {date(2030, 12, 25)}

    def test_a_point_with_no_days_leaves_the_collections_days(self, world):
        NetworkPoint.objects.create(
            collection=world["network"], user=world["lele"], closed_dates=["2030-08-15"]
        )

        assert fresh(world).rental_rules_for("ENTA01").weekdays == [0, 1, 2, 3, 4]

    @pytest.mark.parametrize("field", ["deposit_policy", "request_info", "email_note"])
    def test_a_point_condition_wins_when_written_and_the_collections_otherwise(self, world, field):
        NetworkPoint.objects.create(
            collection=world["network"], user=world["lele"], **{field: "the entity's own"}
        )
        network = fresh(world)

        assert network.effective_text(field, "ENTA01") == "the entity's own"
        assert network.effective_text(field, "ENTB01") == getattr(network, field)

    def test_each_condition_falls_back_on_its_own(self, world):
        NetworkPoint.objects.create(
            collection=world["network"], user=world["lele"], deposit_policy="entity deposit"
        )
        network = fresh(world)

        assert network.effective_text("deposit_policy", "ENTA01") == "entity deposit"
        assert network.effective_text("request_info", "ENTA01") == "network request note"
        assert network.effective_text("email_note", "ENTA01") == "network email note"

    def test_outside_a_network_nothing_changes(self, db):
        founder = _user("FOUN01", "Lala")
        group = CollectionFactory(
            owner=founder,
            mode=Collection.Mode.PROPRIETARY,
            rental_weekdays=[1],
            closed_dates=["2030-01-01"],
            request_info="the note",
        )
        NetworkPoint.objects.create(collection=group, user=founder, weekdays=[5], request_info="x")

        rules = Collection.objects.get(code=group.code).rental_rules_for("FOUN01")

        assert rules.weekdays == [1]
        assert rules.closed == {date(2030, 1, 1)}
        assert Collection.objects.get(code=group.code).effective_text("request_info", "FOUN01") == (
            "the note"
        )

    def test_a_network_without_rules_of_its_own_still_resolves_for_the_points(self, world):
        network = world["network"]
        network.rental_weekdays = []
        network.rental_durations = []
        network.save()
        thing = world["leles"]
        thing = type(thing).objects.get(code=thing.code)

        assert resolve_rental_collection(thing).code == network.code


class TestWhatTheServerRefuses:
    def ask(self, world, thing, start, end):
        return client_for(world["lolo"]).post(
            f"/api/v1/things/{thing.code}/request/",
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "collection_code": world["network"].code,
            },
            format="json",
        )

    def test_the_points_days_decide_the_pickup_of_its_dinamizadors_things(self, world):
        NetworkPoint.objects.create(collection=world["network"], user=world["lele"], weekdays=[2])
        wednesday, monday = next_weekday(2), next_weekday(0)

        refused = self.ask(world, world["leles"], monday, monday + timedelta(days=7))
        accepted = self.ask(world, world["leles"], wednesday, wednesday + timedelta(days=7))

        assert refused.status_code == status.HTTP_400_BAD_REQUEST
        assert refused.data["code"] == "rental_pickup_weekday"
        assert accepted.status_code == status.HTTP_201_CREATED

    def test_another_dinamizadors_thing_keeps_the_collections_days(self, world):
        NetworkPoint.objects.create(collection=world["network"], user=world["lele"], weekdays=[2])
        monday = next_weekday(0)

        res = self.ask(world, world["lilis"], monday, monday + timedelta(days=7))

        assert res.status_code == status.HTTP_201_CREATED

    def test_a_closure_of_the_point_and_one_of_the_collection_both_apply(self, world):
        network = world["network"]
        monday = next_weekday(0)
        tuesday = next_weekday(1, after=30)
        network.closed_dates = [monday.isoformat()]
        network.save()
        NetworkPoint.objects.create(
            collection=network, user=world["lele"], closed_dates=[tuesday.isoformat()]
        )

        by_network = self.ask(world, world["leles"], monday, monday + timedelta(days=7))
        by_point = self.ask(world, world["leles"], tuesday, tuesday + timedelta(days=7))

        assert by_network.data["code"] == "rental_pickup_closed"
        assert by_point.data["code"] == "rental_pickup_closed"

    def test_the_lengths_stay_the_collections(self, world):
        NetworkPoint.objects.create(collection=world["network"], user=world["lele"], weekdays=[0])
        monday = next_weekday(0)

        res = self.ask(world, world["leles"], monday, monday + timedelta(days=14))

        assert res.data["code"] == "rental_length_not_allowed"


class TestWhatThePageIsTold:
    def read(self, world, thing, viewer="lolo"):
        res = client_for(world[viewer]).get(
            f"/api/v1/things/{thing.code}/?collection={world['network'].code}"
        )
        assert res.status_code == status.HTTP_200_OK
        return res.data

    def test_the_payload_carries_the_rules_already_resolved(self, world):
        tuesday = next_weekday(1, after=30)
        NetworkPoint.objects.create(
            collection=world["network"],
            user=world["lele"],
            weekdays=[2],
            closed_dates=[tuesday.isoformat()],
        )

        data = self.read(world, world["leles"])

        assert data["rental_weekdays"] == [2]
        assert data["closed_dates"] == [tuesday.isoformat()]
        assert data["rental_durations"] == [7]

    @pytest.mark.parametrize("weekdays", [[2], [], [0, 4]])
    def test_the_payload_and_the_refusal_agree_on_every_day(self, world, weekdays):
        """The request page greys out what the payload says and the server refuses what
        ``rental_violation`` says: over every pickup day they must not disagree."""
        closed = next_weekday(3, after=20)
        NetworkPoint.objects.create(
            collection=world["network"],
            user=world["lele"],
            weekdays=weekdays,
            closed_dates=[closed.isoformat()],
        )
        data = self.read(world, world["leles"])
        network = fresh(world)
        page_weekdays = set(data["rental_weekdays"])
        page_closed = set(data["closed_dates"])
        today = timezone.localdate()

        for offset in range(1, 45):
            start = today + timedelta(days=offset)
            end = start + timedelta(days=7)
            page_allows = (
                (not page_weekdays or start.weekday() in page_weekdays)
                and (not page_weekdays or end.weekday() in page_weekdays)
                and start.isoformat() not in page_closed
                and end.isoformat() not in page_closed
            )
            server_allows = network.rental_violation(start, end, owner_code="ENTA01") is None
            assert page_allows == server_allows, start

    def test_the_request_note_is_the_points_or_the_collections(self, world):
        NetworkPoint.objects.create(
            collection=world["network"], user=world["lele"], request_info="bring the card"
        )

        assert self.read(world, world["leles"])["collection_request_info"] == "bring the card"
        assert self.read(world, world["lilis"])["collection_request_info"] == (
            "network request note"
        )

    def test_the_live_availability_follows_the_points_days(self, world):
        thing = world["leles"]
        NetworkPoint.objects.create(collection=world["network"], user=world["lele"], weekdays=[2])

        data = self.read(world, thing)

        assert data["next_available"].weekday() == 2

    def test_the_thing_says_who_lends_it_and_where(self, world):
        NetworkPoint.objects.create(
            collection=world["network"],
            user=world["lele"],
            entity_name="Cooperativa La Fusteria",
            address="Carrer Major 4",
            hours_note="martes y jueves de 18 a 20",
            contact="93 000 00 00",
        )

        mine = self.read(world, world["leles"])["network_point"]
        theirs = self.read(world, world["lilis"])["network_point"]

        assert mine == {
            "display_name": "Cooperativa La Fusteria",
            "address": "Carrer Major 4",
            "hours_note": "martes y jueves de 18 a 20",
            "contact": "93 000 00 00",
            "logo_url": None,
        }
        assert theirs == {
            "display_name": "Lili",
            "address": "",
            "hours_note": "",
            "contact": "",
            "logo_url": None,
        }

    def test_the_thing_carries_the_logo_of_its_entity(self, world):
        NetworkPoint.objects.create(
            collection=world["network"],
            user=world["lele"],
            entity_name="La Fusteria",
            logo="oiueei/collections/fusteria",
        )

        mine = self.read(world, world["leles"])["network_point"]
        theirs = self.read(world, world["lilis"])["network_point"]
        card = {
            t["code"]: t
            for t in client_for(world["lolo"])
            .get(f"/api/v1/collections/{world['network'].code}/")
            .data["things"]
        }[world["leles"].code]["network_point"]

        assert mine["logo_url"].endswith("oiueei/collections/fusteria")
        assert card["logo_url"] == mine["logo_url"]
        assert theirs["logo_url"] is None

    def test_a_thing_outside_a_network_has_no_point(self, db):
        founder = _user("FOUN01", "Lala")
        group = CollectionFactory(owner=founder, mode=Collection.Mode.PROPRIETARY)
        thing = ThingFactory(owner=founder, type=LEND)
        group.things.add(thing)

        res = client_for(founder).get(f"/api/v1/things/{thing.code}/?collection={group.code}")

        assert res.data["network_point"] is None
        assert res.data["collection_mode"] == "PROPRIETARY"

    def test_the_things_own_location_is_not_shown_in_a_network(self, world):
        thing = world["leles"]
        thing.location = "Mi casa, Carrer Petit 2"
        thing.save()

        data = self.read(world, thing)
        stored = type(thing).objects.get(code=thing.code).location

        assert data["location"] == ""
        assert data["collection_mode"] == "NETWORK"
        assert stored == "Mi casa, Carrer Petit 2"

    def test_the_card_in_the_collection_carries_the_point_too(self, world):
        NetworkPoint.objects.create(
            collection=world["network"], user=world["lele"], entity_name="La Fusteria"
        )

        res = client_for(world["lolo"]).get(f"/api/v1/collections/{world['network'].code}/")

        cards = {t["code"]: t for t in res.data["things"]}
        assert cards[world["leles"].code]["network_point"]["display_name"] == "La Fusteria"
        assert cards[world["lilis"].code]["network_point"]["display_name"] == "Lili"


class TestTheDepositPolicyReachesThePage:
    """``deposit_policy`` is in the thing's payload, effective for its owner, so the page
    can say how the deposit works next to the deposit itself."""

    def read(self, world, thing):
        res = client_for(world["lolo"]).get(
            f"/api/v1/things/{thing.code}/?collection={world['network'].code}"
        )
        assert res.status_code == status.HTTP_200_OK
        return res.data

    def test_a_point_policy_wins_and_the_collections_is_the_fallback(self, world):
        NetworkPoint.objects.create(
            collection=world["network"], user=world["lele"], deposit_policy="entity deposit"
        )

        assert self.read(world, world["leles"])["deposit_policy"] == "entity deposit"
        assert self.read(world, world["lilis"])["deposit_policy"] == "network deposit"

    def test_a_point_with_no_policy_leaves_the_collections(self, world):
        NetworkPoint.objects.create(collection=world["network"], user=world["lele"])

        assert self.read(world, world["leles"])["deposit_policy"] == "network deposit"

    def test_outside_a_network_it_is_the_collections(self, db):
        founder, lolo = _user("FOUN01", "Lala"), _user("MEMB01", "Lolo")
        group = CollectionFactory(
            owner=founder, mode=Collection.Mode.PROPRIETARY, deposit_policy="50 € back"
        )
        group.invites.add(lolo)
        thing = ThingFactory(owner=founder, type=LEND)
        group.things.add(thing)

        res = client_for(lolo).get(f"/api/v1/things/{thing.code}/?collection={group.code}")

        assert res.data["deposit_policy"] == "50 € back"
