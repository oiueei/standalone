"""
Integration tests for the wish feature: creating a wish (Thing of type
WISH_THING), answering it with WishResponses, accepting an answer, resolving
the wish, and the two key notifications.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection, InAppNotification, Thing, User, WishResponse


def _client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def wish_setup(db):
    """Owner, two invitees, a stranger, a COMMUNITY collection, and a wish."""
    owner = User.objects.create(code="WSOWN4", email="wishowner@test.com", name="Owner")
    invitee = User.objects.create(code="WSINV1", email="wishinv@test.com", name="Invitee")
    invitee2 = User.objects.create(code="WSINV2", email="wishinv2@test.com", name="Invitee2")
    stranger = User.objects.create(code="WSSTR1", email="wishstr@test.com", name="Stranger")

    collection = Collection.objects.create(
        code="WSCOL1", owner=owner, headline="Neighbours", mode="COMMUNITY"
    )
    collection.invites.add(invitee, invitee2)

    wish = Thing.objects.create(
        code="WSWSH4", type="WISH_THING", owner=owner, headline="Need a drill"
    )
    collection.things.add(wish)

    return {
        "owner": owner,
        "invitee": invitee,
        "invitee2": invitee2,
        "stranger": stranger,
        "collection": collection,
        "wish": wish,
        "owner_client": _client(owner),
        "invitee_client": _client(invitee),
        "invitee2_client": _client(invitee2),
        "stranger_client": _client(stranger),
    }


@pytest.mark.django_db
class TestWishCreateBroadcast:
    def test_create_wish_notifies_group(self, wish_setup):
        s = wish_setup
        mail.outbox.clear()
        res = s["invitee_client"].post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Need a saw",
                "collection_code": s["collection"].code,
                "notify_group": True,
            },
            format="json",
        )
        assert res.status_code == 201
        # owner + invitee2 are notified; the creator (invitee) is not
        recipients = {addr for m in mail.outbox for addr in m.to}
        assert s["owner"].email in recipients
        assert s["invitee2"].email in recipients
        assert s["invitee"].email not in recipients
        notif = InAppNotification.objects.filter(
            type=InAppNotification.Type.WISH_POSTED, user=s["owner"]
        ).first()
        assert notif is not None
        # Payload carries the deep-link data (wish + collection codes).
        assert notif.payload["wish_code"] == res.data["code"]
        assert notif.payload["collection_code"] == s["collection"].code

    def test_create_wish_without_broadcast(self, wish_setup):
        s = wish_setup
        mail.outbox.clear()
        res = s["invitee_client"].post(
            "/api/v1/things/",
            {
                "type": "WISH_THING",
                "headline": "Need a saw",
                "collection_code": s["collection"].code,
                "notify_group": False,
            },
            format="json",
        )
        assert res.status_code == 201
        assert len(mail.outbox) == 0
        assert not InAppNotification.objects.filter(
            type=InAppNotification.Type.WISH_POSTED
        ).exists()


@pytest.mark.django_db
class TestWishRespond:
    def test_know_where_response(self, wish_setup):
        s = wish_setup
        mail.outbox.clear()
        res = s["invitee_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "KNOW_WHERE", "message": "Try the shop", "url": "https://example.com"},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["kind"] == "KNOW_WHERE"
        assert res.data["status"] == "PENDING"
        # the creator gets an email + in-app notification
        assert s["owner"].email in {addr for m in mail.outbox for addr in m.to}
        assert InAppNotification.objects.filter(
            type=InAppNotification.Type.WISH_RESPONSE, user=s["owner"]
        ).exists()

    def test_can_make_response(self, wish_setup):
        s = wish_setup
        res = s["invitee_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "CAN_MAKE", "message": "I can build one", "fee": "15.00"},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["fee"] == "15.00"

    def test_have_this_links_own_thing(self, wish_setup):
        s = wish_setup
        offered = Thing.objects.create(
            code="WSOFF3", type="GIFT_THING", owner=s["invitee"], headline="My drill"
        )
        s["collection"].things.add(offered)
        res = s["invitee_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "HAVE_THIS", "thing_code": offered.code},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["thing"] == offered.code
        assert res.data["thing_headline"] == "My drill"

    def test_have_this_requires_own_thing(self, wish_setup):
        s = wish_setup
        not_mine = Thing.objects.create(
            code="WSOFF4", type="GIFT_THING", owner=s["owner"], headline="Owner's drill"
        )
        res = s["invitee_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "HAVE_THIS", "thing_code": not_mine.code},
            format="json",
        )
        assert res.status_code == 400

    def test_have_this_inactive_thing_rejected(self, wish_setup):
        s = wish_setup
        hidden = Thing.objects.create(
            code="WSOFF5",
            type="GIFT_THING",
            owner=s["invitee"],
            headline="Hidden drill",
            status="INACTIVE",
        )
        s["collection"].things.add(hidden)
        res = s["invitee_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "HAVE_THIS", "thing_code": hidden.code},
            format="json",
        )
        assert res.status_code == 400

    def test_know_where_requires_message(self, wish_setup):
        s = wish_setup
        res = s["invitee_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "KNOW_WHERE"},
            format="json",
        )
        assert res.status_code == 400

    def test_owner_cannot_respond(self, wish_setup):
        s = wish_setup
        res = s["owner_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "KNOW_WHERE", "message": "x"},
            format="json",
        )
        assert res.status_code == 400

    def test_stranger_cannot_respond(self, wish_setup):
        s = wish_setup
        res = s["stranger_client"].post(
            f"/api/v1/things/{s['wish'].code}/responses/",
            {"kind": "KNOW_WHERE", "message": "x"},
            format="json",
        )
        assert res.status_code == 403

    def test_respond_to_non_wish_rejected(self, wish_setup):
        s = wish_setup
        gift = Thing.objects.create(
            code="WSGFT1", type="GIFT_THING", owner=s["owner"], headline="A gift"
        )
        s["collection"].things.add(gift)
        res = s["invitee_client"].post(
            f"/api/v1/things/{gift.code}/responses/",
            {"kind": "KNOW_WHERE", "message": "x"},
            format="json",
        )
        assert res.status_code == 400


@pytest.mark.django_db
class TestWishResponseList:
    def test_owner_sees_all_responses(self, wish_setup):
        s = wish_setup
        WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee2"], kind="CAN_MAKE", message="b"
        )
        res = s["owner_client"].get(f"/api/v1/things/{s['wish'].code}/responses/")
        assert res.status_code == 200
        assert res.data["count"] == 2

    def test_responder_sees_only_own(self, wish_setup):
        s = wish_setup
        WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee2"], kind="CAN_MAKE", message="b"
        )
        res = s["invitee_client"].get(f"/api/v1/things/{s['wish'].code}/responses/")
        assert res.status_code == 200
        assert res.data["count"] == 1
        assert res.data["results"][0]["responder"] == s["invitee"].code

    def test_stranger_cannot_list(self, wish_setup):
        s = wish_setup
        res = s["stranger_client"].get(f"/api/v1/things/{s['wish'].code}/responses/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestWishAccept:
    def test_owner_accepts_response(self, wish_setup):
        s = wish_setup
        r = WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        res = s["owner_client"].post(f"/api/v1/wish-responses/{r.code}/accept/")
        assert res.status_code == 200
        assert res.data["status"] == "ACCEPTED"
        assert InAppNotification.objects.filter(
            type=InAppNotification.Type.WISH_ACCEPTED, user=s["invitee"]
        ).exists()

    def test_non_owner_cannot_accept(self, wish_setup):
        s = wish_setup
        r = WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        res = s["invitee2_client"].post(f"/api/v1/wish-responses/{r.code}/accept/")
        assert res.status_code == 403

    def test_accepting_second_response_releases_first(self, wish_setup):
        s = wish_setup
        first = WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        second = WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee2"], kind="CAN_MAKE", message="b"
        )
        s["owner_client"].post(f"/api/v1/wish-responses/{first.code}/accept/")
        s["owner_client"].post(f"/api/v1/wish-responses/{second.code}/accept/")
        first.refresh_from_db()
        second.refresh_from_db()
        # Only one answer can be accepted at a time.
        assert first.status == "PENDING"
        assert second.status == "ACCEPTED"


@pytest.mark.django_db
class TestWishResolve:
    def test_resolve_hides_wish_and_thanks(self, wish_setup):
        s = wish_setup
        r = WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        r.accept()
        mail.outbox.clear()
        res = s["owner_client"].post(f"/api/v1/things/{s['wish'].code}/resolve/")
        assert res.status_code == 200
        s["wish"].refresh_from_db()
        assert s["wish"].status == "INACTIVE"
        # the accepted responder is thanked
        assert s["invitee"].email in {addr for m in mail.outbox for addr in m.to}

    def test_resolve_without_accepted_response(self, wish_setup):
        s = wish_setup
        mail.outbox.clear()
        res = s["owner_client"].post(f"/api/v1/things/{s['wish'].code}/resolve/")
        assert res.status_code == 200
        s["wish"].refresh_from_db()
        assert s["wish"].status == "INACTIVE"
        assert len(mail.outbox) == 0

    def test_non_owner_cannot_resolve(self, wish_setup):
        s = wish_setup
        res = s["invitee_client"].post(f"/api/v1/things/{s['wish'].code}/resolve/")
        assert res.status_code == 403

    def test_resolve_already_resolved(self, wish_setup):
        s = wish_setup
        s["wish"].status = "INACTIVE"
        s["wish"].save(update_fields=["status"])
        res = s["owner_client"].post(f"/api/v1/things/{s['wish'].code}/resolve/")
        assert res.status_code == 400


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
            {"type": "WISH_THING", "headline": "Need a hammer", "collection_code": prop_col.code},
            format="json",
        )
        assert res.status_code == 400
        assert "community" in res.data["type"].lower()

    def test_create_wish_without_collection_rejected(self, wish_setup):
        s = wish_setup
        res = s["owner_client"].post(
            "/api/v1/things/",
            {"type": "WISH_THING", "headline": "Need something"},
            format="json",
        )
        assert res.status_code == 400
        assert "community" in res.data["type"].lower()


@pytest.mark.django_db
class TestWishSerializer:
    def test_response_count_in_serializer(self, wish_setup):
        s = wish_setup
        WishResponse.objects.create(
            wish=s["wish"], responder=s["invitee"], kind="KNOW_WHERE", message="a"
        )
        res = s["invitee_client"].get(f"/api/v1/things/{s['wish'].code}/")
        assert res.status_code == 200
        assert res.data["response_count"] == 1
        assert res.data["my_response"]["kind"] == "KNOW_WHERE"

    def test_response_count_null_for_non_wish(self, wish_setup):
        s = wish_setup
        gift = Thing.objects.create(
            code="WSGF02", type="GIFT_THING", owner=s["owner"], headline="Gift"
        )
        s["collection"].things.add(gift)
        res = s["owner_client"].get(f"/api/v1/things/{gift.code}/")
        assert res.status_code == 200
        assert res.data["response_count"] is None
