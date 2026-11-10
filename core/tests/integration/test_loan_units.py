"""A loan or a rental with several identical units: a request holds ``quantity`` of them.

One rule of "full" (``saturated_periods``, weighed by each booking's ``quantity`` and told
how many more are wanted with ``need``) is what a request is judged by, what the calendar
serves the browser and what the live availability reads. With every quantity at 1 it is
what it always was — ``hourlyGridParity.json`` and the rest of the suite are that proof —
so these tests are about what changes: who gets in, what is served, and what the
people involved are told.
"""

from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from django.core import mail
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, ThingTransfer, User
from core.models.booking import saturated_periods
from core.services.calendar_export_service import build_calendar_export

pytestmark = pytest.mark.django_db

REQUEST_URL = "/api/v1/things/{}/request/"
CALENDAR_URL = "/api/v1/things/{}/calendar/"
START = date.today() + timedelta(days=10)
END = START + timedelta(days=4)


def _as(api_client, who):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(who).access_token}")
    return api_client


@pytest.fixture
def library(db, user):
    """A library holding one loan with six identical units; three members."""
    collection = Collection.objects.create(
        code="LUNLB1",
        owner=user,
        headline="Library",
        status="ACTIVE",
        mode=Collection.Mode.PROPRIETARY,
        kind="LIBRARY",
        allowed_thing_types=["LEND_THING", "RENT_THING"],
    )
    thing = Thing.objects.create(
        code="LUNTH1",
        type=Thing.Type.LEND_THING,
        owner=user,
        headline="Arduino kit",
        units=6,
        fee=None,
    )
    collection.things.add(thing)
    people = [
        User.objects.create(code=f"LUN{n:03d}", email=f"lun{n}@your-domain.test", name=f"Lun{n}")
        for n in (1, 2, 3)
    ]
    collection.invites.add(*people)
    return collection, thing, people


def _ask(api_client, who, thing, collection, quantity=None, start=START, end=END):
    body = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "collection_code": collection.code,
    }
    if quantity is not None:
        body["quantity"] = quantity
    return _as(api_client, who).post(REQUEST_URL.format(thing.code), body, format="json")


def _row(start, end, quantity=1, start_time=None, end_time=None):
    return SimpleNamespace(
        start_date=start,
        end_date=end,
        start_time=start_time,
        end_time=end_time,
        quantity=quantity,
        status="ACCEPTED",
    )


class TestWeighedSaturatedPeriods:
    d = date(2026, 6, 1)

    def test_a_booking_counts_as_many_as_its_quantity(self):
        rows = [_row(self.d, self.d + timedelta(days=2), quantity=4)]

        # 4 of 6 are on: one more fits, three more do not.
        assert saturated_periods(rows, 6, need=1) == []
        full = saturated_periods(rows, 6, need=3)
        assert [(p.start_date, p.end_date) for p in full] == [(self.d, self.d + timedelta(days=2))]

    def test_the_need_is_how_many_more_are_wanted(self):
        rows = [_row(self.d, self.d + timedelta(days=1), quantity=3)]

        assert saturated_periods(rows, 6, need=3) == []
        assert len(saturated_periods(rows, 6, need=4)) == 1

    def test_weights_add_up_across_bookings_on_the_same_day(self):
        rows = [
            _row(self.d, self.d + timedelta(days=3), quantity=2),
            _row(self.d + timedelta(days=1), self.d + timedelta(days=2), quantity=3),
        ]

        # Day 1 has 5 of 6 on: only that day is full for a request of 2.
        full = saturated_periods(rows, 6, need=2)
        assert [(p.start_date, p.end_date) for p in full] == [
            (self.d + timedelta(days=1), self.d + timedelta(days=2))
        ]

    def test_with_every_quantity_one_and_need_one_it_is_units_at_once(self):
        rows = [_row(self.d, self.d + timedelta(days=2)), _row(self.d, self.d + timedelta(days=1))]

        full = saturated_periods(rows, 2, need=1)

        assert [(p.start_date, p.end_date) for p in full] == [(self.d, self.d + timedelta(days=1))]

    def test_an_hourly_booking_is_weighed_too(self):
        rows = [_row(self.d, self.d + timedelta(days=1), 3, time(10), time(12))]

        assert saturated_periods(rows, 4, need=2)[0].start_time == time(10)
        assert saturated_periods(rows, 4, need=1) == []

    def test_a_stretch_stays_one_while_more_start_and_one_ends_above_the_threshold(self):
        """Two units: three hourly slots overlap, the second and third starting while it is
        already full and the second ending while it still is. The full stretch is one,
        from when the second came in to when the others end."""
        day, nxt = self.d, self.d + timedelta(days=1)
        rows = [
            _row(day, nxt, 1, time(10), time(12)),
            _row(day, nxt, 1, time(10, 30), time(11, 30)),
            _row(day, nxt, 1, time(11), time(12)),
        ]

        full = saturated_periods(rows, 2, need=1)

        assert [(p.start_time, p.end_time) for p in full] == [(time(10, 30), time(12))]

    def test_a_booking_without_dates_does_not_hide_the_ones_after_it(self):
        """A held gift has no dates; the dated bookings listed after it still count."""
        rows = [
            _row(None, None),
            _row(self.d, self.d + timedelta(days=1)),
            _row(self.d, self.d + timedelta(days=1)),
        ]

        full = saturated_periods(rows, 2, need=1)

        assert [(p.start_date, p.end_date) for p in full] == [(self.d, self.d + timedelta(days=1))]


class TestLoweringTheUnitsBelowWhatIsRequested:
    def test_a_pending_request_of_three_keeps_a_library_thing_from_dropping_to_two(
        self, api_client, library, user
    ):
        collection, thing, (a, _, _) = library
        Thing.objects.filter(pk=thing.pk).update(units=4)
        assert _ask(api_client, a, thing, collection, quantity=3).status_code == 201

        res = _as(api_client, user).patch(
            f"/api/v1/things/{thing.code}/", {"units": 2}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "units_below_booked"
        assert res.json()["params"] == {"min": 3}
        thing.refresh_from_db()
        assert thing.units == 4

    def test_overlapping_requests_of_three_and_two_say_five_is_the_least(
        self, api_client, library, user
    ):
        collection, thing, (a, b, _) = library
        assert _ask(api_client, a, thing, collection, quantity=3).status_code == 201
        assert _ask(api_client, b, thing, collection, quantity=2).status_code == 201

        res = _as(api_client, user).patch(
            f"/api/v1/things/{thing.code}/", {"units": 1}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "units_below_booked"
        assert res.json()["params"] == {"min": 5}
        thing.refresh_from_db()
        assert thing.units == 6


class TestAskingForSeveral:
    def test_the_quantity_is_stored_and_answered(self, api_client, library):
        collection, thing, (a, _, _) = library

        res = _ask(api_client, a, thing, collection, quantity=4)

        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["quantity"] == 4
        assert BookingPeriod.objects.get(code=res.data["booking_code"]).quantity == 4

    def test_without_saying_it_is_one(self, api_client, library):
        collection, thing, (a, _, _) = library

        res = _ask(api_client, a, thing, collection)

        assert BookingPeriod.objects.get(code=res.data["booking_code"]).quantity == 1

    def test_the_second_person_gets_in_only_while_enough_remain(self, api_client, library):
        collection, thing, (a, b, c) = library
        assert _ask(api_client, a, thing, collection, quantity=4).status_code == 201

        refused = _ask(api_client, b, thing, collection, quantity=3)

        assert refused.status_code == status.HTTP_409_CONFLICT
        assert refused.data["code"] == "not_enough_units"
        assert refused.data["params"] == {"count": 3}
        assert _ask(api_client, b, thing, collection, quantity=2).status_code == 201
        assert _ask(api_client, c, thing, collection, quantity=1).status_code == 409

    def test_one_live_request_per_person_on_the_same_dates(self, api_client, library):
        collection, thing, (a, _, _) = library
        assert _ask(api_client, a, thing, collection, quantity=2).status_code == 201

        again = _ask(api_client, a, thing, collection, quantity=1)

        assert again.status_code == status.HTTP_409_CONFLICT
        assert again.data["code"] == "loan_one_per_person"

    def test_the_same_person_can_ask_again_for_other_dates(self, api_client, library):
        collection, thing, (a, _, _) = library
        _ask(api_client, a, thing, collection, quantity=2)

        later = _ask(
            api_client, a, thing, collection, quantity=2, start=END, end=END + timedelta(days=2)
        )

        assert later.status_code == 201, later.data
        assert BookingPeriod.objects.get(code=later.data["booking_code"]).quantity == 2

    def test_a_cancelled_request_frees_its_units_and_the_person(self, api_client, library):
        collection, thing, (a, b, _) = library
        first = _ask(api_client, a, thing, collection, quantity=5)
        BookingPeriod.objects.filter(code=first.data["booking_code"]).update(
            status=BookingPeriod.Status.CANCELLED
        )

        freed = _ask(api_client, b, thing, collection, quantity=6)
        assert freed.status_code == 201
        assert BookingPeriod.objects.get(code=freed.data["booking_code"]).quantity == 6
        # A cancelled one does not count as "already asked" either.
        BookingPeriod.objects.filter(requester_code=b).delete()
        again = _ask(api_client, a, thing, collection, quantity=6)
        assert again.status_code == 201
        assert BookingPeriod.objects.get(code=again.data["booking_code"]).quantity == 6

    @pytest.mark.parametrize("quantity", [0, 7, -1])
    def test_outside_one_to_the_units_is_refused_with_the_limit(
        self, api_client, library, quantity
    ):
        collection, thing, (a, _, _) = library

        res = _ask(api_client, a, thing, collection, quantity=quantity)

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "quantity_invalid"
        assert res.data["params"] == {"max": 6}
        assert not BookingPeriod.objects.exists()

    def test_a_thing_with_one_unit_takes_only_one(self, api_client, library):
        collection, thing, (a, _, _) = library
        Thing.objects.filter(pk=thing.pk).update(units=1)

        res = _ask(api_client, a, thing, collection, quantity=2)

        assert res.status_code == 400
        assert res.data["code"] == "quantity_invalid"
        assert res.data["params"] == {"max": 1}

    def test_a_thing_with_one_unit_still_answers_taken_dates_as_before(self, api_client, library):
        collection, thing, (a, b, _) = library
        Thing.objects.filter(pk=thing.pk).update(units=1)
        assert _ask(api_client, a, thing, collection).status_code == 201

        res = _ask(api_client, b, thing, collection)

        assert res.status_code == 409
        assert res.data["code"] == "dates_taken"

    def test_a_reservation_takes_one_space_whatever_it_says(self, api_client, user, library):
        collection, _, (a, _, _) = library
        shed = Collection.objects.create(
            code="LUNSH1",
            owner=user,
            headline="Shed",
            kind="SHED",
            allowed_thing_types=["RESERVE_THING"],
            reservation_max_days=3,
        )
        space = Thing.objects.create(
            code="LUNSP1", type=Thing.Type.RESERVE_THING, owner=user, headline="Lathe", units=4
        )
        shed.things.add(space)
        shed.invites.add(a)

        res = _as(api_client, a).post(
            REQUEST_URL.format(space.code),
            {
                "start_date": START.isoformat(),
                "duration_days": 1,
                "quantity": 2,
                "collection_code": shed.code,
            },
            format="json",
        )

        assert res.status_code == 400
        assert res.data["code"] == "quantity_invalid"
        assert not BookingPeriod.objects.exists()

    def test_a_gift_takes_one_whatever_it_says(self, api_client, user, library):
        _, _, (a, _, _) = library
        stall = Collection.objects.create(code="LUNST1", owner=user, headline="Stall")
        gift = Thing.objects.create(
            code="LUNGF1", type=Thing.Type.GIFT_THING, owner=user, headline="Chair"
        )
        stall.things.add(gift)
        stall.invites.add(a)

        res = _as(api_client, a).post(
            REQUEST_URL.format(gift.code),
            {"quantity": 3, "collection_code": stall.code},
            format="json",
        )

        assert res.status_code == 400
        assert res.data["code"] == "quantity_invalid"

    def test_naming_one_on_a_gift_is_harmless(self, api_client, user, library):
        _, _, (a, _, _) = library
        stall = Collection.objects.create(code="LUNST2", owner=user, headline="Stall")
        gift = Thing.objects.create(
            code="LUNGF2", type=Thing.Type.GIFT_THING, owner=user, headline="Chair"
        )
        stall.things.add(gift)
        stall.invites.add(a)

        res = _as(api_client, a).post(
            REQUEST_URL.format(gift.code),
            {"quantity": 1, "collection_code": stall.code},
            format="json",
        )

        assert res.status_code == 201, res.data


class TestTheCalendarForWhoAsks:
    def _hold(self, thing, person, quantity, owner):
        return BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=person,
            requester_email=person.email,
            owner_code=owner,
            start_date=START,
            end_date=END,
            quantity=quantity,
            status=BookingPeriod.Status.ACCEPTED,
        )

    def test_the_days_with_fewer_free_than_asked_come_back_as_taken(
        self, api_client, user, library
    ):
        collection, thing, (a, b, _) = library
        self._hold(thing, a, 4, user)

        three = _as(api_client, b).get(CALENDAR_URL.format(thing.code) + "?quantity=3").json()
        one = _as(api_client, b).get(CALENDAR_URL.format(thing.code) + "?quantity=1").json()
        none = _as(api_client, b).get(CALENDAR_URL.format(thing.code)).json()

        assert [(r["start_date"], r["end_date"]) for r in three] == [
            (START.isoformat(), END.isoformat())
        ]
        assert one == []
        assert none == []

    def test_a_quantity_outside_the_units_is_read_as_one(self, api_client, user, library):
        collection, thing, (a, b, _) = library
        self._hold(thing, a, 6, user)

        for odd in ("0", "99", "x", "-2"):
            res = _as(api_client, library[2][2]).get(
                CALENDAR_URL.format(thing.code) + f"?quantity={odd}"
            )
            assert res.status_code == 200

        # With all six held, a request for one is already taken: reading 99 as 1
        # gives the same stretch, not an error and not an empty calendar.
        served = _as(api_client, library[2][2]).get(
            CALENDAR_URL.format(thing.code) + "?quantity=99"
        )
        assert len(served.json()) == 1

    def test_the_manager_sees_the_bookings_with_their_quantity(self, api_client, user, library):
        collection, thing, (a, _, _) = library
        self._hold(thing, a, 4, user)

        rows = _as(api_client, user).get(CALENDAR_URL.format(thing.code)).json()

        assert rows[0]["quantity"] == 4
        assert rows[0]["requester_name"] == "Lun1"

    def test_a_reservation_calendar_ignores_the_quantity(self, api_client, user, library):
        _, _, (a, _, _) = library
        shed = Collection.objects.create(
            code="LUNSH2",
            owner=user,
            headline="Shed",
            kind="SHED",
            allowed_thing_types=["RESERVE_THING"],
        )
        space = Thing.objects.create(
            code="LUNSP2", type=Thing.Type.RESERVE_THING, owner=user, headline="Lathe", units=4
        )
        shed.things.add(space)
        shed.invites.add(a)
        BookingPeriod.objects.create(
            thing_code=space,
            thing_type=space.type,
            requester_code=user,
            requester_email=user.email,
            owner_code=user,
            start_date=START,
            end_date=END,
            status=BookingPeriod.Status.ACCEPTED,
        )

        res = _as(api_client, a).get(CALENDAR_URL.format(space.code) + "?quantity=4")

        assert res.json() == []


class TestHowManyAreFreeToday:
    def _hold(self, thing, person, owner, quantity, start, end):
        return BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=person,
            requester_email=person.email,
            owner_code=owner,
            start_date=start,
            end_date=end,
            quantity=quantity,
            status=BookingPeriod.Status.ACCEPTED,
        )

    def test_it_counts_what_is_out_today(self, api_client, user, library):
        collection, thing, (a, b, _) = library
        today = date.today()
        self._hold(thing, a, user, 4, today - timedelta(days=1), today + timedelta(days=2))
        self._hold(thing, b, user, 1, today, today + timedelta(days=1))
        # Back today: free again. Starting tomorrow: not out yet.
        self._hold(thing, a, user, 1, today - timedelta(days=3), today)
        self._hold(thing, b, user, 2, today + timedelta(days=1), today + timedelta(days=3))

        res = _as(api_client, user).get(f"/api/v1/things/{thing.code}/")

        assert res.data["units"] == 6
        assert res.data["units_free_today"] == 1

    def test_two_units_are_counted_too(self, api_client, user, library):
        collection, thing, (a, _, _) = library
        Thing.objects.filter(pk=thing.pk).update(units=2)
        thing.refresh_from_db()
        today = date.today()
        self._hold(thing, a, user, 1, today - timedelta(days=1), today + timedelta(days=2))

        assert thing.units_free_today() == 1

    def test_a_pause_that_has_since_ended_still_leaves_none_on_a_day_inside_it(
        self, api_client, user, library
    ):
        collection, thing, _ = library
        today = date.today()
        inside = today - timedelta(days=3)
        Thing.objects.filter(pk=thing.pk).update(
            paused_from=inside - timedelta(days=1), paused_until=today - timedelta(days=1)
        )
        thing.refresh_from_db()

        assert thing.units_free_today(inside) == 0
        assert thing.units_free_today(today) == 6

    def test_all_free_when_nothing_is_out(self, api_client, user, library):
        _, thing, _ = library

        res = _as(api_client, user).get(f"/api/v1/things/{thing.code}/")

        assert res.data["units_free_today"] == 6

    def test_it_is_never_below_zero(self, library, user):
        _, thing, (a, b, _) = library
        today = date.today()
        self._hold(thing, a, user, 6, today, today + timedelta(days=1))
        # Units lowered after the fact below what is already lent out.
        Thing.objects.filter(pk=thing.pk).update(units=3)
        thing.refresh_from_db()

        assert thing.units_free_today() == 0

    def test_a_pause_in_force_leaves_none(self, api_client, user, library):
        _, thing, _ = library
        Thing.objects.filter(pk=thing.pk).update(
            paused_from=date.today(), paused_until=date.today() + timedelta(days=3)
        )

        res = _as(api_client, user).get(f"/api/v1/things/{thing.code}/")

        assert res.data["units_free_today"] == 0

    def test_it_says_nothing_for_one_unit_or_for_what_is_not_carried_away(
        self, api_client, user, library
    ):
        collection, thing, _ = library
        Thing.objects.filter(pk=thing.pk).update(units=1)
        res = _as(api_client, user).get(f"/api/v1/things/{thing.code}/")
        assert res.data["units_free_today"] is None

        shed = Collection.objects.create(
            code="LUNSH3",
            owner=user,
            headline="Shed",
            kind="SHED",
            allowed_thing_types=["RESERVE_THING"],
        )
        space = Thing.objects.create(
            code="LUNSP3", type=Thing.Type.RESERVE_THING, owner=user, headline="Lathe", units=4
        )
        shed.things.add(space)
        assert (
            _as(api_client, user).get(f"/api/v1/things/{space.code}/").data["units_free_today"]
            is None
        )

    def test_the_collection_card_carries_it_too(self, api_client, user, library):
        collection, thing, _ = library

        res = _as(api_client, user).get(f"/api/v1/collections/{collection.code}/")

        card = next(t for t in res.data["things"] if t["code"] == thing.code)
        assert card["units_free_today"] == 6


class TestWhatTheyAreTold:
    def test_the_managers_and_the_requester_read_the_quantity_in_the_title(
        self, api_client, library
    ):
        collection, thing, (a, _, _) = library
        mail.outbox.clear()

        res = _ask(api_client, a, thing, collection, quantity=4)

        assert res.status_code == 201
        assert len(mail.outbox) == 2
        for message in mail.outbox:
            assert "4 × Arduino kit" in message.body
            assert "4 × Arduino kit" in message.alternatives[0][0]

    def test_a_single_one_is_named_as_before(self, api_client, library):
        collection, thing, (a, _, _) = library
        mail.outbox.clear()

        _ask(api_client, a, thing, collection, quantity=1)

        for message in mail.outbox:
            assert "×" not in message.body

    def test_the_inbox_notice_carries_the_quantity_only_when_it_is_more_than_one(
        self, api_client, user, library
    ):
        collection, thing, (a, b, _) = library
        _ask(api_client, a, thing, collection, quantity=4)
        _ask(api_client, b, thing, collection, quantity=1)

        payloads = [n.payload for n in user.inbox_notifications.filter(type="BOOKING_REQUESTED")]

        by_name = {p["requester_name"]: p for p in payloads}
        assert by_name["Lun1"]["quantity"] == 4
        assert "quantity" not in by_name["Lun2"]

    def test_the_decision_notices_carry_it_for_the_requester_and_the_rest_of_the_team(
        self, api_client, user, library
    ):
        collection, thing, (a, b, _) = library
        collection.co_owners.add(b)
        booking = BookingPeriod.objects.get(
            code=_ask(api_client, a, thing, collection, quantity=3).data["booking_code"]
        )

        _as(api_client, user).post(f"/api/v1/bookings/{booking.code}/accept/")

        told_requester = a.inbox_notifications.get(type="BOOKING_ACCEPTED").payload
        told_team = b.inbox_notifications.get(type="BOOKING_DECIDED").payload
        assert told_requester["quantity"] == 3
        assert told_team["quantity"] == 3

    def test_my_requests_and_requests_to_me_list_it(self, api_client, user, library):
        collection, thing, (a, _, _) = library
        _ask(api_client, a, thing, collection, quantity=4)

        mine = _as(api_client, a).get("/api/v1/my-bookings/").json()["results"]
        theirs = _as(api_client, user).get("/api/v1/owner-bookings/").json()["results"]

        assert mine[0]["quantity"] == 4
        assert theirs[0]["quantity"] == 4

    def test_the_decision_and_the_reminder_name_the_quantity(self, api_client, user, library):
        collection, thing, (a, _, _) = library
        booking = BookingPeriod.objects.get(
            code=_ask(api_client, a, thing, collection, quantity=3).data["booking_code"]
        )
        mail.outbox.clear()

        _as(api_client, user).post(f"/api/v1/bookings/{booking.code}/accept/")

        assert mail.outbox
        assert "3 × Arduino kit" in mail.outbox[0].body

        from core.services import email_service

        mail.outbox.clear()
        email_service.send_return_due_email("Lala", thing, END, a.email, quantity=3)
        email_service.send_pickup_due_email("Lala", thing, START, a.email, quantity=3)
        email_service.send_return_reminder_email("Lun1", thing, END, user.email, quantity=3)
        email_service.send_pickup_reminder_email("Lun1", thing, START, user.email, quantity=3)
        email_service.send_return_overdue_email(user, thing, END, a.email, quantity=3)
        assert len(mail.outbox) == 5
        assert all("3 × Arduino kit" in m.body for m in mail.outbox)

    def test_the_calendar_file_names_the_quantity(self, user, library):
        collection, thing, (a, _, _) = library
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=a,
            requester_email=a.email,
            owner_code=user,
            start_date=START,
            end_date=END,
            quantity=4,
            status=BookingPeriod.Status.ACCEPTED,
        )

        ics, count, _ = build_calendar_export(collection, user)

        assert count == 1
        assert "SUMMARY:4 × Arduino kit" in ics.decode().replace("\r\n ", "")

    def test_the_account_copy_lists_it(self, user, library):
        from core.services.export_service import build_account_export

        collection, thing, (a, _, _) = library
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=a,
            requester_email=a.email,
            owner_code=user,
            start_date=START,
            end_date=END,
            quantity=4,
            status=BookingPeriod.Status.ACCEPTED,
        )

        assert build_account_export(a)["bookings"]["requested_by_me"][0]["quantity"] == 4


class TestTheJourneyOfSeveral:
    def test_no_current_holder_when_there_are_several_units(self, api_client, user, library):
        _, thing, (a, _, _) = library
        ThingTransfer.objects.create(thing=thing, from_user=user, to_user=a, lent_date=date.today())

        data = _as(api_client, user).get(f"/api/v1/things/{thing.code}/transfers/").json()

        assert data["current_holder"] is None
        assert data["current_holder_name"] is None
        assert data["total_transfers"] == 1

    def test_one_unit_still_names_its_holder(self, api_client, user, library):
        _, thing, (a, _, _) = library
        Thing.objects.filter(pk=thing.pk).update(units=1)
        ThingTransfer.objects.create(thing=thing, from_user=user, to_user=a, lent_date=date.today())

        data = _as(api_client, user).get(f"/api/v1/things/{thing.code}/transfers/").json()

        assert data["current_holder"] == a.code


def test_the_column_has_a_database_default_for_the_previous_release():
    field = BookingPeriod._meta.get_field("quantity")

    assert field.default == 1
    assert field.db_default == 1
