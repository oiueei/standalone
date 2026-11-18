"""A reminder keeps the loan going: `POST /bookings/{code}/remind-return/` after it.

A borrower who has been reminded still holds the thing, so it must not read as free to
the next person. The reminder lends it again from today — for the shortest fixed length of
the collection (7 days with none) — but only over days nobody else has asked for, and it
never touches another request. These tests pin how long, over which days, what is left
alone, and that the email names the new date.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 7)  # a Wednesday
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture(autouse=True)
def _frozen_today():
    with time_machine.travel(datetime(2026, 10, 7, 12, 0, tzinfo=UTC)):
        yield


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner():
    return User.objects.create(code="RXOWN1", email="lala6@your-domain.test", name="Lala")


@pytest.fixture
def borrower():
    return User.objects.create(code="RXBOR1", email="lele8@your-domain.test", name="Lele")


@pytest.fixture
def other():
    return User.objects.create(code="RXOTH1", email="lili6@your-domain.test", name="Lili")


def make_group(owner, borrower, other, **extra):
    group = Collection.objects.create(
        code="RXCOL1",
        owner=owner,
        headline="Tool library",
        kind=Collection.Kind.LIBRARY,
        mode=extra.pop("mode", Collection.Mode.PROPRIETARY),
        allowed_thing_types=["LEND_THING", "RENT_THING"],
        **extra,
    )
    group.invites.add(borrower, other)
    return group


def make_drill(owner, group, units=1):
    thing = Thing.objects.create(
        code="RXTHN1", owner=owner, headline="Drill", type="LEND_THING", units=units
    )
    group.things.add(thing)
    return thing


def lend(thing, requester, start, end, *, status="ACCEPTED", quantity=1):
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=requester,
        requester_email=requester.email,
        owner_code=thing.owner,
        start_date=start,
        end_date=end,
        status=status,
        quantity=quantity,
    )


def remind(user, booking):
    return client_for(user).post(f"/api/v1/bookings/{booking.code}/remind-return/")


def overdue(thing, borrower, **extra):
    return lend(thing, borrower, TODAY - timedelta(days=8), YESTERDAY, **extra)


class TestHowLongItLendsAgain:
    @pytest.mark.parametrize(
        ("durations", "days"),
        [
            pytest.param([7, 14], 7, id="a library that lends by the week"),
            pytest.param([1, 3], 1, id="a library that lends by the day"),
            pytest.param([14, 3, 7], 3, id="the shortest of several"),
            pytest.param([], 7, id="no fixed lengths"),
        ],
    )
    def test_from_today_for_the_shortest_fixed_length(
        self, owner, borrower, other, durations, days
    ):
        group = make_group(owner, borrower, other, rental_durations=durations)
        booking = overdue(make_drill(owner, group), borrower)

        response = remind(owner, booking)

        assert response.status_code == 200
        assert response.data["extended_to"] == str(TODAY + timedelta(days=days))
        assert response.data["cut_short"] is False
        booking.refresh_from_db()
        assert booking.end_date == TODAY + timedelta(days=days)

    def test_the_weekdays_and_closures_do_not_apply_it_is_the_lenders_decision(
        self, owner, borrower, other
    ):
        # Wednesday + 7 is a Wednesday, which "Mondays only" refuses for any request,
        # and the closure sits on that very day.
        group = make_group(
            owner,
            borrower,
            other,
            rental_weekdays=[0],
            closed_dates=[str(TODAY + timedelta(days=7))],
        )
        booking = overdue(make_drill(owner, group), borrower)

        response = remind(owner, booking)

        assert response.data["extended_to"] == str(TODAY + timedelta(days=7))

    def test_a_network_uses_its_own_lengths(self, owner, borrower, other):
        group = make_group(
            owner, borrower, other, mode=Collection.Mode.NETWORK, rental_durations=[3, 7]
        )
        booking = overdue(make_drill(owner, group), borrower)

        assert remind(owner, booking).data["extended_to"] == str(TODAY + timedelta(days=3))

    def test_the_old_return_date_is_what_the_email_says_was_missed(self, owner, borrower, other):
        group = make_group(owner, borrower, other)
        booking = overdue(make_drill(owner, group), borrower)

        remind(owner, booking)

        assert "was due back on 06/10/2026" in mail.outbox[0].body


class TestOnlyOverFreeDays:
    def test_another_request_in_three_days_cuts_it_to_the_day_before_their_pickup(
        self, owner, borrower, other
    ):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        later = lend(
            drill, other, TODAY + timedelta(days=3), TODAY + timedelta(days=6), status="PENDING"
        )

        response = remind(owner, booking)

        assert response.data["extended_to"] == str(TODAY + timedelta(days=3))
        assert response.data["cut_short"] is True
        booking.refresh_from_db()
        # Back on the day the next person picks it up: a handover, not a clash.
        assert booking.end_date == TODAY + timedelta(days=3)
        later.refresh_from_db()
        assert (later.start_date, later.end_date, later.status) == (
            TODAY + timedelta(days=3),
            TODAY + timedelta(days=6),
            "PENDING",
        )

    def test_a_request_for_tomorrow_leaves_one_day(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        lend(drill, other, TODAY + timedelta(days=1), TODAY + timedelta(days=4), status="PENDING")

        response = remind(owner, booking)

        assert response.data["extended_to"] == str(TODAY + timedelta(days=1))
        assert response.data["cut_short"] is True

    def test_a_request_that_already_covers_today_leaves_nothing(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        lend(drill, other, TODAY, TODAY + timedelta(days=4), status="PENDING")

        response = remind(owner, booking)

        assert response.status_code == 200
        assert response.data["extended_to"] is None
        assert response.data["cut_short"] is True
        booking.refresh_from_db()
        assert booking.end_date == YESTERDAY

    def test_the_reminder_still_goes_when_nothing_could_be_extended(self, owner, borrower, other):
        group = make_group(owner, borrower, other)
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        lend(drill, other, TODAY, TODAY + timedelta(days=4), status="PENDING")

        remind(owner, booking)

        assert len(mail.outbox) == 1
        assert "at the latest" not in mail.outbox[0].body
        booking.refresh_from_db()
        assert booking.return_reminded_at is not None

    def test_a_cancelled_request_is_no_obstacle(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        lend(drill, other, TODAY + timedelta(days=2), TODAY + timedelta(days=5), status="CANCELLED")

        assert remind(owner, booking).data["extended_to"] == str(TODAY + timedelta(days=7))

    def test_with_several_units_and_room_it_extends_whole_despite_another_request(
        self, owner, borrower, other
    ):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group, units=3)
        booking = overdue(drill, borrower)
        lend(drill, other, TODAY + timedelta(days=2), TODAY + timedelta(days=5), status="PENDING")

        response = remind(owner, booking)

        assert response.data["extended_to"] == str(TODAY + timedelta(days=7))
        assert response.data["cut_short"] is False

    def test_with_several_units_it_is_cut_where_they_run_out(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group, units=2)
        booking = overdue(drill, borrower, quantity=1)
        # One unit is free; this asks for the other one from day 2 on, and another one is
        # already asked for from day 4: from there the two units would both be out.
        lend(drill, other, TODAY + timedelta(days=2), TODAY + timedelta(days=9), status="PENDING")
        third = User.objects.create(code="RXTHI1", email="lolo3@your-domain.test", name="Lolo")
        group.invites.add(third)
        lend(drill, third, TODAY + timedelta(days=4), TODAY + timedelta(days=9), status="PENDING")

        response = remind(owner, booking)

        assert response.data["extended_to"] == str(TODAY + timedelta(days=4))
        assert response.data["cut_short"] is True

    def test_a_loan_of_several_units_weighs_what_it_holds(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group, units=3)
        booking = overdue(drill, borrower, quantity=2)
        lend(
            drill,
            other,
            TODAY + timedelta(days=2),
            TODAY + timedelta(days=5),
            status="PENDING",
            quantity=2,
        )

        # 2 held + 2 asked is 4 of 3 units from day 2: it can only run until then.
        assert remind(owner, booking).data["extended_to"] == str(TODAY + timedelta(days=2))


class TestWhatItNeverTouches:
    def test_a_second_press_finds_a_loan_that_is_no_longer_overdue_and_extends_nothing_more(
        self, owner, borrower, other
    ):
        """The reminder lent it again, so it is not waiting to be returned until the new
        date passes: the second press is the usual refusal, with no second email and no
        second extension."""
        group = make_group(owner, borrower, other, rental_durations=[3])
        booking = overdue(make_drill(owner, group), borrower)
        remind(owner, booking)
        booking.refresh_from_db()
        first_end = booking.end_date

        again = remind(owner, booking)

        assert again.status_code == 400
        assert again.data["code"] == "not_awaiting_return"
        booking.refresh_from_db()
        assert booking.end_date == first_end
        assert len(mail.outbox) == 1

    def test_when_the_new_date_has_passed_it_can_be_reminded_and_lent_again(
        self, owner, borrower, other
    ):
        group = make_group(owner, borrower, other, rental_durations=[3])
        booking = overdue(make_drill(owner, group), borrower)
        remind(owner, booking)  # now due back on the 10th

        with time_machine.travel(datetime(2026, 10, 11, 12, 0, tzinfo=UTC)):
            response = remind(owner, booking)

        assert response.status_code == 200
        assert response.data["extended_to"] == "2026-10-14"
        assert len(mail.outbox) == 2

    def test_a_refused_reminder_does_not_extend(self, owner, borrower, other):
        group = make_group(owner, borrower, other)
        drill = make_drill(owner, group)
        not_due = lend(drill, borrower, TODAY - timedelta(days=2), TODAY + timedelta(days=3))

        response = remind(owner, not_due)

        assert response.status_code == 400
        not_due.refresh_from_db()
        assert not_due.end_date == TODAY + timedelta(days=3)

    def test_somebody_who_may_not_remind_cannot_extend_it(self, owner, borrower, other):
        group = make_group(owner, borrower, other)
        booking = overdue(make_drill(owner, group), borrower)

        assert remind(other, booking).status_code == 403
        booking.refresh_from_db()
        assert booking.end_date == YESTERDAY

    def test_the_booking_is_the_only_row_written(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        bystander = lend(drill, other, date(2026, 1, 5), date(2026, 1, 9))

        remind(owner, booking)

        bystander.refresh_from_db()
        assert (bystander.start_date, bystander.end_date) == (date(2026, 1, 5), date(2026, 1, 9))


class TestTheEmailNamesTheNewDate:
    @pytest.mark.parametrize(
        ("language", "line"),
        [
            ("en", "Please bring it back by 14/10/2026 at the latest."),
            ("es", "Por favor, devuélvelo como tarde el 14/10/2026."),
            ("ca", "Si us plau, torna-ho com a molt tard el 14/10/2026."),
        ],
    )
    def test_in_the_borrowers_language_in_both_parts(self, owner, borrower, other, language, line):
        borrower.language = language
        borrower.save()
        group = make_group(owner, borrower, other, rental_durations=[7])
        booking = overdue(make_drill(owner, group), borrower)

        remind(owner, booking)

        sent = mail.outbox[0]
        assert line in sent.body
        assert line in sent.alternatives[0][0]

    def test_it_is_the_date_the_loan_now_ends_cut_short_included(self, owner, borrower, other):
        group = make_group(owner, borrower, other, rental_durations=[7])
        drill = make_drill(owner, group)
        booking = overdue(drill, borrower)
        lend(drill, other, TODAY + timedelta(days=3), TODAY + timedelta(days=6), status="PENDING")

        remind(owner, booking)

        assert "Please bring it back by 10/10/2026 at the latest." in mail.outbox[0].body
