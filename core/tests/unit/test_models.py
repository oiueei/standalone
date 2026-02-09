"""
Unit tests for OIUEEI models.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import FAQ, RSVP, Collection, Theeeme, Thing, User
from core.utils import cloudinary_url, generate_id


class TestGenerateId:
    """Tests for generate_id utility."""

    def test_generate_id_length(self):
        """ID should be 6 characters."""
        id_ = generate_id()
        assert len(id_) == 6

    def test_generate_id_uppercase(self):
        """ID should be uppercase alphanumeric."""
        id_ = generate_id()
        assert id_.isupper() or id_.isdigit() or all(c.isupper() or c.isdigit() for c in id_)

    def test_generate_id_unique(self):
        """IDs should be unique (statistically)."""
        ids = [generate_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestCloudinaryUrl:
    """Tests for cloudinary_url utility."""

    def test_cloudinary_url_with_id(self):
        """Should return valid Cloudinary URL."""
        url = cloudinary_url("abc123")
        assert "cloudinary.com" in url
        assert "abc123" in url
        assert url.endswith(".png")

    def test_cloudinary_url_without_id(self):
        """Should return None for empty ID."""
        assert cloudinary_url(None) is None
        assert cloudinary_url("") is None


@pytest.mark.django_db
class TestUserModel:
    """Tests for User model."""

    def test_create_user(self):
        """Should create a user with generated ID."""
        user = User.objects.create(email="test@example.com")
        assert len(user.code) == 6
        assert user.email == "test@example.com"
        assert user.is_active is True

    def test_user_str(self):
        """Should return readable string representation."""
        user = User.objects.create(
            code="ABC123",
            email="test@example.com",
        )
        assert "ABC123" in str(user)
        assert "test@example.com" in str(user)

    def test_user_reverse_relations_empty(self):
        """User reverse relations should be empty by default."""
        user = User.objects.create(email="test@example.com")
        assert user.owned_collections.count() == 0
        assert user.invited_to_collections.count() == 0
        assert user.owned_things.count() == 0

    def test_update_last_activity(self):
        """Should update last activity date."""
        user = User.objects.create(email="test@example.com")
        old_date = user.last_activity
        user.update_last_activity()
        assert user.last_activity >= old_date

    def test_user_email_must_be_unique(self):
        """Duplicate email should raise IntegrityError."""
        from django.db import IntegrityError

        User.objects.create(email="duplicate@example.com")
        with pytest.raises(IntegrityError):
            User.objects.create(email="duplicate@example.com")

    def test_user_email_is_required(self):
        """Creating user without email should raise ValueError."""
        with pytest.raises(ValueError):
            User.objects.create_user(email=None)

    def test_optional_fields_can_be_empty(self):
        """Optional fields (headline, thumbnail, hero) default to empty strings."""
        user = User.objects.create(email="test@example.com")
        assert user.headline == ""
        assert user.thumbnail == ""
        assert user.hero == ""

    def test_optional_fields_can_be_set(self):
        """Optional fields can be populated."""
        user = User.objects.create(
            email="test@example.com",
            headline="My headline",
            thumbnail="THUMB1",
            hero="HERO01",
        )
        assert user.headline == "My headline"
        assert user.thumbnail == "THUMB1"
        assert user.hero == "HERO01"

    def test_user_created_date_persisted(self):
        """Creation date should be persisted automatically."""
        from datetime import date

        user = User.objects.create(email="test@example.com")
        assert user.created == date.today()

    def test_user_name_is_optional(self):
        """User name should default to empty string."""
        user = User.objects.create(email="test@example.com")
        assert user.name == ""


@pytest.mark.django_db
class TestRSVPModel:
    """Tests for RSVP model."""

    def test_create_rsvp(self):
        """Should create an RSVP with generated code."""
        user = User.objects.create(code="ABC123", email="test@example.com")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="test@example.com",
        )
        assert len(rsvp.code) == 6
        assert rsvp.user_email == "test@example.com"

    def test_rsvp_is_valid(self):
        """New RSVP should be valid."""
        user = User.objects.create(code="ABC123", email="test@example.com")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="test@example.com",
        )
        assert rsvp.is_valid() is True

    def test_rsvp_expired(self):
        """Old RSVP should be invalid."""
        user = User.objects.create(code="ABC123", email="test@example.com")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="test@example.com",
        )
        rsvp.created = timezone.now() - timedelta(hours=25)
        rsvp.save()
        assert rsvp.is_valid() is False


@pytest.mark.django_db
class TestTheeemeModel:
    """Tests for Theeeme model."""

    def test_create_theeeme(self):
        """Should create a theeeme with generated code."""
        theeeme = Theeeme.objects.create(
            name="BAR_CEL_ONA",
            color_01="FFCA2C",
            color_02="CB4E22",
            color_03="827F2A",
            color_04="2B9A9E",
            color_05="4F3B28",
            color_06="FFF2EB",
        )
        assert len(theeeme.code) == 6
        assert theeeme.name == "BAR_CEL_ONA"

    def test_theeeme_str(self):
        """Should return readable string representation."""
        theeeme = Theeeme.objects.create(
            code="TSTSTR",
            name="TestTheme",
            color_01="FFCA2C",
            color_02="CB4E22",
            color_03="827F2A",
            color_04="2B9A9E",
            color_05="4F3B28",
            color_06="FFF2EB",
        )
        assert "TSTSTR" in str(theeeme)
        assert "TestTheme" in str(theeeme)


@pytest.mark.django_db
class TestCollectionModel:
    """Tests for Collection model."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@example.com")

    def test_create_collection(self, default_theeeme):
        """Should create a collection with generated code."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        assert len(collection.code) == 6
        assert collection.status == "ACTIVE"
        assert collection.theeeme == default_theeeme

    def test_add_thing(self, default_theeeme):
        """Should add thing to collection."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        Thing.objects.create(code="THNG01", owner=user, headline="Thing")
        collection.add_thing("THNG01")
        assert collection.things.filter(code="THNG01").exists()

    def test_remove_thing(self, default_theeeme):
        """Should remove thing from collection."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        t1 = Thing.objects.create(code="THNG01", owner=user, headline="Thing 1")
        t2 = Thing.objects.create(code="THNG02", owner=user, headline="Thing 2")
        collection.things.add(t1, t2)
        collection.remove_thing("THNG01")
        assert not collection.things.filter(code="THNG01").exists()
        assert collection.things.filter(code="THNG02").exists()

    def test_add_invite(self, default_theeeme):
        """Should add user to invites."""
        user = self._create_user()
        User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        collection.add_invite("USR001")
        assert collection.invites.filter(code="USR001").exists()

    def test_is_owner(self, default_theeeme):
        """Should check ownership correctly."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        assert collection.is_owner("ABC123") is True
        assert collection.is_owner("XYZ789") is False

    def test_can_view(self, default_theeeme):
        """Should check view permission correctly."""
        user = self._create_user()
        invited = User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        collection.invites.add(invited)
        assert collection.can_view("ABC123") is True  # Owner
        assert collection.can_view("USR001") is True  # Invited
        assert collection.can_view("XYZ789") is False  # Neither

    def test_remove_invite(self, default_theeeme):
        """Should remove user from invites."""
        user = self._create_user()
        u1 = User.objects.create(code="USR001", email="usr001@example.com")
        u2 = User.objects.create(code="USR002", email="usr002@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        collection.invites.add(u1, u2)
        collection.remove_invite("USR001")
        assert not collection.invites.filter(code="USR001").exists()
        assert collection.invites.filter(code="USR002").exists()

    def test_is_invited(self, default_theeeme):
        """Should check if user is invited."""
        user = self._create_user()
        invited = User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        collection.invites.add(invited)
        assert collection.is_invited("USR001") is True
        assert collection.is_invited("USR002") is False
        assert collection.is_invited("ABC123") is False  # Owner is not in invites

    def test_collection_defaults(self, default_theeeme):
        """Collection things and invites should default to empty."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        assert collection.things.count() == 0
        assert collection.invites.count() == 0

    def test_collection_created_timestamp(self, default_theeeme):
        """Collection should have creation timestamp."""
        from django.utils import timezone

        user = self._create_user()
        before = timezone.now()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        after = timezone.now()
        assert before <= collection.created <= after

    def test_optional_fields_default_empty(self, default_theeeme):
        """Optional fields should default to empty strings."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        assert collection.description == ""
        assert collection.thumbnail == ""
        assert collection.hero == ""

    def test_add_thing_idempotent(self, default_theeeme):
        """Adding same thing twice should not duplicate."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        Thing.objects.create(code="THNG01", owner=user, headline="Thing")
        collection.add_thing("THNG01")
        collection.add_thing("THNG01")
        assert collection.things.filter(code="THNG01").count() == 1

    def test_add_invite_idempotent(self, default_theeeme):
        """Adding same invite twice should not duplicate."""
        user = self._create_user()
        User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            theeeme=default_theeeme,
        )
        collection.add_invite("USR001")
        collection.add_invite("USR001")
        assert collection.invites.filter(code="USR001").count() == 1


@pytest.mark.django_db
class TestThingModel:
    """Tests for Thing model."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@example.com")

    def test_create_thing(self):
        """Should create a thing with generated code."""
        user = self._create_user()
        thing = Thing.objects.create(
            owner=user,
            headline="My Thing",
        )
        assert len(thing.code) == 6
        assert thing.type == "GIFT_THING"
        assert thing.status == "ACTIVE"
        assert thing.available is True

    def test_reserve(self):
        """Should reserve thing for user."""
        user = self._create_user()
        User.objects.create(code="USR001", email="usr001@example.com")
        thing = Thing.objects.create(
            owner=user,
            headline="My Thing",
        )
        thing.reserve("USR001")
        assert thing.deal.filter(code="USR001").exists()
        assert thing.available is False

    def test_release(self):
        """Should release reservation."""
        user = self._create_user()
        reserver = User.objects.create(code="USR001", email="usr001@example.com")
        thing = Thing.objects.create(
            owner=user,
            headline="My Thing",
            available=False,
        )
        thing.deal.add(reserver)
        thing.release("USR001")
        assert not thing.deal.filter(code="USR001").exists()
        assert thing.available is True


@pytest.mark.django_db
class TestFAQModel:
    """Tests for FAQ model."""

    def _create_user(self, code="USR001"):
        return User.objects.create(code=code, email=f"{code}@example.com")

    def _create_thing(self, owner, code="THNG01"):
        return Thing.objects.create(code=code, owner=owner, headline="Thing")

    def test_create_faq(self):
        """Should create a FAQ with generated code."""
        owner = self._create_user("OWNER1")
        thing = self._create_thing(owner)
        questioner = self._create_user("USR001")
        faq = FAQ.objects.create(
            thing=thing,
            questioner=questioner,
            question="Is this available?",
        )
        assert len(faq.code) == 6
        assert faq.is_visible is True
        assert faq.answer == ""

    def test_has_answer(self):
        """Should check if answered correctly."""
        owner = self._create_user("OWNER1")
        thing = self._create_thing(owner)
        questioner = self._create_user("USR001")
        faq = FAQ.objects.create(
            thing=thing,
            questioner=questioner,
            question="Is this available?",
        )
        assert faq.has_answer() is False
        faq.set_answer("Yes it is!")
        assert faq.has_answer() is True

    def test_answer(self):
        """Should set answer correctly."""
        owner = self._create_user("OWNER1")
        thing = self._create_thing(owner)
        questioner = self._create_user("USR001")
        faq = FAQ.objects.create(
            thing=thing,
            questioner=questioner,
            question="Is this available?",
        )
        faq.set_answer("Yes it is!")
        assert faq.answer == "Yes it is!"
