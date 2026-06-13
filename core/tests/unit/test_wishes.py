"""
Unit tests for the wish feature (a Thing of type WISH_THING) and its
WishResponse answers.
"""

import pytest

from core.models import Thing, User, WishResponse


@pytest.mark.django_db
class TestWishThingModel:
    def test_wish_thing_type_valid(self):
        owner = User.objects.create(code="WSOWN1", email="wowner@test.com")
        wish = Thing.objects.create(
            code="WSWSH1", type="WISH_THING", owner=owner, headline="Need a drill"
        )
        assert wish.type == "WISH_THING"


@pytest.mark.django_db
class TestWishResponseModel:
    def _wish(self):
        owner = User.objects.create(code="WSOWN2", email="wowner2@test.com")
        return Thing.objects.create(
            code="WSWSH2", type="WISH_THING", owner=owner, headline="Need a ladder"
        )

    def test_create_know_where_response(self):
        wish = self._wish()
        responder = User.objects.create(code="WSRES1", email="res1@test.com")
        r = WishResponse.objects.create(
            wish=wish,
            responder=responder,
            kind=WishResponse.Kind.KNOW_WHERE,
            message="The hardware shop on Main St",
            url="https://example.com",
        )
        assert r.status == WishResponse.Status.PENDING
        assert wish.responses.count() == 1
        assert r.is_responder(responder.code)
        assert not r.is_responder("NOBODY")

    def test_create_have_this_links_thing(self):
        wish = self._wish()
        responder = User.objects.create(code="WSRES2", email="res2@test.com")
        offered = Thing.objects.create(
            code="WSOFF1", type="GIFT_THING", owner=responder, headline="A spare ladder"
        )
        r = WishResponse.objects.create(
            wish=wish,
            responder=responder,
            kind=WishResponse.Kind.HAVE_THIS,
            thing=offered,
        )
        assert r.thing == offered
        assert offered.offered_in_responses.count() == 1

    def test_accept_sets_status(self):
        wish = self._wish()
        responder = User.objects.create(code="WSRES3", email="res3@test.com")
        r = WishResponse.objects.create(
            wish=wish,
            responder=responder,
            kind=WishResponse.Kind.CAN_MAKE,
            message="I can build it",
        )
        r.accept()
        r.refresh_from_db()
        assert r.status == WishResponse.Status.ACCEPTED

    def test_offered_thing_set_null_on_delete(self):
        wish = self._wish()
        responder = User.objects.create(code="WSRES4", email="res4@test.com")
        offered = Thing.objects.create(
            code="WSOFF2", type="GIFT_THING", owner=responder, headline="Drill"
        )
        r = WishResponse.objects.create(
            wish=wish, responder=responder, kind=WishResponse.Kind.HAVE_THIS, thing=offered
        )
        offered.delete()
        r.refresh_from_db()
        assert r.thing is None  # SET_NULL keeps the response alive
