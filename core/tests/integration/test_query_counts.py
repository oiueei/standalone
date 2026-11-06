"""Query-count regression guards for list endpoints.

These lock in the prefetch/annotation work so a future change can't silently
reintroduce a per-thing query (N+1) on transfer_count / my_pending_booking /
the nested-things serialisation.
"""

import json
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, BookingPeriod, Collection, Thing
from core.models.transfer import ThingTransfer
from core.tests.factories import (
    BookingPeriodFactory,
    CollectionFactory,
    FAQFactory,
    RSVPFactory,
    ThingFactory,
    ThingTransferFactory,
    UserFactory,
    also_in,
)


def _make_things(owner, collection, n):
    collection.things.add(*ThingFactory.create_batch(n, owner=owner))


def _warm_activity(client):
    """Prime DailyActivityMiddleware's once-per-user/day write + cache guard.

    The middleware writes a DailyActivity row on a user's first authenticated
    request of the day and only reads cache thereafter. Without this warm-up the
    first measured request below would alone carry that INSERT, so the equality
    guards would be comparing first-visit bookkeeping instead of serialisation
    cost. One throwaway request makes both measured requests steady-state.
    """
    client.get("/api/v1/auth/me/")


@pytest.mark.django_db
class TestListEndpointQueryBudgets:
    """The query count of a list/detail response must be CONSTANT in the number
    of things it serialises — adding more things must add zero queries."""

    def test_collection_detail_has_no_per_thing_queries(
        self, authenticated_client, user, collection
    ):
        url = f"/api/v1/collections/{collection.code}/"
        _warm_activity(authenticated_client)
        _make_things(user, collection, 2)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        _make_things(user, collection, 4)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200
        assert len(r2.data["things"]) == 6

        assert len(big) == len(small), (
            f"N+1 on collection detail: {len(small)} queries for 2 things, {len(big)} for 6"
        )

    def test_anon_collection_detail_reuses_things_prefetch(self, api_client, user):
        """Non-curator viewers (including anonymous ones) take the Python-side
        INACTIVE filter in get_things(). A regression to .exclude() there
        discards the collection's Prefetch("things", ...) cache — it doesn't
        scale with N, but it does re-fire the things query plus its 4 nested
        prefetches (faq_set/deal/2x bookings), doubling 9 queries to 14."""
        coll = CollectionFactory(owner=user, visibility=Collection.Visibility.PUBLIC)
        _make_things(user, coll, 2)
        with CaptureQueriesContext(connection) as small:
            r1 = api_client.get(f"/api/v1/collections/{coll.code}/")
        assert r1.status_code == 200

        _make_things(user, coll, 4)
        with CaptureQueriesContext(connection) as big:
            r2 = api_client.get(f"/api/v1/collections/{coll.code}/")
        assert r2.status_code == 200
        assert len(r2.data["things"]) == 6

        assert len(big) == len(small), (
            f"N+1 on anon collection detail: {len(small)} queries for 2 things, {len(big)} for 6"
        )
        assert len(small) == 9, (
            f"expected the collection's things Prefetch to be reused (9 queries — 7 plus the "
            f"co_owners prefetch added for is_curator/co_owners and the one for the curators' "
            f"pages, which every collection carries), "
            f"got {len(small)} — an .exclude() on obj.things would discard it"
        )

    def test_an_hourly_collection_costs_no_query_per_space(self, authenticated_client, user):
        """Every card on an HOUR-unit collection's page walks that day-by-day
        availability search (`compute_hourly_availability`, up to the whole
        horizon). It has to run off the prefetched bookings and the collection
        already in hand: a query per space — or per day — would turn one page
        of a space-booking venue into hundreds, on the page its curators and
        members open most."""
        coll = CollectionFactory(
            owner=user,
            allowed_thing_types=["RESERVE_THING"],
            reservation_unit=Collection.ReservationUnit.HOUR,
            reservation_horizon_days=365,
            opening_hours={"0": [["10:00", "14:00"]]},  # Mondays only: a long walk
        )
        url = f"/api/v1/collections/{coll.code}/"
        _warm_activity(authenticated_client)
        coll.things.add(*ThingFactory.create_batch(2, owner=user, type="RESERVE_THING"))
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        coll.things.add(*ThingFactory.create_batch(4, owner=user, type="RESERVE_THING"))
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200
        assert len(r2.data["things"]) == 6
        # The walk really ran: a Monday within the horizon is the answer.
        assert r2.data["things"][0]["next_available"] is not None

        assert len(big) == len(small), (
            f"N+1 on an hourly collection: {len(small)} queries for 2 spaces, {len(big)} for 6"
        )

    def test_things_list_has_no_per_thing_queries(self, authenticated_client, user, collection):
        url = "/api/v1/things/"
        _warm_activity(authenticated_client)
        _make_things(user, collection, 2)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        _make_things(user, collection, 4)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200

        assert len(big) == len(small), f"N+1 on things list: {len(small)} queries vs {len(big)}"

    def test_transfer_count_annotation_is_correct(
        self, authenticated_client, user, user2, collection
    ):
        """The _transfer_count annotation (Count distinct) reports the true
        per-thing transfer count through the endpoint."""
        thing = ThingFactory(owner=user, type="LEND_THING")
        collection.things.add(thing)
        ThingTransferFactory(thing=thing, from_user=user, to_user=user2, lent_date=date.today())
        ThingTransferFactory(thing=thing, from_user=user2, to_user=user, lent_date=date.today())

        r = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert r.status_code == 200
        thing_data = next(t for t in r.data["things"] if t["code"] == thing.code)
        assert thing_data["transfer_count"] == 2
        assert ThingTransfer.objects.filter(thing=thing).count() == 2


@pytest.mark.django_db
class TestNPlusOneGuards:
    """Endpoints whose query count must NOT grow with the number of rows they
    serialise. Each guard fails if its prefetch/annotation/memoisation regresses."""

    def test_owner_calendar_constant_with_requesters(self, authenticated_client, user, collection):
        """The owner calendar must select_related the requester (its name is read
        per period) so more bookings don't add per-period queries."""
        thing = ThingFactory(owner=user, type="LEND_THING")
        collection.things.add(thing)

        def make(n, offset):
            for i in range(n):
                BookingPeriodFactory(
                    thing_code=thing,
                    requester_code=UserFactory(),
                    thing_type="LEND_THING",
                    start_date=date(2026, 1, 1) + timedelta(days=(offset + i) * 10),
                    end_date=date(2026, 1, 5) + timedelta(days=(offset + i) * 10),
                    status="PENDING",
                )

        url = f"/api/v1/things/{thing.code}/calendar/"
        _warm_activity(authenticated_client)
        make(2, 0)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        make(2, 2)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200
        assert len(big) == len(small), (
            f"N+1 on owner calendar requesters: {len(small)} vs {len(big)}"
        )

    def test_collection_detail_embeds_owner_bookings_for_free(
        self, authenticated_client, user, collection
    ):
        """Serving the owner's bookings on the card must add no query, per thing
        or per booking.

        The card used to GET /things/{code}/calendar/ once each, so an owner
        opening a 30-item lending library fired 30 requests. Those rows were
        already in memory (`_blocked_periods`), so the field is free — but only
        while the prefetch keeps `select_related("requester_code")`: the
        serialiser prints the requester's name, and dropping that join trades one
        request per card for one query per booking, which is worse.
        """
        url = f"/api/v1/collections/{collection.code}/"
        _warm_activity(authenticated_client)

        def lend_thing_with_bookings(n, offset):
            thing = ThingFactory(owner=user, type="LEND_THING")
            collection.things.add(thing)
            for i in range(n):
                BookingPeriodFactory(
                    thing_code=thing,
                    requester_code=UserFactory(),
                    thing_type="LEND_THING",
                    start_date=date(2099, 1, 1) + timedelta(days=(offset + i) * 10),
                    end_date=date(2099, 1, 5) + timedelta(days=(offset + i) * 10),
                    status="PENDING",
                )

        lend_thing_with_bookings(2, 0)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200
        assert any(t["bookings"] for t in r1.data["things"]), (
            "the owner must actually receive the embedded bookings"
        )

        # Two more things, each with its own bookings and its own requesters.
        lend_thing_with_bookings(2, 2)
        lend_thing_with_bookings(2, 4)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200

        assert len(big) == len(small), (
            f"N+1 on embedded owner bookings: {len(small)} queries for 1 thing, "
            f"{len(big)} for 3 (each with 2 bookings and distinct requesters)"
        )

    def test_collection_detail_hides_bookings_from_non_owners(self, api_client, user):
        """A card's booking list names the people who requested it — owner only.

        The field rides on the same serialiser an anonymous visitor gets for a
        PUBLIC collection, so the gate is the only thing between a requester's
        name and the open web.
        """
        public = CollectionFactory(owner=user, visibility=Collection.Visibility.PUBLIC)
        thing = ThingFactory(owner=user, type="LEND_THING")
        public.things.add(thing)
        BookingPeriodFactory(
            thing_code=thing,
            requester_code=UserFactory(name="Nosy Neighbour"),
            thing_type="LEND_THING",
            start_date=date(2099, 2, 1),
            end_date=date(2099, 2, 5),
            status="PENDING",
        )

        resp = api_client.get(f"/api/v1/collections/{public.code}/")

        assert resp.status_code == 200
        assert resp.data["things"][0]["bookings"] is None
        assert "Nosy Neighbour" not in str(resp.data)

    def test_collection_list_constant_with_pending_invites(self, authenticated_client, user):
        """The collection list must batch pending_invites (one RSVP query for the
        whole page), not query the RSVP table once per owned collection."""

        def make(n):
            for _ in range(n):
                coll = CollectionFactory(owner=user)
                RSVPFactory(
                    user_code=UserFactory(),
                    action=RSVP.Action.COLLECTION_INVITE,
                    target_code=coll.code,
                )

        _warm_activity(authenticated_client)
        make(2)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get("/api/v1/collections/")
        assert r1.status_code == 200

        make(2)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get("/api/v1/collections/")
        assert r2.status_code == 200
        assert len(big) == len(small), (
            f"N+1 on collection-list pending_invites: {len(small)} vs {len(big)}"
        )


@pytest.mark.django_db
class TestInvitedCollectionsQueryBudget:
    """`GET /invited-collections/` is not paginated and serialises every thing of
    every group the member belongs to (Home and the profile read it). The contract
    stays as it is; what is pinned here is what it costs, so a regression shows."""

    URL = "/api/v1/invited-collections/"

    def _groups(self, member, owner, n, things):
        for _ in range(n):
            group = CollectionFactory(owner=owner)
            group.invites.add(member)
            _make_things(owner, group, things)

    def test_the_cost_does_not_grow_with_the_things_in_each_group(self, authenticated_client, user):
        owner = UserFactory()
        self._groups(user, owner, 3, 5)
        _warm_activity(authenticated_client)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(self.URL)
        assert r1.status_code == 200
        assert [len(c["things"]) for c in r1.data] == [5, 5, 5]

        for group in user.invited_to_collections.all():
            _make_things(owner, group, 55)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(self.URL)
        assert r2.status_code == 200
        assert [len(c["things"]) for c in r2.data] == [60, 60, 60]

        assert len(big) == len(small), (
            f"N+1 per thing on invited-collections: {len(small)} queries for 3x5 things, "
            f"{len(big)} for 3x60 ({len(r2.content)} bytes)"
        )

    def test_the_cost_does_not_grow_with_the_number_of_groups(self, authenticated_client, user):
        owner = UserFactory()
        self._groups(user, owner, 2, 5)
        _warm_activity(authenticated_client)
        with CaptureQueriesContext(connection) as few:
            r1 = authenticated_client.get(self.URL)
        assert len(r1.data) == 2

        self._groups(user, owner, 4, 5)
        with CaptureQueriesContext(connection) as many:
            r2 = authenticated_client.get(self.URL)
        assert len(r2.data) == 6

        assert len(many) == len(few), (
            f"N+1 per group on invited-collections: {len(few)} queries for 2 groups, "
            f"{len(many)} for 6"
        )


@pytest.mark.django_db
class TestDataExportQueryBudgets:
    """An export walks every table a person appears in, so an N+1 here is not a
    slow page — it is a 30-second Heroku timeout on the one request somebody
    makes when they are already unhappy enough to be leaving."""

    def test_account_export_is_constant_in_what_it_carries(self, authenticated_client, user):
        def grow():
            coll = CollectionFactory(owner=user)
            _make_things(user, coll, 3)
            coll.invites.add(UserFactory(), UserFactory())
            RSVPFactory(
                user_code=UserFactory(),
                action=RSVP.Action.COLLECTION_INVITE,
                target_code=coll.code,
            )
            for thing in ThingFactory.create_batch(2, owner=user):
                BookingPeriodFactory(thing_code=thing)
                ThingTransferFactory(thing=thing, from_user=user)

        _warm_activity(authenticated_client)
        grow()
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get("/api/v1/auth/export/")
        assert r1.status_code == 200

        for _ in range(3):
            grow()
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get("/api/v1/auth/export/")
        assert r2.status_code == 200
        assert len(big) == len(small), (
            f"N+1 in the account export: {len(small)} queries for one group, {len(big)} for four"
        )

    def test_collection_export_is_constant_in_the_size_of_the_group(
        self, authenticated_client, user
    ):
        coll = CollectionFactory(owner=user)
        url = f"/api/v1/collections/{coll.code}/export/"
        _warm_activity(authenticated_client)
        _make_things(user, coll, 5)
        coll.invites.add(*UserFactory.create_batch(3))
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        _make_things(user, coll, 195)
        coll.invites.add(*UserFactory.create_batch(20))
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200
        assert len(json.loads(r2.content)["things"]) == 200
        assert len(big) == len(small), (
            f"N+1 in the collection export: {len(small)} queries for 5 things, {len(big)} for 200"
        )

    def test_a_two_hundred_thing_group_is_still_a_file_and_not_a_disk(
        self, authenticated_client, user
    ):
        """The other half of the budget, which query counts can't see.

        `assertNumQueries` catches the N+1; it says nothing about the megabytes
        assembled in memory before the response is written. Photos travel as
        URLs precisely so this stays bounded — the day somebody
        inlines an image as base64 "for convenience", this is what notices.
        """
        coll = CollectionFactory(owner=user)
        _make_things(user, coll, 200)

        res = authenticated_client.get(f"/api/v1/collections/{coll.code}/export/")

        assert res.status_code == 200
        assert len(res.content) < 1_000_000, f"200 things weighed {len(res.content)} bytes"


@pytest.mark.django_db
class TestNoticeFanOutQueryBudgets:
    """The FAQ-question notice fans out to every manager of the thing
    (`Thing.managers()` — the owner plus the curators of each PROPRIETARY
    collection it sits in). `managers()` is prefetch-aware; the fetch in
    `ThingFAQListView.get_thing` is what makes it so here, keeping the POST
    constant in the number of collections the thing lives in — without the
    prefetch, every collection the fan-out considers costs its own co_owners
    query."""

    def test_asking_a_question_costs_no_query_per_collection(
        self, authenticated_client2, user2, user
    ):
        thing = ThingFactory(owner=user)
        home = CollectionFactory(owner=user, mode=Collection.Mode.PROPRIETARY)
        home.invites.add(user2)
        home.things.add(thing)
        _warm_activity(authenticated_client2)

        def ask():
            with CaptureQueriesContext(connection) as captured:
                r = authenticated_client2.post(
                    f"/api/v1/things/{thing.code}/faq/",
                    {"question": "How heavy is it?"},
                    format="json",
                )
            assert r.status_code == 201
            return len(captured)

        one_collection = ask()

        # Two more PROPRIETARY collections with the same owner and no
        # co-curators, so the manager set stays {owner} — the only thing
        # growing is the number of collections the fan-out considers.
        for _ in range(2):
            extra = CollectionFactory(owner=user, mode=Collection.Mode.PROPRIETARY)
            also_in(extra, thing)

        three_collections = ask()

        assert three_collections == one_collection, (
            f"N+1 on the FAQ notice fan-out: {one_collection} queries with one "
            f"collection, {three_collections} with three"
        )

    # -- The rest of the fan-outs -------------------------------------------
    # Each test below runs the same action against a thing in one PROPRIETARY
    # collection and then in three (the two extras have the same owner and no
    # co-curators, so the manager set stays {owner}: the only thing growing is
    # the number of collections the notice considers) and demands the same
    # number of queries. `act` builds its own fresh state outside the measured
    # block and returns the queries of the one request it measures.

    @staticmethod
    def _queries(send):
        with CaptureQueriesContext(connection) as captured:
            response = send()
        return response, len(captured)

    @staticmethod
    def _grow(owner, thing, **collection_kwargs):
        for _ in range(2):
            extra = CollectionFactory(
                owner=owner, mode=Collection.Mode.PROPRIETARY, **collection_kwargs
            )
            also_in(extra, thing)

    def _assert_constant(self, owner, thing, act, what, **collection_kwargs):
        one_collection = act()
        self._grow(owner, thing, **collection_kwargs)
        three_collections = act()
        assert three_collections == one_collection, (
            f"N+1 on {what}: {one_collection} queries with one collection, "
            f"{three_collections} with three"
        )

    @staticmethod
    def _client_for(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
        _warm_activity(client)
        return client

    def _team_thing(self, owner, *members, **thing_kwargs):
        thing = ThingFactory(owner=owner, **thing_kwargs)
        home = CollectionFactory(owner=owner, mode=Collection.Mode.PROPRIETARY)
        home.invites.add(*members)
        home.things.add(thing)
        return thing

    def test_answering_a_question_costs_no_query_per_collection(
        self, authenticated_client, user, user2
    ):
        thing = self._team_thing(user, user2)
        _warm_activity(authenticated_client)

        def act():
            faq = FAQFactory(thing=thing, questioner=user2)
            response, count = self._queries(
                lambda: authenticated_client.post(
                    f"/api/v1/faq/{faq.code}/answer/", {"answer": "Two kilos."}, format="json"
                )
            )
            assert response.status_code == 200
            return count

        self._assert_constant(user, thing, act, "answering a FAQ")

    def test_hiding_a_question_costs_no_query_per_collection(
        self, authenticated_client, user, user2
    ):
        thing = self._team_thing(user, user2)
        _warm_activity(authenticated_client)

        def act():
            faq = FAQFactory(thing=thing, questioner=user2)
            response, count = self._queries(
                lambda: authenticated_client.post(f"/api/v1/faq/{faq.code}/hide/")
            )
            assert response.status_code == 200
            return count

        self._assert_constant(user, thing, act, "hiding a FAQ")

    def _pending_loan(self, thing, requester, offset):
        start = date.today() + timedelta(days=10 * offset)
        return BookingPeriodFactory(
            thing_code=thing,
            requester_code=requester,
            start_date=start,
            end_date=start + timedelta(days=3),
        )

    @pytest.mark.parametrize("presser", ["owner", "co_curator"])
    def test_accepting_a_hold_in_the_app_costs_no_query_per_collection(self, user, user2, presser):
        # A co-curator has to prove they run the thing by walking its
        # collections; the owner is recognised before that.
        co_curator = UserFactory()
        thing = self._team_thing(user, user2, type=Thing.Type.LEND_THING)
        home = thing.collections.get()
        home.invites.add(co_curator)
        home.co_owners.add(co_curator)
        client = self._client_for(user if presser == "owner" else co_curator)
        bookings = iter(range(1, 10))

        def act():
            booking = self._pending_loan(thing, user2, next(bookings))
            response, count = self._queries(
                lambda: client.post(f"/api/v1/bookings/{booking.code}/accept/")
            )
            assert response.status_code == 200
            return count

        self._assert_constant(user, thing, act, "accepting a hold in the app")

    @pytest.mark.parametrize("presser", ["owner", "co_curator"])
    def test_accepting_a_hold_from_the_email_link_costs_no_query_per_collection(
        self, api_client, user, user2, presser
    ):
        # The owner's link passes the authority check without asking who runs
        # the thing; a co-curator's has to walk every collection to prove it.
        co_curator = UserFactory()
        thing = self._team_thing(user, user2, type=Thing.Type.LEND_THING)
        home = thing.collections.get()
        home.invites.add(co_curator)
        home.co_owners.add(co_curator)
        holder = user if presser == "owner" else co_curator
        bookings = iter(range(1, 10))

        def act():
            booking = self._pending_loan(thing, user2, next(bookings))
            link = RSVP.create_for_booking(RSVP.Action.BOOKING_ACCEPT, booking, holder)
            response, count = self._queries(
                lambda: api_client.post(f"/api/v1/auth/verify/{link.token}/")
            )
            assert response.status_code == 200
            return count

        self._assert_constant(user, thing, act, "accepting a hold from the email link")

    def test_refusing_an_outsider_in_the_app_costs_no_query_per_collection(self, user, user2):
        # Proving someone does NOT run a thing walks every collection it sits
        # in, so this is where a missing prefetch shows.
        thing = self._team_thing(user, user2, type=Thing.Type.LEND_THING)
        client = self._client_for(user2)
        bookings = iter(range(1, 10))

        def act():
            booking = self._pending_loan(thing, user2, next(bookings))
            response, count = self._queries(
                lambda: client.post(f"/api/v1/bookings/{booking.code}/accept/")
            )
            assert response.status_code == 403
            return count

        self._assert_constant(user, thing, act, "refusing an outsider in the app")

    def test_refusing_a_demoted_co_curators_link_costs_no_query_per_collection(
        self, api_client, user, user2
    ):
        former = UserFactory()  # was a co-curator when the email went out
        thing = self._team_thing(user, user2, former, type=Thing.Type.LEND_THING)
        bookings = iter(range(1, 10))

        def act():
            booking = self._pending_loan(thing, user2, next(bookings))
            link = RSVP.create_for_booking(RSVP.Action.BOOKING_ACCEPT, booking, former)
            response, count = self._queries(
                lambda: api_client.post(f"/api/v1/auth/verify/{link.token}/")
            )
            assert response.status_code == 403
            return count

        self._assert_constant(user, thing, act, "refusing a demoted co-curator's link")

    def test_a_decision_costs_no_query_per_collection_whoever_loaded_the_booking(self, user, user2):
        # `finalize_booking_decision` is the one place every decision converges,
        # so it does not trust its caller to have prefetched the team.
        from core.services.booking_service import finalize_booking_decision

        thing = self._team_thing(user, user2, type=Thing.Type.LEND_THING)
        bookings = iter(range(1, 10))

        def act():
            pending = self._pending_loan(thing, user2, next(bookings))
            booking = BookingPeriod.objects.get(pk=pending.pk)  # nothing prefetched
            with CaptureQueriesContext(connection) as captured:
                finalize_booking_decision(booking, accepted=True, decided_by=user)
            return len(captured)

        self._assert_constant(user, thing, act, "a decision loaded with no prefetch")

    def test_asking_for_a_loan_costs_no_query_per_collection(self, user, user2):
        thing = self._team_thing(user, user2, type=Thing.Type.LEND_THING)
        requesters = iter(UserFactory.create_batch(4))
        offsets = iter(range(1, 10))

        def act():
            requester = next(requesters)
            for group in thing.collections.all():
                group.invites.add(requester)
            client = self._client_for(requester)
            start = date.today() + timedelta(days=10 * next(offsets))
            response, count = self._queries(
                lambda: client.post(
                    f"/api/v1/things/{thing.code}/request/",
                    {"start_date": str(start), "end_date": str(start + timedelta(days=3))},
                    format="json",
                )
            )
            assert response.status_code == 201, response.data
            return count

        self._assert_constant(user, thing, act, "asking for a loan")

    def test_asking_for_a_gift_costs_no_query_per_collection(self, user, user2):
        thing = self._team_thing(user, user2, is_endless=True)
        requesters = iter(UserFactory.create_batch(4))

        def act():
            requester = next(requesters)
            for group in thing.collections.all():
                group.invites.add(requester)
            client = self._client_for(requester)
            response, count = self._queries(
                lambda: client.post(f"/api/v1/things/{thing.code}/request/", {}, format="json")
            )
            assert response.status_code == 201, response.data
            return count

        self._assert_constant(user, thing, act, "asking for a gift")

    @staticmethod
    def _reservations_collection(owner, **kwargs):
        return CollectionFactory(
            owner=owner,
            mode=Collection.Mode.PROPRIETARY,
            allowed_thing_types=["RESERVE_THING"],
            reservation_max_days=3,
            **kwargs,
        )

    def _space(self, owner, *members):
        thing = ThingFactory(owner=owner, type=Thing.Type.RESERVE_THING)
        home = self._reservations_collection(owner)
        home.invites.add(*members)
        home.things.add(thing)
        return thing

    def _grow_reservations(self, owner, thing):
        for _ in range(2):
            extra = self._reservations_collection(owner)
            also_in(extra, thing)

    def _assert_constant_reservations(self, owner, thing, act, what):
        one_collection = act()
        self._grow_reservations(owner, thing)
        three_collections = act()
        assert three_collections == one_collection, (
            f"N+1 on {what}: {one_collection} queries with one collection, "
            f"{three_collections} with three"
        )

    def test_reserving_a_space_costs_no_query_per_collection(self, user):
        thing = self._space(user)
        members = iter(UserFactory.create_batch(4))
        weeks = iter(range(1, 10))

        def act():
            member = next(members)
            for group in thing.collections.all():
                group.invites.add(member)
            client = self._client_for(member)
            start = date.today() + timedelta(weeks=next(weeks))
            response, count = self._queries(
                lambda: client.post(
                    f"/api/v1/things/{thing.code}/request/",
                    {"start_date": str(start), "duration_days": 1},
                    format="json",
                )
            )
            assert response.status_code == 201, response.data
            return count

        self._assert_constant_reservations(user, thing, act, "reserving a space")

    def test_cancelling_a_reservation_costs_no_query_per_collection(self, user):
        thing = self._space(user)
        members = iter(UserFactory.create_batch(4))
        weeks = iter(range(1, 10))

        def act():
            member = next(members)
            for group in thing.collections.all():
                group.invites.add(member)
            client = self._client_for(member)
            start = date.today() + timedelta(weeks=next(weeks))
            made = client.post(
                f"/api/v1/things/{thing.code}/request/",
                {"start_date": str(start), "duration_days": 1},
                format="json",
            )
            assert made.status_code == 201, made.data
            booking = BookingPeriod.objects.get(code=made.data["booking_code"])
            response, count = self._queries(
                lambda: client.post(f"/api/v1/bookings/{booking.code}/cancel/")
            )
            assert response.status_code == 200, response.data
            return count

        self._assert_constant_reservations(user, thing, act, "cancelling a reservation")
