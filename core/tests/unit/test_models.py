"""
Unit tests for OIUEEI models.
"""

from datetime import date, timedelta
from unittest import mock

import pytest
import time_machine
from django.utils import timezone

from core.models import FAQ, RSVP, Collection, Theeeme, Thing, User
from core.utils import asset_url, doc_asset_url, generate_id


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


class TestAssetUrl:
    """The contract every serializer leans on: a key in, a URL or None out.

    The URL itself is `core.services.storage`'s business and is tested there.
    What matters here is the None: serializers pass unset image fields straight
    through and render whatever comes back, so a helper that returned "" or a
    base URL with nothing after it would put a broken <img> on the page instead
    of no image at all.
    """

    def test_a_key_becomes_a_url_containing_it(self, settings):
        settings.MEDIA_PUBLIC_BASE_URL = "https://bucket.your-domain.test"
        assert (
            asset_url("oiueei/things/abc123")
            == "https://bucket.your-domain.test/oiueei/things/abc123"
        )

    def test_an_unset_field_has_no_url(self):
        assert asset_url(None) is None
        assert asset_url("") is None

    def test_a_document_key_resolves_the_same_way(self, settings):
        """Same answer as asset_url today; separate function, so pin both."""
        settings.MEDIA_PUBLIC_BASE_URL = "https://bucket.your-domain.test"
        assert (
            doc_asset_url("oiueei/documents/w")
            == "https://bucket.your-domain.test/oiueei/documents/w"
        )
        assert doc_asset_url("") is None


@pytest.mark.django_db
class TestUserModel:
    """Tests for User model."""

    def test_create_user(self):
        """Should create a user with generated ID."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert len(user.code) == 6
        assert user.email == "lala3@your-domain.test"
        assert user.is_active is True

    def test_user_str(self):
        """Should return readable string representation."""
        user = User.objects.create(
            code="ABC123",
            email="lala3@your-domain.test",
        )
        assert "ABC123" in str(user)
        assert "lala3@your-domain.test" in str(user)

    def test_user_reverse_relations_empty(self):
        """User reverse relations should be empty by default."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.owned_collections.count() == 0
        assert user.invited_to_collections.count() == 0
        assert user.owned_things.count() == 0

    @time_machine.travel(date(2026, 6, 15))
    def test_update_last_activity(self):
        """Should update last activity date.

        New users start with `last_activity = None` so the first verify is
        detectable as a true first login (powers the analytics `signup` event).
        Time is frozen so the assertion compares against a fixed date, not a
        ``date.today()`` re-evaluated after a possible midnight rollover.
        """
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.last_activity is None
        user.update_last_activity()
        assert user.last_activity == date(2026, 6, 15)

    @time_machine.travel(date(2026, 6, 15))
    def test_the_second_call_of_the_day_writes_nothing(self, django_assert_num_queries):
        """The column holds a date, so today's second call has the same answer.

        `MeView` calls this on every `GET /auth/me/`, and the SPA asks three or
        four times per page load — so an unconditional save is that many `UPDATE`s
        on the user row for a value that already reads correctly.
        """
        user = User.objects.create(email="lala@your-domain.test")
        user.update_last_activity()

        with django_assert_num_queries(0):
            user.update_last_activity()

        user.refresh_from_db()
        assert user.last_activity == date(2026, 6, 15)

    @time_machine.travel(date(2026, 6, 15))
    def test_a_stale_date_is_still_refreshed(self):
        """The guard skips a write that changes nothing — never one that does."""
        user = User.objects.create(email="lele@your-domain.test", last_activity=date(2026, 6, 1))

        user.update_last_activity()

        user.refresh_from_db()
        assert user.last_activity == date(2026, 6, 15)

    @time_machine.travel(date(2026, 6, 15))
    def test_a_standing_warning_is_cancelled_even_when_the_date_is_already_today(self):
        """The one case the guard must not swallow.

        Somebody warned this morning who comes back this afternoon has
        `last_activity` already set to today — but `inactivity_notified` is what
        the deletion grace period counts from, so skipping the write here would
        leave them queued for erasure after doing exactly what the email asked.
        """
        user = User.objects.create(
            email="lili@your-domain.test",
            last_activity=date(2026, 6, 15),
            inactivity_notified=date(2026, 6, 15),
        )

        user.update_last_activity()

        user.refresh_from_db()
        assert user.inactivity_notified is None
        assert user.last_activity == date(2026, 6, 15)

    def test_user_email_must_be_unique(self):
        """Duplicate email should raise IntegrityError."""
        from django.db import IntegrityError

        User.objects.create(email="lolo@your-domain.test")
        with pytest.raises(IntegrityError):
            User.objects.create(email="lolo@your-domain.test")

    def test_user_email_is_required(self):
        """Creating user without email should raise ValueError."""
        with pytest.raises(ValueError):
            User.objects.create_user(email=None)

    def test_optional_fields_can_be_empty(self):
        """Optional fields (headline) default to empty strings."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.headline == ""

    def test_optional_fields_can_be_set(self):
        """Optional fields can be populated."""
        user = User.objects.create(
            email="lala3@your-domain.test",
            headline="My headline",
        )
        assert user.headline == "My headline"

    @time_machine.travel(date(2026, 6, 15))
    def test_user_created_date_persisted(self):
        """Creation date should be persisted automatically (frozen for a stable
        assertion across midnight)."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.created == date(2026, 6, 15)

    def test_user_name_is_optional(self):
        """User name should default to empty string."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.name == ""


@pytest.mark.django_db
class TestRSVPModel:
    """Tests for RSVP model."""

    def test_create_rsvp(self):
        """Should create an RSVP with generated code."""
        user = User.objects.create(code="ABC123", email="lala3@your-domain.test")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="lala3@your-domain.test",
        )
        assert len(rsvp.code) == 6
        assert rsvp.user_email == "lala3@your-domain.test"

    def test_rsvp_is_valid(self):
        """New RSVP should be valid."""
        user = User.objects.create(code="ABC123", email="lala3@your-domain.test")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="lala3@your-domain.test",
        )
        assert rsvp.is_valid() is True

    def test_rsvp_expired(self):
        """Old RSVP should be invalid."""
        user = User.objects.create(code="ABC123", email="lala3@your-domain.test")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="lala3@your-domain.test",
        )
        rsvp.created = timezone.now() - timedelta(hours=25)
        rsvp.save()
        assert rsvp.is_valid() is False

    def test_rsvp_booking_link_outlives_24h(self):
        """A booking accept/reject link stays valid for the full 72h PENDING window
        (it used to 401 after 24h, mid-way through the booking's life)."""
        user = User.objects.create(code="ABC123", email="lala3@your-domain.test")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="lala3@your-domain.test",
            action=RSVP.Action.BOOKING_ACCEPT,
        )
        rsvp.created = timezone.now() - timedelta(hours=30)
        rsvp.save()
        assert rsvp.is_valid() is True
        rsvp.created = timezone.now() - timedelta(hours=73)
        rsvp.save()
        assert rsvp.is_valid() is False

    def test_rsvp_invite_link_outlives_24h(self):
        """A pending collection invitation lingers far beyond 24h (~30 days)."""
        user = User.objects.create(code="ABC123", email="lala3@your-domain.test")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="lala3@your-domain.test",
            action=RSVP.Action.COLLECTION_INVITE,
        )
        rsvp.created = timezone.now() - timedelta(hours=48)
        rsvp.save()
        assert rsvp.is_valid() is True

    def test_expiry_hours_for_maps_each_action(self):
        """Single source of truth for is_valid() and cleanup_rsvps."""
        assert RSVP.expiry_hours_for(RSVP.Action.MAGIC_LINK) == 24
        assert RSVP.expiry_hours_for(RSVP.Action.BOOKING_ACCEPT) == 72
        assert RSVP.expiry_hours_for(RSVP.Action.BOOKING_REJECT) == 72
        assert RSVP.expiry_hours_for(RSVP.Action.COLLECTION_INVITE) == 720
        assert RSVP.expiry_hours_for(RSVP.Action.COLLECTION_REJECT) == 720


@pytest.mark.django_db
class TestTheeemeModel:
    """Tests for Theeeme model."""

    def test_create_theeeme(self):
        """Should create a theeeme with generated code."""
        theeeme = Theeeme.objects.create(
            name="Test",
            color_01="metro",
            color_02="gold",
            color_03="tram",
            color_04="black",
            color_05="white",
        )
        assert len(theeeme.code) == 6

    def test_theeeme_str(self):
        """Should return readable string representation."""
        theeeme = Theeeme.objects.create(
            code="TSTSTR",
            name="Test Str",
            color_01="bus",
            color_02="copper",
            color_03="fog",
            color_04="black",
            color_05="white",
        )
        assert "TSTSTR" in str(theeeme)


@pytest.mark.django_db
class TestCollectionModel:
    """Tests for Collection model."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@your-domain.test")

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
        User.objects.create(code="USR001", email="lolo10@your-domain.test")
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
        invited = User.objects.create(code="USR001", email="lolo10@your-domain.test")
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
        u1 = User.objects.create(code="USR001", email="lolo10@your-domain.test")
        u2 = User.objects.create(code="USR002", email="lulu@your-domain.test")
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
        invited = User.objects.create(code="USR001", email="lolo10@your-domain.test")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
        )
        collection.invites.add(invited)
        assert collection.is_invited("USR001") is True
        assert collection.is_invited("USR002") is False
        assert collection.is_invited("ABC123") is False  # Owner is not in invites

    def test_is_curator(self):
        """Owner and co-owner are curators; a plain member or a stranger are not."""
        user = self._create_user()
        co_owner = User.objects.create(code="USR001", email="lolo10@your-domain.test")
        member = User.objects.create(code="USR002", email="lulu@your-domain.test")
        collection = Collection.objects.create(
            owner=user,
            headline="My Collection",
            mode=Collection.Mode.COMMUNITY,
        )
        collection.invites.add(co_owner, member)
        collection.co_owners.add(co_owner)
        assert collection.is_curator("ABC123") is True  # Owner
        assert collection.is_curator("USR001") is True  # Co-owner
        assert collection.is_curator("USR002") is False  # Plain member
        assert collection.is_curator("XYZ789") is False  # Stranger

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
        User.objects.create(code="USR001", email="lolo10@your-domain.test")
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
        return User.objects.create(code=code, email=f"{code}@your-domain.test")

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

    def test_reserve(self):
        """Should add user to deal M2M."""
        user = self._create_user()
        User.objects.create(code="USR001", email="lolo10@your-domain.test")
        thing = Thing.objects.create(
            owner=user,
            headline="My Thing",
        )
        thing.reserve("USR001")
        assert thing.deal.filter(code="USR001").exists()

    def test_release(self):
        """Should remove user from deal M2M."""
        user = self._create_user()
        reserver = User.objects.create(code="USR001", email="lolo10@your-domain.test")
        thing = Thing.objects.create(
            owner=user,
            headline="My Thing",
        )
        thing.deal.add(reserver)
        thing.release("USR001")
        assert not thing.deal.filter(code="USR001").exists()


@pytest.mark.django_db
class TestFAQModel:
    """Tests for FAQ model."""

    def _create_user(self, code="USR001"):
        return User.objects.create(code=code, email=f"{code}@your-domain.test")

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
        return User.objects.create(code=code, email=f"{code}@your-domain.test")

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
            requester_email="lili9@your-domain.test",
            owner_code=owner,
            start_date="2026-03-01",
            end_date="2026-03-10",
        )
        result = str(booking)
        assert "2026-03-01" in result
        assert "2026-03-10" in result

    def test_str_standard(self):
        """Should show basic info for standard bookings."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="lili9@your-domain.test",
            owner_code=owner,
        )
        result = str(booking)
        assert booking.code in result
        assert thing.code in result

    @pytest.mark.parametrize(
        "thing_type,date_based,single_use",
        [
            ("LEND_THING", True, False),
            ("RENT_THING", True, False),
            ("GIFT_THING", False, True),
            ("SELL_THING", False, True),
        ],
    )
    def test_booking_type_classification(self, thing_type, date_based, single_use):
        """is_date_based / is_single_use classify each type. The full matrix
        matters: a type wrongly in SINGLE_USE_TYPES would flip things INACTIVE
        on accept; wrongly in DATE_BASED_TYPES it would demand dates."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing_type,
            requester_code=self._create_user("REQ001"),
            requester_email="lili9@your-domain.test",
            owner_code=owner,
        )
        assert booking.is_date_based() is date_based
        assert booking.is_single_use() is single_use

    def test_expire(self):
        """Should mark booking as expired."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="lili9@your-domain.test",
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
            requester_email="lili9@your-domain.test",
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

    @pytest.mark.parametrize("units", [1, 3])
    def test_the_bookings_of_one_thing_do_not_block_another(self, units):
        """The same dates on a different thing are free, with one unit or several: a
        thing with ``units`` bookings on them is full, the other one is untouched."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        busy = self._create_thing(owner, code="BUSY01", thing_type="LEND_THING")
        other = self._create_thing(owner, code="FREE01", thing_type="LEND_THING")
        for i in range(units):
            BookingPeriod.objects.create(
                thing_code=busy,
                thing_type="LEND_THING",
                requester_code=self._create_user(f"REQ00{i}"),
                requester_email=f"lili{i}@your-domain.test",
                owner_code=owner,
                start_date="2026-03-01",
                end_date="2026-03-10",
            )

        taken = BookingPeriod.has_overlap(busy.code, "2026-03-05", "2026-03-15", units=units)
        free = BookingPeriod.has_overlap(other.code, "2026-03-05", "2026-03-15", units=units)

        assert (taken, free) == (True, False)

    def test_has_overlap_back_to_back_boundary(self):
        """Back-to-back handovers are legal: a pickup ON the return day (or a
        return ON the pickup day) does not overlap. compute_availability and
        the frontend picker both promise this — if has_overlap ever went
        inclusive, the card would offer a day the endpoint 409s."""
        from core.models.booking import BookingPeriod

        owner = self._create_user()
        thing = self._create_thing(owner, thing_type="LEND_THING")
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=self._create_user("REQ001"),
            requester_email="lili9@your-domain.test",
            owner_code=owner,
            start_date="2026-03-01",
            end_date="2026-03-10",
        )
        # Pickup on the existing booking's return day — free.
        assert BookingPeriod.has_overlap(thing.code, "2026-03-10", "2026-03-15") is False
        # Return on the existing booking's pickup day — free.
        assert BookingPeriod.has_overlap(thing.code, "2026-02-25", "2026-03-01") is False
        # One day inside either edge — taken.
        assert BookingPeriod.has_overlap(thing.code, "2026-03-09", "2026-03-15") is True
        assert BookingPeriod.has_overlap(thing.code, "2026-02-25", "2026-03-02") is True


@pytest.mark.django_db
class TestPromoteCoOwner:
    """`Collection.promote_co_owner` — the ceiling on the co-curator set, as one
    locked step. What it does with the lock is proved on PostgreSQL in
    `test_booking_row_locks.py`; these are the three answers it can give."""

    def _group(self, co_owners):
        """A group holding ``co_owners`` co-curators, and one more plain member."""
        owner = User.objects.create(code="PCOOWN", email="lala@your-domain.test")
        group = Collection.objects.create(code="PCOGRP", owner=owner, headline="Group")
        for i in range(co_owners):
            curator = User.objects.create(code=f"PCOC{i:02d}", email=f"lele{i}@your-domain.test")
            group.invites.add(curator)
            group.co_owners.add(curator)
        newcomer = User.objects.create(code="PCONEW", email="lili@your-domain.test")
        group.invites.add(newcomer)
        return group, newcomer

    def test_a_member_is_added_while_there_is_room(self):
        group, newcomer = self._group(Collection.MAX_CO_OWNERS - 1)

        result = group.promote_co_owner(newcomer)

        assert result is Collection.Promotion.ADDED
        assert group.co_owners.filter(code=newcomer.code).exists()
        assert group.co_owners.count() == Collection.MAX_CO_OWNERS

    def test_a_full_set_refuses_a_new_co_curator_and_stays_as_it_was(self):
        group, newcomer = self._group(Collection.MAX_CO_OWNERS)

        result = group.promote_co_owner(newcomer)

        assert result is Collection.Promotion.FULL
        assert not group.co_owners.filter(code=newcomer.code).exists()
        assert group.co_owners.count() == Collection.MAX_CO_OWNERS

    def test_someone_who_already_is_one_is_reported_as_such_even_at_the_ceiling(self):
        # Re-promoting grows nothing, so it must never meet the ceiling: "already"
        # and "full" are different answers, and the view notifies only on "added".
        group, _ = self._group(Collection.MAX_CO_OWNERS)
        existing = group.co_owners.first()

        result = group.promote_co_owner(existing)

        assert result is Collection.Promotion.ALREADY
        assert group.co_owners.count() == Collection.MAX_CO_OWNERS

    def test_promoting_the_same_member_twice_adds_them_once(self):
        group, newcomer = self._group(1)

        assert group.promote_co_owner(newcomer) is Collection.Promotion.ADDED
        assert group.promote_co_owner(newcomer) is Collection.Promotion.ALREADY
        assert group.co_owners.filter(code=newcomer.code).count() == 1


@pytest.mark.django_db
class TestCollectionModelEdgeCases:
    """Tests for Collection model DoesNotExist branches."""

    def _create_user(self, code="ABC123"):
        return User.objects.create(code=code, email=f"{code}@your-domain.test")

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
        return User.objects.create(code=code, email=f"{code}@your-domain.test")

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

    def test_release_nonexistent_user(self):
        """Releasing nonexistent user should silently pass."""
        user = self._create_user()
        thing = Thing.objects.create(owner=user, headline="My Thing")
        thing.release("NOCODE")
        assert thing.deal.count() == 0


@pytest.mark.django_db
class TestUserModelEdgeCases:
    """Tests for User model edge cases."""

    def test_a_collection_default_palette_only_picks_existing_codes(self):
        """C9: the default palette is drawn from the live Theeeme table, so a
        theeeme the old hardcoded list still named — but that was deleted — can
        never be assigned (which would be a dangling FK / IntegrityError)."""
        owner = User.objects.create(email="lala-owner@your-domain.test")
        # Bussi stays: it is `DEFAULT_THEEEME_CODE`, what `random_theeeme` falls back to
        # when the table is empty, so the table is never left without it.
        Theeeme.objects.exclude(code="BUU331").delete()
        Theeeme.objects.create(
            code="ZZZ999",
            name="Solo",
            color_01="bus",
            color_02="gold",
            color_03="copper",
            color_04="black",
            color_05="white",
        )
        drawn = {
            Collection.objects.create(code=f"PAL{i:03d}", owner=owner, headline="x").theeeme_id
            for i in range(40)
        }

        assert drawn <= {"BUU331", "ZZZ999"}
        assert "ZZZ999" in drawn

    def test_random_theeeme_falls_back_when_table_empty(self):
        """With no theeemes at all, fall back to the documented default code
        rather than raising (empty random.choice)."""
        from core.models.theeeme import DEFAULT_THEEEME_CODE, random_theeeme

        Theeeme.objects.all().delete()
        assert random_theeeme() == DEFAULT_THEEEME_CODE

    def test_random_theeeme_falls_back_when_table_missing(self):
        """Before migrations exist (fresh CI checkout), Django's system checks
        instantiate models and evaluate this default — it must fall back
        instead of propagating the missing-table error."""
        from django.db import OperationalError

        from core.models.theeeme import DEFAULT_THEEEME_CODE, random_theeeme

        with mock.patch.object(
            Theeeme.objects,
            "values_list",
            side_effect=OperationalError("no such table: theeemes"),
        ):
            assert random_theeeme() == DEFAULT_THEEEME_CODE

    def test_a_user_no_longer_carries_a_palette(self):
        """The theeeme and the koro are a collection's now."""
        user = User.objects.create(email="lele-nopal@your-domain.test")

        assert not hasattr(user, "theeeme")
        assert not hasattr(user, "koro")
        assert {f.name for f in User._meta.get_fields()}.isdisjoint({"theeeme", "koro"})

    def test_create_superuser(self):
        """Should create a superuser."""
        user = User.objects.create_superuser(email="lala8@your-domain.test")
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_has_perm_regular_user(self):
        """Regular user should not have any perms."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.has_perm("any_perm") is False

    def test_has_perm_superuser(self):
        """Superuser should have all perms."""
        user = User.objects.create_superuser(email="lala8@your-domain.test")
        assert user.has_perm("any_perm") is True

    def test_has_module_perms_regular_user(self):
        """Regular user should not have module perms."""
        user = User.objects.create(email="lala3@your-domain.test")
        assert user.has_module_perms("core") is False

    def test_has_module_perms_superuser(self):
        """Superuser should have module perms."""
        user = User.objects.create_superuser(email="lala8@your-domain.test")
        assert user.has_module_perms("core") is True


@pytest.mark.django_db
class TestRSVPModelEdgeCases:
    """Tests for RSVP model edge cases."""

    def test_rsvp_str(self):
        """Should return readable string representation."""
        user = User.objects.create(code="ABC123", email="lala3@your-domain.test")
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email="lala3@your-domain.test",
            action="COLLECTION_INVITE",
        )
        result = str(rsvp)
        assert rsvp.code in result
        assert "COLLECTION_INVITE" in result
        assert "lala3@your-domain.test" in result

    def test_create_for_booking(self):
        """Should create RSVP with booking context."""
        from core.models.booking import BookingPeriod

        owner = User.objects.create(code="OWNER1", email="lala1@your-domain.test")
        requester = User.objects.create(code="REQ001", email="lili9@your-domain.test")
        thing = Thing.objects.create(code="THNG01", owner=owner, headline="Thing")
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=requester,
            requester_email="lili9@your-domain.test",
            owner_code=owner,
        )
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, owner)
        assert rsvp.action == "BOOKING_ACCEPT"
        assert rsvp.target_code == booking.code
        assert rsvp.user_code_id == owner.code
        assert rsvp.user_email == "lala1@your-domain.test"
        assert rsvp.context["thing_code"] == thing.code
