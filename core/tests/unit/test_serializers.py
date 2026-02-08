"""
Unit tests for OIUEEI serializers.
"""

import pytest

from core.models import FAQ, Collection, Thing, User
from core.serializers import (
    CollectionCreateSerializer,
    CollectionSerializer,
    FAQCreateSerializer,
    FAQSerializer,
    RequestLinkSerializer,
    ThingCreateSerializer,
    ThingSerializer,
    UserPublicSerializer,
    UserSerializer,
)


class TestRequestLinkSerializer:
    """Tests for RequestLinkSerializer."""

    def test_valid_email(self):
        """Should accept valid email."""
        serializer = RequestLinkSerializer(data={"email": "test@example.com"})
        assert serializer.is_valid()
        assert serializer.validated_data["email"] == "test@example.com"

    def test_invalid_email(self):
        """Should reject invalid email."""
        serializer = RequestLinkSerializer(data={"email": "not-an-email"})
        assert not serializer.is_valid()
        assert "email" in serializer.errors


@pytest.mark.django_db
class TestUserSerializer:
    """Tests for UserSerializer."""

    def test_serialize_user(self):
        """Should serialize user with all fields."""
        user = User.objects.create(
            code="ABC123",
            email="test@example.com",
            name="Test User",
            thumbnail="thumb123",
        )
        serializer = UserSerializer(user)
        data = serializer.data

        assert data["code"] == "ABC123"
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["thumbnail_url"] is not None
        assert "cloudinary" in data["thumbnail_url"]


@pytest.mark.django_db
class TestUserPublicSerializer:
    """Tests for UserPublicSerializer."""

    def test_serialize_public_user(self):
        """Should serialize only public fields."""
        user = User.objects.create(
            code="ABC123",
            email="test@example.com",
            name="Test User",
        )
        serializer = UserPublicSerializer(user)
        data = serializer.data

        assert data["code"] == "ABC123"
        assert data["name"] == "Test User"
        assert "email" not in data


@pytest.mark.django_db
class TestCollectionSerializer:
    """Tests for CollectionSerializer."""

    def test_serialize_collection(self, default_theeeme):
        """Should serialize collection with all fields."""
        collection = Collection.objects.create(
            code="COLL01",
            owner="ABC123",
            headline="My Collection",
            thumbnail="thumb123",
            theeeme=default_theeeme,
        )
        serializer = CollectionSerializer(collection)
        data = serializer.data

        assert data["code"] == "COLL01"
        assert data["headline"] == "My Collection"
        assert data["thumbnail_url"] is not None
        assert data["theeeme"] == "JMPA01"


class TestCollectionCreateSerializer:
    """Tests for CollectionCreateSerializer."""

    def test_valid_collection(self):
        """Should accept valid collection data (theeeme is optional)."""
        serializer = CollectionCreateSerializer(
            data={
                "headline": "My Collection",
            }
        )
        assert serializer.is_valid()

    @pytest.mark.django_db
    def test_valid_collection_with_theeeme(self, default_theeeme):
        """Should accept valid collection data with theeeme."""
        serializer = CollectionCreateSerializer(
            data={
                "headline": "My Collection",
                "theeeme": default_theeeme.code,
            }
        )
        assert serializer.is_valid()

    def test_missing_headline(self):
        """Should reject missing headline."""
        serializer = CollectionCreateSerializer(data={})
        assert not serializer.is_valid()
        assert "headline" in serializer.errors


@pytest.mark.django_db
class TestThingSerializer:
    """Tests for ThingSerializer."""

    def test_serialize_thing(self):
        """Should serialize thing with all fields."""
        thing = Thing.objects.create(
            code="THNG01",
            owner="ABC123",
            headline="My Thing",
            pictures=["pic1", "pic2"],
        )
        serializer = ThingSerializer(thing)
        data = serializer.data

        assert data["code"] == "THNG01"
        assert data["headline"] == "My Thing"
        assert len(data["pictures_urls"]) == 2


class TestThingCreateSerializer:
    """Tests for ThingCreateSerializer."""

    def test_valid_thing(self):
        """Should accept valid thing data."""
        serializer = ThingCreateSerializer(
            data={
                "headline": "My Thing",
                "type": "GIFT_THING",
            }
        )
        assert serializer.is_valid()

    def test_missing_headline(self):
        """Should reject missing headline."""
        serializer = ThingCreateSerializer(data={"type": "GIFT_THING"})
        assert not serializer.is_valid()


@pytest.mark.django_db
class TestFAQSerializer:
    """Tests for FAQSerializer."""

    def test_serialize_faq(self):
        """Should serialize FAQ with all fields."""
        faq = FAQ.objects.create(
            code="FAQ001",
            thing="THNG01",
            questioner="USR001",
            question="Is this available?",
            answer="Yes!",
        )
        serializer = FAQSerializer(faq)
        data = serializer.data

        assert data["code"] == "FAQ001"
        assert data["question"] == "Is this available?"
        assert data["answer"] == "Yes!"


class TestFAQCreateSerializer:
    """Tests for FAQCreateSerializer."""

    def test_valid_faq(self):
        """Should accept valid FAQ data."""
        serializer = FAQCreateSerializer(data={"question": "Is this available?"})
        assert serializer.is_valid()

    def test_missing_question(self):
        """Should reject missing question."""
        serializer = FAQCreateSerializer(data={})
        assert not serializer.is_valid()
