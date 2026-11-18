"""A manager says a loan came back: `POST /bookings/{code}/returned/`.

OIUEEI used to know a loan was over only because its date passed. What these tests pin
is when the action exists (an ACCEPTED loan or rental that has started and was not
marked before), who may press it (the thing's managers, and in a network its owner
alone), what it writes (the moment, a shorter loan when it came back early, a real
return date on the journey) and what it leaves free for the next request.
"""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
import time_machine
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import BookingPeriod, Collection, Thing, ThingTransfer, User
from core.serializers import BookingPeriodSerializer

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 7)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


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
    return User.objects.create(code="RTOWN1", email="lala5@your-domain.test", name="Lala")


@pytest.fixture
def borrower():
    return User.objects.create(code="RTBOR1", email="lele7@your-domain.test", name="Lele")


@pytest.fixture
def member():
    return User.objects.create(code="RTMEM1", email="lili5@your-domain.test", name="Lili")


@pytest.fixture
def co_curator():
    return User.objects.create(code="RTCOC1", email="lolo2@your-domain.test", name="Lolo")


@pytest.fixture
def group(owner, borrower, member, co_curator):
    collection = Collection.objects.create(
        code="RTCOL1",
        owner=owner,
        headline="Tool library",
        kind=Collection.Kind.LIBRARY,
        mode=Collection.Mode.PROPRIETARY,
        allowed_thing_types=["LEND_THING", "RENT_THING"],
    )
    collection.invites.add(borrower, member, co_curator)
    collection.co_owners.add(co_curator)
    return collection


@pytest.fixture
def drill(owner, group):
    thing = Thing.objects.create(code="RTTHN1", owner=owner, headline="Drill", type="LEND_THING")
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


def returned(user, booking):
    return client_for(user).post(f"/api/v1/bookings/{booking.code}/returned/")


def serialized(user, booking):
    request = SimpleNamespace(user=user)
    return BookingPeriodSerializer(booking, context={"request": request}).data


class TestMarkingAReturn:
    def test_the_manager_marks_it_and_it_is_kept(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        response = returned(owner, booking)

        assert response.status_code == 200
        booking.refresh_from_db()
        assert booking.returned_at is not None
        assert booking.returned_at.astimezone(UTC).date() == TODAY
        assert response.data["returned_at"] == booking.returned_at
        assert response.data["end_date"] == YESTERDAY

    def test_a_co_curator_of_a_proprietary_group_may_too(self, drill, co_curator, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        assert returned(co_curator, booking).status_code == 200

    def test_a_late_return_keeps_its_end_date(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=9), TODAY - timedelta(days=3))

        returned(owner, booking)

        booking.refresh_from_db()
        assert booking.end_date == TODAY - timedelta(days=3)

    def test_a_loan_back_on_its_last_day_keeps_its_end_date(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=3), TODAY)

        returned(owner, booking)

        booking.refresh_from_db()
        assert booking.end_date == TODAY

    def test_a_rental_is_marked_like_a_loan(self, owner, borrower, group):
        saw = Thing.objects.create(code="RTTHN2", owner=owner, headline="Saw", type="RENT_THING")
        group.things.add(saw)
        booking = lend(saw, borrower, TODAY - timedelta(days=2), TOMORROW)

        assert returned(owner, booking).status_code == 200

    def test_marking_does_not_email_anybody(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=5), YESTERDAY)

        returned(owner, booking)

        assert mail.outbox == []


class TestAnEarlyReturnFreesTheThing:
    def test_it_ends_the_loan_today(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=2), TODAY + timedelta(days=5))

        response = returned(owner, booking)

        assert response.status_code == 200
        booking.refresh_from_db()
        assert booking.end_date == TODAY
        assert response.data["end_date"] == TODAY

    def test_the_next_request_for_tomorrow_goes_in(self, drill, owner, borrower, member):
        lend(drill, borrower, TODAY - timedelta(days=2), TODAY + timedelta(days=5))
        booking = BookingPeriod.objects.get()
        ask = {
            "start_date": str(TOMORROW),
            "end_date": str(TOMORROW + timedelta(days=2)),
            "collection_code": "RTCOL1",
        }

        refused = client_for(member).post(
            f"/api/v1/things/{drill.code}/request/", ask, format="json"
        )
        returned(owner, booking)
        accepted = client_for(member).post(
            f"/api/v1/things/{drill.code}/request/", ask, format="json"
        )

        assert refused.status_code == 409
        assert accepted.status_code in (200, 201)

    def test_the_return_day_itself_is_a_handover_not_a_clash(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=2), TODAY + timedelta(days=5))
        returned(owner, booking)

        assert BookingPeriod.has_overlap(drill, TODAY, TOMORROW) is False
        assert BookingPeriod.has_overlap(drill, TODAY - timedelta(days=1), TODAY) is True


class TestTheJourney:
    def _transfer(self, booking, **extra):
        return ThingTransfer.objects.create(
            thing=booking.thing_code,
            from_user=booking.owner_code,
            to_user=booking.requester_code,
            booking=booking,
            lent_date=booking.start_date,
            **extra,
        )

    def test_a_transfer_still_open_gets_the_real_date(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TODAY + timedelta(days=3))
        transfer = self._transfer(booking)

        returned(owner, booking)

        transfer.refresh_from_db()
        assert transfer.returned_date == TODAY
        assert transfer.auto_closed is False

    def test_one_the_daily_command_closed_as_due_back_is_now_confirmed(
        self, drill, owner, borrower
    ):
        booking = lend(drill, borrower, TODAY - timedelta(days=9), TODAY - timedelta(days=3))
        transfer = self._transfer(
            booking, returned_date=TODAY - timedelta(days=2), auto_closed=True
        )

        returned(owner, booking)

        transfer.refresh_from_db()
        assert transfer.auto_closed is False
        assert transfer.returned_date == TODAY

    def test_a_loan_with_no_transfer_is_still_marked(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        assert returned(owner, booking).status_code == 200
        assert ThingTransfer.objects.count() == 0

    def test_only_this_loans_transfer_is_touched(self, drill, owner, borrower, member):
        earlier = lend(drill, member, TODAY - timedelta(days=30), TODAY - timedelta(days=20))
        old = self._transfer(earlier, returned_date=TODAY - timedelta(days=20), auto_closed=True)
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)
        self._transfer(booking)

        returned(owner, booking)

        old.refresh_from_db()
        assert old.returned_date == TODAY - timedelta(days=20)
        assert old.auto_closed is True


class TestWhoMayPress:
    def test_the_borrower_may_not(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        response = returned(borrower, booking)

        assert response.status_code == 403
        assert response.data["code"] == "not_allowed"
        booking.refresh_from_db()
        assert booking.returned_at is None

    def test_another_member_may_not(self, drill, borrower, member):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        assert returned(member, booking).status_code == 403

    def test_somebody_signed_out_is_turned_away(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        response = APIClient().post(f"/api/v1/bookings/{booking.code}/returned/")

        assert response.status_code in (401, 403)
        booking.refresh_from_db()
        assert booking.returned_at is None

    def test_an_unknown_booking_is_a_404(self, owner):
        assert client_for(owner).post("/api/v1/bookings/NOPE00/returned/").status_code == 404

    def test_in_a_network_the_founder_does_not_mark_another_dinamizadors_loan(
        self, owner, borrower, co_curator
    ):
        network = Collection.objects.create(
            code="RTNET1",
            owner=owner,
            headline="Network",
            kind=Collection.Kind.LIBRARY,
            mode=Collection.Mode.NETWORK,
            allowed_thing_types=["LEND_THING", "RENT_THING"],
        )
        network.invites.add(borrower, co_curator)
        network.co_owners.add(co_curator)
        theirs = Thing.objects.create(
            code="RTTHN3", owner=co_curator, headline="Ladder", type="LEND_THING"
        )
        network.things.add(theirs)
        booking = lend(theirs, borrower, TODAY - timedelta(days=4), TOMORROW)

        assert returned(owner, booking).status_code == 403
        assert returned(co_curator, booking).status_code == 200


class TestWhenItIsNotALoanInProgress:
    @pytest.mark.parametrize(
        "make",
        [
            pytest.param(
                lambda t, b: lend(
                    t, b, TODAY - timedelta(days=4), TOMORROW, thing_type="RESERVE_THING"
                ),
                id="a reservation",
            ),
            pytest.param(
                lambda t, b: lend(
                    t, b, TODAY - timedelta(days=4), TOMORROW, thing_type="GIFT_THING"
                ),
                id="a gift",
            ),
            pytest.param(
                lambda t, b: lend(t, b, TODAY - timedelta(days=4), TOMORROW, status="PENDING"),
                id="a request nobody accepted",
            ),
            pytest.param(
                lambda t, b: lend(t, b, TODAY - timedelta(days=4), TOMORROW, status="CANCELLED"),
                id="a cancelled one",
            ),
            pytest.param(
                lambda t, b: lend(t, b, TOMORROW, TOMORROW + timedelta(days=3)),
                id="a loan that has not started",
            ),
        ],
    )
    def test_it_is_a_coded_400_and_nothing_is_written(self, drill, owner, borrower, make):
        booking = make(drill, borrower)

        response = returned(owner, booking)

        assert response.status_code == 400
        assert response.data["code"] == "not_on_loan"
        booking.refresh_from_db()
        assert booking.returned_at is None

    def test_a_loan_that_starts_today_is_in_progress(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY, TODAY + timedelta(days=3))

        assert returned(owner, booking).status_code == 200

    def test_one_already_marked_is_refused_and_keeps_its_first_moment(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)
        returned(owner, booking)
        booking.refresh_from_db()
        first = booking.returned_at

        with time_machine.travel(datetime(2026, 10, 7, 18, 0, tzinfo=UTC)):
            again = returned(owner, booking)

        assert again.status_code == 400
        assert again.data["code"] == "not_on_loan"
        booking.refresh_from_db()
        assert booking.returned_at == first


class TestWhatTheListSays:
    def test_the_manager_is_told_a_loan_in_progress_can_be_marked(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        data = serialized(owner, booking)

        assert data["can_mark_returned"] is True
        assert data["returned_at"] is None

    def test_a_borrower_is_never_offered_it(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        assert serialized(borrower, booking)["can_mark_returned"] is False

    def test_without_a_request_it_is_false(self, drill, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=4), TOMORROW)

        assert BookingPeriodSerializer(booking).data["can_mark_returned"] is False

    def test_a_marked_loan_says_when_and_offers_nothing_more(self, drill, owner, borrower):
        booking = lend(drill, borrower, TODAY - timedelta(days=9), YESTERDAY)
        returned(owner, booking)
        booking.refresh_from_db()

        data = serialized(owner, booking)

        assert data["returned_at"] is not None
        assert data["can_mark_returned"] is False
        assert data["can_remind_return"] is False

    def test_a_returned_loan_cannot_be_reminded_and_the_endpoint_says_so(
        self, drill, owner, borrower
    ):
        booking = lend(drill, borrower, TODAY - timedelta(days=9), YESTERDAY)
        assert booking.can_be_return_reminded() is True
        returned(owner, booking)
        booking.refresh_from_db()

        assert booking.can_be_return_reminded() is False
        response = client_for(owner).post(f"/api/v1/bookings/{booking.code}/remind-return/")
        assert response.status_code == 400
        assert response.data["code"] == "not_awaiting_return"
        assert mail.outbox == []
