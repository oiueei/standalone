"""The row locks in ``booking_service`` (and the collection lock behind the
co-curator ceiling) — tested as locks, not as re-reads.

Every accept/reject/cancel path re-reads its booking through
``select_for_update()`` and re-checks ``PENDING`` under that lock. Until this
file, **nothing in the suite could tell the lock from the re-read**: removing all
five ``select_for_update()`` calls (and the sixth in ``views/things.py``) left
1428 tests green. That is not a missing assertion, it is a missing *shape* — the
whole suite runs single-threaded, inside one transaction, on one connection, and
a ``FOR UPDATE`` never blocks against the transaction that took it. Zero tests
used ``transaction=True``; zero used threads.

So the guard has to be a real race: two connections, both reading the booking as
PENDING before either commits. Without the lock both proceed and the money /
ownership side effects run twice. With it, the second blocks until the first
commits, re-reads, finds the booking settled and returns ``None``.

**This file is why CI runs on Postgres.** SQLite reports
``has_select_for_update = False``, so Django drops the clause silently and these
tests would measure the unlocked behaviour — they skip there instead of lying.
Locally they are skipped; in CI (``DATABASE_URL`` → postgres:16) they run. The
skip must never happen *in the job that has Postgres*: ``tests.yml`` declares
``REQUIRE_POSTGRES_LOCK_TESTS=1`` next to its ``DATABASE_URL``, and under that
promise a lockless database fails the run instead of skipping it. To rehearse
one by hand, point DATABASE_URL at a Postgres and run this file; to rehearse
the guard, run it on SQLite with the variable set.

The barrier is the only artificial part, and it buys determinism rather than
behaviour: ``BookingPeriod.accept``/``reject``/``cancel`` are wrapped so the
first thread inside the transaction waits until the second has reached the
locked read. Nothing about the code under test is patched — the wrapper calls
straight through.
"""

import os
import threading
import time
from datetime import date, timedelta

import pytest
from django.core import mail
from django.db import connection, connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.collection import kind_for_thing_type
from core.models.transfer import ThingTransfer
from core.services.booking_service import (
    BookingRequestError,
    accept_booking,
    cancel_booking,
    reject_booking,
    request_date_based_booking,
    request_reservation,
    request_standard_booking,
)

pytestmark = [pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _postgres_or_skip():
    """The module's database gate, checked per test so ``-k`` can deselect it.

    A ``skipif`` would keep the build green even where silence is the lie: if
    the CI job that owns this file ever lost its ``postgres`` service or its
    ``DATABASE_URL``, these lock tests would quietly not run. That job
    declares ``REQUIRE_POSTGRES_LOCK_TESTS=1`` next to its ``DATABASE_URL``
    (see ``tests.yml``), and under that promise a database without
    ``select_for_update`` fails the run instead of skipping it. Jobs without
    Postgres — ``hosted.yml``'s, which runs ``-k hosted`` and never collects
    this file — never set the variable. Locally on SQLite the tests skip as
    they always did; set the variable to rehearse the guard.
    """
    if connection.features.has_select_for_update:
        return
    if os.environ.get("REQUIRE_POSTGRES_LOCK_TESTS"):
        pytest.fail(
            "REQUIRE_POSTGRES_LOCK_TESTS is set — this job promises Postgres, but the "
            "database reports no select_for_update support, so these lock tests "
            "would silently not run",
            pytrace=False,
        )
    pytest.skip("SQLite drops FOR UPDATE silently — these prove the lock, so they need Postgres")


def _pending_booking(thing, owner, requester):
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=requester,
        requester_email=requester.email,
        owner_code=owner,
        status=BookingPeriod.Status.PENDING,
    )


# How long the first transaction keeps holding the row after the second has said
# it is about to read. There is no way to observe "that query is now blocked"
# without reading `pg_locks`, so this is the one timing constant in the file. It
# only ever has to outlast the second thread's own `SELECT … FOR UPDATE` reaching
# the server; a whole second is enormous for that and still costs three seconds
# across the file. The assertion does not depend on the value being *just* right:
# too short and the second thread simply is not blocked yet, which shows up as
# the "never blocked" failure below, never as a false pass.
_HOLD_SECONDS = 1.0


def _run_both(first, second):
    """Run ``first`` and ``second`` concurrently, ``first`` holding its lock.

    Returns ``(first_result, second_result, was_blocked)``.

    The ordering is the whole test, and getting it wrong makes this file pass
    against unlocked code:

    1. ``first`` reaches the inside of its transaction, past the locked read,
       and signals ``inside``.
    2. ``second`` wakes, signals ``attempting`` and calls straight into its own
       locked read.
    3. ``first`` waits ``_HOLD_SECONDS`` *still holding the row*, then commits.

    Step 3 is what an earlier version of this helper got wrong: it released the
    first transaction the moment the second **woke up**, rather than after
    letting it run into the lock. The first could then commit before the second
    had read anything, so the second found the booking already settled and
    returned ``None`` — the exact result a working lock produces — with the lock
    playing no part. It would have passed with ``select_for_update()`` deleted.

    ``was_blocked`` is the direct evidence, rather than an inference from the
    outcome: it records whether the second call was *still running* at the moment
    the first was about to commit. Under a real lock it must be.
    """
    errors = []
    inside = threading.Event()
    attempting = threading.Event()
    second_done = threading.Event()
    observed = {}
    results = {}

    def guard():
        """Hold the row while the second transaction runs into it."""
        inside.set()
        attempting.wait(timeout=5)
        time.sleep(_HOLD_SECONDS)
        # Sampled before this transaction commits: with the row locked the other
        # one cannot have got past its own read yet.
        observed["blocked"] = not second_done.is_set()

    def run_first():
        try:
            results["first"] = first(guard)
        except BaseException as exc:  # noqa: BLE001 — re-raised by the caller
            errors.append(("first", exc))
        finally:
            connections.close_all()

    def run_second():
        try:
            inside.wait(timeout=5)
            attempting.set()
            results["second"] = second()
        except BaseException as exc:  # noqa: BLE001 — re-raised by the caller
            errors.append(("second", exc))
        finally:
            second_done.set()
            connections.close_all()

    threads = [threading.Thread(target=run_first), threading.Thread(target=run_second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a thread deadlocked instead of serialising"

    # Without this, a thread that *crashed* leaves its result unset — and "unset"
    # reads as the `None` that means "the lock made me stand down", so the whole
    # file passes while proving nothing. That is exactly what happened on the
    # first run of these tests against SQLite, whose coarse table lock threw
    # `database table is locked` at the second thread. A blocked transaction
    # waits; it does not raise.
    assert not errors, "a transaction raised instead of waiting its turn: " + "; ".join(
        f"{who}: {exc!r}" for who, exc in errors
    )
    assert set(results) == {"first", "second"}, f"a thread produced no result at all: {results}"
    return results["first"], results["second"], observed.get("blocked", False)


def _with_barrier(model_method, guard):
    """Call ``guard()`` from inside the service's transaction, then carry on."""
    original = getattr(BookingPeriod, model_method)

    def wrapper(self, *args, **kwargs):
        guard()
        return original(self, *args, **kwargs)

    return original, wrapper


class TestOnlyOneTransitionWins:
    def test_two_concurrent_accepts_accept_the_booking_once(self, monkeypatch, user, user2, thing):
        """An owner double-clicking, or the email link racing the in-app button,
        must not run the transfer and the deal twice.

        The observable that needs the lock is the **pair** of return values:
        exactly one Thing and exactly one None. Unlocked, both transactions read
        PENDING and both return a Thing — and `ThingTransfer`'s unique constraint
        would hide it, since `get_or_create` quietly settles for the existing row.
        """
        booking = _pending_booking(thing, user, user2)

        def first(guard):
            original, wrapper = _with_barrier("accept", guard)
            monkeypatch.setattr(BookingPeriod, "accept", wrapper)
            try:
                return accept_booking(booking)
            finally:
                monkeypatch.setattr(BookingPeriod, "accept", original)

        first_result, second_result, was_blocked = _run_both(first, lambda: accept_booking(booking))

        assert was_blocked, "the second transaction read straight past the lock"
        assert [first_result, second_result].count(None) == 1, (
            "both transactions accepted the same booking — the row was never locked"
        )
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.ACCEPTED
        assert ThingTransfer.objects.filter(booking=booking).count() == 1

    def test_an_accept_racing_a_reject_settles_one_way_only(self, monkeypatch, user, user2, thing):
        """The two decisions are mutually exclusive, and the loser is a no-op —
        not a booking that ends up rejected while a transfer says it was lent."""
        booking = _pending_booking(thing, user, user2)

        def first(guard):
            original, wrapper = _with_barrier("accept", guard)
            monkeypatch.setattr(BookingPeriod, "accept", wrapper)
            try:
                return accept_booking(booking)
            finally:
                monkeypatch.setattr(BookingPeriod, "accept", original)

        first_result, second_result, was_blocked = _run_both(first, lambda: reject_booking(booking))

        assert was_blocked, "the reject read straight past the lock"
        assert [first_result, second_result].count(None) == 1
        booking.refresh_from_db()
        assert booking.status == BookingPeriod.Status.ACCEPTED
        # The reject lost, so nothing may claim the thing came back.
        assert ThingTransfer.objects.filter(booking=booking).count() == 1

    def test_a_requester_cancelling_cannot_race_the_owner_accepting(
        self, monkeypatch, user, user2, thing
    ):
        """The reported shape: the guest withdraws at the moment the owner says
        yes. One of them must find the booking already settled."""
        booking = _pending_booking(thing, user, user2)

        def first(guard):
            original, wrapper = _with_barrier("cancel", guard)
            monkeypatch.setattr(BookingPeriod, "cancel", wrapper)
            try:
                return cancel_booking(booking)
            finally:
                monkeypatch.setattr(BookingPeriod, "cancel", original)

        first_result, second_result, was_blocked = _run_both(first, lambda: accept_booking(booking))

        assert was_blocked, "the accept read straight past the cancel's lock"
        assert [first_result, second_result].count(None) == 1
        booking.refresh_from_db()
        assert booking.status in (
            BookingPeriod.Status.CANCELLED,
            BookingPeriod.Status.ACCEPTED,
        )


# ── The create side: two requests for one slot ───────────────────────────────
# `request_reservation` / `request_standard_booking` / `request_date_based_booking`
# each lock the Thing row and *then* check for a clash under that lock. Drop the
# lock and two requests for the same slot both read "free" before either commits,
# and both create the booking. The audit that added this file (2026-09) covered
# accept/reject/cancel; the create paths went in unguarded by any real race.


def _one_shot(original, guard):
    """Wrap ``original`` so ``guard()`` fires exactly once, on the first call.

    The second racing thread reaches the same patched callable once it unblocks
    — it must run straight through, not re-enter the barrier.
    """
    fired = threading.Event()

    def wrapper(*args, **kwargs):
        if not fired.is_set():
            fired.set()
            guard()
        return original(*args, **kwargs)

    return wrapper


class TestTwoRequestsForOneSlotAreSerialised:
    def _reservations_collection(self, owner, *members):
        coll = Collection.objects.create(
            code="RCEC01",
            owner=owner,
            headline="Rooms",
            mode=Collection.Mode.PROPRIETARY,
            kind=Collection.Kind.SHED,
            allowed_thing_types=["RESERVE_THING"],
            reservation_max_days=3,
        )
        coll.invites.add(*members)
        thing = Thing.objects.create(
            code="RCET01", type=Thing.Type.RESERVE_THING, owner=owner, headline="Sala"
        )
        coll.things.add(thing)
        return coll, thing

    def _group_of(self, owner, thing, code, *members):
        """An ACTIVE group holding ``thing`` with ``members`` in it: asking for any
        thing takes a seat in one of its groups, so the two requesters need one to
        reach the lock at all."""
        group = Collection.objects.create(
            code=code,
            owner=owner,
            headline="Neighbours",
            kind=kind_for_thing_type(thing.type),
        )
        group.invites.add(*members)
        group.things.add(thing)
        return group

    def test_a_reservation_clash_is_serialised_not_double_booked(self, monkeypatch, user, user2):
        """RESERVE auto-confirms with no owner step, so an unlocked clash is two
        members turning up to one room. The loser must get the 409, and exactly
        one ACCEPTED booking may exist."""
        other = User.objects.create(code="RCEUSR", email="lolo@your-domain.test")
        coll, thing = self._reservations_collection(user, user2, other)
        day = date.today() + timedelta(days=2)
        original = BookingPeriod.has_overlap

        def first(guard):
            monkeypatch.setattr(BookingPeriod, "has_overlap", _one_shot(original, guard))
            try:
                return request_reservation(
                    thing, user2, user.email, day, 1, collection_code=coll.code
                )
            finally:
                monkeypatch.setattr(BookingPeriod, "has_overlap", original)

        def second():
            try:
                return request_reservation(
                    thing, other, user.email, day, 1, collection_code=coll.code
                )
            except BookingRequestError as exc:
                return ("refused", exc.status_code)

        first_result, second_result, was_blocked = _run_both(first, second)

        assert was_blocked, "the second request read straight past the Thing lock"
        assert isinstance(first_result, BookingPeriod)
        assert second_result == ("refused", 409), second_result
        assert (
            BookingPeriod.objects.filter(
                thing_code=thing, status=BookingPeriod.Status.ACCEPTED
            ).count()
            == 1
        )

    def test_two_requests_for_the_last_unit_let_exactly_one_in(self, monkeypatch, user, user2):
        """A space with two identical units and one already taken: the last unit is
        asked for by two members at once. Both read "one booking, one free" before
        either commits unless the Thing lock serialises them; the loser must get the
        409 and the space must end with exactly two bookings, never three."""
        other = User.objects.create(code="RCEUSR", email="lolo@your-domain.test")
        holder = User.objects.create(code="RCEUS3", email="lulu@your-domain.test")
        coll, thing = self._reservations_collection(user, user2, other, holder)
        Thing.objects.filter(pk=thing.pk).update(units=2)
        thing.refresh_from_db()
        day = date.today() + timedelta(days=2)
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=holder,
            requester_email=holder.email,
            owner_code=user,
            start_date=day,
            end_date=day + timedelta(days=1),
            status=BookingPeriod.Status.ACCEPTED,
        )
        original = BookingPeriod.has_overlap

        def first(guard):
            # With several units the first call is the one-person-at-a-time check,
            # inside the Thing lock and before the units are counted.
            monkeypatch.setattr(BookingPeriod, "has_overlap", _one_shot(original, guard))
            try:
                return request_reservation(
                    thing, user2, user.email, day, 1, collection_code=coll.code
                )
            finally:
                monkeypatch.setattr(BookingPeriod, "has_overlap", original)

        def second():
            try:
                return request_reservation(
                    thing, other, user.email, day, 1, collection_code=coll.code
                )
            except BookingRequestError as exc:
                return ("refused", exc.status_code)

        first_result, second_result, was_blocked = _run_both(first, second)

        assert was_blocked, "the second request read straight past the Thing lock"
        assert isinstance(first_result, BookingPeriod)
        assert second_result == ("refused", 409), second_result
        assert (
            BookingPeriod.objects.filter(
                thing_code=thing, status=BookingPeriod.Status.ACCEPTED
            ).count()
            == 2
        )

    def test_a_gift_cannot_be_claimed_twice_at_once(self, monkeypatch, user, user2):
        """Two members claiming the same single-use GIFT: one booking, the thing
        TAKEN once. Unlocked, both read status ACTIVE and both create."""
        other = User.objects.create(code="RCEG02", email="lala@your-domain.test")
        thing = Thing.objects.create(
            code="RCEG01", type=Thing.Type.GIFT_THING, owner=user, headline="A lamp"
        )
        self._group_of(user, thing, "RCEG03", user2, other)
        original = BookingPeriod.save

        def first(guard):
            monkeypatch.setattr(BookingPeriod, "save", _one_shot(original, guard))
            try:
                return request_standard_booking(thing, user2)
            finally:
                monkeypatch.setattr(BookingPeriod, "save", original)

        def second():
            try:
                return request_standard_booking(thing, other)
            except BookingRequestError as exc:
                return ("refused", exc.status_code)

        first_result, second_result, was_blocked = _run_both(first, second)

        assert was_blocked, "the second claim read past the lock the first was holding"
        assert isinstance(first_result, BookingPeriod)
        assert second_result[0] == "refused", second_result
        thing.refresh_from_db()
        assert thing.status == Thing.Status.TAKEN
        assert BookingPeriod.objects.filter(thing_code=thing).count() == 1

    def test_two_overlapping_loans_cannot_both_be_created(self, monkeypatch, user, user2):
        """Same dates, same drill: the second request finds the first's booking
        under the lock and is a 409, not a second row."""
        other = User.objects.create(code="RCEL02", email="lele@your-domain.test")
        thing = Thing.objects.create(
            code="RCEL01", type=Thing.Type.LEND_THING, owner=user, headline="A drill"
        )
        self._group_of(user, thing, "RCEL03", user2, other)
        start = date.today() + timedelta(days=3)
        end = start + timedelta(days=4)
        original = BookingPeriod.has_overlap

        def first(guard):
            monkeypatch.setattr(BookingPeriod, "has_overlap", _one_shot(original, guard))
            try:
                return request_date_based_booking(thing, user2, start, end)
            finally:
                monkeypatch.setattr(BookingPeriod, "has_overlap", original)

        def second():
            try:
                return request_date_based_booking(thing, other, start, end)
            except BookingRequestError as exc:
                return ("refused", exc.status_code)

        first_result, second_result, was_blocked = _run_both(first, second)

        assert was_blocked, "the second loan request read past the lock"
        assert isinstance(first_result, BookingPeriod)
        assert second_result == ("refused", 409), second_result
        assert BookingPeriod.objects.filter(thing_code=thing).count() == 1

    def test_two_requests_for_the_last_units_of_a_loan_let_exactly_one_in(
        self, monkeypatch, user, user2
    ):
        """A loan with three identical units and one already asked for: two members
        ask for two each at the same time. Both count "two free" before either
        commits unless the Thing lock serialises them; the loser must get the 409
        and the units held must add up to three, never five.

        With several units the first ``has_overlap`` the service makes inside the
        lock is the one-live-request-per-person check, before the units are counted,
        so the barrier sits there."""
        other = User.objects.create(code="RCEL12", email="lele@your-domain.test")
        holder = User.objects.create(code="RCEL13", email="lulu@your-domain.test")
        thing = Thing.objects.create(
            code="RCEL11",
            type=Thing.Type.LEND_THING,
            owner=user,
            headline="A ladder",
            units=3,
        )
        self._group_of(user, thing, "RCEL14", user2, other)
        start = date.today() + timedelta(days=3)
        end = start + timedelta(days=4)
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=holder,
            requester_email=holder.email,
            owner_code=user,
            start_date=start,
            end_date=end,
            status=BookingPeriod.Status.PENDING,
            quantity=1,
        )
        original = BookingPeriod.has_overlap

        def first(guard):
            monkeypatch.setattr(BookingPeriod, "has_overlap", _one_shot(original, guard))
            try:
                return request_date_based_booking(thing, user2, start, end, quantity=2)
            finally:
                monkeypatch.setattr(BookingPeriod, "has_overlap", original)

        def second():
            try:
                return request_date_based_booking(thing, other, start, end, quantity=2)
            except BookingRequestError as exc:
                return ("refused", exc.status_code, exc.code)

        first_result, second_result, was_blocked = _run_both(first, second)

        assert was_blocked, "the second loan request counted the units past the lock"
        assert isinstance(first_result, BookingPeriod)
        assert second_result == ("refused", 409, "not_enough_units"), second_result
        held = BookingPeriod.objects.filter(
            thing_code=thing,
            status__in=[BookingPeriod.Status.PENDING, BookingPeriod.Status.ACCEPTED],
        )
        assert sum(row.quantity for row in held) == 3


# ── The collection row: the co-curator ceiling ───────────────────────────────
# `Collection.promote_co_owner` reads the set's size and adds under a lock on the
# collection row. A bare `count()` then `add()` (what the view did until
# 2026-09-29) lets promotions that run together all read the same count.


class TestTheCoCuratorCeilingIsAtomic:
    def test_two_promotions_at_the_last_place_cannot_both_win(self, monkeypatch, user):
        """The ceiling is what bounds a stolen curator credential, and a race is
        how to walk past it: with the set one short of `MAX_CO_OWNERS`, two
        promotions running together both read "room for one". Locked, the second
        waits for the first to commit, counts the full set and is refused.

        The barrier sits on the `add` — after the first promotion has read its
        count under the lock — so that, unlocked, the second one reads the same
        count while the first is still holding back its add. Nothing is patched
        away: the wrapper calls straight through.
        """
        group = Collection.objects.create(code="CORC01", owner=user, headline="Curators")
        for i in range(Collection.MAX_CO_OWNERS - 1):
            curator = User.objects.create(code=f"CORM{i:02d}", email=f"lulu{i}@your-domain.test")
            group.invites.add(curator)
            group.co_owners.add(curator)
        first_new = User.objects.create(code="CORN01", email="lili@your-domain.test")
        second_new = User.objects.create(code="CORN02", email="lolo1@your-domain.test")
        group.invites.add(first_new, second_new)
        manager = Collection.co_owners.related_manager_cls
        original = manager.add

        def first(guard):
            monkeypatch.setattr(manager, "add", _one_shot(original, guard))
            try:
                return group.promote_co_owner(first_new)
            finally:
                monkeypatch.setattr(manager, "add", original)

        first_result, second_result, was_blocked = _run_both(
            first, lambda: group.promote_co_owner(second_new)
        )

        assert was_blocked, "the second promotion read the count past the lock"
        assert first_result is Collection.Promotion.ADDED
        assert second_result is Collection.Promotion.FULL, second_result
        assert group.co_owners.count() == Collection.MAX_CO_OWNERS


# ── The return reminder: one nudge a day, even pressed twice at once ──────────
# `BookingRemindReturnView` claims the day with one conditional UPDATE before the
# email goes. There is no lock held across statements to block on, so this race
# is not run through `_run_both`: both presses are let past every check and then
# meet at the claim together.


class TestTwoRemindersAtOnceSendOne:
    def test_two_presses_together_mail_the_borrower_once(self, monkeypatch, user, user2):
        """A double click, or two curators pressing in the same second. Both requests
        load the booking and pass `can_be_return_reminded()` before either claims
        the day — the barrier sees to it. The conditional UPDATE is evaluated by the
        database against the row as the other request left it, so one matches and
        one gets the 429. A claim written as "read `return_reminded_at` off the
        loaded booking, then save" lets both through here and mails twice."""
        group = Collection.objects.create(
            code="RMRC01", owner=user, headline="Taller", kind=Collection.Kind.LIBRARY
        )
        group.invites.add(user2)
        drill = Thing.objects.create(code="RMRT01", owner=user, headline="Drill", type="LEND_THING")
        group.things.add(drill)
        today = date.today()
        booking = BookingPeriod.objects.create(
            thing_code=drill,
            thing_type=drill.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=3),
            status=BookingPeriod.Status.ACCEPTED,
        )
        token = RefreshToken.for_user(user).access_token
        both_checked = threading.Barrier(2, timeout=5)
        original = BookingPeriod.can_be_return_reminded

        def checked_then_wait(self):
            answer = original(self)
            both_checked.wait()
            return answer

        monkeypatch.setattr(BookingPeriod, "can_be_return_reminded", checked_then_wait)
        statuses, errors = [], []

        def press():
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
                response = client.post(f"/api/v1/bookings/{booking.code}/remind-return/")
                statuses.append(response.status_code)
            except BaseException as exc:  # noqa: BLE001 — reported below
                errors.append(exc)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=press) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not any(t.is_alive() for t in threads), "a press never came back"
        assert not errors, f"a press raised instead of answering: {errors!r}"
        assert sorted(statuses) == [200, 429], statuses
        assert [m.to for m in mail.outbox] == [[user2.email]]
