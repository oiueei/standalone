"""Query-count regression guards for list endpoints.

These lock in the prefetch/annotation work so a future change can't silently
reintroduce a per-thing query (N+1) on transfer_count / my_pending_booking /
the nested-things serialisation.
"""

from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models import RSVP
from core.models.transfer import ThingTransfer
from core.tests.factories import (
    BookingPeriodFactory,
    CollectionFactory,
    RSVPFactory,
    ThingFactory,
    ThingTransferFactory,
    UserFactory,
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

    def _swap_booking(self, owner, requester, collection):
        """A SWAP booking on ``owner``'s thing, requested by ``requester``, who
        offers two of their own swap things in exchange."""
        thing = ThingFactory(owner=owner, type="SWAP_THING")
        collection.things.add(thing)
        booking = BookingPeriodFactory(thing_code=thing, requester_code=requester)
        booking.offered_things.add(
            *ThingFactory.create_batch(2, owner=requester, type="SWAP_THING")
        )
        return booking

    def test_owner_bookings_constant_with_swap_offers(self, authenticated_client, user, user2):
        """owner-bookings must prefetch offered_things (not values_list per row)."""
        coll = CollectionFactory(owner=user, mode="COMMUNITY", is_swap=True)
        _warm_activity(authenticated_client)
        for _ in range(2):
            self._swap_booking(user, user2, coll)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get("/api/v1/owner-bookings/")
        assert r1.status_code == 200

        for _ in range(2):
            self._swap_booking(user, user2, coll)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get("/api/v1/owner-bookings/")
        assert r2.status_code == 200
        assert len(big) == len(small), (
            f"N+1 on owner-bookings swap offers: {len(small)} vs {len(big)}"
        )

    def test_my_bookings_constant_with_swap_offers(self, authenticated_client, user, user2):
        """my-bookings must prefetch offered_things for the requester's swaps."""
        coll = CollectionFactory(owner=user2, mode="COMMUNITY", is_swap=True)
        _warm_activity(authenticated_client)
        for _ in range(2):
            self._swap_booking(user2, user, coll)
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get("/api/v1/my-bookings/")
        assert r1.status_code == 200

        for _ in range(2):
            self._swap_booking(user2, user, coll)
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get("/api/v1/my-bookings/")
        assert r2.status_code == 200
        assert len(big) == len(small), f"N+1 on my-bookings swap offers: {len(small)} vs {len(big)}"

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

    def test_things_list_swap_count_is_memoised(self, authenticated_client, user):
        """my_swap_count_in_collection must be memoised per collection, not counted
        once per swap thing in the things list."""
        coll = CollectionFactory(owner=user, mode="COMMUNITY", is_swap=True)
        _warm_activity(authenticated_client)
        coll.things.add(*ThingFactory.create_batch(2, owner=user, type="SWAP_THING"))
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get("/api/v1/things/")
        assert r1.status_code == 200

        coll.things.add(*ThingFactory.create_batch(4, owner=user, type="SWAP_THING"))
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get("/api/v1/things/")
        assert r2.status_code == 200
        assert len(big) == len(small), f"N+1 on things-list swap count: {len(small)} vs {len(big)}"
