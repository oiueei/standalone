"""Query-count regression guards for list endpoints.

These lock in the prefetch/annotation work so a future change can't silently
reintroduce a per-thing query (N+1) on transfer_count / my_pending_booking /
the nested-things serialisation.
"""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models import Thing
from core.models.transfer import ThingTransfer


def _make_things(owner, collection, n, prefix):
    for i in range(n):
        thing = Thing.objects.create(
            code=f"{prefix}{i:04d}",
            type="GIFT_THING",
            owner=owner,
            headline=f"Thing {prefix}{i}",
        )
        collection.things.add(thing)


@pytest.mark.django_db
class TestListEndpointQueryBudgets:
    """The query count of a list/detail response must be CONSTANT in the number
    of things it serialises — adding more things must add zero queries."""

    def test_collection_detail_has_no_per_thing_queries(
        self, authenticated_client, user, collection
    ):
        url = f"/api/v1/collections/{collection.code}/"
        _make_things(user, collection, 2, "QA")
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        _make_things(user, collection, 4, "QB")
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200
        assert len(r2.data["things"]) == 6

        assert len(big) == len(small), (
            f"N+1 on collection detail: {len(small)} queries for 2 things, " f"{len(big)} for 6"
        )

    def test_things_list_has_no_per_thing_queries(self, authenticated_client, user, collection):
        url = "/api/v1/things/"
        _make_things(user, collection, 2, "QC")
        with CaptureQueriesContext(connection) as small:
            r1 = authenticated_client.get(url)
        assert r1.status_code == 200

        _make_things(user, collection, 4, "QD")
        with CaptureQueriesContext(connection) as big:
            r2 = authenticated_client.get(url)
        assert r2.status_code == 200

        assert len(big) == len(small), f"N+1 on things list: {len(small)} queries vs {len(big)}"

    def test_transfer_count_annotation_is_correct(
        self, authenticated_client, user, user2, collection
    ):
        """The _transfer_count annotation (Count distinct) reports the true
        per-thing transfer count through the endpoint."""
        thing = Thing.objects.create(
            code="QXFER1", type="LEND_THING", owner=user, headline="Lent thing"
        )
        collection.things.add(thing)
        ThingTransfer.objects.create(
            thing=thing, from_user=user, to_user=user2, lent_date=date.today()
        )
        ThingTransfer.objects.create(
            thing=thing, from_user=user2, to_user=user, lent_date=date.today()
        )

        r = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert r.status_code == 200
        thing_data = next(t for t in r.data["things"] if t["code"] == "QXFER1")
        assert thing_data["transfer_count"] == 2
