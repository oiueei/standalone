"""
Integration tests for the owner-only COMMUNITY usage-stats CSV.

Covers the owner + community gate and that the CSV carries the expected snapshot
counts and the aggregate age/postal breakdown.
"""

import csv as csvlib

from core.models import Collection, Thing, User

URL = "/api/v1/collections/{code}/stats/"


def _csv_dict(res):
    reader = csvlib.reader(res.content.decode().splitlines())
    return {row[0]: row[1] for row in reader if len(row) >= 2}


class TestCollectionStats:
    def _community(self, owner, code="COMM01"):
        return Collection.objects.create(
            code=code, owner=owner, headline="C", mode=Collection.Mode.COMMUNITY
        )

    def test_non_owner_forbidden(self, authenticated_client2, user):
        coll = self._community(user)
        res = authenticated_client2.get(URL.format(code=coll.code))
        assert res.status_code == 403

    def test_proprietary_collection_forbidden(self, authenticated_client, user):
        coll = Collection.objects.create(
            code="PROP01", owner=user, headline="P", mode=Collection.Mode.PROPRIETARY
        )
        res = authenticated_client.get(URL.format(code=coll.code))
        assert res.status_code == 403

    def test_csv_counts_and_demographics(self, authenticated_client, user, user2):
        coll = self._community(user)
        user2.age_range = "22_35"
        user2.postal_code = "48001"
        user2.save()
        m2 = User.objects.create(code="MEM002", email="m2@example.com")  # no demographics
        coll.invites.add(user2, m2)

        t1 = Thing.objects.create(
            code="TT0001", type="GIFT_THING", owner=user, headline="a", status="ACTIVE"
        )
        t2 = Thing.objects.create(
            code="TT0002", type="GIFT_THING", owner=user, headline="b", status="TAKEN"
        )
        coll.things.add(t1, t2)

        res = authenticated_client.get(URL.format(code=coll.code))
        assert res.status_code == 200
        assert res["Content-Type"].startswith("text/csv")
        assert "attachment" in res["Content-Disposition"]
        assert f"{coll.code}-stats.csv" in res["Content-Disposition"]

        data = _csv_dict(res)
        assert data["Members"] == "2"
        assert data["Things total"] == "2"
        assert data["Things active"] == "1"
        assert data["Things reserved"] == "1"
        assert data["Age 22-35"] == "1"
        assert data["Age not specified"] == "1"
        assert data["Postal 48001"] == "1"
        assert data["Postal not specified"] == "1"
