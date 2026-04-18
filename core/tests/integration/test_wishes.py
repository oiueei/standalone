"""
Integration tests for WISH_THING endpoints.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, Thing, User


@pytest.fixture
def wish_setup(db):
    """Create owner, invitee, community collection, and wish thing."""
    owner = User.objects.create(code="WSOWN4", email="wishowner@test.com", name="Owner")
    invitee = User.objects.create(code="WSINV1", email="wishinv@test.com", name="Invitee")
    stranger = User.objects.create(code="WSSTR1", email="wishstr@test.com", name="Stranger")

    collection = Collection.objects.create(
        code="WSCOL1", owner=owner, headline="Neighbours", mode="COMMUNITY"
    )
    collection.invites.add(invitee)

    wish = Thing.objects.create(
        code="WSWSH4", type="WISH_THING", owner=owner, headline="Need a drill"
    )
    collection.things.add(wish)

    owner_client = APIClient()
    owner_token = RefreshToken.for_user(owner)
    owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token.access_token}")

    invitee_client = APIClient()
    invitee_token = RefreshToken.for_user(invitee)
    invitee_client.credentials(HTTP_AUTHORIZATION=f"Bearer {invitee_token.access_token}")

    stranger_client = APIClient()
    stranger_token = RefreshToken.for_user(stranger)
    stranger_client.credentials(HTTP_AUTHORIZATION=f"Bearer {stranger_token.access_token}")

    return {
        "owner": owner,
        "invitee": invitee,
        "stranger": stranger,
        "collection": collection,
        "wish": wish,
        "owner_client": owner_client,
        "invitee_client": invitee_client,
        "stranger_client": stranger_client,
    }


@pytest.mark.django_db
class TestWishOfferHelp:
    def test_invitee_can_offer_help(self, wish_setup):
        s = wish_setup
        res = s["invitee_client"].post(f"/api/v1/things/{s['wish'].code}/offer-help/")
        assert res.status_code == 200
        assert res.data["offering"] is True
        assert res.data["helper_count"] == 1

    def test_invitee_can_toggle_off(self, wish_setup):
        s = wish_setup
        s["invitee_client"].post(f"/api/v1/things/{s['wish'].code}/offer-help/")
        res = s["invitee_client"].post(f"/api/v1/things/{s['wish'].code}/offer-help/")
        assert res.status_code == 200
        assert res.data["offering"] is False
        assert res.data["helper_count"] == 0

    def test_owner_cannot_offer_help(self, wish_setup):
        s = wish_setup
        res = s["owner_client"].post(f"/api/v1/things/{s['wish'].code}/offer-help/")
        assert res.status_code == 400

    def test_stranger_cannot_offer_help(self, wish_setup):
        s = wish_setup
        res = s["stranger_client"].post(f"/api/v1/things/{s['wish'].code}/offer-help/")
        assert res.status_code == 403

    def test_offer_help_non_wish_rejected(self, wish_setup):
        s = wish_setup
        gift = Thing.objects.create(
            code="WSGFT1", type="GIFT_THING", owner=s["owner"], headline="A gift"
        )
        s["collection"].things.add(gift)
        res = s["invitee_client"].post(f"/api/v1/things/{gift.code}/offer-help/")
        assert res.status_code == 400


@pytest.mark.django_db
class TestWishHelpers:
    def test_list_helpers(self, wish_setup):
        s = wish_setup
        s["wish"].deal.add(s["invitee"])
        res = s["owner_client"].get(f"/api/v1/things/{s['wish'].code}/helpers/")
        assert res.status_code == 200
        assert res.data["helper_count"] == 1
        assert res.data["helpers"][0]["code"] == s["invitee"].code

    def test_empty_helpers(self, wish_setup):
        s = wish_setup
        res = s["owner_client"].get(f"/api/v1/things/{s['wish'].code}/helpers/")
        assert res.status_code == 200
        assert res.data["helper_count"] == 0

    def test_stranger_cannot_list(self, wish_setup):
        s = wish_setup
        res = s["stranger_client"].get(f"/api/v1/things/{s['wish'].code}/helpers/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestWishReservationGuard:
    def test_reservation_blocked_for_wish(self, wish_setup):
        s = wish_setup
        res = s["invitee_client"].post(f"/api/v1/things/{s['wish'].code}/request/")
        assert res.status_code == 400
        assert "does not support reservations" in res.data["error"]


@pytest.mark.django_db
class TestWishThingCreate:
    def test_create_wish_in_community_collection(self, wish_setup):
        s = wish_setup
        res = s["owner_client"].post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Need a saw",
                "collection_code": s["collection"].code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["type"] == "WISH_THING"

    def test_create_wish_in_proprietary_collection_rejected(self, wish_setup):
        s = wish_setup
        prop_col = Collection.objects.create(
            code="WSCOL2", owner=s["owner"], headline="Private", mode="PROPRIETARY"
        )
        res = s["owner_client"].post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Need a hammer",
                "collection_code": prop_col.code,
            },
            format="json",
        )
        assert res.status_code == 400
        assert "community" in res.data["error"].lower()

    def test_create_wish_without_collection_rejected(self, wish_setup):
        s = wish_setup
        res = s["owner_client"].post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Need something",
            },
            format="json",
        )
        assert res.status_code == 400
        assert "community" in res.data["error"].lower()

    def test_invitee_can_create_wish_in_community(self, wish_setup):
        s = wish_setup
        res = s["invitee_client"].post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Need a wrench",
                "collection_code": s["collection"].code,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["type"] == "WISH_THING"


@pytest.mark.django_db
class TestWishSerializer:
    def test_helper_count_in_serializer(self, wish_setup):
        s = wish_setup
        s["wish"].deal.add(s["invitee"])
        res = s["invitee_client"].get(f"/api/v1/things/{s['wish'].code}/")
        assert res.status_code == 200
        assert res.data["helper_count"] == 1

    def test_helper_count_null_for_non_wish(self, wish_setup):
        s = wish_setup
        gift = Thing.objects.create(
            code="WSGF02", type="GIFT_THING", owner=s["owner"], headline="Gift"
        )
        s["collection"].things.add(gift)
        res = s["owner_client"].get(f"/api/v1/things/{gift.code}/")
        assert res.status_code == 200
        assert res.data["helper_count"] is None
