"""The server's half of the hourly-grid parity table.

The request page offers hourly starts (`freeStartTimes`, and greys out a day
with `isHourlyPickupDisabled`, in `frontend/src/utils/rental.js`); the server
accepts them (`Collection.reservation_hour_violation`, `BookingPeriod.
has_overlap`) and reports whether a day has room (`_day_has_a_free_hour`, which
feeds the "available" line on every card). Tested apart, the two could drift and
both suites stay green: a member offered a start the server refuses, or a card
saying "today" for a day the picker greys out.

So the cases live in one JSON file, read here and by
`frontend/src/utils/hourlyGridParity.test.js`, each with its expected starts
worked out by hand. Here, every start on a five-minute sweep of the day is put
to the server, and the ones it accepts must be exactly those. No case's slot
spans a whole day across a gap: the server still accepts that one full-day form
the page stopped offering (2026-09), so it is the one place they differ on
purpose.
"""

import json
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from core.models import BookingPeriod, Collection, Thing, User
from core.services.booking_service import _day_has_a_free_hour

ROOT = Path(__file__).resolve().parents[3]
CASES = json.loads((ROOT / "frontend" / "src" / "test" / "hourlyGridParity.json").read_text())[
    "cases"
]

pytestmark = pytest.mark.django_db


def _hm(value):
    hours, minutes = (int(part) for part in value.split(":"))
    return time(hours, minutes)


def _next_monday():
    day = timezone.localdate() + timedelta(days=1)
    while day.weekday() != 0:
        day += timedelta(days=1)
    return day


@pytest.fixture
def space(request):
    case = request.param
    owner = User.objects.create(code="GRDOWN", email="lala@your-domain.test")
    member = User.objects.create(code="GRDMEM", email="lele@your-domain.test")
    collection = Collection.objects.create(
        code="GRDCOL",
        owner=owner,
        headline="Parity",
        allowed_thing_types=["RESERVE_THING"],
        reservation_unit=Collection.ReservationUnit.HOUR,
        reservation_min_minutes=case["min_minutes"],
        # Out of the way: the cap is its own rule, not the grid's.
        reservation_max_minutes=720,
        opening_hours={"0": case["blocks"]},
    )
    monday = _next_monday()
    # `pause` is [from, until] in days from that Monday, both included.
    pause = case.get("pause")
    thing = Thing.objects.create(
        code="GRDTHG",
        type=Thing.Type.RESERVE_THING,
        owner=owner,
        headline="Sala",
        paused_from=monday + timedelta(days=pause[0]) if pause else None,
        paused_until=monday + timedelta(days=pause[1]) if pause else None,
    )
    collection.things.add(thing)
    for booked in case["bookings"]:
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=member,
            requester_email=member.email,
            owner_code=owner,
            start_date=monday,
            end_date=monday + timedelta(days=1),
            start_time=_hm(booked[0]) if booked else None,
            end_time=_hm(booked[1]) if booked else None,
            status=BookingPeriod.Status.ACCEPTED,
        )
    # Half-way through the case's minute on that Monday, or the evening before
    # when the case is not about today — as the page's own clock is.
    if case["now_minutes"] is None:
        now = datetime.combine(monday - timedelta(days=1), time(23, 0))
    else:
        minutes = case["now_minutes"]
        now = datetime.combine(monday, time(minutes // 60, minutes % 60, 30))
    return case, collection, thing, monday, timezone.make_aware(now)


@pytest.mark.parametrize("space", CASES, ids=[c["name"] for c in CASES], indirect=True)
def test_the_server_accepts_exactly_the_starts_the_page_offers(space):
    case, collection, thing, monday, now = space
    accepted = []
    for start in range(0, 24 * 60 - case["duration"], 5):
        begins = time(start // 60, start % 60)
        ends = time((start + case["duration"]) // 60, (start + case["duration"]) % 60)
        if collection.reservation_hour_violation(monday, begins, ends, now=now):
            continue
        # The request refuses the pause before it counts bookings.
        if thing.pause_overlaps(monday, monday + timedelta(days=1)):
            continue
        if BookingPeriod.has_overlap(
            thing.code,
            monday,
            monday + timedelta(days=1),
            start_time=begins,
            end_time=ends,
            units=case.get("units", 1),
        ):
            continue
        accepted.append(begins.strftime("%H:%M"))
    assert accepted == case["starts"]


@pytest.mark.parametrize("space", CASES, ids=[c["name"] for c in CASES], indirect=True)
def test_the_server_finds_a_free_slot_exactly_when_the_picker_offers_the_day(space):
    case, collection, thing, monday, now = space
    # As `Thing.availability_window` does: with several units a day is taken only
    # where they are all on.
    thing.units = case.get("units", 1)
    blocked = thing.served_periods(list(BookingPeriod.objects.filter(thing_code=thing)))
    earliest = now.hour * 60 + now.minute if now.date() == monday else 0
    assert (
        _day_has_a_free_hour(monday, collection, blocked, earliest=earliest)
        is case["day_has_a_free_slot"]
    )


def _shape(row):
    """A row as the JSON file writes it: None for a whole day, [start, end] otherwise."""
    if row.start_time is None:
        return None
    return [row.start_time.strftime("%H:%M"), row.end_time.strftime("%H:%M")]


def _ordered(rows):
    return sorted(rows, key=lambda r: ("", "") if r is None else tuple(r))


@pytest.mark.parametrize("space", CASES, ids=[c["name"] for c in CASES], indirect=True)
def test_the_server_serves_exactly_the_taken_periods_the_page_is_fed(space):
    """The stretches the server works out as full are the ones the file hands the
    page as `served_periods` (the bookings themselves, with one unit)."""
    case, collection, thing, monday, now = space
    rows = list(BookingPeriod.objects.filter(thing_code=thing))

    thing.units = case.get("units", 1)
    served = thing.served_periods(rows)

    assert _ordered(_shape(r) for r in served) == _ordered(
        case.get("served_periods", case["bookings"])
    )
