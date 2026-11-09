"""Each dinamizador reads and edits only their own pickup point; the points are public
with the collection. (Outside a network the same page is an identity card: see
``test_curator_entity.py``.)"""

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, NetworkPoint, User
from core.serializers.network_point import NetworkPointWriteSerializer
from core.tests.factories import CollectionFactory

LEND, RENT = "LEND_THING", "RENT_THING"


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _user(code, name):
    return User.objects.create(code=code, email=f"{name.lower()}@your-domain.test", name=name)


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
        visibility=Collection.Visibility.PUBLIC,
        allowed_thing_types=[LEND, RENT],
        email_note="the network's note",
    )
    network.invites.add(lele, lili, lolo)
    network.co_owners.add(lele, lili)
    return {"network": network, "founder": founder, "lele": lele, "lili": lili, "lolo": lolo}


def url(world):
    return f"/api/v1/collections/{world['network'].code}/point/"


def test_a_dinamizador_without_a_point_reads_the_empty_one(world):
    res = client_for(world["lele"]).get(url(world))

    assert res.status_code == status.HTTP_200_OK
    assert res.data["entity_name"] == ""
    assert res.data["display_name"] == "Lele"
    assert not NetworkPoint.objects.exists()


def test_a_dinamizador_sets_up_their_point_and_it_is_theirs_alone(world):
    body = {
        "entity_name": "Cooperativa La Fusteria",
        "address": "Carrer Major 4",
        "hours_note": "martes y jueves de 18 a 20",
        "contact": "93 000 00 00",
        "weekdays": [3, 1, 1],
        "request_info": '{"es": "Trae el DNI", "ca": "Porta el DNI"}',
    }

    res = client_for(world["lele"]).put(url(world), body, format="json")

    assert res.status_code == status.HTTP_200_OK
    point = NetworkPoint.objects.get()
    assert (point.user_id, point.collection_id) == ("ENTA01", world["network"].code)
    assert point.weekdays == [1, 3]
    assert res.data["display_name"] == "Cooperativa La Fusteria"
    other = client_for(world["lili"]).get(url(world))
    assert other.data["entity_name"] == ""


def test_the_founder_has_a_point_like_any_dinamizador(world):
    res = client_for(world["founder"]).put(url(world), {"address": "Plaza 1"}, format="json")

    assert res.status_code == status.HTTP_200_OK
    assert NetworkPoint.objects.get().user_id == "FOUN01"


def test_putting_twice_updates_the_same_point(world):
    client_for(world["lele"]).put(url(world), {"address": "A"}, format="json")
    client_for(world["lele"]).put(url(world), {"hours_note": "B"}, format="json")

    point = NetworkPoint.objects.get()
    assert (point.address, point.hours_note) == ("A", "B")


def test_a_plain_member_cannot_set_a_point(world):
    res = client_for(world["lolo"]).put(url(world), {"address": "A"}, format="json")

    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert not NetworkPoint.objects.exists()


@pytest.mark.parametrize(
    "body",
    [
        {"entity_name": "x" * 65},
        {"address": "x" * 65},
        {"hours_note": "x" * 129},
        {"contact": "x" * 65},
        {"entity_name": "<b>Co-op</b>"},
        {"weekdays": [7]},
        {"closed_dates": "not a date"},
        {"deposit_policy": "x" * 257},
        {"request_info": "x" * 513},
        {"email_note": "x" * 513},
        {"about": "x" * 2001},
    ],
)
def test_the_limits_are_the_collections_own(world, body):
    res = client_for(world["lele"]).put(url(world), body, format="json")

    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_closed_dates_are_cleaned_like_the_collections(world):
    future = timezone.localdate() + timezone.timedelta(days=30)
    past = timezone.localdate() - timezone.timedelta(days=30)
    line = f"{future:%d/%m/%Y}, {past:%d/%m/%Y}, {future:%d/%m/%Y}"

    client_for(world["lele"]).put(url(world), {"closed_dates": line}, format="json")

    assert NetworkPoint.objects.get().closed_dates == [future.isoformat()]


def test_the_points_travel_with_the_collection_to_everyone_address_included(world):
    NetworkPoint.objects.create(
        collection=world["network"],
        user=world["lele"],
        entity_name="Cooperativa La Fusteria",
        address="Carrer Major 4",
        email_note="the entity's note",
    )

    res = client_for().get(f"/api/v1/collections/{world['network'].code}/")

    [point] = res.data["points"]
    assert point["display_name"] == "Cooperativa La Fusteria"
    assert point["address"] == "Carrer Major 4"
    assert point["user"] == "ENTA01"
    assert point["email_note"] == ""


def test_the_entitys_email_note_is_read_back_by_its_dinamizador_and_the_founder_only(world):
    NetworkPoint.objects.create(
        collection=world["network"], user=world["lele"], email_note="the entity's note"
    )
    code = world["network"].code

    seen = {
        name: client_for(world[name])
        .get(f"/api/v1/collections/{code}/")
        .data["points"][0]["email_note"]
        for name in ("lele", "founder", "lili", "lolo")
    }

    assert seen == {
        "lele": "the entity's note",
        "founder": "the entity's note",
        "lili": "",
        "lolo": "",
    }


def test_a_dinamizador_saves_and_removes_the_logo_of_their_entity(world):
    key = "oiueei/collections/fusteria"

    saved = client_for(world["lele"]).put(url(world), {"logo": key}, format="json")

    assert saved.status_code == status.HTTP_200_OK
    assert NetworkPoint.objects.get().logo == key
    assert saved.data["logo"] == key
    assert saved.data["logo_url"].endswith(key)

    removed = client_for(world["lele"]).put(url(world), {"logo": ""}, format="json")

    assert removed.status_code == status.HTTP_200_OK
    assert NetworkPoint.objects.get().logo == ""
    assert removed.data["logo_url"] is None


def test_a_point_with_no_logo_has_no_logo_url(world):
    res = client_for(world["lele"]).get(url(world))

    assert res.data["logo"] == ""
    assert res.data["logo_url"] is None


def test_a_logo_from_another_folder_is_refused(world):
    res = client_for(world["lele"]).put(
        url(world), {"logo": "oiueei/documents/someone-elses-rules"}, format="json"
    )

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "logo" in res.data
    assert not NetworkPoint.objects.exists()


def test_a_plain_member_cannot_set_the_logo(world):
    res = client_for(world["lolo"]).put(
        url(world), {"logo": "oiueei/collections/fusteria"}, format="json"
    )

    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert not NetworkPoint.objects.exists()


def test_the_logo_travels_with_the_collection_to_everyone(world):
    NetworkPoint.objects.create(
        collection=world["network"], user=world["lele"], logo="oiueei/collections/fusteria"
    )

    res = client_for().get(f"/api/v1/collections/{world['network'].code}/")

    [point] = res.data["points"]
    assert point["logo_url"].endswith("oiueei/collections/fusteria")


def test_a_list_body_is_no_change_in_a_network(world):
    res = client_for(world["lele"]).put(url(world), [1, 2], format="json")

    assert res.status_code == status.HTTP_200_OK
    assert res.data["entity_name"] == ""


def test_two_first_puts_of_the_same_curator_leave_one_row_with_the_data_of_the_second(
    world, monkeypatch
):
    """The row a concurrent first PUT created just before this one's save is the one
    this PUT applies to, instead of a 500 on `one_point_per_curator`."""
    original = NetworkPointWriteSerializer.is_valid
    raced = []

    def validate_after_a_rival_created_the_row(self, **kwargs):
        if not raced:
            raced.append(True)
            NetworkPoint.objects.create(
                collection=world["network"], user=world["lele"], entity_name="Rival"
            )
        return original(self, **kwargs)

    monkeypatch.setattr(
        NetworkPointWriteSerializer, "is_valid", validate_after_a_rival_created_the_row
    )

    res = client_for(world["lele"]).put(url(world), {"entity_name": "Mine"}, format="json")

    assert res.status_code == status.HTTP_200_OK
    assert res.data["entity_name"] == "Mine"
    assert NetworkPoint.objects.get().entity_name == "Mine"
