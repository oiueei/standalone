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

    def test_create_collection(self):
        """Should create a collection with generated code."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        assert len(collection.code) == 6
        assert collection.status == "ACTIVE"

    def test_add_thing(self):
        """Should add thing to collection."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        Thing.objects.create(code="THNG01", owner=user, headline="Thing")
        collection.add_thing("THNG01")
        assert collection.things.filter(code="THNG01").exists()

    def test_remove_thing(self):
        """Should remove thing from collection."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        t1 = Thing.objects.create(code="THNG01", owner=user, headline="Thing 1")
        t2 = Thing.objects.create(code="THNG02", owner=user, headline="Thing 2")
        collection.things.add(t1, t2)
        collection.remove_thing("THNG01")
        assert not collection.things.filter(code="THNG01").exists()
        assert collection.things.filter(code="THNG02").exists()

    def test_add_invite(self):
        """Should add user to invites."""
        user = self._create_user()
        User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        collection.add_invite("USR001")
        assert collection.invites.filter(code="USR001").exists()

    def test_is_owner(self):
        """Should check ownership correctly."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        assert collection.is_owner("ABC123") is True
        assert collection.is_owner("XYZ789") is False

    def test_can_view(self):
        """Should check view permission correctly."""
        user = self._create_user()
        invited = User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        collection.invites.add(invited)
        assert collection.can_view("ABC123") is True  # Owner
        assert collection.can_view("USR001") is True  # Invited
        assert collection.can_view("XYZ789") is False  # Neither

    def test_remove_invite(self):
        """Should remove user from invites."""
        user = self._create_user()
        u1 = User.objects.create(code="USR001", email="usr001@example.com")
        u2 = User.objects.create(code="USR002", email="usr002@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        collection.invites.add(u1, u2)
        collection.remove_invite("USR001")
        assert not collection.invites.filter(code="USR001").exists()
        assert collection.invites.filter(code="USR002").exists()

    def test_is_invited(self):
        """Should check if user is invited."""
        user = self._create_user()
        invited = User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        collection.invites.add(invited)
        assert collection.is_invited("USR001") is True
        assert collection.is_invited("USR002") is False
        assert collection.is_invited("ABC123") is False  # Owner is not in invites

    def test_collection_defaults(self):
        """Collection things and invites should default to empty."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        assert collection.things.count() == 0
        assert collection.invites.count() == 0

    def test_collection_created_timestamp(self):
        """Collection should have creation timestamp."""
        from django.utils import timezone

        user = self._create_user()
        before = timezone.now()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        after = timezone.now()
        assert before <= collection.created <= after

    def test_optional_fields_default_empty(self):
        """Optional fields should default to empty strings."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        assert collection.description == ""
        assert collection.thumbnail == ""
        assert collection.hero == ""

    def test_add_thing_idempotent(self):
        """Adding same thing twice should not duplicate."""
        user = self._create_user()
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        Thing.objects.create(code="THNG01", owner=user, headline="Thing")
        collection.add_thing("THNG01")
        collection.add_thing("THNG01")
        assert collection.things.filter(code="THNG01").count() == 1

    def test_add_invite_idempotent(self):
        """Adding same invite twice should not duplicate."""
        user = self._create_user()
        User.objects.create(code="USR001", email="usr001@example.com")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
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

    def test_faq_str(self):
        """Should return readable string representation."""
        owner = self._create_user("OWNER1")
        thing = self._create_thing(owner)
        questioner = self._create_user("USR001")
        faq = FAQ.objects.create(
            thing=thing,
            questioner=questioner,
            question="Is this available in blue?",
        )
        result = str(faq)
        assert faq.code in result
        assert "Is this available in blue?" in result


@pytest.mark.django_db
class TestBookingPeriodModel:
    """Tests for BookingPeriod model."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@example.com")

    def _create_thing(self, owner, code="THNG01", thing_type="GIFT_THING"):
        return Thing.objects.create(code=code, owner=owner, headline="Thing", type=thing_type)

    def test_str_date_based(self):
        """Should show date range for date-based bookings."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner, thing_type="LEND_THING")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
            start_date="2026-03-01",
            end_date="2026-03-10",
        )
        result = str(booking)
        assert "2026-03-01" in result
        assert "2026-03-10" in result

    def test_str_order(self):
        """Should show delivery date for order bookings."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner, thing_type="ORDER_THING")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="ORDER_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
            delivery_date="2026-04-01",
            quantity=5,
        )
        result = str(booking)
        assert "2026-04-01" in result
        assert "x5" in result

    def test_str_standard(self):
        """Should show basic info for standard bookings."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
        )
        result = str(booking)
        assert booking.code in result
        assert thing.code in result

    def test_is_date_based(self):
        """Should identify date-based booking types."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
        )
        assert booking.is_date_based() is True
        assert booking.is_single_use() is False
        assert booking.is_repeatable() is False

    def test_is_single_use(self):
        """Should identify single-use booking types."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
        )
        assert booking.is_single_use() is True
        assert booking.is_date_based() is False
        assert booking.is_repeatable() is False

    def test_is_repeatable(self):
        """Should identify repeatable booking types."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="ORDER_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
        )
        assert booking.is_repeatable() is True
        assert booking.is_date_based() is False
        assert booking.is_single_use() is False

    def test_expire(self):
        """Should mark booking as expired."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
        )
        assert booking.status == "PENDING"
        booking.expire()
        booking.refresh_from_db()
        assert booking.status == "EXPIRED"

    def test_has_overlap_with_exclude(self):
        """Should exclude specific booking from overlap check."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner, thing_type="LEND_THING")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="req@example.com",
            owner_code=owner,
            start_date="2026-03-01",
            end_date="2026-03-10",
        )
        # Without exclude: should overlap
        assert BookingPeriod.has_overlap(thing.code, "2026-03-05", "2026-03-15") is True
        # With exclude: should not overlap
        assert (
            BookingPeriod.has_overlap(
                thing.code, "2026-03-05", "2026-03-15", exclude_booking_code=booking.code
            )
            is False
        )


@pytest.mark.django_db
class TestCollectionModelEdgeCases:
    """Tests for Collection model DoesNotExist branches."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@example.com")

    def test_collection_str(self):
        """Should return readable string representation."""
        user = self._create_user()
        collection = Collection.objects.create(owner=user, headline="My Collection")
        result = str(collection)
        assert collection.code in result
        assert "My Collection" in result

    def test_add_thing_nonexistent(self):
        """Adding nonexistent thing should silently pass."""
        user = self._create_user()
        collection = Collection.objects.create(owner=user, headline="My Collection")
        collection.add_thing("NOCODE")
        assert collection.things.count() == 0

    def test_remove_thing_nonexistent(self):
        """Removing nonexistent thing should silently pass."""
        user = self._create_user()
        collection = Collection.objects.create(owner=user, headline="My Collection")
        collection.remove_thing("NOCODE")
        assert collection.things.count() == 0

    def test_add_invite_nonexistent(self):
        """Adding nonexistent user as invite should silently pass."""
        user = self._create_user()
        collection = Collection.objects.create(owner=user, headline="My Collection")
        collection.add_invite("NOCODE")
        assert collection.invites.count() == 0

    def test_remove_invite_nonexistent(self):
        """Removing nonexistent user from invites should silently pass."""
        user = self._create_user()
        collection = Collection.objects.create(owner=user, headline="My Collection")
        collection.remove_invite("NOCODE")
        assert collection.invites.count() == 0


@pytest.mark.django_db
class TestThingModelEdgeCases:
    """Tests for Thing model DoesNotExist branches."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@example.com")

    def test_thing_str(self):
        """Should return readable string representation."""
        user = self._create_user()
        thing = Thing.objects.create(owner=user, headline="My Thing")
        result = str(thing)
        assert thing.code in result
        assert "My Thing" in result

    def test_reserve_nonexistent_user(self):
        """Reserving with nonexistent user should silently pass."""
        user = self._create_user()
        thing = Thing.objects.create(owner=user, headline="My Thing")
        thing.reserve("NOCODE")
        assert thing.deal.count() == 0
        assert thing.available is True

    def test_release_nonexistent_user(self):
        """Releasing nonexistent user should silently pass."""
        user = self._create_user()
        thing = Thing.objects.create(owner=user, headline="My Thing", available=False)
        thing.release("NOCODE")
        assert thing.available is False


@pytest.mark.django_db
class TestUserModelEdgeCases:
    """Tests for User model edge cases."""

    def test_create_superuser(self):
        """Should create a superuser."""
        user = User.objects.create_superuser(email="admin@example.com")
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_has_perm_regular_user(self):
        """Regular user should not have any perms."""
        user = User.objects.create(email="test@example.com")
        assert user.has_perm("any_perm") is False

    def test_has_perm_superuser(self):
        """Superuser should have all perms."""
        user = User.objects.create_superuser(email="admin@example.com")
        assert user.has_perm("any_perm") is True

    def test_has_module_perms_regular_user(self):
        """Regular user should not have module perms."""
        user = User.objects.create(email="test@example.com")
        assert user.has_module_perms("core") is False

    def test_has_module_perms_superuser(self):
        """Superuser should have module perms."""
        user = User.objects.create_superuser(email="admin@example.com")
        assert user.has_module_perms("core") is True


@pytest.mark.django_db
class TestRSVPModelEdgeCases:
    """Tests for RSVP model edge cases."""

    def test_rsvp_str(self):
        """Should return readable string representation."""
        user = User.objects.create(code="ABC123", email="test@example.com")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="test@example.com",
            action="COLLECTION_INVITE",
        )
        result = str(rsvp)
        assert rsvp.code in result
        assert "COLLECTION_INVITE" in result
        assert "test@example.com" in result

    def test_create_for_booking(self):
        """Should create RSVP with booking context."""
        from core.models.booking import BookingPeriod

        owner = User.objects.create(code="OWNER1", email="owner@example.com")
        requester = User.objects.create(code="REQ001", email="req@example.com")
        thing = Thing.objects.create(code="THNG01", owner=owner, headline="Thing")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=requester,
            requester_email="req@example.com",
            owner_code=owner,
        )
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, "owner@example.com")
        assert rsvp.action == "BOOKING_ACCEPT"
        assert rsvp.target_code == booking.code
        assert rsvp.user_email == "owner@example.com"
        assert rsvp.context["thing_code"] == thing.code
