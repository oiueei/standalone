"""Integration tests for anonymous read of PUBLIC collections (#5, phase 2).

A PUBLIC collection (and the things, FAQs, loan chain and calendar within it) is
readable without authentication; a PRIVATE one keeps the invite-only 401/403.
Acting (reserving, asking) still requires login, and the collection *list* stays
private. INACTIVE things never leak to an anonymous reader.
"""

import pytest

from core.models import FAQ, Collection, Thing
from core.models.transfer import ThingTransfer

pytestmark = pytest.mark.django_db


def _collection(owner, visibility, code="PUB001"):
    return Collection.objects.create(
        code=code,
        owner=owner,
        headline="A collection",
        visibility=visibility,
    )


def _thing(owner, collection, code="THG001", status=Thing.Status.ACTIVE):
    t = Thing.objects.create(
        code=code, type="GIFT_THING", owner=owner, headline="A thing", status=status
    )
    collection.things.add(t)
    return t


def _items(res):
    data = res.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


# --- collection retrieve --------------------------------------------------


def test_anonymous_can_read_public_collection(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    _thing(user, coll)
    res = api_client.get(f"/api/v1/collections/{coll.code}/")
    assert res.status_code == 200
    assert res.json()["code"] == coll.code
    assert len(res.json()["things"]) == 1


def test_anonymous_cannot_read_private_collection(api_client, user):
    coll = _collection(user, Collection.Visibility.PRIVATE)
    res = api_client.get(f"/api/v1/collections/{coll.code}/")
    assert res.status_code in (401, 403)


def test_inactive_things_are_hidden_from_anonymous_readers(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    _thing(user, coll, code="ACT001", status=Thing.Status.ACTIVE)
    _thing(user, coll, code="INA001", status=Thing.Status.INACTIVE)
    res = api_client.get(f"/api/v1/collections/{coll.code}/")
    assert res.status_code == 200
    codes = {t["code"] for t in res.json()["things"]}
    assert codes == {"ACT001"}


def test_authenticated_non_member_can_read_public_collection(authenticated_client2, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    res = authenticated_client2.get(f"/api/v1/collections/{coll.code}/")
    assert res.status_code == 200


def test_collection_list_still_requires_auth(api_client, user):
    _collection(user, Collection.Visibility.PUBLIC)
    res = api_client.get("/api/v1/collections/")
    assert res.status_code in (401, 403)


# --- thing retrieve + social layer ----------------------------------------


def test_anonymous_can_read_thing_in_public_collection(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    res = api_client.get(f"/api/v1/things/{thing.code}/")
    assert res.status_code == 200
    assert res.json()["code"] == thing.code


def test_anonymous_cannot_read_thing_in_private_collection(api_client, user):
    coll = _collection(user, Collection.Visibility.PRIVATE)
    thing = _thing(user, coll)
    res = api_client.get(f"/api/v1/things/{thing.code}/")
    assert res.status_code in (401, 403)


def test_anonymous_can_read_faqs_on_public_thing(api_client, user, user2):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    FAQ.objects.create(code="FQ0001", thing=thing, questioner=user2, question="Available?")
    res = api_client.get(f"/api/v1/things/{thing.code}/faq/")
    assert res.status_code == 200
    assert len(_items(res)) == 1


def test_anonymous_cannot_read_faqs_on_private_thing(api_client, user, user2):
    coll = _collection(user, Collection.Visibility.PRIVATE)
    thing = _thing(user, coll)
    FAQ.objects.create(code="FQ0002", thing=thing, questioner=user2, question="Available?")
    res = api_client.get(f"/api/v1/things/{thing.code}/faq/")
    assert res.status_code in (401, 403)


def test_anonymous_can_read_transfers_on_public_thing(api_client, user, user2):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    ThingTransfer.objects.create(
        code="TR0001", thing=thing, from_user=user, to_user=user2, lent_date="2026-01-01"
    )
    res = api_client.get(f"/api/v1/things/{thing.code}/transfers/")
    assert res.status_code == 200
    assert res.json()["total_transfers"] == 1


def test_anonymous_can_read_calendar_on_public_thing(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    res = api_client.get(f"/api/v1/things/{thing.code}/calendar/")
    assert res.status_code == 200


# --- acting still requires login ------------------------------------------


def test_anonymous_cannot_reserve_a_public_thing(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    res = api_client.post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
    assert res.status_code == 401


def test_anonymous_cannot_ask_a_question_on_a_public_thing(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    res = api_client.post(f"/api/v1/things/{thing.code}/faq/", {"question": "Hi?"}, format="json")
    assert res.status_code == 401
