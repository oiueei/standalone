"""The page a curator has in a group exists in every collection, not only in a network.

Outside a network it is an identity card: name, logo, about and contact. The pickup point
(place and conditions of the loans) stays a network's, and so do the rules that read it.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, NetworkPoint, User
from core.serializers.network_point import NetworkPointSerializer
from core.services.export_service import build_account_export
from core.tests.factories import CollectionFactory, ThingFactory

NETWORK_FIELDS = {
    "address": "",
    "hours_note": "",
    "weekdays": [],
    "closed_dates": [],
    "deposit_policy": "",
    "request_info": "",
    "email_note": "",
}


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


@pytest.fixture
def group(db):
    founder, curator, member = (
        _user("FOUN01", "Lala"),
        _user("CURA01", "Lele"),
        _user("MEMB01", "Lili"),
    )
    collection = CollectionFactory(
        owner=founder,
        mode=Collection.Mode.PROPRIETARY,
        visibility=Collection.Visibility.PUBLIC,
        allowed_thing_types=["LEND_THING"],
    )
    collection.invites.add(curator, member)
    collection.co_owners.add(curator)
    return {"collection": collection, "founder": founder, "curator": curator, "member": member}


def url(group):
    return f"/api/v1/collections/{group['collection'].code}/point/"


def test_a_co_curator_reads_the_empty_page_outside_a_network(group):
    res = client_for(group["curator"]).get(url(group))

    assert res.status_code == status.HTTP_200_OK
    assert res.data["display_name"] == "Lele"
    assert res.data["about"] == ""
    assert not NetworkPoint.objects.exists()


def test_the_founder_and_a_co_curator_each_set_their_own_page(group):
    client_for(group["founder"]).put(
        url(group), {"entity_name": "Asociación", "about": "Somos **vecinas**"}, format="json"
    )
    res = client_for(group["curator"]).put(
        url(group), {"contact": "93 000 00 00", "about": "Hola"}, format="json"
    )

    assert res.status_code == status.HTTP_200_OK
    cards = {p.user_id: p for p in NetworkPoint.objects.all()}
    assert cards["FOUN01"].entity_name == "Asociación"
    assert cards["CURA01"].about == "Hola"
    assert cards["CURA01"].entity_name == ""


def test_a_put_outside_a_network_keeps_the_identity_and_ignores_the_place(group):
    body = {
        "entity_name": "Taller",
        "about": "Texto",
        "contact": "web",
        "logo": "",
        "address": "Carrer Major 4",
        "hours_note": "lunes",
        "weekdays": [1],
        "closed_dates": "01/01/2027",
        "deposit_policy": "20 €",
        "request_info": "nota",
        "email_note": "correo",
    }

    res = client_for(group["curator"]).put(url(group), body, format="json")

    assert res.status_code == status.HTTP_200_OK
    card = NetworkPoint.objects.get()
    assert (card.entity_name, card.about, card.contact) == ("Taller", "Texto", "web")
    for field, empty in NETWORK_FIELDS.items():
        assert getattr(card, field) == empty, field


def test_a_plain_member_gets_403_outside_a_network(group):
    client = client_for(group["member"])

    assert client.get(url(group)).status_code == status.HTTP_403_FORBIDDEN
    assert client.put(url(group), {"about": "x"}, format="json").status_code == 403
    assert not NetworkPoint.objects.exists()


def test_the_serializer_serves_the_network_fields_empty_whatever_the_columns_hold(group):
    card = NetworkPoint.objects.create(
        collection=group["collection"],
        user=group["curator"],
        about="Hola",
        address="Carrer Major 4",
        hours_note="lunes",
        weekdays=[1],
        closed_dates=["2027-01-01"],
        deposit_policy="20 €",
        request_info="nota",
        email_note="correo",
    )

    data = NetworkPointSerializer(card, context={}).data

    assert data["about"] == "Hola"
    for field, empty in NETWORK_FIELDS.items():
        assert data[field] == empty, field


def test_in_a_network_the_same_columns_are_served(group):
    network = CollectionFactory(
        owner=group["founder"], mode=Collection.Mode.NETWORK, allowed_thing_types=["LEND_THING"]
    )
    card = NetworkPoint.objects.create(collection=network, user=group["founder"], address="Major 4")

    assert NetworkPointSerializer(card, context={}).data["address"] == "Major 4"


def test_the_pages_travel_with_a_proprietary_collection_to_everyone(group):
    NetworkPoint.objects.create(
        collection=group["collection"], user=group["curator"], entity_name="Taller", about="Hola"
    )

    res = client_for().get(f"/api/v1/collections/{group['collection'].code}/")

    [card] = res.data["points"]
    assert (card["user"], card["entity_name"], card["about"]) == ("CURA01", "Taller", "Hola")
    assert card["display_name"] == "Taller"
    assert card["email_note"] == ""


def test_a_card_is_only_a_pickup_point_in_a_network(group):
    collection = group["collection"]
    card = NetworkPoint.objects.create(
        collection=collection,
        user=group["curator"],
        weekdays=[1],
        deposit_policy="20 €",
    )

    assert collection.card_for("CURA01") == card
    assert collection.point_for("CURA01") is None
    # So the loan rules and the conditions stay the collection's own.
    assert collection.rental_rules_for("CURA01") == collection.rental_rules_for()
    assert collection.effective_text("deposit_policy", "CURA01") == collection.deposit_policy
    assert collection.card_for("MEMB01") is None


def test_demoting_a_co_curator_outside_a_network_deletes_their_page_and_not_their_things(group):
    collection = group["collection"]
    thing = ThingFactory(owner=group["curator"], type="LEND_THING")
    collection.things.add(thing)
    mine = NetworkPoint.objects.create(collection=collection, user=group["curator"], about="x")
    founders = NetworkPoint.objects.create(collection=collection, user=group["founder"])

    res = client_for(group["founder"]).delete(
        f"/api/v1/collections/{collection.code}/co-owners/",
        {"user_code": "CURA01"},
        format="json",
    )

    assert res.status_code == status.HTTP_200_OK
    assert not NetworkPoint.objects.filter(code=mine.code).exists()
    assert NetworkPoint.objects.filter(code=founders.code).exists()
    assert collection.things.filter(code=thing.code).exists()


def test_removing_a_co_curator_outside_a_network_deletes_their_page(group):
    collection = group["collection"]
    mine = NetworkPoint.objects.create(collection=collection, user=group["curator"])

    res = client_for(group["founder"]).delete(
        f"/api/v1/collections/{collection.code}/invite/",
        {"user_code": "CURA01"},
        format="json",
    )

    assert res.status_code == status.HTTP_200_OK
    assert not NetworkPoint.objects.filter(code=mine.code).exists()


def test_the_account_copy_carries_their_pages(group):
    network = CollectionFactory(
        owner=group["founder"], mode=Collection.Mode.NETWORK, allowed_thing_types=["LEND_THING"]
    )
    network.invites.add(group["curator"])
    network.co_owners.add(group["curator"])
    NetworkPoint.objects.create(
        collection=group["collection"],
        user=group["curator"],
        entity_name="Taller",
        about="Hola",
        contact="web",
        address="no se copia fuera de red",
    )
    NetworkPoint.objects.create(
        collection=network, user=group["curator"], about="Red", address="Major 4"
    )

    payload = build_account_export(group["curator"])

    rows = {row["collection"]: row for row in payload["organisations"]}
    outside = rows[group["collection"].code]
    assert (outside["entity_name"], outside["about"], outside["contact"]) == (
        "Taller",
        "Hola",
        "web",
    )
    assert "address" not in outside
    assert rows[network.code]["address"] == "Major 4"
    assert payload["_manifest"]["counts"]["organisations"] == 2
    assert "organisations" in payload["_readme"]["about"]


@pytest.mark.parametrize("lang", ["es", "ca", "en"])
def test_the_readme_names_the_pages_in_every_language(lang):
    from core.services.export_service import README_TEXTS

    assert "organisations" in README_TEXTS[lang]["account"]["about"]
