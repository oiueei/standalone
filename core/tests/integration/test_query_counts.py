"""Query-count regression guards for list endpoints.

These lock in the prefetch/annotation work so a future change can't silently
reintroduce a per-thing query (N+1) on transfer_count / my_pending_booking /
the nested-things serialisation.
"""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models.transfer import ThingTransfer
from core.tests.factories import ThingFactory, ThingTransferFactory


def _make_things(owner, collection, n):
    collection.things.add(*ThingFactory.create_batch(n, owner=owner))


@pytest.mark.django_db
class TestListEndpointQueryBudgets:
    """The query count of a list/detail response must be CONSTANT in the number
    of things it serialises — adding more things must add zero queries."""

    def test_collection_detail_has_no_per_thing_queries(
        self, authenticated_client, user, collection
    ):
        url = f"/api/v1/collections/{collection.code}/"
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
