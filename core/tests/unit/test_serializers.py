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
        )
        serializer = UserSerializer(user)
        data = serializer.data

        assert data["code"] == "ABC123"
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"


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

    def test_serialize_collection(self):
        """Should serialize collection with all fields."""
        user = User.objects.create(code="ABC123", email="test@example.com")
        collection = Collection.objects.create(
            code="COLL01",
            owner=user,
            headline="My Collection",
        )
        serializer = CollectionSerializer(collection)
        data = serializer.data

        assert data["code"] == "COLL01"
        assert data["headline"] == "My Collection"
        assert "theeeme" not in data


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
        user = User.objects.create(code="ABC123", email="test@example.com")
        thing = Thing.objects.create(
            code="THNG01",
            owner=user,
            headline="My Thing",
            thumbnail="oiueei/things/pic1",
        )
        serializer = ThingSerializer(thing)
        data = serializer.data

        assert data["code"] == "THNG01"
        assert data["headline"] == "My Thing"
        assert "thumbnail_url" in data

    def test_owner_name_does_not_leak_email(self):
        """L2: owner_name uses the bare name, never the email fallback — it's
        shown to co-members, so a no-name owner must not expose their address."""
        owner = User.objects.create(code="NMLES1", email="nameless@example.com", name="")
        thing = Thing.objects.create(code="THNG09", owner=owner, headline="Y")
        data = ThingSerializer(thing).data
        assert data["owner_name"] == ""
        assert "nameless@example.com" not in str(data)

    def test_owner_email_fallback_only_for_collection_owner(self):
        """On the community grid a no-name thing owner's email is shown to the
        collection owner (who already sees co-members' emails) but never to other
        members or anonymous visitors (L2)."""
        from django.contrib.auth.models import AnonymousUser
        from rest_framework.test import APIRequestFactory

        owner = User.objects.create(code="GRDOWN", email="owner@example.com", name="Owner")
        nameless = User.objects.create(code="GHOST1", email="ghost@example.com", name="")
        collection = Collection.objects.create(
            code="GRID01",
            owner=owner,
            headline="Community",
            mode=Collection.Mode.COMMUNITY,
        )
        thing = Thing.objects.create(code="GTHNG1", owner=nameless, headline="Z")
        collection.things.add(thing)

        def owner_name_seen_by(viewer):
            request = APIRequestFactory().get("/")
            request.user = viewer
            data = CollectionSerializer(collection, context={"request": request}).data
            return data["things"][0]["owner_name"]

        # The collection owner gets the email fallback for a no-name owner.
        assert owner_name_seen_by(owner) == "ghost@example.com"
        # A different member never sees the email.
        other = User.objects.create(code="OTHER1", email="other@example.com", name="Other")
        assert owner_name_seen_by(other) == ""
        # Neither does an anonymous visitor (PUBLIC collections are public-readable).
        assert owner_name_seen_by(AnonymousUser()) == ""

    def test_serialize_thing_with_collection(self):
        """Should include collection_code and collection_headline."""
        user = User.objects.create(code="OWN001", email="owner@example.com")
        thing = Thing.objects.create(
            code="THNG02",
            owner=user,
            headline="Collected Thing",
        )
        collection = Collection.objects.create(
            code="COL001",
            owner=user,
            headline="My Collection",
        )
        collection.things.add(thing)

        serializer = ThingSerializer(thing)
        data = serializer.data

        assert data["collection_code"] == "COL001"
        assert data["collection_headline"] == "My Collection"

    def test_serialize_thing_without_collection(self):
        """Should return None for collection fields when thing has no collection."""
        user = User.objects.create(code="OWN002", email="owner2@example.com")
        thing = Thing.objects.create(
            code="THNG03",
            owner=user,
            headline="Orphan Thing",
        )

        serializer = ThingSerializer(thing)
        data = serializer.data

        assert data["collection_code"] is None
        assert data["collection_headline"] is None

    def test_pending_questions_excludes_hidden_faqs(self):
        """A question the owner hid is dealt with, not pending — the badge
        must not keep nagging about it forever."""
        owner = User.objects.create(code="PQOWN1", email="pqowner@example.com")
        questioner = User.objects.create(code="PQASK1", email="pqasker@example.com")
        thing = Thing.objects.create(code="PQTH01", owner=owner, headline="Pending Q")

        visible_unanswered = FAQ.objects.create(
            thing=thing, questioner=questioner, question="Visible?", answer=""
        )
        FAQ.objects.create(thing=thing, questioner=questioner, question="Answered?", answer="Yes")
        hidden_unanswered = FAQ.objects.create(
            thing=thing,
            questioner=questioner,
            question="Hidden?",
            answer="",
            is_visible=False,
        )

        assert ThingSerializer(thing).data["pending_questions"] == 1

        # Showing the hidden one again restores it to the count.
        hidden_unanswered.is_visible = True
        hidden_unanswered.save()
        assert ThingSerializer(thing).data["pending_questions"] == 2

        # Hiding the other unanswered one drops it back out.
        visible_unanswered.is_visible = False
        visible_unanswered.save()
        assert ThingSerializer(thing).data["pending_questions"] == 1


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

    def test_valid_with_detail_fields(self):
        """Should accept availability, location, and condition."""
        serializer = ThingCreateSerializer(
            data={
                "headline": "My Thing",
                "type": "GIFT_THING",
                "availability": "IMMEDIATE",
                "location": "Helsinki",
                "condition": "GOOD",
            }
        )
        assert serializer.is_valid()

    def test_location_max_length(self):
        """Should reject location exceeding 32 characters."""
        serializer = ThingCreateSerializer(
            data={
                "headline": "My Thing",
                "type": "GIFT_THING",
                "location": "A" * 33,
            }
        )
        assert not serializer.is_valid()
        assert "location" in serializer.errors

    def test_location_rejects_html(self):
        """Should reject HTML tags in location."""
        serializer = ThingCreateSerializer(
            data={
                "headline": "My Thing",
                "type": "GIFT_THING",
                "location": "<script>alert(1)</script>",
            }
        )
        assert not serializer.is_valid()
        assert "location" in serializer.errors


@pytest.mark.django_db
class TestFAQSerializer:
    """Tests for FAQSerializer."""

    def test_serialize_faq(self):
        """Should serialize FAQ with all fields."""
        owner = User.objects.create(code="OWNER1", email="owner@example.com")
        thing = Thing.objects.create(code="THNG01", owner=owner, headline="Thing")
        questioner = User.objects.create(code="USR001", email="usr001@example.com", name="Ana")
        faq = FAQ.objects.create(
            code="FAQ001",
            thing=thing,
            questioner=questioner,
            question="Is this available?",
            answer="Yes!",
        )
        serializer = FAQSerializer(faq)
        data = serializer.data

        assert data["code"] == "FAQ001"
        assert data["question"] == "Is this available?"
        assert data["answer"] == "Yes!"
        assert data["questioner_name"] == "Ana"


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


class TestInputBounds:
    """L7: numeric/date input bounds on thing fee and booking dates."""

    def test_negative_fee_rejected(self):
        serializer = ThingCreateSerializer(
            data={"type": "SELL_THING", "headline": "X", "fee": "-5.00"}
        )
        assert not serializer.is_valid()
        assert "fee" in serializer.errors

    def test_dates_beyond_three_months_rejected(self):
        from datetime import date, timedelta

        from core.serializers.booking import ThingRequestWithDatesSerializer

        far = date.today() + timedelta(days=120)
        serializer = ThingRequestWithDatesSerializer(
            data={"start_date": str(date.today()), "end_date": str(far)}
        )
        assert not serializer.is_valid()
        assert "end_date" in serializer.errors

    def test_dates_within_three_months_accepted(self):
        from datetime import date, timedelta

        from core.serializers.booking import ThingRequestWithDatesSerializer

        soon = date.today() + timedelta(days=30)
        serializer = ThingRequestWithDatesSerializer(
            data={"start_date": str(date.today()), "end_date": str(soon)}
        )
        assert serializer.is_valid()


@pytest.mark.django_db
class TestCoMemberNameLeak:
    """L2: serializers shown to a co-member must use the bare name, never the
    display_name email fallback. Locks in the Must-Have fix for the two
    serializers that previously used display_name."""

    def test_my_booking_owner_name_does_not_leak_email(self):
        """MyBookingSerializer.owner_name is the bare owner name — a no-name
        owner's email must not reach the requester."""
        from core.models.booking import BookingPeriod
        from core.serializers import MyBookingSerializer

        owner = User.objects.create(code="OWNNML", email="owner-nameless@example.com", name="")
        requester = User.objects.create(code="REQ001", email="req@example.com", name="Req")
        thing = Thing.objects.create(code="BTH001", owner=owner, headline="Lent thing")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=owner,
        )

        data = MyBookingSerializer(booking).data
        assert data["owner_name"] == ""
        assert "owner-nameless@example.com" not in str(data)

    def test_wish_response_responder_name_does_not_leak_email(self):
        """WishResponseSerializer.responder_name is the bare name — a no-name
        responder's email must not reach the wish creator."""
        from core.models import WishResponse
        from core.serializers import WishResponseSerializer

        creator = User.objects.create(code="WCRTR1", email="creator@example.com", name="Creator")
        responder = User.objects.create(
            code="RSPNML", email="responder-nameless@example.com", name=""
        )
        wish = Thing.objects.create(
            code="WSH001", owner=creator, headline="Want X", type="WISH_THING"
        )
        response = WishResponse.objects.create(
            wish=wish,
            responder=responder,
            kind="KNOW_WHERE",
            message="Try the shop on 5th",
        )

        data = WishResponseSerializer(response).data
        assert data["responder_name"] == ""
        assert "responder-nameless@example.com" not in str(data)
