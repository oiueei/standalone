"""
The two data-portability exports — and everything they must never carry.

The positive half of this file is bookkeeping: the tree has the keys it claims,
and ``_manifest.counts`` matches the database. The negative half is the reason
the module exists. An export is a file people email to themselves, forward to a
lawyer and leave on a laptop, so each of these is a real incident rehearsed:

- a ``share_token`` in the bytes is somebody's group handed over with the file;
- an ``RSVP.token`` is somebody's account;
- a co-member's email from a group you merely joined is a leak of a roster that
  was never yours;
- a member's postal code out of a PROPRIETARY group is the guests page's
  COMMUNITY gate quietly bypassed;
- a report against your things is the anonymity the whole feature promises.

Most are asserted against the **raw bytes**, not the tree: a refactor that moves
a value to a new key still fails them.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models import (
    FAQ,
    RSVP,
    BookingPeriod,
    Collection,
    DailyActivity,
    Event,
    InAppNotification,
    InvitationProposal,
    Report,
    Thing,
    ThingTransfer,
    User,
)
from core.services.export_service import (
    ACCOUNT_FORMAT,
    COLLECTION_FORMAT,
    README_TEXTS,
    build_account_export,
    build_collection_export,
    collection_stats_rows,
    export_bytes,
    export_filename,
)
from core.tests.factories import also_in
from core.utils import parse_localized

pytestmark = pytest.mark.django_db

LOCALIZED_HEADLINE = '{"es": "Las cosas de mamá", "ca": "Les coses de mama"}'


@pytest.fixture
def stranger(db):
    """Somebody who shares a group with the exporter but has no dealings with them."""
    return User.objects.create(code="STRN01", email="lolo7@your-domain.test", name="Stranger")


@pytest.fixture
def world(user, user2, stranger):
    """One person's whole life in OIUEEI, small enough to assert on.

    ``user`` owns a COMMUNITY group that ``user2`` belongs to; ``user2`` owns
    another group that ``user`` was invited to, alongside ``stranger``. That
    second group is what makes the "only where you already see it" rule testable
    — ``stranger``'s email must not appear anywhere in ``user``'s export.
    """
    mine = Collection.objects.create(
        code="MINE01",
        owner=user,
        headline=LOCALIZED_HEADLINE,
        description="Everything mum lends out",
        mode=Collection.Mode.COMMUNITY,
        share_token="sh4re-t0ken-01",
        thumbnail="collections/mine",
        welcome_doc="docs/welcome",
        tags=["tools", "kitchen"],
    )
    mine.invites.add(user2)
    User.objects.filter(pk=user2.pk).update(age_range="GEN_X", postal_code="08001")
    user2.refresh_from_db()

    theirs = Collection.objects.create(
        code="THRS01", owner=user2, headline="Their group", share_token="sh4re-t0ken-02"
    )
    theirs.invites.add(user, stranger)

    elsewhere = Collection.objects.create(code="ELSE01", owner=stranger, headline="Somewhere else")

    my_thing = Thing.objects.create(
        code="MYTH01",
        owner=user,
        headline="My drill",
        description="Works fine",
        type=Thing.Type.LEND_THING,
        fee=Decimal("12.50"),
        gallery=["things/one", "things/two"],
        tags=["tools"],
    )
    member_thing = Thing.objects.create(
        code="MBTH01",
        owner=user2,
        headline="Their ladder",
        description="Four steps, aluminium",
        type=Thing.Type.LEND_THING,
    )
    mine.things.add(my_thing, member_thing)
    their_thing = Thing.objects.create(code="THTH01", owner=user2, headline="Their tent")
    theirs.things.add(their_thing)

    received = BookingPeriod.objects.create(
        code="BKIN01",
        thing_code=my_thing,
        thing_type=my_thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
    )
    BookingPeriod.objects.create(
        code="BKOU01",
        thing_code=their_thing,
        thing_type=their_thing.type,
        requester_code=user,
        requester_email=user.email,
        owner_code=user2,
    )

    FAQ.objects.create(code="FAQIN1", thing=my_thing, questioner=user2, question="Does it work?")
    FAQ.objects.create(code="FAQOU1", thing=their_thing, questioner=user, question="How big?")

    ThingTransfer.objects.create(
        code="TRNS01",
        thing=my_thing,
        from_user=user,
        to_user=user2,
        lent_date=date(2026, 7, 1),
        booking=received,
    )
    # The hop whose other end deleted their account (SET_NULL).
    ThingTransfer.objects.create(
        code="TRNS02", thing=my_thing, from_user=user, to_user=None, lent_date=date(2026, 6, 1)
    )

    InvitationProposal.objects.create(
        code="PRPMD1",
        collection=theirs,
        proposer=user,
        email="lele15@your-domain.test",
        note="She would love this",
    )
    InvitationProposal.objects.create(
        code="PRPRC1", collection=mine, proposer=user2, email="lala@your-domain.test"
    )

    InAppNotification.objects.create(
        code="NOTI01", user=user, type="BOOKING_REQUESTED", payload={"booking_code": "BKIN01"}
    )

    # One report *about* my thing (must never surface) and one *by* me (must).
    Report.objects.create(
        code="RPTAG1", thing=my_thing, thing_headline=my_thing.headline, reporter=user2
    )
    Report.objects.create(
        code="RPTBY1", thing=their_thing, thing_headline=their_thing.headline, reporter=user
    )

    DailyActivity.objects.create(code="DAY001", user=user, date=date(2026, 8, 20))
    Event.objects.create(
        code="EVNT01", kind=Event.Kind.THING_ADDED, actor_code=user.code, thing_code=my_thing.code
    )
    Event.objects.create(
        code="EVNT02",
        kind=Event.Kind.THING_ADDED,
        actor_code=user2.code,
        thing_code=member_thing.code,
    )

    RSVP.objects.create(
        code="RSVIN1",
        user_code=stranger,
        user_email="lili2@your-domain.test",
        action=RSVP.Action.COLLECTION_INVITE,
        target_code=mine.code,
        token="pending-invite-token-01",
    )
    RSVP.objects.create(
        code="RSVME1",
        user_code=user,
        user_email=user.email,
        action=RSVP.Action.COLLECTION_INVITE,
        target_code=elsewhere.code,
        token="my-pending-invite-token",
    )
    return {
        "mine": mine,
        "theirs": theirs,
        "elsewhere": elsewhere,
        "my_thing": my_thing,
        "member_thing": member_thing,
        "their_thing": their_thing,
    }


class TestAccountExportShape:
    def test_manifest_indexes_every_key_that_holds_rows(self, user, world):
        payload = build_account_export(user)

        assert payload["_manifest"]["format"] == ACCOUNT_FORMAT
        assert payload["_manifest"]["user_code"] == user.code
        # `profile` is the one data key with nothing to count — it is you, not a
        # list of anything. Every other key is in the index.
        assert set(payload) - {"_manifest", "_readme", "profile"} == set(
            payload["_manifest"]["counts"]
        )

    def test_counts_match_what_is_in_the_file(self, user, world):
        payload = build_account_export(user)
        counts = payload["_manifest"]["counts"]

        assert counts["collections_owned"] == len(payload["collections_owned"]) == 1
        assert counts["things"] == len(payload["things"]) == 1
        assert counts["bookings"] == {"requested_by_me": 1, "received_by_me": 1}
        assert counts["faqs"] == {"asked_by_me": 1, "on_my_things": 1}
        assert counts["collections_member_of"] == {"joined": 1, "pending_invitations": 1}
        assert counts["activity"] == {"days": 1, "events": 1}

    def test_counts_match_the_database(self, user, world):
        counts = build_account_export(user)["_manifest"]["counts"]

        assert counts["collections_owned"] == user.owned_collections.count()
        assert counts["things"] == user.owned_things.count()
        assert counts["transfers"] == user.transfers_out.count() + user.transfers_in.count()
        assert counts["notifications"] == user.inbox_notifications.count()
        assert counts["proposals_made"] == user.invitation_proposals.count()

    def test_profile_carries_the_account_but_not_the_credentials_or_the_staff_flags(
        self, user, world
    ):
        profile = build_account_export(user)["profile"]

        assert profile["code"] == user.code
        assert profile["email"] == user.email
        assert not {"theeeme", "koro"} & set(profile)
        assert not {"password", "is_staff", "is_superuser", "is_active"} & set(profile)

    def test_a_thing_carries_its_photos_as_urls_and_its_price_as_a_decimal_string(
        self, user, world
    ):
        thing = build_account_export(user)["things"][0]

        assert thing["code"] == "MYTH01"
        # A float would round a price; the export says exactly what was charged.
        assert thing["fee"] == "12.50"
        assert len(thing["gallery_urls"]) == 2
        assert all(url.startswith("http") for url in thing["gallery_urls"])
        assert thing["collection_codes"] == ["MINE01"]

    def test_a_booking_names_its_counterpart_but_never_their_email(self, user, world):
        bookings = build_account_export(user)["bookings"]

        received = bookings["received_by_me"][0]
        assert received["requester"] == {"code": "TEST02", "name": "Test User 2"}
        assert "requester_email" not in received
        assert bookings["requested_by_me"][0]["owner"] == {"code": "TEST02", "name": "Test User 2"}


class TestTheContactPhoneLeftWhenBooking:
    """The phone is the booker's own data (right of access), but it is promised to be seen
    only by whoever manages the booking and gone the day after: a downloaded file is not
    deleted, so only the booker's own copy carries it."""

    PHONE = "600123456"

    def _phones(self, **by_code):
        for code, phone in by_code.items():
            BookingPeriod.objects.filter(code=code).update(contact_phone=phone)

    def test_the_one_who_booked_gets_it_in_what_they_requested(self, user, world):
        self._phones(BKOU01=self.PHONE)

        requested = build_account_export(user)["bookings"]["requested_by_me"]

        assert requested[0]["code"] == "BKOU01"
        assert requested[0]["contact_phone"] == self.PHONE

    def test_it_reads_empty_once_the_purge_has_emptied_it(self, user, world):
        requested = build_account_export(user)["bookings"]["requested_by_me"]

        assert requested[0]["contact_phone"] == ""

    def test_whoever_manages_the_booking_does_not_get_it_in_their_copy(self, user2, world):
        self._phones(BKOU01=self.PHONE)  # booked by `user` on a thing of `user2`

        received = build_account_export(user2)["bookings"]["received_by_me"]

        assert [b["code"] for b in received] == ["BKOU01"]
        assert "contact_phone" not in received[0]
        assert self.PHONE not in json.dumps(build_account_export(user2))

    def test_the_groups_copy_does_not_carry_it_either(self, user, world):
        self._phones(BKIN01=self.PHONE)

        payload = build_collection_export(world["mine"])

        assert [b["code"] for b in payload["bookings"]] == ["BKIN01"]
        assert "contact_phone" not in payload["bookings"][0]
        assert self.PHONE not in json.dumps(payload)


class TestAccountExportOmissions:
    def test_share_tokens_never_reach_the_bytes(self, user, world):
        raw = export_bytes(build_account_export(user))

        # Both the token of the group they own and of the one they joined.
        assert b"sh4re-t0ken-01" not in raw
        assert b"sh4re-t0ken-02" not in raw
        assert b"share_token" not in raw

    def test_rsvp_tokens_never_reach_the_bytes(self, user, world):
        raw = export_bytes(build_account_export(user))

        # Their own pending invitation and one they can see as an owner: an
        # invitation token is whoever holds it.
        assert b"my-pending-invite-token" not in raw
        assert b"pending-invite-token-01" not in raw

    def test_a_members_email_rides_along_in_a_group_you_own(self, user, world):
        owned = build_account_export(user)["collections_owned"][0]

        # The same list the guests page already shows this owner.
        assert owned["members"] == [
            {"code": "TEST02", "name": "Test User 2", "email": "lolo2@your-domain.test"}
        ]
        assert owned["pending_invitations"] == [
            {
                "email": "lili2@your-domain.test",
                "created": owned["pending_invitations"][0]["created"],
            }
        ]

    def test_a_co_members_email_stays_out_of_a_group_you_merely_joined(self, user, world):
        payload = build_account_export(user)
        joined = payload["collections_member_of"]["joined"][0]

        assert joined["code"] == "THRS01"
        assert joined["member_count"] == 2
        assert "members" not in joined
        # Stranger shares that group with them and appears nowhere.
        assert b"lolo7@your-domain.test" not in export_bytes(payload)

    def test_another_members_demographics_stay_out_of_the_account_copy(self, user, world):
        raw = export_bytes(build_account_export(user))

        assert b"08001" not in raw
        assert b"GEN_X" not in raw

    def test_a_members_thing_is_a_title_and_a_name_not_a_record(self, user, world):
        things = build_account_export(user)["collections_owned"][0]["things"]

        member_thing = next(t for t in things if t["code"] == "MBTH01")
        assert member_thing == {
            "code": "MBTH01",
            "headline": "Their ladder",
            "owner_code": "TEST02",
            "owner_name": "Test User 2",
            "is_mine": False,
        }
        # The full record of somebody else's thing is the collection copy's job.
        assert b"Four steps, aluminium" not in export_bytes(build_account_export(user))

    def test_reports_about_your_things_stay_anonymous_the_ones_you_filed_do_not(self, user, world):
        payload = build_account_export(user)

        assert [r["code"] for r in payload["reports_filed"]] == ["RPTBY1"]
        assert b"RPTAG1" not in export_bytes(payload)

    def test_only_your_own_events_come_out(self, user, world):
        activity = build_account_export(user)["activity"]

        assert activity["days"] == ["2026-08-20"]
        assert [e["thing_code"] for e in activity["events"]] == ["MYTH01"]

    def test_a_handover_whose_counterpart_deleted_their_account_exports_null(self, user, world):
        transfers = build_account_export(user)["transfers"]

        orphan = next(t for t in transfers if t["code"] == "TRNS02")
        assert orphan["counterpart"] is None
        assert orphan["direction"] == "out"
        assert orphan["thing"]["headline"] == "My drill"

    def test_owner_text_survives_as_the_map_the_owner_wrote(self, user, world):
        headline = build_account_export(user)["collections_owned"][0]["headline"]

        # Resolving here would silently drop two thirds of what they wrote.
        assert parse_localized(headline) == {
            "es": "Las cosas de mamá",
            "ca": "Les coses de mama",
        }


class TestCollectionExport:
    def test_the_owner_gets_the_whole_group_things_of_others_included(self, user, world):
        payload = build_collection_export(world["mine"])

        assert payload["_manifest"]["format"] == COLLECTION_FORMAT
        assert payload["_manifest"]["collection_code"] == "MINE01"
        member_thing = next(t for t in payload["things"] if t["code"] == "MBTH01")
        assert member_thing["is_mine"] is False
        assert member_thing["description"] == "Four steps, aluminium"
        assert member_thing["owner"] == {"code": "TEST02", "name": "Test User 2"}
        assert payload["_manifest"]["counts"]["things"] == 2

    def test_a_community_group_carries_its_members_demographics(self, user, world):
        payload = build_collection_export(world["mine"])

        assert payload["members"] == [
            {
                "code": "TEST02",
                "name": "Test User 2",
                "email": "lolo2@your-domain.test",
                "age_range": "GEN_X",
                "postal_code": "08001",
            }
        ]

    def test_any_other_mode_never_does(self, user, user2):
        # The mirror of the test above, asserted on the bytes: a positive test
        # alone would let a refactor leak the PROPRIETARY case in silence.
        private = Collection.objects.create(
            code="PRIV01", owner=user, headline="Private group", mode=Collection.Mode.PROPRIETARY
        )
        private.invites.add(user2)
        User.objects.filter(pk=user2.pk).update(age_range="GEN_X", postal_code="08001")

        payload = build_collection_export(private)
        assert payload["members"] == [
            {"code": "TEST02", "name": "Test User 2", "email": "lolo2@your-domain.test"}
        ]
        raw = export_bytes(payload)
        assert b"age_range" not in raw
        assert b"postal_code" not in raw
        assert b"GEN_X" not in raw
        # Nor does the aggregate inside `stats` name them: a code or a bracket
        # fewer than three members share is summed into "other", so in a group
        # this small the one member's postal code is not in the file at all.
        assert "Postal 08001" not in payload["stats"]
        assert payload["stats"]["Postal, other codes"] == 1
        assert b"08001" not in raw

    @pytest.mark.parametrize("mode", Collection.Mode.values)
    def test_the_export_shows_an_owner_exactly_what_the_guests_page_does(
        self, user, user2, mode, api_client
    ):
        """The invariant the shared row shape exists for.

        These were two loops in two files — `CollectionSerializer.get_invites`
        and `_collection_members` — that happened to agree. Nothing made them
        agree, and the direction they drift in is the dangerous one: the export
        is a file, so a mode gate the API applies and the export forgets is a
        leak that leaves the building. Asserting the two answers are *the same
        object* is stronger than asserting each is right, and it is the assertion
        that survives a third caller being added.
        """
        group = Collection.objects.create(
            code="SAME01", owner=user, headline="Same rules", mode=mode
        )
        group.invites.add(user2)
        User.objects.filter(pk=user2.pk).update(age_range="GEN_X", postal_code="08001")

        api_client.force_authenticate(user=user)
        from_api = api_client.get(f"/api/v1/collections/{group.code}/").data["invites"]
        from_export = build_collection_export(Collection.objects.get(code=group.code))["members"]

        assert from_export == from_api, f"the two owner views disagree in {mode} mode"

    def test_the_groups_credentials_stay_out(self, user, world):
        raw = export_bytes(build_collection_export(world["mine"]))

        assert b"sh4re-t0ken-01" not in raw
        assert b"pending-invite-token-01" not in raw
        # The pending invitation itself is here — it is the owner's to manage.
        assert b"lili2@your-domain.test" in raw

    def test_reports_are_absent_in_both_directions(self, user, world):
        raw = export_bytes(build_collection_export(world["mine"]))

        assert b"RPTAG1" not in raw
        assert b"RPTBY1" not in raw

    def test_the_history_of_the_group_covers_every_thing_in_it(self, user, world):
        payload = build_collection_export(world["mine"])

        assert [b["code"] for b in payload["bookings"]] == ["BKIN01"]
        assert [f["code"] for f in payload["faqs"]] == ["FAQIN1"]
        assert {t["code"] for t in payload["transfers"]} == {"TRNS01", "TRNS02"}
        assert payload["transfers"][0]["to"] is None  # ordered by lent_date

    def test_the_stats_block_is_the_csv_block(self, user, world):
        payload = build_collection_export(world["mine"])

        # One definition of every metric, two renderings.
        assert payload["stats"] == dict(collection_stats_rows(world["mine"]))
        assert payload["stats"]["Members"] == 1
        assert payload["stats"]["Things total"] == 2
        # The one member's bracket is not named; it is counted.
        assert "Born 1965-1980 (Gen X)" not in payload["stats"]
        assert payload["stats"]["Birth year shared by fewer than 3"] == 1


class TestCollectionExportStaysInsideTheGroup:
    """A group's copy is the history of *that group*, not of a thing's every visitor.

    A thing can sit in two groups, and a booking records who asked — not through
    which group. The organiser of a COMMUNITY group manages nothing but the group
    (``Thing.can_manage`` wants PROPRIETARY), so a request a cousin from *another*
    group made on a member's drill, or a question of theirs its owner hid, is
    something the app never shows them — and the file must not either. Asserted on
    the bytes for the person, since the row shape is the file's business.
    """

    @pytest.fixture
    def cousin(self, db):
        """Somebody in a second group that holds a member's thing — not in MINE01."""
        return User.objects.create(code="CUSN01", email="lala@your-domain.test", name="Cousin Out")

    @pytest.fixture
    def family(self, world, user2, cousin):
        """A second group holding the member's ladder, with the cousin in it."""
        family = Collection.objects.create(code="FAMY01", owner=user2, headline="Family")
        family.invites.add(cousin)
        also_in(family, world["member_thing"])
        return family

    @pytest.fixture
    def member(self, world):
        """A second member of MINE01, so a request can be made *inside* the group."""
        member = User.objects.create(
            code="MEMB02", email="lele2@your-domain.test", name="Member Two"
        )
        world["mine"].invites.add(member)
        return member

    def _booking(self, code, thing, requester):
        return BookingPeriod.objects.create(
            code=code,
            thing_code=thing,
            thing_type=thing.type,
            requester_code=requester,
            requester_email=requester.email,
            owner_code=thing.owner,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
        )

    def _codes(self, payload, key):
        return {row["code"] for row in payload[key]}

    def test_a_request_from_someone_outside_a_community_group_is_not_in_its_copy(
        self, world, family, cousin
    ):
        self._booking("BKOUT1", world["member_thing"], cousin)

        payload = build_collection_export(world["mine"])

        assert "BKOUT1" not in self._codes(payload, "bookings")
        raw = export_bytes(payload)
        assert b"CUSN01" not in raw
        assert b"Cousin Out" not in raw

    def test_a_request_from_a_member_is_in_a_community_groups_copy(self, world, member):
        self._booking("BKMEM1", world["my_thing"], member)

        payload = build_collection_export(world["mine"])

        booking = next(b for b in payload["bookings"] if b["code"] == "BKMEM1")
        assert booking["requester"] == {"code": "MEMB02", "name": "Member Two"}

    def test_the_organisers_own_request_is_in_their_groups_copy(self, world, user):
        self._booking("BKORG1", world["member_thing"], user)

        payload = build_collection_export(world["mine"])

        assert "BKORG1" in self._codes(payload, "bookings")

    def test_a_hidden_question_from_someone_outside_the_group_is_not_in_its_copy(
        self, world, family, cousin
    ):
        FAQ.objects.create(
            code="FAQHID",
            thing=world["member_thing"],
            questioner=cousin,
            question="Is it dented?",
            is_visible=False,
        )

        payload = build_collection_export(world["mine"])

        assert "FAQHID" not in self._codes(payload, "faqs")
        raw = export_bytes(payload)
        assert b"CUSN01" not in raw
        assert b"Cousin Out" not in raw

    def test_a_hidden_question_from_a_member_is_in_a_community_groups_copy(self, world, member):
        FAQ.objects.create(
            code="FAQMEM",
            thing=world["my_thing"],
            questioner=member,
            question="Is it loud?",
            is_visible=False,
        )

        payload = build_collection_export(world["mine"])

        faq = next(f for f in payload["faqs"] if f["code"] == "FAQMEM")
        assert faq["questioner"] == {"code": "MEMB02", "name": "Member Two"}

    def test_a_hidden_question_whose_account_is_gone_is_nobodys_in_the_group(self, world):
        FAQ.objects.create(
            code="FAQGON",
            thing=world["my_thing"],
            questioner=None,
            question="Who am I?",
            is_visible=False,
        )

        payload = build_collection_export(world["mine"])

        assert "FAQGON" not in self._codes(payload, "faqs")

    def test_a_visible_question_from_someone_outside_the_group_is_in_the_copy_with_its_author(
        self, world, family, cousin
    ):
        # Anyone who sees the thing sees this question and who asked it; there is
        # nothing to withhold from the organiser that the thing's own page shows.
        FAQ.objects.create(
            code="FAQVIS",
            thing=world["member_thing"],
            questioner=cousin,
            question="Is it tall?",
            is_visible=True,
        )

        payload = build_collection_export(world["mine"])

        faq = next(f for f in payload["faqs"] if f["code"] == "FAQVIS")
        assert faq["questioner"] == {"code": "CUSN01", "name": "Cousin Out"}

    def test_a_proprietary_groups_copy_keeps_requests_from_other_groups(self, user, cousin):
        # Its curators manage every thing in it and already read every request in
        # the app, so nothing is withheld there and the copy must not start.
        private = Collection.objects.create(
            code="PRIV01", owner=user, headline="Private", mode=Collection.Mode.PROPRIETARY
        )
        drill = Thing.objects.create(code="PRTH01", owner=user, headline="Drill")
        private.things.add(drill)
        self._booking("BKPRV1", drill, cousin)
        FAQ.objects.create(
            code="FAQPRV",
            thing=drill,
            questioner=cousin,
            question="Is it sharp?",
            is_visible=False,
        )

        payload = build_collection_export(private)

        assert "BKPRV1" in self._codes(payload, "bookings")
        assert "FAQPRV" in self._codes(payload, "faqs")

    def test_the_boundary_costs_no_query_per_row(self, world, member):
        # The group's people are settled once for the whole file, not asked of each
        # booking (``is_invited`` per row is the cost this pins away).
        world["mine"].theeeme  # noqa: B018 - the group's palette is read once, not per row
        with CaptureQueriesContext(connection) as few:
            build_collection_export(world["mine"])
        for n in range(6):
            self._booking(f"BKROW{n}", world["my_thing"], member)
            FAQ.objects.create(
                code=f"FQROW{n}",
                thing=world["my_thing"],
                questioner=member,
                question=f"Question {n}?",
                is_visible=n % 2 == 0,
            )
        with CaptureQueriesContext(connection) as many:
            build_collection_export(world["mine"])

        assert len(many) == len(few)


class TestReadme:
    def test_every_language_says_the_same_things(self):
        # The catalogue is copy, and copy drifts: this is the export's
        # equivalent of i18nParity.
        reference = README_TEXTS["en"]
        for lang, texts in README_TEXTS.items():
            assert set(texts) == set(reference), lang
            for kind, block in texts.items():
                assert set(block) == set(reference[kind]), (lang, kind)
                assert len(block["not_included"]) == len(reference[kind]["not_included"]), (
                    lang,
                    kind,
                )

    def test_the_readme_speaks_the_readers_language(self, user, world):
        user.language = "ca"
        user.save()

        assert build_account_export(user)["_readme"] == README_TEXTS["ca"]["account"]

    def test_a_group_speaks_its_owners_language_not_its_own(self, user, world):
        # Same hierarchy as the email: the recipient's preference wins over the
        # group's, and this file has exactly one recipient — the owner.
        user.language = "es"
        user.save()
        world["mine"].language = "ca"
        world["mine"].save()

        readme = build_collection_export(world["mine"])["_readme"]
        assert readme == README_TEXTS["es"]["collection"]
        assert "otras personas" in readme["your_responsibility"]

    def test_a_language_the_catalogue_does_not_speak_falls_back_to_english(
        self, user, world, settings
    ):
        settings.EMAIL_LANGUAGE = "fi"

        assert build_account_export(user)["_readme"] == README_TEXTS["en"]["account"]

    def test_the_collection_readme_warns_that_the_file_holds_other_peoples_data(self):
        for texts in README_TEXTS.values():
            assert texts["collection"]["your_responsibility"]


class TestTheFile:
    def test_the_bytes_are_utf8_json_with_the_accents_intact(self, user, world):
        raw = export_bytes(build_account_export(user))

        assert "mamá".encode() in raw
        assert json.loads(raw.decode("utf-8"))["profile"]["code"] == user.code

    def test_the_filename_says_which_copy_and_when_it_stopped_being_true(self):
        from django.utils import timezone

        assert export_filename("ABC123") == f"oiueei-ABC123-{timezone.localdate().isoformat()}.json"
