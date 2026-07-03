"""Integration tests for per-collection rental rules (#7).

A collection can constrain its LEND/RENT things to a set of fixed rental lengths
(days) and a set of allowed pickup/return weekdays. The renter picks a duration
and a pickup date; the booking view is the server-side backstop.
"""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User

pytestmark = pytest.mark.django_db

REQUEST_URL = "/api/v1/things/{}/request/"


def _next_weekday(weekday):
    """First future date (from tomorrow) that falls on the given weekday (0=Mon)."""
    d = date.today() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


@pytest.fixture
def rental_setup(db):
    owner = User.objects.create(code="RNOWN1", email="rnown@test.com", name="Owner")
    renter = User.objects.create(code="RNTER1", email="rnter@test.com", name="Renter")
    # Fixed lengths 3 and 7 days; pickup/return only Mon–Fri (0–4).
    collection = Collection.objects.create(
        code="RCOL01",
        owner=owner,
        headline="Tool library",
        status="ACTIVE",
        rental_durations=[3, 7],
        rental_weekdays=[0, 1, 2, 3, 4],
    )
    collection.invites.add(renter)
    thing = Thing.objects.create(
        code="RTHG01", type=Thing.Type.RENT_THING, owner=owner, headline="Drill", fee=5
    )
    collection.things.add(thing)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(renter).access_token}")
    return {
        "owner": owner,
        "renter": renter,
        "collection": collection,
        "thing": thing,
        "client": client,
    }


# --- model method (pure) --------------------------------------------------


def test_rental_violation_rejects_wrong_duration(rental_setup):
    coll = rental_setup["collection"]
    start = _next_weekday(0)  # Monday
    # 4-day span (Mon–Thu) — not in [3, 7].
    assert coll.rental_violation(start, start + timedelta(days=3)) is not None


def test_rental_violation_rejects_disallowed_pickup_weekday(rental_setup):
    coll = rental_setup["collection"]
    sat = _next_weekday(5)  # Saturday, not allowed
    # 3-day span starting Saturday → pickup weekday violation.
    assert "pickup" in coll.rental_violation(sat, sat + timedelta(days=2)).lower()


def test_rental_violation_rejects_disallowed_return_weekday(rental_setup):
    coll = rental_setup["collection"]
    thu = _next_weekday(3)  # Thursday
    # 3-day span Thu–Sat → return lands on Saturday (5), not allowed.
    assert "return" in coll.rental_violation(thu, thu + timedelta(days=2)).lower()


def test_rental_violation_accepts_valid(rental_setup):
    coll = rental_setup["collection"]
    mon = _next_weekday(0)
    # 3-day span Mon–Wed: valid length, both ends Mon–Fri.
    assert coll.rental_violation(mon, mon + timedelta(days=2)) is None


def test_no_rules_never_violates(db):
    owner = User.objects.create(code="NRUL01", email="nrul@test.com", name="O")
    coll = Collection.objects.create(code="NRUL02", owner=owner, headline="Free")
    assert not coll.has_rental_rules()
    today = date.today()
    assert coll.rental_violation(today, today + timedelta(days=99)) is None


# --- booking enforcement (API) --------------------------------------------


def _book(setup, start, end):
    return setup["client"].post(
        REQUEST_URL.format(setup["thing"].code),
        {
            "start_date": str(start),
            "end_date": str(end),
            "collection_code": setup["collection"].code,
        },
        format="json",
    )


def test_request_accepts_valid_rental(rental_setup):
    mon = _next_weekday(0)
    res = _book(rental_setup, mon, mon + timedelta(days=2))  # 3 days, Mon–Wed
    assert res.status_code == 200
    assert BookingPeriod.objects.filter(thing_code=rental_setup["thing"]).count() == 1


def test_request_rejects_wrong_duration(rental_setup):
    mon = _next_weekday(0)
    res = _book(rental_setup, mon, mon + timedelta(days=3))  # 4 days
    assert res.status_code == 400
    assert not BookingPeriod.objects.filter(thing_code=rental_setup["thing"]).exists()


def test_request_rejects_disallowed_weekday(rental_setup):
    sat = _next_weekday(5)
    res = _book(rental_setup, sat, sat + timedelta(days=2))  # 3 days but pickup Sat
    assert res.status_code == 400
    assert not BookingPeriod.objects.filter(thing_code=rental_setup["thing"]).exists()


def test_request_without_rules_allows_any_dates(rental_setup):
    # Drop the rules → any valid future range books fine.
    coll = rental_setup["collection"]
    coll.rental_durations = []
    coll.rental_weekdays = []
    coll.save(update_fields=["rental_durations", "rental_weekdays"])
    sat = _next_weekday(5)
    res = _book(rental_setup, sat, sat + timedelta(days=10))
    assert res.status_code == 200


# --- serializer -----------------------------------------------------------


def test_thing_serializer_exposes_rules(rental_setup):
    res = rental_setup["client"].get(f"/api/v1/things/{rental_setup['thing'].code}/")
    assert res.status_code == 200
    assert res.json()["rental_durations"] == [3, 7]
    assert res.json()["rental_weekdays"] == [0, 1, 2, 3, 4]


def test_collection_update_normalizes_rental(rental_setup):
    owner_client = APIClient()
    owner_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(rental_setup['owner']).access_token}"
    )
    res = owner_client.patch(
        f"/api/v1/collections/{rental_setup['collection'].code}/",
        {"rental_durations": [7, 3, 3], "rental_weekdays": [4, 0, 0]},
        format="json",
    )
    assert res.status_code == 200
    rental_setup["collection"].refresh_from_db()
    assert rental_setup["collection"].rental_durations == [3, 7]
    assert rental_setup["collection"].rental_weekdays == [0, 4]
