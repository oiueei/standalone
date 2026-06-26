"""
Integration tests for the optional demographic profile fields (age range +
postal code).

The fields are saved on the user's own profile and exposed back through
/auth/me/. Per member they're visible only to the owner of a COMMUNITY
collection (never to non-owners, never in other modes); in aggregate they feed
any collection owner's stats CSV.
"""

from core.models import Collection

USER = "/api/v1/users/{code}/"
COLLECTION = "/api/v1/collections/{code}/"


class TestCommunityProfileFields:
    def test_update_saves_age_and_postal(self, authenticated_client, user):
        res = authenticated_client.put(
            USER.format(code=user.code),
            {"age_range": "22_35", "postal_code": "48001"},
            format="json",
        )
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.age_range == "22_35"
        assert user.postal_code == "48001"
        # Echoed back on the read serializer.
        assert res.data["age_range"] == "22_35"
        assert res.data["postal_code"] == "48001"

    def test_invalid_age_range_rejected(self, authenticated_client, user):
        res = authenticated_client.put(
            USER.format(code=user.code), {"age_range": "999"}, format="json"
        )
        assert res.status_code == 400

    def test_postal_code_rejects_html(self, authenticated_client, user):
        res = authenticated_client.put(
            USER.format(code=user.code), {"postal_code": "<b>x</b>"}, format="json"
        )
        assert res.status_code == 400

    def test_owner_sees_member_demographics_in_community(self, authenticated_client, user, user2):
        coll = Collection.objects.create(
            code="COMM02", owner=user, headline="C", mode=Collection.Mode.COMMUNITY
        )
        user2.age_range = "36_55"
        user2.postal_code = "28013"
        user2.save()
        coll.invites.add(user2)

        res = authenticated_client.get(COLLECTION.format(code=coll.code))
        assert res.status_code == 200
        member = next(m for m in res.data["invites"] if m["code"] == user2.code)
        assert member["age_range"] == "36_55"
        assert member["postal_code"] == "28013"

    def test_proprietary_owner_does_not_see_demographics(self, authenticated_client, user, user2):
        coll = Collection.objects.create(
            code="PROP01", owner=user, headline="P", mode=Collection.Mode.PROPRIETARY
        )
        user2.age_range = "36_55"
        user2.save()
        coll.invites.add(user2)

        res = authenticated_client.get(COLLECTION.format(code=coll.code))
        member = next(m for m in res.data["invites"] if m["code"] == user2.code)
        assert "age_range" not in member
        assert "postal_code" not in member

    def test_non_owner_member_does_not_see_demographics(self, authenticated_client2, user, user2):
        coll = Collection.objects.create(
            code="COMM03", owner=user, headline="C", mode=Collection.Mode.COMMUNITY
        )
        user2.age_range = "36_55"
        user2.save()
        coll.invites.add(user2)

        # user2 is a member (can view) but not the owner — gets code + name only.
        res = authenticated_client2.get(COLLECTION.format(code=coll.code))
        member = next(m for m in res.data["invites"] if m["code"] == user2.code)
        assert "age_range" not in member
        assert "postal_code" not in member
        assert "email" not in member
