"""A manager nudges the borrower of a loan that should already be back.

`POST /bookings/{code}/remind-return/` is the manual half of the return emails:
the daily command only speaks the day *before* a return, so whoever lent a drill
had no way to ask for it once the date had passed. What these tests pin is when
the action exists (an overdue loan, and only the thing's **last** one), who may
press it, that it cannot be pressed twice in a day, and what the borrower is
sent — and that `/owner-bookings/` says all of it per row without a query per row.
"""

from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace

import pytest
import time_machine
from django.core import mail
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, User
from core.serializers import BookingPeriodSerializer

pytestmark = pytest.mark.django_db

# A Wednesday; the whole file lives on it unless a test travels.
TODAY = date(2026, 10, 7)
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture(autouse=True)
def _frozen_today():
    # Noon, so the server's day is the same in every `DJANGO_TIME_ZONE` a
    # developer's `.env` may set.
    with time_machine.travel(datetime(2026, 10, 7, 12, 0, tzinfo=UTC)):
        yield


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def owner():
    return User.objects.create(code="RROWN1", email="lala4@your-domain.test", name="Lala")


@pytest.fixture
def borrower():
    return User.objects.create(code="RRBOR1", email="lele6@your-domain.test", name="Lele")


@pytest.fixture
def member():
    return User.objects.create(code="RRMEM1", email="lili4@your-domain.test", name="Lili")


@pytest.fixture
def co_curator():
    return User.objects.create(code="RRCOC1", email="lolo@your-domain.test", name="Lolo")


@pytest.fixture
def group(owner, borrower, member, co_curator):
    """A PROPRIETARY group: Lala founds it, Lolo co-curates, Lele and Lili are members."""
    collection = Collection.objects.create(
        code="RRCOL1", owner=owner, headline="Taller", mode=Collection.Mode.PROPRIETARY
    )
    collection.invites.add(borrower, member, co_curator)
    collection.co_owners.add(co_curator)
    return collection


@pytest.fixture
def drill(owner, group):
    thing = Thing.objects.create(code="RRTHN1", owner=owner, headline="Drill", type="LEND_THING")
    group.things.add(thing)
    return thing


def lend(thing, requester, start, end, *, status="ACCEPTED", thing_type=None):
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing_type or thing.type,
        requester_code=requester,
        requester_email=requester.email,
        owner_code=thing.owner,
        start_date=start,
        end_date=end,
        status=status,
    )


def keep_overdue(thing, other):
    """Somebody has already asked for the thing from today, so a reminder has no free day
    to lend it again over and the loan stays overdue: what the once-a-day cap is about.
    (Otherwise the reminder lends the loan again and it is no longer overdue.)"""
    return lend(thing, other, TODAY, TODAY + timedelta(days=30), status="PENDING")


def remind(user, booking):
    return client_for(user).post(f"/api/v1/bookings/{booking.code}/remind-return/")


# --- When the action exists ---------------------------------------------------


class TestWhenAReturnCanBeReminded:
    def test_it_cannot_be_on_the_return_day_itself(self, drill, borrower):
        """The day-before email has just been sent; the return day is still the borrower's."""
        due_today = lend(drill, borrower, TODAY - timedelta(days=5), TODAY)
        assert due_today.can_be_return_reminded() is False

    def test_it_can_be_from_the_day_after_the_return_date(self, drill, borrower):
        overdue = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)
        assert overdue.can_be_return_reminded() is True

    def test_a_loan_still_out_is_not_overdue(self, drill, borrower):
        out = lend(drill, borrower, YESTERDAY, TODAY + timedelta(days=3))
        assert out.can_be_return_reminded() is False

    @pytest.mark.parametrize("status", ["PENDING", "REJECTED", "CANCELLED", "EXPIRED"])
    def test_only_an_accepted_booking_was_ever_lent(self, drill, borrower, status):
        never_lent = lend(drill, borrower, TODAY - timedelta(days=9), YESTERDAY, status=status)
        assert never_lent.can_be_return_reminded() is False

    @pytest.mark.parametrize("thing_type", ["GIFT_THING", "SELL_THING", "RESERVE_THING"])
    def test_only_a_loan_or_a_rental_comes_back(self, drill, borrower, thing_type):
        """Dates are given on purpose: the type alone must keep these out."""
        gone = lend(drill, borrower, TODAY - timedelta(days=9), YESTERDAY, thing_type=thing_type)
        assert gone.can_be_return_reminded() is False

    def test_a_rental_is_remindable_like_a_loan(self, owner, borrower, group):
        saw = Thing.objects.create(code="RRTHN2", owner=owner, headline="Saw", type="RENT_THING")
        group.things.add(saw)
        overdue = lend(saw, borrower, TODAY - timedelta(days=5), YESTERDAY)
        assert overdue.can_be_return_reminded() is True

    def test_an_earlier_loan_does_not_veto_the_latest_overdue_one(self, drill, borrower, member):
        """Lent in January and returned, lent again in March and overdue: March is the
        one nobody has brought back, January is long over. Only a **later** booking
        that has started proves the thing came back."""
        january = lend(drill, member, date(2026, 1, 5), date(2026, 1, 12))
        march = lend(drill, borrower, date(2026, 3, 2), date(2026, 3, 9))

        assert march.can_be_return_reminded() is True
        assert january.can_be_return_reminded() is False

    def test_a_thing_lent_again_has_come_back(self, drill, borrower, member):
        first = lend(drill, borrower, TODAY - timedelta(days=20), TODAY - timedelta(days=10))
        lend(drill, member, TODAY - timedelta(days=4), TODAY + timedelta(days=2))

        assert first.can_be_return_reminded() is False

    def test_a_later_booking_that_has_not_started_yet_proves_nothing(self, drill, borrower, member):
        overdue = lend(drill, borrower, TODAY - timedelta(days=20), TODAY - timedelta(days=10))
        lend(drill, member, TODAY + timedelta(days=1), TODAY + timedelta(days=4))

        assert overdue.can_be_return_reminded() is True

    def test_a_later_booking_nobody_accepted_proves_nothing(self, drill, borrower, member):
        overdue = lend(drill, borrower, TODAY - timedelta(days=20), TODAY - timedelta(days=10))
        lend(drill, member, TODAY - timedelta(days=4), TODAY + timedelta(days=2), status="PENDING")

        assert overdue.can_be_return_reminded() is True


# --- The endpoint -------------------------------------------------------------


class TestRemindReturnEndpoint:
    def test_the_owner_reminds_and_the_borrower_gets_it_with_a_reply_path(
        self, drill, owner, borrower
    ):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), date(2026, 10, 5))

        response = remind(owner, booking)

        assert response.status_code == 200
        assert len(mail.outbox) == 1
        sent = mail.outbox[0]
        assert sent.to == ["lele6@your-domain.test"]
        # "Reply" reaches whoever pressed — the borrower's natural answer is
        # "I'll bring it tomorrow", and it belongs to that person.
        assert sent.reply_to == ["lala4@your-domain.test"]
        assert sent.subject == "Reminder: please return Drill"
        assert (
            "Lala is reminding you that 'Drill' was due back on 05/10/2026. "
            "If you've already returned it, you can ignore this email."
        ) in sent.body
        booking.refresh_from_db()
        assert booking.return_reminded_at is not None
        assert timezone.localdate(booking.return_reminded_at) == TODAY

    def test_the_email_names_whoever_pressed_not_the_thing_owner(
        self, drill, group, co_curator, borrower
    ):
        """A PROPRIETARY group's curators run its loans together; the borrower reads
        the person who actually pressed, and replies to them."""
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        response = remind(co_curator, booking)

        assert response.status_code == 200
        sent = mail.outbox[0]
        assert sent.reply_to == ["lolo@your-domain.test"]
        assert "Lolo is reminding you" in sent.body
        assert "Lala" not in sent.body

    def test_a_manager_with_no_name_is_a_member_in_the_sentence_not_an_address(
        self, drill, group, co_curator, borrower
    ):
        """`display_name` falls back to the email. The address reaches the borrower
        as `Reply-To` (the page says so before the press); in the sentence that
        names who is asking it would be a name nobody chose."""
        co_curator.name = ""
        co_curator.save()
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        remind(co_curator, booking)

        sent = mail.outbox[0]
        assert sent.reply_to == ["lolo@your-domain.test"]
        assert "A member is reminding you" in sent.body
        assert "lolo@your-domain.test" not in sent.body
        assert "lolo@your-domain.test" not in sent.alternatives[0][0]

    @pytest.mark.parametrize(
        ("language", "subject", "sentence"),
        [
            (
                "es",
                "Recordatorio: devolver Drill",
                "Lala te recuerda que 'Drill' tenía que volver el 06/10/2026. "
                "Si ya has hecho la devolución, puedes ignorar este correo.",
            ),
            (
                "ca",
                "Recordatori: tornar Drill",
                "Lala et recorda que 'Drill' havia de tornar el 06/10/2026. "
                "Si ja has fet la devolució, pots ignorar aquest correu.",
            ),
            (
                "en",
                "Reminder: please return Drill",
                "Lala is reminding you that 'Drill' was due back on 06/10/2026. "
                "If you've already returned it, you can ignore this email.",
            ),
        ],
    )
    def test_the_email_speaks_the_borrowers_language(
        self, drill, owner, borrower, language, subject, sentence
    ):
        borrower.language = language
        borrower.save()
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        remind(owner, booking)

        assert mail.outbox[0].subject == subject
        assert sentence in mail.outbox[0].body

    def test_the_email_carries_the_link_to_the_listing(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        remind(owner, booking)

        html = mail.outbox[0].alternatives[0][0]
        assert f"/stall/RRCOL1/things/{drill.code}" in html

    def test_another_member_may_not_nudge_somebody_elses_loan(self, drill, borrower, member):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        response = remind(member, booking)

        assert response.status_code == 403
        assert mail.outbox == []
        booking.refresh_from_db()
        assert booking.return_reminded_at is None

    def test_the_borrower_may_not_remind_themselves(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        assert remind(borrower, booking).status_code == 403
        assert mail.outbox == []

    def test_somebody_signed_out_is_turned_away(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        response = APIClient().post(f"/api/v1/bookings/{booking.code}/remind-return/")

        assert response.status_code in (401, 403)
        assert mail.outbox == []

    def test_an_unknown_booking_is_a_404(self, owner):
        response = client_for(owner).post("/api/v1/bookings/NOPE99/remind-return/")

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "make",
        [
            pytest.param(
                lambda t, b: lend(t, b, TODAY - timedelta(days=5), YESTERDAY, status="PENDING"),
                id="a request nobody accepted",
            ),
            pytest.param(
                lambda t, b: lend(
                    t, b, TODAY - timedelta(days=5), YESTERDAY, thing_type="GIFT_THING"
                ),
                id="a gift",
            ),
            pytest.param(
                lambda t, b: lend(
                    t, b, TODAY - timedelta(days=5), YESTERDAY, thing_type="RESERVE_THING"
                ),
                id="a reservation",
            ),
            pytest.param(
                lambda t, b: lend(t, b, YESTERDAY, TODAY + timedelta(days=3)),
                id="a loan not yet due",
            ),
            pytest.param(
                lambda t, b: lend(t, b, TODAY - timedelta(days=5), TODAY),
                id="a loan due today",
            ),
        ],
    )
    def test_there_is_nothing_to_remind_unless_it_is_overdue(self, drill, owner, borrower, make):
        booking = make(drill, borrower)

        response = remind(owner, booking)

        assert response.status_code == 400
        # Coded, so the page says why in the reader's language rather than its generic error.
        assert response.data["code"] == "not_awaiting_return"
        assert mail.outbox == []
        booking.refresh_from_db()
        assert booking.return_reminded_at is None

    def test_the_day_after_the_return_date_is_the_first_day_it_works(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), TODAY)
        assert remind(owner, booking).status_code == 400

        with time_machine.travel(datetime(2026, 10, 8, 12, 0, tzinfo=UTC)):
            assert remind(owner, booking).status_code == 200

        assert len(mail.outbox) == 1

    def test_a_thing_already_lent_again_has_nothing_to_remind(self, drill, owner, borrower, member):
        first = lend(drill, borrower, TODAY - timedelta(days=20), TODAY - timedelta(days=10))
        lend(drill, member, TODAY - timedelta(days=4), TODAY + timedelta(days=2))

        assert remind(owner, first).status_code == 400
        assert mail.outbox == []

    def test_only_one_reminder_a_day_and_the_second_says_why(self, drill, owner, borrower, member):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)
        keep_overdue(drill, member)
        assert remind(owner, booking).status_code == 200
        booking.refresh_from_db()
        reminded_at = booking.return_reminded_at

        again = remind(owner, booking)

        assert again.status_code == 429
        assert again.data["code"] == "already_reminded_today"
        assert len(mail.outbox) == 1
        booking.refresh_from_db()
        assert booking.return_reminded_at == reminded_at

    def test_another_manager_cannot_get_round_the_cap(
        self, drill, owner, co_curator, borrower, member
    ):
        """The cap is the booking's, not the person's: two curators pressing in turn
        would otherwise mail the same borrower twice a day."""
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)
        keep_overdue(drill, member)
        assert remind(owner, booking).status_code == 200

        again = remind(co_curator, booking)

        assert again.status_code == 429
        assert len(mail.outbox) == 1

    def test_tomorrow_it_works_again(self, drill, owner, borrower, member):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)
        keep_overdue(drill, member)
        assert remind(owner, booking).status_code == 200

        with time_machine.travel(datetime(2026, 10, 8, 12, 0, tzinfo=UTC)):
            assert remind(owner, booking).status_code == 200

        assert len(mail.outbox) == 2

    def test_a_day_is_the_calendar_day_not_twenty_four_hours(self, drill, owner, borrower, member):
        """Pressed at 23:55 and again at 00:05 are two different days; pressed at
        00:05 and again at 23:55 are the same one."""
        zone = timezone.get_current_timezone()

        def at(day, hour, minute):
            return datetime.combine(day, time(hour, minute), tzinfo=zone)

        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)
        keep_overdue(drill, member)
        with time_machine.travel(at(TODAY, 23, 55), tick=False):
            assert remind(owner, booking).status_code == 200
        with time_machine.travel(at(TODAY + timedelta(days=1), 0, 5), tick=False):
            assert remind(owner, booking).status_code == 200

        with time_machine.travel(at(TODAY + timedelta(days=1), 23, 55), tick=False):
            assert remind(owner, booking).status_code == 429
        assert len(mail.outbox) == 2

    @override_settings(
        RATELIMIT_ENABLE=True,
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "remind-return-rate-limit",
            }
        },
    )
    def test_it_is_rate_limited_per_user(self, owner, borrower, group):
        from django.core.cache import caches

        caches["default"].clear()
        bookings = []
        for n in range(31):
            thing = Thing.objects.create(
                code=f"RRTH{n:02d}", owner=owner, headline=f"Tool {n}", type="LEND_THING"
            )
            group.things.add(thing)
            bookings.append(lend(thing, borrower, TODAY - timedelta(days=5), YESTERDAY))

        statuses = [remind(owner, b) for b in bookings]

        assert [r.status_code for r in statuses[:30]] == [200] * 30
        assert statuses[30].status_code == 429
        # The hourly limit has no body to read a code from — the client says its own words.
        assert "code" not in statuses[30].data


# --- /owner-bookings/ ---------------------------------------------------------


def owner_rows(user):
    response = client_for(user).get("/api/v1/owner-bookings/")
    assert response.status_code == 200
    return {row["code"]: row for row in response.data["results"]}


class TestOwnerBookingsSaysWhereTheActionIs:
    def test_only_the_rows_that_can_be_reminded_say_so(self, owner, borrower, group):
        """One thing per row, so each answer has exactly one reason."""

        def thing(code):
            made = Thing.objects.create(code=code, owner=owner, headline=code, type="LEND_THING")
            group.things.add(made)
            return made

        overdue = lend(thing("RRTHA1"), borrower, TODAY - timedelta(days=5), YESTERDAY)
        pending = lend(
            thing("RRTHA2"), borrower, TODAY - timedelta(days=5), YESTERDAY, status="PENDING"
        )
        due_today = lend(thing("RRTHA3"), borrower, TODAY - timedelta(days=5), TODAY)
        still_out = lend(thing("RRTHA4"), borrower, YESTERDAY, TODAY + timedelta(days=3))

        rows = owner_rows(owner)

        assert rows[overdue.code]["can_remind_return"] is True
        assert rows[pending.code]["can_remind_return"] is False
        assert rows[due_today.code]["can_remind_return"] is False
        assert rows[still_out.code]["can_remind_return"] is False

    def test_an_earlier_loan_of_a_thing_lent_again_has_no_action(
        self, drill, owner, borrower, member
    ):
        january = lend(drill, member, date(2026, 1, 5), date(2026, 1, 12))
        march = lend(drill, borrower, date(2026, 3, 2), date(2026, 3, 9))

        rows = owner_rows(owner)

        assert rows[march.code]["can_remind_return"] is True
        assert rows[january.code]["can_remind_return"] is False

    def test_a_co_curator_is_offered_it_on_the_founders_things(self, drill, co_curator, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        assert owner_rows(co_curator)[booking.code]["can_remind_return"] is True

    def test_somebody_who_does_not_manage_the_thing_is_not_offered_it(
        self, drill, borrower, member
    ):
        """The list never shows such a reader this row; the field still decides for
        the reader it was asked about, not for whoever the row belongs to."""
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        data = BookingPeriodSerializer(
            booking, context={"request": SimpleNamespace(user=member)}
        ).data

        assert data["can_remind_return"] is False

    def test_no_reader_no_action(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        assert BookingPeriodSerializer(booking).data["can_remind_return"] is False

    def test_the_row_says_when_it_was_last_reminded(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)
        assert owner_rows(owner)[booking.code]["return_reminded_at"] is None

        remind(owner, booking)

        stamp = owner_rows(owner)[booking.code]["return_reminded_at"]
        assert datetime.fromisoformat(stamp).date() == TODAY

    def test_the_list_costs_the_same_queries_however_many_rows_it_has(self, group, owner, borrower):
        client = client_for(owner)
        client.get("/api/v1/auth/me/")  # settle the once-a-day activity write

        def grow(count, start):
            for n in range(start, start + count):
                thing = Thing.objects.create(
                    code=f"RRQY{n:02d}", owner=owner, headline=f"Tool {n}", type="LEND_THING"
                )
                group.things.add(thing)
                lend(thing, borrower, TODAY - timedelta(days=5), YESTERDAY)

        grow(2, 0)
        with CaptureQueriesContext(connection) as small:
            assert client.get("/api/v1/owner-bookings/").status_code == 200
        grow(4, 2)
        with CaptureQueriesContext(connection) as big:
            response = client.get("/api/v1/owner-bookings/")
        assert len(response.data["results"]) == 6

        assert len(big) == len(small), (
            f"a query per row on /owner-bookings/: {len(small)} for 2 rows, {len(big)} for 6"
        )

    def test_and_so_does_a_co_curators_list_of_somebody_elses_things(
        self, group, owner, co_curator, borrower
    ):
        """A co-curator's rows belong to the founder: `can_manage` has to walk the
        thing's collections and their curators, which must already be loaded."""
        client = client_for(co_curator)
        client.get("/api/v1/auth/me/")

        def grow(count, start):
            for n in range(start, start + count):
                thing = Thing.objects.create(
                    code=f"RRCQ{n:02d}", owner=owner, headline=f"Tool {n}", type="LEND_THING"
                )
                group.things.add(thing)
                lend(thing, borrower, TODAY - timedelta(days=5), YESTERDAY)

        grow(2, 0)
        with CaptureQueriesContext(connection) as small:
            assert client.get("/api/v1/owner-bookings/").status_code == 200
        grow(4, 2)
        with CaptureQueriesContext(connection) as big:
            response = client.get("/api/v1/owner-bookings/")
        assert len(response.data["results"]) == 6
        assert all(row["can_remind_return"] for row in response.data["results"])

        assert len(big) == len(small), (
            f"a query per row for a co-curator: {len(small)} for 2 rows, {len(big)} for 6"
        )
