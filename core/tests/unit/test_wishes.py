"""
Unit tests for WISH_THING model behaviour.
"""

import pytest

from core.models import Thing, User


@pytest.mark.django_db
class TestWishThingModel:
    def test_wish_thing_type_valid(self):
        owner = User.objects.create(code="WSOWN1", email="wowner@test.com")
        wish = Thing.objects.create(
            code="WSWSH1", type="WISH_THING", owner=owner, headline="Need a drill"
        )
        assert wish.type == "WISH_THING"

    def test_wish_help_via_deal(self):
        owner = User.objects.create(code="WSOWN2", email="wowner2@test.com")
        helper = User.objects.create(code="WSHLP1", email="helper@test.com")
        wish = Thing.objects.create(
            code="WSWSH2", type="WISH_THING", owner=owner, headline="Need a ladder"
        )
        wish.deal.add(helper)
        assert wish.deal.count() == 1
        assert wish.deal.filter(code=helper.code).exists()

    def test_wish_help_toggle(self):
        owner = User.objects.create(code="WSOWN3", email="wowner3@test.com")
        helper = User.objects.create(code="WSHLP2", email="helper2@test.com")
        wish = Thing.objects.create(
            code="WSWSH3", type="WISH_THING", owner=owner, headline="Need a blender"
        )
        wish.deal.add(helper)
        assert wish.deal.count() == 1
        wish.deal.remove(helper)
        assert wish.deal.count() == 0
