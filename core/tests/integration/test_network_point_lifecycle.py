"""A dinamizador's pickup point exists for as long as they run things in the network.

It is one row per (network, dinamizador), it names the entity they answer for, and it
goes with the role (demoted, removed) or with the account, never before.
"""

import pytest
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, NetworkPoint, User
from core.services.account_service import delete_account
from core.tests.factories import CollectionFactory, ThingFactory

LEND, RENT = "LEND_THING", "RENT_THING"
BASE = "/api/v1/collections/{code}/"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


@pytest.fixture
def network(db):
    founder, lele, lili = _user("FOUN01", "Lala"), _user("ENTA01", "Lele"), _user("ENTB01", "Lili")
    group = CollectionFactory(
        owner=founder, mode=Collection.Mode.NETWORK, allowed_thing_types=[LEND, RENT]
    )
    group.invites.add(lele, lili)
    group.co_owners.add(lele, lili)
    group.things.add(ThingFactory(owner=lele, type=LEND))
    return {
        "group": group,
        "founder": founder,
        "lele": lele,
        "lili": lili,
        "point": NetworkPoint.objects.create(
            collection=group, user=lele, entity_name="Cooperativa La Fusteria"
        ),
        "other": NetworkPoint.objects.create(collection=group, user=lili),
    }


def test_a_dinamizador_has_one_point_per_network(network):
    with pytest.raises(IntegrityError), transaction.atomic():
        NetworkPoint.objects.create(collection=network["group"], user=network["lele"])


def test_a_point_goes_by_its_entity_and_falls_back_to_the_person(network):
    assert network["point"].display_name == "Cooperativa La Fusteria"
    assert network["other"].display_name == "Lili"


def test_point_for_finds_the_point_of_a_dinamizador_only_in_a_network(network):
    group = network["group"]

    assert group.point_for("ENTA01") == network["point"]
    assert group.point_for("FOUN01") is None
    group.mode = Collection.Mode.PROPRIETARY
    assert group.point_for("ENTA01") is None
    # The card is the same row in any mode: it is what point_for narrows to a network.
    assert group.card_for("ENTA01") == network["point"]


def test_demoting_a_dinamizador_deletes_their_point_and_leaves_the_others(network):
    url = BASE.format(code=network["group"].code) + "co-owners/"

    res = client_for(network["founder"]).delete(url, {"user_code": "ENTA01"}, format="json")

    assert res.status_code == status.HTTP_200_OK
    assert not NetworkPoint.objects.filter(code=network["point"].code).exists()
    assert NetworkPoint.objects.filter(code=network["other"].code).exists()


def test_removing_a_dinamizador_deletes_their_point(network):
    url = BASE.format(code=network["group"].code) + "invite/"

    res = client_for(network["founder"]).delete(url, {"user_code": "ENTA01"}, format="json")

    assert res.status_code == status.HTTP_200_OK
    assert not NetworkPoint.objects.filter(code=network["point"].code).exists()
    assert NetworkPoint.objects.filter(code=network["other"].code).exists()


def test_erasing_the_account_of_a_dinamizador_deletes_their_point(network):
    delete_account(network["lele"])

    assert not NetworkPoint.objects.filter(code=network["point"].code).exists()
    assert NetworkPoint.objects.filter(code=network["other"].code).exists()


def test_deleting_the_network_deletes_its_points(network):
    res = client_for(network["founder"]).delete(f"/api/v1/collections/{network['group'].code}/")

    assert res.status_code == status.HTTP_204_NO_CONTENT
    assert not NetworkPoint.objects.exists()
