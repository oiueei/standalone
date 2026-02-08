"""
Pytest fixtures for OIUEEI tests.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import FAQ, RSVP, Collection, Theeeme, Thing, User


@pytest.fixture(autouse=True)
def default_theeeme(db):
    """Create the default theeeme for all tests."""
    theeeme, _ = Theeeme.objects.get_or_create(
        code="JMPA01",
        defaults={
            "name": "BAR_CEL_ONA",
            "color_01": "FFCA2C",
            "color_02": "CB4E22",
            "color_03": "827F2A",
            "color_04": "2B9A9E",
            "color_05": "4F3B28",
            "color_06": "FFF2EB",
        },
    )
    return theeeme


@pytest.fixture
def api_client():
    """Return an API client for testing."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create(
        code="TEST01",
        email="test@example.com",
        name="Test User",
    )


@pytest.fixture
def user2(db):
    """Create a second test user."""
    return User.objects.create(
        code="TEST02",
        email="test2@example.com",
        name="Test User 2",
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Return an authenticated API client."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def authenticated_client2(api_client, user2):
    """Return an authenticated API client for user2."""
    refresh = RefreshToken.for_user(user2)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def rsvp(db, user):
    """Create a test RSVP."""
    return RSVP.objects.create(
        code="RSVP01",
        user_code=user.code,
        user_email=user.email,
    )


@pytest.fixture
def theeeme(default_theeeme):
    """Return the default theeeme for tests that explicitly need it."""
    return default_theeeme


@pytest.fixture
def collection(db, user, theeeme):
    """Create a test collection."""
    coll = Collection.objects.create(
        code="COLL01",
        owner=user.code,
        headline="Test Collection",
        theeeme=theeeme,
    )
    user.own_collections.append(coll.code)
    user.save()
    return coll


@pytest.fixture
def thing(db, user, collection):
    """Create a test thing."""
    t = Thing.objects.create(
        code="THNG01",
        type="GIFT_THING",
        owner=user.code,
        headline="Test Thing",
    )
    user.things.append(t.code)
    user.save()
    collection.add_thing(t.code)
    return t


@pytest.fixture
def faq(db, user2, thing):
    """Create a test FAQ."""
    f = FAQ.objects.create(
        code="FAQ001",
        thing=thing.code,
        questioner=user2.code,
        question="Is this available?",
    )
    thing.add_faq(f.code)
    return f
