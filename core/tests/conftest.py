"""
Pytest fixtures for OIUEEI tests.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import FAQ, RSVP, Collection, Theeeme, Thing, User


@pytest.fixture(autouse=True)
def default_theeeme(db):
    """Create the default theeemes for all tests."""
    hds, _ = Theeeme.objects.get_or_create(
        code="BUU331",
        defaults={
            "name": "Bussi",
            "color_01": "bus",
            "color_02": "suomenlinna-light",
            "color_03": "copper",
            "color_04": "black",
            "color_05": "white",
        },
    )
    Theeeme.objects.get_or_create(
        code="JMPA01",
        defaults={
            "name": "JMPA01",
            "color_01": "metro",
            "color_02": "gold",
            "color_03": "tram",
            "color_04": "black",
            "color_05": "white",
        },
    )
    return hds


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
        # Explicit so the fixtures don't flip when the notify_news model default
        # changes (Cat. 3/news is opt-in for real new users — DESIGN §6).
        notify_news=True,
    )


@pytest.fixture
def user2(db):
    """Create a second test user."""
    return User.objects.create(
        code="TEST02",
        email="test2@example.com",
        name="Test User 2",
        notify_news=True,
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
        user_code=user,
        user_email=user.email,
    )


@pytest.fixture
def theeeme(default_theeeme):
    """Return the default theeeme for tests that explicitly need it."""
    return default_theeeme


@pytest.fixture
def collection(db, user):
    """Create a test collection."""
    coll = Collection.objects.create(
        code="COLL01",
        owner=user,
        headline="Test Collection",
    )
    return coll


@pytest.fixture
def thing(db, user, collection):
    """Create a test thing."""
    t = Thing.objects.create(
        code="THNG01",
        type="GIFT_THING",
        owner=user,
        headline="Test Thing",
    )
    collection.things.add(t)
    return t


@pytest.fixture
def faq(db, user2, thing):
    """Create a test FAQ."""
    f = FAQ.objects.create(
        code="FAQ001",
        thing=thing,
        questioner=user2,
        question="Is this available?",
    )
    return f
