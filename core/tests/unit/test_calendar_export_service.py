"""The collection calendar export — one VEVENT per date-based reservation (.ics).

The behaviours this file guards:

- a confirmed loan/rental/reservation becomes exactly one event, all-day over
  the days the thing is out, with the exclusive DTEND that leaves the return
  day open;
- an hourly reservation renders in UTC, read in the deployment's timezone —
  correctly on both sides of a DST change, which is the exact shape of the
  production bug that retired the CSV (an account's locale read ``10/01/2026``
  as January the 10th);
- the file is honest RFC 5545: CRLF everywhere, TEXT escaping, folding at 75
  *octets* that never splits a UTF-8 character;
- every upcoming reservation ships every time, under a stable UID — no
  watermark;
- what is *not* a calendar commitment — a pending hold, a rejected or cancelled
  one, a gift/sale with no dates, a booking that already ended — stays out.
"""

import datetime
import re

import pytest
import time_machine
from django.test import override_settings

from core.models import BookingPeriod, Collection, Thing, User
from core.services.calendar_export_service import (
    CALENDAR_TEXTS,
    build_calendar_export,
    calendar_filename,
)
from core.tests.factories import also_in

pytestmark = pytest.mark.django_db

TODAY = datetime.date(2026, 9, 10)


@pytest.fixture(autouse=True)
def _frozen_today():
    # Every "future / in progress / past" assertion below is relative to TODAY;
    # freeze the clock so the suite doesn't rot the day these dates go stale.
    with time_machine.travel(TODAY):
        yield


# --- Reading the file back ----------------------------------------------------


def _physical_lines(ics_bytes):
    """The file's actual lines — CRLF-delimited, as RFC 5545 demands."""
    text = ics_bytes.decode("utf-8")
    assert text.endswith("\r\n")
    return text.split("\r\n")[:-1]


def _unfolded(ics_bytes):
    """Content lines with RFC 5545 folding undone (a continuation is a line
    starting with exactly one space)."""
    out = []
    for line in _physical_lines(ics_bytes):
        if line.startswith(" ") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _events(ics_bytes):
    """The VEVENTs as ``{name: value}`` dicts — a property's parameters
    (``DTSTART;VALUE=DATE``) are folded into the name."""
    events = []
    current = None
    for line in _unfolded(ics_bytes):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            events.append(current)
            current = None
        elif current is not None:
            name, _, value = line.partition(":")
            current[name] = value
    return events


def _calendar_props(ics_bytes):
    props = {}
    for line in _unfolded(ics_bytes):
        if line.startswith(("BEGIN:VEVENT", "END:VEVENT")):
            break
        name, _, value = line.partition(":")
        props[name] = value
    return props


@pytest.fixture
def owner(db):
    return User.objects.create(code="OWN001", email="lala@your-domain.test", name="Olga")


@pytest.fixture
def member(db):
    return User.objects.create(code="MEM001", email="lele@your-domain.test", name="Júlia")


@pytest.fixture
def group(owner):
    # A real curated group has a language; the standalone default is English and
    # the TestLanguage class covers that path explicitly.
    return Collection.objects.create(
        code="GRP001", owner=owner, headline="El taller", language="es"
    )


def _thing(owner, code="THG001", thing_type="LEND_THING", headline="Taladre", location=""):
    return Thing.objects.create(
        code=code,
        type=thing_type,
        owner=owner,
        headline=headline,
        location=location,
        status="ACTIVE",
    )


def _booking(
    thing,
    member,
    owner,
    *,
    code="BKG001",
    thing_type=None,
    start=TODAY + datetime.timedelta(days=3),
    days=3,
    status="ACCEPTED",
    deposit=None,
    note="",
    start_time=None,
    end_time=None,
):
    return BookingPeriod.objects.create(
        code=code,
        thing_code=thing,
        thing_type=thing_type or thing.type,
        requester_code=member,
        requester_email=member.email,
        owner_code=owner,
        start_date=start,
        end_date=start + datetime.timedelta(days=days),
        status=status,
        deposit_amount=deposit,
        project_note=note,
        start_time=start_time,
        end_time=end_time,
    )


class TestOneEventPerReservation:
    def test_a_confirmed_loan_is_one_all_day_event_over_the_days_it_is_out(
        self, group, owner, member
    ):
        thing = _thing(owner, location="Nau 3")
        group.things.add(thing)
        # picked up the 14th, back the 17th → out on 14/15/16, free again the 17th
        _booking(thing, member, owner, start=datetime.date(2026, 9, 14), days=3)

        ics_bytes, count, _ = build_calendar_export(group)

        assert count == 1
        (event,) = _events(ics_bytes)
        assert event["SUMMARY"] == "Taladre → Júlia"  # es default, no kind in front
        assert event["DTSTART;VALUE=DATE"] == "20260914"
        # iCalendar's all-day DTEND is exclusive — OIUEEI's end_date already
        # is the day the thing is free again, so the 17th stays open.
        assert event["DTEND;VALUE=DATE"] == "20260917"
        assert event["LOCATION"] == "Nau 3"
        assert "Devolución el 17/09/2026" in event["DESCRIPTION"]
        assert event["UID"] == "BKG001@oiueei"
        assert re.fullmatch(r"\d{8}T\d{6}Z", event["DTSTAMP"])

    def test_a_weeks_loan_blocks_seven_days_and_leaves_the_return_day_open(
        self, group, owner, member
    ):
        # The rule: pick up Monday the 14th, return Monday the 21st → the
        # 14th–20th are blocked and the 21st is bookable again.
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, start=datetime.date(2026, 9, 14), days=7)

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DTSTART;VALUE=DATE"] == "20260914"
        assert event["DTEND;VALUE=DATE"] == "20260921"  # exclusive: covers 14–20, frees 21

    def test_a_one_day_reservation_blocks_exactly_that_day(self, group, owner, member):
        thing = _thing(owner, thing_type="RESERVE_THING")
        group.things.add(thing)
        # request_reservation stores end_date = start + duration, so a 1-day
        # reservation has end_date = start + 1 — the exclusive DTEND that
        # renders as the single booked day.
        _booking(
            thing,
            member,
            owner,
            thing_type="RESERVE_THING",
            start=datetime.date(2026, 9, 20),
            days=1,
        )

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DTSTART;VALUE=DATE"] == "20260920"
        assert event["DTEND;VALUE=DATE"] == "20260921"  # exclusive → only the 20th shows

    def test_a_multi_day_reservation_blocks_every_booked_day(self, group, owner, member):
        # A 4-day reservation blocks all 4 days (unlike a loan, whose "return
        # day" is free) — end_date = start + 4, exclusive, so 20/21/22/23.
        thing = _thing(owner, thing_type="RESERVE_THING")
        group.things.add(thing)
        _booking(
            thing,
            member,
            owner,
            thing_type="RESERVE_THING",
            start=datetime.date(2026, 9, 20),
            days=4,
        )

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DTSTART;VALUE=DATE"] == "20260920"
        assert event["DTEND;VALUE=DATE"] == "20260924"  # covers 20, 21, 22, 23

    def test_a_deposit_and_a_project_note_reach_the_description(self, group, owner, member):
        loan = _thing(owner, code="THG010", thing_type="RENT_THING")
        space = _thing(owner, code="THG011", thing_type="RESERVE_THING", headline="Sala")
        group.things.add(loan, space)
        _booking(loan, member, owner, code="BKG010", thing_type="RENT_THING", deposit="25.00")
        _booking(
            space,
            member,
            owner,
            code="BKG011",
            thing_type="RESERVE_THING",
            note="Ensayo de teatro",
        )

        events = {e["SUMMARY"]: e["DESCRIPTION"] for e in _events(build_calendar_export(group)[0])}

        assert "Fianza: 25.00" in events["Taladre → Júlia"]
        assert "Proyecto: Ensayo de teatro" in events["Sala — Júlia"]

    def test_the_calendar_names_the_collection(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        props = _calendar_props(build_calendar_export(group)[0])

        assert props["X-WR-CALNAME"] == "El taller"
        assert props["VERSION"] == "2.0"
        assert props["PRODID"] == "-//OIUEEI//Calendar export//EN"
        assert props["CALSCALE"] == "GREGORIAN"
        assert props["METHOD"] == "PUBLISH"


class TestHourlyReservation:
    @override_settings(TIME_ZONE="Europe/Madrid")
    def test_the_exact_production_bug_17_to_21_on_oct_1st(self, group, owner, member):
        # An early adopter's report: the CSV rendered 01/10/2026 and a
        # day/month Google account imported it as January the 10th. In .ics it
        # is 17:00–21:00 Europe/Madrid (UTC+2) = 15:00–19:00 UTC, and no
        # account's locale can read it any other way.
        thing = _thing(owner, thing_type="RESERVE_THING", headline="Sala")
        group.things.add(thing)
        _booking(
            thing,
            member,
            owner,
            thing_type="RESERVE_THING",
            start=datetime.date(2026, 10, 1),
            days=1,
            start_time=datetime.time(17, 0),
            end_time=datetime.time(21, 0),
        )

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DTSTART"] == "20261001T150000Z"
        assert event["DTEND"] == "20261001T190000Z"
        assert "DTSTART;VALUE=DATE" not in event  # timed, never all-day

    @override_settings(TIME_ZONE="Europe/Madrid")
    def test_both_sides_of_the_dst_change_render_their_own_utc_offset(self, group, owner, member):
        # 1 October is UTC+2 (CEST); 1 December is UTC+1 (CET) — the same wall
        # clock must land an hour apart in UTC, or the export only works on one
        # side of the change.
        thing = _thing(owner, thing_type="RESERVE_THING", headline="Sala")
        group.things.add(thing)
        _booking(
            thing,
            member,
            owner,
            code="BKGOCT",
            thing_type="RESERVE_THING",
            start=datetime.date(2026, 10, 1),
            days=1,
            start_time=datetime.time(17, 0),
            end_time=datetime.time(18, 0),
        )
        _booking(
            thing,
            member,
            owner,
            code="BKGDEC",
            thing_type="RESERVE_THING",
            start=datetime.date(2026, 12, 1),
            days=1,
            start_time=datetime.time(17, 0),
            end_time=datetime.time(18, 0),
        )

        by_uid = {e["UID"]: e for e in _events(build_calendar_export(group)[0])}

        assert by_uid["BKGOCT@oiueei"]["DTSTART"] == "20261001T150000Z"  # +2
        assert by_uid["BKGDEC@oiueei"]["DTSTART"] == "20261201T160000Z"  # +1

    def test_a_whole_day_reservation_stays_an_all_day_event(self, group, owner, member):
        # A DAY-unit reservation has start_time = NULL and must keep the
        # original all-day shape — the two code paths must not bleed together.
        thing = _thing(owner, thing_type="RESERVE_THING", headline="Sala")
        group.things.add(thing)
        _booking(
            thing,
            member,
            owner,
            thing_type="RESERVE_THING",
            start=datetime.date(2026, 9, 20),
            days=1,
        )

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DTSTART;VALUE=DATE"] == "20260920"
        assert "DTSTART" not in event  # no timed DTSTART bled in
        assert event["DTEND;VALUE=DATE"] == "20260921"  # exclusive, as ever


class TestEveryDownloadCarriesEverything:
    """The stable UID retired the incremental watermark: re-downloading after a
    failed import is the normal path now, and the calendar dedupes on its side."""

    def test_a_second_download_carries_the_same_events_not_an_empty_file(
        self, group, owner, member
    ):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        first_bytes, first_count, _ = build_calendar_export(group)
        second_bytes, second_count, _ = build_calendar_export(group)

        assert first_count == second_count == 1
        assert _events(second_bytes) == _events(first_bytes)

    def test_the_uid_is_identical_across_downloads(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        first = _events(build_calendar_export(group)[0])
        second = _events(build_calendar_export(group)[0])

        assert first[0]["UID"] == second[0]["UID"] == "BKG001@oiueei"

    def test_a_reservation_confirmed_after_a_download_ships_with_the_rest(
        self, group, owner, member
    ):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, code="BKG100")

        build_calendar_export(group)
        _booking(thing, member, owner, code="BKG101", start=TODAY + datetime.timedelta(days=20))

        _, count, _ = build_calendar_export(group)

        assert count == 2

    def test_a_thing_in_two_collections_exports_from_both(self, owner, member):
        # No watermark also means no per-collection bookkeeping to get right —
        # each collection simply ships its own reservations.
        thing = _thing(owner)
        a = Collection.objects.create(code="GRPA00", owner=owner, headline="A")
        b = Collection.objects.create(code="GRPB00", owner=owner, headline="B")
        a.things.add(thing)
        also_in(b, thing)
        _booking(thing, member, owner)

        _, a_count, _ = build_calendar_export(a)
        _, b_count, _ = build_calendar_export(b)

        assert a_count == 1
        assert b_count == 1


class TestWhoseReservationsTheFileHolds:
    """The file follows the app's rule for who sees whoever asks: a PROPRIETARY
    collection's curators see everything; in a COMMUNITY one a curator sees only
    the reservations of things they own (`Thing.can_manage` is just the owner there)."""

    @pytest.fixture
    def asker(self, db):
        return User.objects.create(code="ASK001", email="nuria@your-domain.test", name="Núria")

    def _community(self, owner, member):
        group = Collection.objects.create(
            code="COM001", owner=owner, headline="La calle", mode=Collection.Mode.COMMUNITY
        )
        group.invites.add(member)
        return group

    def test_a_community_curator_gets_their_own_things_and_not_a_members(
        self, owner, member, asker
    ):
        group = self._community(owner, member)
        mine = _thing(owner, code="THGOWN", headline="Mi taladro")
        theirs = _thing(member, code="THGMEM", headline="Su sierra")
        group.things.add(mine, theirs)
        _booking(mine, asker, owner, code="BKGOWN")
        _booking(theirs, asker, member, code="BKGMEM")

        ics, count, _ = build_calendar_export(group, user=owner)

        assert [e["UID"] for e in _events(ics)] == ["BKGOWN@oiueei"]
        assert count == 1
        assert b"Su sierra" not in ics

    def test_a_community_curator_who_owns_the_members_thing_too_sees_it(self, owner, member, asker):
        group = self._community(owner, member)
        group.co_owners.add(member)  # the member also curates
        theirs = _thing(member, code="THGMEM", headline="Su sierra")
        group.things.add(theirs)
        _booking(theirs, asker, member, code="BKGMEM")

        ics, count, _ = build_calendar_export(group, user=member)

        assert [e["UID"] for e in _events(ics)] == ["BKGMEM@oiueei"]
        assert count == 1

    def test_a_community_file_asked_for_by_nobody_holds_nothing(self, owner, member, asker):
        group = self._community(owner, member)
        mine = _thing(owner)
        group.things.add(mine)
        _booking(mine, asker, owner)

        ics, count, cancelled = build_calendar_export(group)

        assert (_events(ics), count, cancelled) == ([], 0, 0)

    def test_a_proprietary_co_curator_sees_the_reservations_of_things_another_curator_owns(
        self, group, owner, member, asker
    ):
        group.invites.add(member)
        group.co_owners.add(member)
        founders = _thing(owner, code="THGFND", headline="Del fundador")
        group.things.add(founders)
        _booking(founders, asker, owner, code="BKGFND")

        ics, count, _ = build_calendar_export(group, user=member)

        assert [e["UID"] for e in _events(ics)] == ["BKGFND@oiueei"]
        assert count == 1


class TestRfc5545Shape:
    def test_every_line_ends_crlf_and_none_is_blank(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        ics_bytes, _, _ = build_calendar_export(group)

        text = ics_bytes.decode("utf-8")
        assert "\n" not in text.replace("\r\n", "")  # no bare LF anywhere
        assert all(line for line in _physical_lines(ics_bytes))

    def test_text_values_escape_comma_semicolon_backslash_and_newline(self, group, owner, member):
        thing = _thing(
            owner,
            thing_type="RESERVE_THING",
            headline="Sala, principal; 1ª",
            location="Carrer Nou, 3; baixos",
        )
        group.things.add(thing)
        _booking(
            thing,
            member,
            owner,
            thing_type="RESERVE_THING",
            note="Línea uno\nlínea dos, con coma; y punto\\coma",
        )

        (event,) = _events(build_calendar_export(group)[0])

        assert event["SUMMARY"] == r"Sala\, principal\; 1ª — Júlia"
        assert event["LOCATION"] == r"Carrer Nou\, 3\; baixos"
        # A newline becomes literal \n in the TEXT value; commas/semicolons in
        # the note are escaped too, and the backslash itself is doubled.
        # (The default `group` fixture's language is "es" — "Proyecto:", not
        # the Catalan "Projecte:" the fixture would use with language="ca".)
        assert r"Proyecto: Línea uno\nlínea dos\, con coma\; y punto\\coma" in event["DESCRIPTION"]

    def test_a_long_accented_headline_folds_at_75_octets_and_unfolds_exactly(
        self, group, owner, member
    ):
        headline = "Bicicleta de carril boladísima ñandú camión japonés " + "éàüöß" * 12
        thing = _thing(owner, headline=headline)
        group.things.add(thing)
        _booking(thing, member, owner)

        ics_bytes, _, _ = build_calendar_export(group)

        for line in _physical_lines(ics_bytes):
            assert len(line.encode("utf-8")) <= 75, line
        # The fold never split a UTF-8 character: unfolding recovers the exact
        # headline, accents and all.
        (event,) = _events(ics_bytes)
        assert headline in event["SUMMARY"]


class TestOnlyRealCommitments:
    def test_a_pending_hold_is_not_a_calendar_event(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, status="PENDING")

        _, count, _ = build_calendar_export(group)

        assert count == 0

    @pytest.mark.parametrize("status", ["REJECTED", "CANCELLED", "EXPIRED"])
    def test_a_settled_or_dead_hold_is_not_exported(self, group, owner, member, status):
        # A loan is only ever cancelled while PENDING, so a cancelled one never
        # reached a calendar and has nothing to take back off it.
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, status=status)

        ics_bytes, count, cancelled = build_calendar_export(group)

        assert (count, cancelled) == (0, 0)
        assert _events(ics_bytes) == []

    @pytest.mark.parametrize("thing_type", ["GIFT_THING", "SELL_THING"])
    def test_a_dateless_gift_or_sale_is_never_in_the_calendar(
        self, group, owner, member, thing_type
    ):
        thing = _thing(owner, thing_type=thing_type)
        group.things.add(thing)
        BookingPeriod.objects.create(
            code="BKG050",
            thing_code=thing,
            thing_type=thing_type,
            requester_code=member,
            requester_email=member.email,
            owner_code=owner,
            status="ACCEPTED",
        )

        _, count, _ = build_calendar_export(group)

        assert count == 0

    def test_a_reservation_that_already_ended_is_dropped(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, start=TODAY - datetime.timedelta(days=10), days=3)

        _, count, _ = build_calendar_export(group)

        assert count == 0

    def test_a_reservation_in_progress_today_is_kept(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        # started before today, ends after today — "en curso"
        _booking(thing, member, owner, start=TODAY - datetime.timedelta(days=1), days=5)

        _, count, _ = build_calendar_export(group)

        assert count == 1


class TestACancelledReservationLeavesTheCalendar:
    """A calendar that imported a reservation keeps it after it is cancelled —
    the file is a copy. So the next download carries the cancellation under the
    same UID, as a revision (SEQUENCE above the confirmed copy's) with
    STATUS:CANCELLED, for the importing app to drop."""

    def test_a_confirmed_reservation_is_revision_zero_and_confirmed(self, group, owner, member):
        thing = _thing(owner, thing_type="RESERVE_THING")
        group.things.add(thing)
        _booking(thing, member, owner, code="BKG070", days=1)

        (event,) = _events(build_calendar_export(group)[0])

        assert (event["STATUS"], event["SEQUENCE"]) == ("CONFIRMED", "0")

    def test_a_cancelled_reservation_ships_as_a_cancelled_revision_of_its_event(
        self, group, owner, member
    ):
        thing = _thing(owner, thing_type="RESERVE_THING")
        group.things.add(thing)
        booking = _booking(thing, member, owner, code="BKG071", days=1)
        (confirmed,) = _events(build_calendar_export(group)[0])

        booking.status = BookingPeriod.Status.CANCELLED
        booking.save()
        ics_bytes, count, cancelled = build_calendar_export(group)
        (revision,) = _events(ics_bytes)

        assert (count, cancelled) == (0, 1)
        assert revision["UID"] == confirmed["UID"] == "BKG071@oiueei"
        assert revision["STATUS"] == "CANCELLED"
        assert int(revision["SEQUENCE"]) > int(confirmed["SEQUENCE"])
        # Same slot, so an app that matches on more than the UID still finds it.
        assert revision["DTSTART;VALUE=DATE"] == confirmed["DTSTART;VALUE=DATE"]

    def test_confirmed_and_cancelled_are_counted_apart(self, group, owner, member):
        thing = _thing(owner, thing_type="RESERVE_THING")
        group.things.add(thing)
        _booking(thing, member, owner, code="BKG072", days=1)
        _booking(
            thing,
            member,
            owner,
            code="BKG073",
            start=TODAY + datetime.timedelta(days=6),
            days=1,
            status="CANCELLED",
        )

        ics_bytes, count, cancelled = build_calendar_export(group)

        assert (count, cancelled) == (1, 1)
        by_uid = {e["UID"]: e["STATUS"] for e in _events(ics_bytes)}
        assert by_uid == {"BKG072@oiueei": "CONFIRMED", "BKG073@oiueei": "CANCELLED"}

    def test_a_cancellation_of_a_reservation_already_over_is_not_shipped(
        self, group, owner, member
    ):
        thing = _thing(owner, thing_type="RESERVE_THING")
        group.things.add(thing)
        _booking(
            thing,
            member,
            owner,
            start=TODAY - datetime.timedelta(days=10),
            days=1,
            status="CANCELLED",
        )

        ics_bytes, count, cancelled = build_calendar_export(group)

        assert (count, cancelled) == (0, 0)
        assert _events(ics_bytes) == []


class TestLanguage:
    def test_events_speak_the_collections_language(self, group, owner, member):
        group.language = "ca"
        group.save()
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DESCRIPTION"].startswith("Préstec")  # ca, not es "Préstamo"

    def test_the_downloading_curator_language_wins_over_the_group(self, group, owner, member):
        group.language = "ca"
        group.save()
        owner.language = "en"
        owner.save()
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        (event,) = _events(build_calendar_export(group, user=owner)[0])

        assert event["DESCRIPTION"].startswith("Loan")

    def test_a_localized_headline_map_resolves_to_that_language(self, group, owner, member):
        group.language = "ca"
        group.save()
        thing = _thing(owner, headline='{"es": "Taladro", "ca": "Trepant"}')
        group.things.add(thing)
        _booking(thing, member, owner)

        (event,) = _events(build_calendar_export(group)[0])

        assert "Trepant" in event["SUMMARY"]
        assert "{" not in event["SUMMARY"]

    def test_a_deployment_language_the_catalogue_lacks_falls_back_to_english(
        self, group, owner, member, settings
    ):
        settings.EMAIL_LANGUAGE = "fi"
        group.language = ""  # inherit the (unknown) deployment default
        group.save()
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        (event,) = _events(build_calendar_export(group)[0])

        assert event["DESCRIPTION"].startswith("Loan")


class TestMemberIdentity:
    def test_a_member_with_no_display_name_is_a_member_not_a_blank_or_an_email(
        self, group, owner, member
    ):
        member.name = ""
        member.save()
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        (event,) = _events(build_calendar_export(group)[0])

        assert event["SUMMARY"].endswith("un miembro")
        assert member.email not in event["SUMMARY"]


class TestTheKindOfReservationLeadsTheDescription:
    """The title is the thing and the person; what kind of reservation it is moves to
    the first words of the description, where a library holding both loans and
    rentals can still tell them apart."""

    @pytest.mark.parametrize(
        "thing_type,kind,title",
        [
            ("LEND_THING", "Préstamo", "Taladre → Júlia"),
            ("RENT_THING", "Alquiler", "Taladre → Júlia"),
            ("RESERVE_THING", "Reserva", "Taladre — Júlia"),
        ],
    )
    def test_the_kind_is_the_first_thing_in_the_description_and_not_in_the_title(
        self, group, owner, member, thing_type, kind, title
    ):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, thing_type=thing_type)

        (event,) = _events(build_calendar_export(group)[0])

        assert event["SUMMARY"] == title
        assert event["DESCRIPTION"].split(" — ")[0] == kind

    def test_a_loan_and_a_rental_of_one_thing_differ_by_their_description(
        self, group, owner, member
    ):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner, code="BKG020", thing_type="LEND_THING")
        _booking(
            thing,
            member,
            owner,
            code="BKG021",
            thing_type="RENT_THING",
            start=datetime.date(2026, 10, 14),
        )

        events = {e["UID"]: e for e in _events(build_calendar_export(group)[0])}

        assert events["BKG020@oiueei"]["SUMMARY"] == events["BKG021@oiueei"]["SUMMARY"]
        assert events["BKG020@oiueei"]["DESCRIPTION"].startswith("Préstamo")
        assert events["BKG021@oiueei"]["DESCRIPTION"].startswith("Alquiler")

    def test_the_uid_and_the_sequence_do_not_move(self, group, owner, member):
        thing = _thing(owner)
        group.things.add(thing)
        _booking(thing, member, owner)

        (event,) = _events(build_calendar_export(group)[0])

        assert event["UID"] == "BKG001@oiueei"
        assert event["SEQUENCE"] == "0"


class TestCatalogueParity:
    def test_every_language_carries_the_same_keys(self):
        reference = set(CALENDAR_TEXTS["en"])
        for lang, texts in CALENDAR_TEXTS.items():
            assert set(texts) == reference, lang

    def test_there_is_a_subject_line_for_every_date_based_type(self):
        from core.models.booking import DATE_BASED_TYPES

        for lang, texts in CALENDAR_TEXTS.items():
            for thing_type in DATE_BASED_TYPES:
                assert texts[f"subject_{thing_type}"], (lang, thing_type)

    def test_there_is_a_kind_for_every_date_based_type(self):
        from core.models.booking import DATE_BASED_TYPES

        for lang, texts in CALENDAR_TEXTS.items():
            for thing_type in DATE_BASED_TYPES:
                assert texts[f"kind_{thing_type}"], (lang, thing_type)

    def test_no_title_carries_the_kind_any_more(self):
        for lang, texts in CALENDAR_TEXTS.items():
            for key, value in texts.items():
                if key.startswith("subject_"):
                    kind = texts["kind_" + key.removeprefix("subject_")]
                    assert kind not in value, (lang, key)


def test_the_filename_is_an_ics():
    assert calendar_filename("ABC123") == "ABC123-calendar.ics"
