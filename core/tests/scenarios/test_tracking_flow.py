"""End-to-end tracking scenario: Carlos's example flow, and the 19 metrics it feeds.

Reproduces (illustrative dates) — one CREATOR (Chiara) and one GUEST who converts:

    01/01  Chiara creates a COLLECTION
    02/01  the COLLECTION invites the GUEST (who joins)
    03/01  a THING is added   (+ a second THING added and removed, to exercise both)
    01/02  the GUEST asks a FAQ about the THING
    02/02  the GUEST holds the THING (owner accepts)
    01/03  the GUEST creates their own COLLECTION  → guest→creator conversion

Events are written with `Event.log` (exactly what the view/service instrumentation
calls — that instrumentation firing on the real endpoints is covered separately in
test_events.py) at the flow's timestamps, so the temporal metrics (time-to-first-
hold, guest→creator time) and the accumulated history come out real.
"""

from datetime import datetime, timezone

import pytest
import time_machine

from core.management.commands.stats_summary import build_report, render_text
from core.models import FAQ, BookingPeriod, Collection, DailyActivity, Event, Thing, User

# Illustrative flow dates (UTC).
D = {
    "coll": datetime(2026, 1, 1, tzinfo=timezone.utc),
    "join": datetime(2026, 1, 2, tzinfo=timezone.utc),
    "thing": datetime(2026, 1, 3, tzinfo=timezone.utc),
    "faq": datetime(2026, 2, 1, tzinfo=timezone.utc),
    "hold": datetime(2026, 2, 2, tzinfo=timezone.utc),
    "convert": datetime(2026, 3, 1, tzinfo=timezone.utc),
}
AFTER_FLOW = datetime(2026, 3, 2, tzinfo=timezone.utc)


def _row(sections, title, label):
    return dict(next(s for s in sections if s["title"] == title)["rows"])[label]


def _stamp(obj, when):
    obj.created = when
    obj.save(update_fields=["created"])


def _build_flow():
    K = Event.Kind
    chiara = User.objects.create(code="CHIARA", email="chiara@x.com", name="Chiara")
    chiara.created = D["coll"].date()
    chiara.save(update_fields=["created"])
    guest = User.objects.create(code="GUEST1", email="guest@x.com", name="Guest")
    guest.created = D["join"].date()
    guest.save(update_fields=["created"])

    # 01/01 — Chiara creates a collection.
    coll = Collection.objects.create(
        code="CCOLL1", owner=chiara, headline="Chiara's", mode="COMMUNITY"
    )
    _stamp(coll, D["coll"])
    Event.log(K.USER_JOINED, actor=chiara, created=D["coll"])
    Event.log(K.COLLECTION_CREATED, actor=chiara, collection=coll, created=D["coll"])
    DailyActivity.objects.create(code="DAC101", user=chiara, date=D["coll"].date())

    # 02/01 — invite the guest; the guest joins.
    coll.invites.add(guest)
    Event.log(K.USER_JOINED, actor=guest, created=D["join"])
    Event.log(K.MEMBER_JOINED, actor=guest, collection=coll, created=D["join"])
    DailyActivity.objects.create(code="DAC102", user=chiara, date=D["join"].date())
    DailyActivity.objects.create(code="DAG102", user=guest, date=D["join"].date())

    # 03/01 — add a thing (survives), plus a second one added and removed.
    thing = Thing.objects.create(code="CTHNG1", owner=chiara, headline="Drill", type="GIFT_THING")
    _stamp(thing, D["thing"])
    coll.things.add(thing)
    Event.log(K.THING_ADDED, actor=chiara, collection=coll, thing=thing, created=D["thing"])
    Event.log(
        K.THING_ADDED,
        actor=chiara,
        collection=coll,
        thing="CTHNG2",
        thing_type="SELL_THING",
        created=D["thing"],
    )
    Event.log(
        K.THING_REMOVED, actor=chiara, thing="CTHNG2", thing_type="SELL_THING", created=D["thing"]
    )
    DailyActivity.objects.create(code="DAC103", user=chiara, date=D["thing"].date())

    # 01/02 — guest asks a FAQ.
    FAQ.objects.create(code="CFAQ01", thing=thing, questioner=guest, question="Works?")
    Event.log(K.FAQ_ASKED, actor=guest, thing=thing, created=D["faq"])
    DailyActivity.objects.create(code="DAG201", user=guest, date=D["faq"].date())

    # 02/02 — guest holds the thing; owner accepts.
    booking = BookingPeriod.objects.create(
        code="CBOOK1",
        thing_code=thing,
        thing_type="GIFT_THING",
        requester_code=guest,
        requester_email=guest.email,
        owner_code=chiara,
        status="ACCEPTED",
    )
    _stamp(booking, D["hold"])
    Event.log(
        K.HOLD_REQUESTED, actor=guest, thing=thing, thing_type="GIFT_THING", created=D["hold"]
    )
    Event.log(K.HOLD_ACCEPTED, actor=guest, thing=thing, thing_type="GIFT_THING", created=D["hold"])
    DailyActivity.objects.create(code="DAG202", user=guest, date=D["hold"].date())
    DailyActivity.objects.create(code="DAC202", user=chiara, date=D["hold"].date())

    # 01/03 — guest creates their own collection → guest becomes a creator.
    coll_b = Collection.objects.create(
        code="GCOLL1", owner=guest, headline="Guest's", mode="COMMUNITY"
    )
    _stamp(coll_b, D["convert"])
    Event.log(K.COLLECTION_CREATED, actor=guest, collection=coll_b, created=D["convert"])
    DailyActivity.objects.create(code="DAG301", user=guest, date=D["convert"].date())
    return chiara, guest, coll, thing


@pytest.mark.django_db
class TestTrackingFlow:
    def _report(self):
        _build_flow()
        with time_machine.travel(AFTER_FLOW):
            sections = build_report()
        return sections

    def test_prints_full_report(self, capsys):
        # Emits the whole report so the run log shows every metric for the flow.
        print(render_text(self._report()))
        assert "OIUEEI stats summary" in capsys.readouterr().out

    def test_population_and_conversion(self):
        s = self._report()
        # Chiara is a creator; the guest converted, so 2 creators / 0 pure guests.
        assert _row(s, "Users (real)", "Creators (own ≥1 real collection)") == 2
        assert _row(s, "Users (real)", "Guests (invited only)") == 0
        assert _row(s, "Conversion", "Guest → creator conversions") == 1
        # 02/01 join → 01/03 own collection = 58 days.
        assert _row(s, "Conversion", "Avg time guest → first collection") == "58.0d"

    def test_collections_and_things(self):
        s = self._report()
        assert _row(s, "Collections (real)", "Total") == 2
        assert _row(s, "Collections (real)", "Active (status ACTIVE)") == 2
        assert _row(s, "Collections (real)", "Avg collections per creator") == "1.0"
        # Chiara's collection has 1 guest; the guest's has none → 0.5 avg.
        assert _row(s, "Collections (real)", "Avg guests per collection") == "0.5"
        # One thing survives; the second was removed.
        assert _row(s, "Things (real)", "Total") == 1
        assert _row(s, "Things (real)", "Available (status ACTIVE)") == 1
        assert _row(s, "Things (real)", "GIFT_THING") == "1 (100%)"

    def test_history_holds_and_timing(self):
        s = self._report()
        h = "History (accumulated, from Event log)"
        assert _row(s, h, "Collections created / deleted") == "2 / 0"
        assert _row(s, h, "Things added / removed") == "2 / 1"
        assert _row(s, h, "Members joined / left") == "1 / 0"
        assert _row(s, h, "FAQs asked") == 1
        assert _row(s, h, "Holds requested / accepted") == "1 / 1"
        # 03/01 thing → 02/02 hold = 30 days; 1/1 accepted.
        assert (
            _row(s, "Holds (real, current bookings)", "Avg time from thing added → first hold")
            == "30.0d"
        )
        assert (
            _row(s, "Holds (real, current bookings)", "Success rate (accepted / requested)")
            == "100%"
        )

    def test_retention(self):
        s = self._report()
        r = "Retention (from DailyActivity)"
        # Both ended as creators, each active on 4 distinct days → both returners.
        assert _row(s, r, "Creator returns (active ≥2 days)") == "2 returned (avg 4.0 active days)"
