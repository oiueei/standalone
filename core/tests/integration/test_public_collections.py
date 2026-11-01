"""Integration tests for anonymous read of PUBLIC collections (#5, phase 2).

A PUBLIC collection (and the things, FAQs, loan chain and calendar within it) is
readable without authentication; a PRIVATE one keeps the invite-only 401/403.
Acting (reserving, asking) still requires login, and the collection *list* stays
private. INACTIVE things never leak to an anonymous reader.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import FAQ, Collection, Thing
from core.models.booking import BookingPeriod
from core.models.transfer import ThingTransfer
from core.tests.factories import also_in

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


def test_anonymous_reader_gets_member_count_but_no_names(api_client, user, user2):
    # Real names of a group's members don't belong to the open web: an anonymous
    # reader keeps the count (codes) but no name and no email.
    coll = _collection(user, Collection.Visibility.PUBLIC)
    coll.invites.add(user2)
    res = api_client.get(f"/api/v1/collections/{coll.code}/")
    assert res.status_code == 200
    invites = res.json()["invites"]
    assert len(invites) == 1
    assert set(invites[0]) == {"code"}


def test_logged_in_guest_still_sees_member_names_but_never_emails(
    authenticated_client2, user, user2
):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    coll.invites.add(user2)
    res = authenticated_client2.get(f"/api/v1/collections/{coll.code}/")
    invites = res.json()["invites"]
    assert invites[0]["name"] == user2.name
    assert "email" not in invites[0]


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


def test_anonymous_reader_gets_the_question_but_not_who_asked_it(api_client, user, user2):
    # Same rule as the member list on the collection itself: the question is
    # public because the thing is, but the member who asked it published
    # nothing, and their name does not belong to the open web.
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    FAQ.objects.create(code="FQ0003", thing=thing, questioner=user2, question="Available?")

    res = api_client.get(f"/api/v1/things/{thing.code}/faq/")

    faq = _items(res)[0]
    assert faq["question"] == "Available?"
    assert faq["questioner_name"] == ""


def test_signed_in_reader_still_sees_who_asked(authenticated_client, user, user2):
    # The counterpart: withholding is about the open web, not about the feature.
    # Anyone with an account who can read the thing still sees the asker.
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    FAQ.objects.create(code="FQ0004", thing=thing, questioner=user2, question="Available?")

    res = authenticated_client.get(f"/api/v1/things/{thing.code}/faq/")

    assert _items(res)[0]["questioner_name"] == user2.name


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


def test_anonymous_reader_gets_the_journey_but_not_who_held_the_thing(api_client, user, user2):
    # The loan chain names every member the thing passed through. Reading it on
    # a PUBLIC collection's thing was a way to enumerate a group's membership
    # from the open web without an account — the same exposure the collection's
    # own member list already closed. The travel story survives; the names go.
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    ThingTransfer.objects.create(
        code="TR0002", thing=thing, from_user=user, to_user=user2, lent_date="2026-01-01"
    )

    data = api_client.get(f"/api/v1/things/{thing.code}/transfers/").json()

    assert data["total_transfers"] == 1
    assert data["unique_homes"] == 2
    assert data["current_holder_name"] is None
    assert data["original_owner_name"] is None
    assert data["transfers"][0]["from_user_name"] == ""
    assert data["transfers"][0]["to_user_name"] == ""
    assert user.name not in str(data)
    assert user2.name not in str(data)


def test_signed_in_reader_still_sees_the_whole_journey(authenticated_client, user, user2):
    # The counterpart: this is about the open web, not about the feature.
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    ThingTransfer.objects.create(
        code="TR0003", thing=thing, from_user=user, to_user=user2, lent_date="2026-01-01"
    )

    data = authenticated_client.get(f"/api/v1/things/{thing.code}/transfers/").json()

    assert data["current_holder_name"] == user2.name
    assert data["original_owner_name"] == user.name
    assert data["transfers"][0]["from_user_name"] == user.name
    assert data["transfers"][0]["to_user_name"] == user2.name


def test_anonymous_can_read_calendar_on_public_thing(api_client, user):
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    res = api_client.get(f"/api/v1/things/{thing.code}/calendar/")
    assert res.status_code == 200


def test_the_anonymous_calendar_says_when_not_who(api_client, user, user2):
    """The open web learns that a thing is out, never who has it.

    This test used to assert a 200 on a thing with **no bookings** — an empty
    list can leak nothing, so it certified only that the endpoint answered. The
    booking below is the whole point: `BookingPeriodCalendarSerializer` is what
    an anonymous reader gets, and every field it grows is public by default.
    """
    coll = _collection(user, Collection.Visibility.PUBLIC)
    thing = _thing(user, coll)
    # Ahead of today: the calendar only carries what is still to come
    # (`BookingPeriod.blocking_filter`), so a fixed date turns this into a test
    # of an empty list the day it passes.
    start = timezone.localdate() + timedelta(days=10)
    end = start + timedelta(days=7)
    BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email="lili6@your-domain.test",
        owner_code=user,
        start_date=start,
        end_date=end,
        status=BookingPeriod.Status.ACCEPTED,
    )

    res = api_client.get(f"/api/v1/things/{thing.code}/calendar/")
    body = res.json()

    assert res.status_code == 200
    assert body == [
        {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "start_time": None,
            "end_time": None,
            "status": "ACCEPTED",
        }
    ]
    # Against the raw bytes, so a field added under any name is caught by what
    # it carries rather than by what it is called.
    assert "lili6@your-domain.test" not in res.content.decode()
    assert user2.code not in res.content.decode()


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


# --- a thing in two collections must not name the one you can't read ------
#
# `Thing.can_view()` lets the thing through on the strength of whichever
# collection the reader *does* have (a public one, or one they belong to). The
# `collection_*` fields then answered with `collections.all()[0]` — the DB's
# first row, viewable or not — so the reader was told the name and code of the
# other one. The drill lent to both the neighbourhood group and the family group
# is the ordinary case, not a contrived one.


def _thing_in_two_collections(owner, second_visibility=Collection.Visibility.PUBLIC):
    """A thing in a PRIVATE collection (created first, so it sorts first) and in
    a second one the reader is meant to reach it through."""
    private = _collection(owner, Collection.Visibility.PRIVATE, code="PRV001")
    private.headline = "Cosas de casa"
    private.tags = ["secreto"]
    private.save()
    reachable = _collection(owner, second_visibility, code="OPN001")
    thing = _thing(owner, private)
    also_in(reachable, thing)
    return private, reachable, thing


def test_anonymous_reader_is_not_told_the_private_collection_a_public_thing_shares(
    api_client, user
):
    private, reachable, thing = _thing_in_two_collections(user)

    res = api_client.get(f"/api/v1/things/{thing.code}/")

    assert res.status_code == 200
    body = res.json()
    assert body["collection_code"] == reachable.code
    assert body["collection_headline"] != private.headline
    assert private.code not in str(body)
    assert "secreto" not in body["collection_tags"]


def test_member_is_not_told_the_private_collection_a_shared_thing_sits_in(
    authenticated_client2, user, user2
):
    """A thing lent to two groups, one of which this member is not in. The thing's
    own page prints collection_headline, the code and the tags of the collection it
    answers with, so those are the fields a member of one group would have read the
    other's name in. (It was checked through `/invited-things/` until that endpoint
    went with the `/shared` page, 2026-10-03; the test above is the anonymous
    reader, this one is the member.)"""
    private, reachable, thing = _thing_in_two_collections(
        user, second_visibility=Collection.Visibility.PRIVATE
    )
    reachable.invites.add(user2)

    res = authenticated_client2.get(f"/api/v1/things/{thing.code}/")

    assert res.status_code == 200
    body = res.json()
    assert body["collection_code"] == reachable.code
    assert body["collection_headline"] != private.headline
    assert private.code not in str(body)
    assert "secreto" not in body["collection_tags"]


def test_owner_still_sees_their_own_private_collection_on_their_thing(authenticated_client, user):
    """The narrowing must not cost the owner the collection they actually own —
    it is `can_view`, not "public only"."""
    private, _reachable, thing = _thing_in_two_collections(user)

    res = authenticated_client.get(f"/api/v1/things/{thing.code}/")

    assert res.status_code == 200
    assert res.json()["collection_code"] == private.code
    assert "secreto" in res.json()["collection_tags"]


def test_the_first_collection_of_a_thing_is_the_earliest_whatever_order_the_rows_come_in(user):
    """`collections.all()` has no ORDER BY, so Postgres may hand the rows back in any order
    (a prefetch of the co-owners is enough to change it). "The first" must not depend on
    that: it is the oldest, then the code, and the owner reads both collections here."""
    from django.db.models import Prefetch
    from rest_framework.test import APIRequestFactory

    from core.serializers import ThingSerializer

    private, _reachable, thing = _thing_in_two_collections(user)
    request = APIRequestFactory().get(f"/api/v1/things/{thing.code}/")
    request.user = user
    # The rows in the opposite order to the one a reader would call "the first".
    reversed_rows = Prefetch("collections", queryset=Collection.objects.order_by("-created"))
    loaded = Thing.objects.prefetch_related(reversed_rows).get(code=thing.code)
    assert [c.code for c in loaded.collections.all()][0] != private.code

    data = ThingSerializer(loaded, context={"request": request}).data

    assert data["collection_code"] == private.code


# --- who contributed a thing (owner_name) ---------------------------------


def _community_with_contribution(owner, member):
    """A PUBLIC COMMUNITY collection whose thing was contributed by a member."""
    coll = Collection.objects.create(
        code="PUB900",
        owner=owner,
        headline="Bibliocosas",
        visibility=Collection.Visibility.PUBLIC,
        mode=Collection.Mode.COMMUNITY,
    )
    coll.invites.add(member)
    return coll, _thing(member, coll, code="THG900")


def test_anonymous_reader_is_not_told_which_member_contributed_a_thing(api_client, user, user2):
    """The third name a group leaked to the open web, after the FAQ asker and the
    journey's past holders: in COMMUNITY mode every card carries the name of the
    member who put the thing there. That member consented to a group, not to the
    web, and the visibility switch is the curator's — so the name goes and the
    contribution stays."""
    coll, thing = _community_with_contribution(user, user2)

    grid = api_client.get(f"/api/v1/collections/{coll.code}/").json()
    detail = api_client.get(f"/api/v1/things/{thing.code}/").json()

    assert grid["things"][0]["owner_name"] == ""
    assert detail["owner_name"] == ""
    # What the reader keeps: the thing itself, and that it belongs to someone
    # other than the curator (the code, which names nobody).
    assert detail["owner"] == user2.code
    assert detail["headline"] == "A thing"


def test_anonymous_reader_is_still_told_who_published_the_collection(api_client, user):
    """The curator is not a third party: they chose to publish, and the
    collection header already serves their name to the very same reader.
    Withholding it on their own listings would be theatre, not privacy."""
    coll, _ = _community_with_contribution(user, user)
    own = _thing(user, coll, code="THG901")

    detail = api_client.get(f"/api/v1/things/{own.code}/").json()

    assert detail["owner_name"] == user.name


def test_signed_in_reader_still_sees_who_contributed(authenticated_client, user, user2):
    """Attribution to the contributing member is half the point of a COMMUNITY
    collection. It is withheld from the open web, never from the group."""
    coll, thing = _community_with_contribution(user2, user)

    grid = authenticated_client.get(f"/api/v1/collections/{coll.code}/").json()
    detail = authenticated_client.get(f"/api/v1/things/{thing.code}/").json()

    assert grid["things"][0]["owner_name"] == user.name
    assert detail["owner_name"] == user.name
