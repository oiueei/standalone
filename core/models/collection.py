"""
Collection model for OIUEEI.
"""

import enum
import logging
import secrets
from collections import namedtuple
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.models.language import Language
from core.models.theeeme import KORO_CHOICES, random_theeeme
from core.utils import Refusal, generate_id

logger = logging.getLogger(__name__)

# Which verbs a kind of collection holds: the single source the serializers, the
# policy and the routes read. A stall gives or sells, a library lends or rents,
# a shed books. ``allowed_thing_types`` is always a subset of these.
KIND_THING_TYPES = {
    "STALL": ("GIFT_THING", "SELL_THING"),
    "LIBRARY": ("LEND_THING", "RENT_THING"),
    "SHED": ("RESERVE_THING",),
}


def derive_thing_type(kind, fee):
    """The verb a thing takes in a ``kind`` collection: it follows the price.

    A stall gives (no price) or sells (a price), a library lends or rents out, a
    shed always books. ``fee`` of ``None`` or ``0`` is no price.
    """
    free, *paid = KIND_THING_TYPES[kind]
    return paid[0] if paid and fee is not None and fee > 0 else free


def kind_for_thing_type(thing_type):
    """The kind of collection a verb belongs to, or ``None`` for an unknown one."""
    for kind, types in KIND_THING_TYPES.items():
        if thing_type in types:
            return kind
    return None


def generate_share_token():
    """22-char URL-safe token for public share links. Bearer credential — must be unguessable."""
    return secrets.token_urlsafe(16)


class RentalRules(namedtuple("RentalRules", "weekdays closed durations")):
    """The LEND/RENT rules in force for one thing: allowed weekdays (0=Mon…6=Sun, empty
    = any), closed days as ``date`` objects and the allowed lengths in days (empty =
    free range). See ``Collection.rental_rules_for``."""

    __slots__ = ()


class Collection(models.Model):
    """
    A collection of things (gifts, sales, orders) owned by a user.
    Can be shared with other users via invites.
    """

    # The ceiling on the co-curator set, enforced at the promote endpoint. The
    # design intent is "owner + 1–2"; the 10 is the abuse ceiling, not the goal —
    # a number, one line, for the owner to change whenever a real group asks. A
    # network of libraries (``Mode.NETWORK``) is a founder plus one co-curator per
    # entity, which is what sets it.
    MAX_CO_OWNERS = 10

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class Kind(models.TextChoices):
        """What a collection is for, fixed when it is created: a stall (give or
        sell), a library (lend or rent) or a shed (book by the day or the hour).
        Its address is ``/{kind}/{code}``."""

        STALL = "STALL", "Stall"
        LIBRARY = "LIBRARY", "Library"
        SHED = "SHED", "Shed"

    class Mode(models.TextChoices):
        PROPRIETARY = "PROPRIETARY", "Proprietary"
        COMMUNITY = "COMMUNITY", "Community"
        # Libraries only (``kind == LIBRARY``), fixed at creation: several
        # entities, each lending its own things from its own pickup point.
        NETWORK = "NETWORK", "Network"

    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        PRIVATE = "PRIVATE", "Private"

    class DigestFrequency(models.TextChoices):
        NONE = "NONE", "None"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"

    class ReservationUnit(models.TextChoices):
        """RESERVE_THING collections only. A collection is booked by whole DAYs
        (the original shape) or by slots within a day's opening hours — never
        both; see `opening_hours` and `reservation_min_minutes`/
        `reservation_max_minutes`."""

        DAY = "DAY", "Day"
        HOUR = "HOUR", "Hour"

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    owner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="owner",
        related_name="owned_collections",
    )
    created = models.DateTimeField(default=timezone.now)
    # headline: 256 stored for the {lang: text} map, 64 visible per language.
    headline = models.CharField(max_length=256)
    # TextField like Thing.description (2000 visible per language, serializer-
    # enforced): a group's description is long-form Markdown and the column is
    # only a backstop.
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.PROPRIETARY)
    visibility = models.CharField(
        max_length=7, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    # MONTHLY by default (it was WEEKLY, and NONE before that). NONE, with
    # `User.notify_news` also defaulting off, is why the digest once reached almost
    # nobody: it needed an owner to find a setting inside an accordion *and* every
    # reader to have opted in.
    #
    # A default that sends email has to be visible to the person it sends on
    # behalf of, so the selector is now in the Create form too (it was Edit-only).
    # And it has to be escapable by the people who receive it, which is
    # `digest_muted` — one click, per group, from the footer of the digest itself.
    #
    # Existing collections keep whatever they have: an `AlterField` default does
    # not rewrite rows, and quietly starting to mail someone else's members on
    # their behalf is not ours to decide (contrast 0127, which subscribes existing
    # *recipients*, who can unsubscribe themselves).
    digest_frequency = models.CharField(
        max_length=7, choices=DigestFrequency.choices, default=DigestFrequency.MONTHLY
    )
    # The language this group's outbound email speaks. Blank = inherit the
    # deployment default (EMAIL_LANGUAGE); a member's own preference still wins
    # over it. See email_service.resolve_email_language.
    language = models.CharField(max_length=2, choices=Language.choices, blank=True, default="")
    # The palette this group's pages are painted with, and its Koros wave: chosen
    # by a curator among the twelve rows of `theeemes`, a random one until they do.
    # (The app's own palette, `Braaanding`, is not one of them and cannot be picked.)
    theeeme = models.ForeignKey(
        "Theeeme",
        on_delete=models.PROTECT,
        to_field="code",
        related_name="collections",
        default=random_theeeme,
    )
    koro = models.CharField(max_length=9, choices=KORO_CHOICES, default="basic")
    # Whether members may suggest new guests (InvitationProposal). The owner
    # always decides on each one — this decides whether they are willing to be
    # asked at all. A group with a waiting list, a subscription or an admission
    # process may not want the question raised, and saying so once beats
    # declining the same suggestion over and over.
    #
    # Default OFF (it was ON): a new collection does not ask its
    # owner anything until the owner says so. The suggestion reaches only the
    # owner, but being asked is still something the person who runs a group
    # should choose rather than be handed, and a feature offered to everybody by
    # default is one most groups never meant to have. Collections that already
    # existed kept the value they had — there was no data migration, only the
    # default for new rows changed.
    allow_member_proposals = models.BooleanField(default=False)
    is_onboarding = models.BooleanField(default=False)
    # Rental rules for LEND/RENT things in this collection (#7).
    # rental_durations: allowed rental lengths in DAYS (weeks are normalised to
    #   days, e.g. [1, 3, 7, 14]); the renter picks exactly one. Empty = no fixed
    #   durations (free date range, the legacy behaviour).
    # rental_weekdays: allowed weekdays for BOTH pickup (start) and return (end),
    #   Python weekday() numbering (0=Mon … 6=Sun). Empty = any day.
    rental_durations = models.JSONField(default=list, blank=True)
    rental_weekdays = models.JSONField(default=list, blank=True)
    # Holidays and one-off closures — ISO date strings ("2026-12-25"), sorted,
    # deduped, past ones dropped on save (the owner re-enters each year). No
    # pickup or return can land on one for a LEND/RENT booking; a RESERVE
    # booking can't span one at all. The serializer parses the owner's
    # comma-separated DD/MM/YYYY line into this. Empty = no closures.
    closed_dates = models.JSONField(default=list, blank=True)
    # Reservations collections (sheds) only (``is_reservations_collection()``).
    # The longest a member may book the space for in one reservation, in days —
    # the renter picks any length from 1 to this. ``rental_weekdays`` above is
    # reused as "days reservations are allowed" (every day of the span must fall
    # on one). Inert on every other collection.
    reservation_max_days = models.PositiveSmallIntegerField(default=1)
    # How far ahead a member may book — the owner's call, since lead time is a
    # fact about the space (a workshop bench next week, an events hall six
    # months out). Default 90, matching the LEND/RENT horizon it replaces for
    # this type. Also caps how far the live-availability calendar looks.
    reservation_horizon_days = models.PositiveSmallIntegerField(default=90)
    # RESERVE_THING collections only. How many of a member's own reservations
    # in THIS collection may be active (ACCEPTED, not yet finished) at once —
    # a courtesy cap against one member sitting on the whole calendar, not a
    # security invariant (see active_reservation_count). 1-50, default 10.
    reservation_max_active_per_member = models.PositiveSmallIntegerField(default=10)
    # SHED only. Whether the request page offers an optional contact phone, for a
    # same-day problem with what was booked that an email would reach too late.
    # Inert on every other kind. Carries a database default as well as the Python
    # one: the previous release's dynos keep inserting rows without naming the
    # column while the release phase runs.
    reservation_asks_phone = models.BooleanField(default=False, db_default=False)
    # RESERVE_THING collections only. DAY (default) is the original shape above:
    # a reservation occupies one or more whole days. HOUR books a single day in
    # slots within that day's opening_hours. Never both at once — a
    # collection picks one unit, and the fields below are inert under the other
    # (reservation_max_days/rental_weekdays-as-open-days for DAY; opening_hours/
    # reservation_min_minutes/reservation_max_minutes for HOUR).
    reservation_unit = models.CharField(
        max_length=4, choices=ReservationUnit.choices, default=ReservationUnit.DAY
    )
    # HOUR unit only. The venue's opening hours per weekday, keyed by Django's
    # string form of Python's weekday() (0=Mon…6=Sun, so keys are "0".."6"),
    # each a list of non-overlapping [start, end] "HH:MM" pairs sorted within
    # the day — e.g. {"0": [["10:00","14:00"],["16:00","20:00"]], "6": []}. A
    # day with an empty list (or an absent key) is closed — this REPLACES
    # rental_weekdays as "which days are open" for a HOUR-unit collection, since
    # keeping both risked the two disagreeing. Default {} = every day closed
    # (an owner switching to HOUR mode must set hours before anyone can book).
    opening_hours = models.JSONField(default=dict, blank=True)
    # HOUR unit only. The shortest a single reservation may run, in minutes —
    # also the step every duration/start-time choice is offered in (15 here
    # means 15/30/45/... up to the max, and start times fall every 15 minutes
    # too): a short minimum that the picker still only offered on the hour
    # would be a minimum in name only. 1-720 (serializer-enforced), default
    # 60 — the fixed floor every HOUR-unit collection already lived under
    # before this field existed, so nothing changes until an owner lowers it.
    # Inert under DAY.
    reservation_min_minutes = models.PositiveSmallIntegerField(default=60)
    # HOUR unit only. The longest a single reservation may run, in minutes —
    # the twin of `reservation_min_minutes` above, and the replacement for the
    # hour-granular `reservation_max_hours` (0147; out of the model since 0152,
    # its column still in the database until a later release drops it — see
    # that migration): same 1-720 range and the same no-exception-for-the-full-day
    # rule (see `reservation_hour_violation`), just counted in minutes so a
    # cap under an hour is expressible too. Default 180 (matches the old
    # field's default of 3 hours). Inert under DAY (reservation_max_days
    # governs there).
    reservation_max_minutes = models.PositiveSmallIntegerField(default=180)
    # How deposits work in this group, in the owner's own words — "50 €, back
    # when the drill comes home in one piece". A bare number is the beginning of
    # an argument: the condition for getting it back is the actual rule, and that
    # rule belongs to the group rather than to each thing.
    #
    # No on/off switch beside it, on purpose: **writing the policy is the
    # switch**, the same shape as `digest_muted` below, where the presence of a
    # row means something and the absence costs no data. A group that wants no
    # deposits simply has no policy and no thing carrying one; a boolean beside
    # it would be a second door that can disagree with the first.
    #
    # 256/1024 like `description`, for the same reason: the visible limit is per
    # language and the column has to hold all three plus the JSON scaffolding.
    deposit_policy = models.CharField(max_length=1024, blank=True, default="")
    # A short note the owner writes for anyone reaching the request page —
    # LEND/RENT/RESERVE alike, not RESERVE_THING only, but never GIFT/SELL:
    # those complete straight from the card and never visit that page, so a
    # note written here is invisible to them ("bring ID", "reservations must
    # be confirmed 24h ahead"...). Rendered as Markdown like `description`.
    # 512/2048 (256 was too short for this one) — same
    # `deposit_policy` shape, wider: the visible limit is per language and the
    # column has to hold all three plus the JSON scaffolding.
    request_info = models.CharField(max_length=2048, blank=True, default="")
    # A note the owner writes into the emails a *requester* receives about
    # their request — "we've let the owner know" and its acceptance for every
    # verb, plus RESERVE's auto-confirmation — right after the link to the
    # listing, before the legal footer. Never a refusal (no next steps for the
    # note's prose to describe) nor the emails the owner themselves gets
    # (their own note read back would be noise).
    # Like `request_info` it reaches only people who asked for something, so
    # the same examples fit ("we confirm requests within 48h", "the space is
    # on floor 2"). A small Markdown subset (bold, italics, lists, links) is
    # rendered into the HTML part by `email_service._note_blocks`; the
    # plain-text part carries the raw Markdown, as text/plain alternatives do.
    # 512/2048 like `request_info`: the visible limit is per language and the
    # column has to hold all three plus the JSON scaffolding.
    email_note = models.CharField(max_length=2048, blank=True, default="")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.STALL)
    # The verbs this collection takes, always within ``KIND_THING_TYPES[kind]`` and
    # never empty: both of the kind's verbs, or — in a COMMUNITY stall or library
    # whose members may not set a price — only the free one.
    allowed_thing_types = models.JSONField(default=list, blank=True)
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Owner-defined tag vocabulary for this collection: an ordered list of "
            "free-text labels. Things in the collection may be tagged with a subset. Max 12."
        ),
    )
    # The group's own website, if it has one — shown in the hero. A URLField, so
    # Django's URLValidator rejects anything but http(s)/ftp(s); the frontend
    # still runs it through `sanitizeUrl` before rendering the link.
    home_page = models.URLField(max_length=128, blank=True, default="")
    thumbnail = models.CharField(max_length=255, blank=True, default="")
    # Storage key of the owner's optional welcome & rules PDF. Emailed as a link
    # (never an attachment) to every member the first time they join, which is why
    # the link has to still work weeks later — see core.utils.doc_asset_url.
    welcome_doc = models.CharField(max_length=255, blank=True, default="")
    pause_message = models.CharField(max_length=256, blank=True, default="")
    share_token = models.CharField(max_length=22, blank=True, null=True, unique=True)
    # Mass-upload guards (see the COLLECTION_* thresholds in settings). The two
    # `*_alarm_sent` flags make each counter's alarm fire once per collection
    # rather than on every add past the line. `capacity_unblocked` is the
    # superuser's override: tick it in the admin and this collection may pass
    # BOTH ceilings — the unblock follows one manual review of the account, the
    # owner and the collection. All three are inert without thresholds.
    things_alarm_sent = models.BooleanField(default=False)
    invites_alarm_sent = models.BooleanField(default=False)
    capacity_unblocked = models.BooleanField(default=False)
    # The last day whose sign-ups ``send_join_summaries`` has already told the
    # curators about. The command claims a day here (a conditional UPDATE) before
    # it sends, so a second run — or two at once — finds nothing left to do, and a
    # day the Scheduler skipped is picked up from the day after this one. NULL
    # means the command has never looked at this group (its first summary names
    # only yesterday); every pass dates the groups it had nothing to tell, so a
    # skipped day is recovered.
    join_summary_sent_on = models.DateField(null=True, blank=True)
    things = models.ManyToManyField(
        "Thing",
        blank=True,
        related_name="collections",
        db_table="collection_things",
    )
    invites = models.ManyToManyField(
        "User",
        blank=True,
        related_name="invited_to_collections",
        db_table="collection_invites",
    )
    # Members who have silenced THIS group's digest. Presence of a row means
    # "don't send"; the absence of one means subscribed — so the default costs no
    # data and a new member starts subscribed without anything being written.
    #
    # It is what makes `User.notify_news` defaulting to True honest rather than a
    # pre-ticked opt-in (DESIGN §6): the global switch is not the only way out,
    # so silencing one noisy group never costs you the booking and question
    # emails you actually want. `notify_news` remains the master switch — this
    # narrows it, it cannot re-enable anything.
    digest_muted = models.ManyToManyField(
        "User",
        blank=True,
        related_name="muted_digest_collections",
        db_table="collection_digest_muted",
    )
    # The admin tier, in **either mode** (2026-09, co-curators in PROPRIETARY),
    # promoted from the collection's own `invites` — never a separate door in. A
    # co-curator gets the founder's collection-level powers (edit, invite/revoke,
    # broadcast, share link, stats/export, decide member proposals, promote/demote
    # another co-curator; and in a PROPRIETARY collection, run its whole catalogue,
    # FAQs and bookings via `Thing.can_manage`) but is deliberately NOT a CASCADE
    # root: deleting a co-curator's account never takes the collection with it,
    # only the founding `owner` does. See `is_curator`.
    co_owners = models.ManyToManyField(
        "User",
        blank=True,
        related_name="co_owned_collections",
        db_table="collection_co_owners",
    )

    class Meta:
        app_label = "core"
        db_table = "collections"

    def __str__(self):
        return f"{self.code}: {self.headline}"

    def add_thing(self, thing_code):
        """Test-only fixture helper: link a thing via the M2M.

        Skips the views' permission/allowed-type checks and Event logging,
        and an unknown code is a silent no-op. Production code must go
        through the views instead of calling this.
        """
        from core.models import Thing

        try:
            thing = Thing.objects.get(code=thing_code)
            self.things.add(thing)
        except Thing.DoesNotExist:
            pass

    def remove_thing(self, thing_code):
        """Test-only fixture helper: unlink a thing via the M2M.

        Same caveats as add_thing — no permission checks, no Event logging,
        silent no-op on unknown codes. Not for production code.
        """
        from core.models import Thing

        try:
            thing = Thing.objects.get(code=thing_code)
            self.things.remove(thing)
        except Thing.DoesNotExist:
            pass

    def add_invite(self, user_code):
        """Test-only fixture helper: add a user to invites via the M2M.

        Skips the views' owner check and the invitation email/RSVP flow,
        and an unknown code is a silent no-op. Production code must go
        through CollectionInviteView instead of calling this.
        """
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.invites.add(user)
        except User.DoesNotExist:
            pass

    def remove_invite(self, user_code):
        """Test-only fixture helper: remove a user from invites via the M2M.

        Same caveats as add_invite — no owner check, no notifications,
        silent no-op on unknown codes. Not for production code.
        """
        from core.models import User

        try:
            user = User.objects.get(code=user_code)
            self.invites.remove(user)
        except User.DoesNotExist:
            pass

    @property
    def is_paused(self):
        return bool(self.pause_message)

    def is_owner(self, user_code):
        """Check if the given user is the owner."""
        return self.owner_id == user_code

    def is_invited(self, user_code):
        """Check if the given user is invited."""
        return self.invites.filter(code=user_code).exists()

    def is_curator(self, user_code):
        """Owner or co-owner — the group's admin tier.

        The single primitive every co-owner permission gate builds on, the way
        `is_owner` already was for owner-only ones. A co-owner is always also
        in `invites` (promotion, not a separate door), so this is strictly
        wider than `is_owner`, never wider than `is_invited`.

        Checks `co_owners` via `.all()` and Python iteration rather than
        `.filter(...).exists()`, deliberately: `co_owners` is prefetched
        alongside `invites` for any signed-in viewer (`_optimise_collection_
        queryset`), and a `.filter()` call would bypass that cache and reopen
        the N+1 the prefetch exists to close — the same reasoning behind
        `get_is_member`'s `any(u.code == ... for u in obj.invites.all())`.

        Does **not** check `is_community()`, and nothing about co-curators does
        any more: a curator has the founder's reach in either mode (2026-09,
        co-curators in PROPRIETARY), and only deleting the collection stays
        `is_owner`. An existing co-owner's status is sticky across a later mode
        switch, the same way `owner` itself is.
        """
        return self.is_owner(user_code) or any(u.code == user_code for u in self.co_owners.all())

    class Promotion(enum.Enum):
        """What `promote_co_owner` did."""

        ADDED = "added"
        ALREADY = "already"
        FULL = "full"

    def promote_co_owner(self, member):
        """Make ``member`` a co-curator, unless the set is already at ``MAX_CO_OWNERS``.

        Returns a `Promotion`: ``ADDED``, ``ALREADY`` (they were one — re-promoting
        is idempotent and never meets the ceiling, since it grows nothing) or
        ``FULL``.

        **The read and the add are one atomic step on a locked row.** The ceiling
        is what bounds a stolen curator credential (`MAX_CO_OWNERS`), and a bare
        ``count()`` then ``add()`` lets every promotion running at once read the
        same count and all add: at four, four requests at once end at eight. So the
        collection's row is locked (``select_for_update``) and both the membership
        test and the count are read **under** the lock — the second promotion waits
        for the first to commit and then counts five. The lock is on the collection
        rather than a constraint because the bound is a rule about a set, which a
        row-level constraint cannot express.

        Does not check that ``member`` is in ``invites`` (``co_owners ⊆ invites``):
        the promote endpoint does, before it gets here. On SQLite Django drops the
        ``FOR UPDATE``, so the race is only provable on PostgreSQL — see
        ``test_booking_row_locks.py``.
        """
        with transaction.atomic():
            locked = Collection.objects.select_for_update().get(pk=self.pk)
            if locked.co_owners.filter(code=member.code).exists():
                return self.Promotion.ALREADY
            if locked.co_owners.count() >= self.MAX_CO_OWNERS:
                return self.Promotion.FULL
            locked.co_owners.add(member)
            return self.Promotion.ADDED

    def is_community(self):
        """Check if this is a community collection."""
        return self.mode == self.Mode.COMMUNITY

    def is_network(self):
        """Check if this is a network of libraries: every curator runs their own things."""
        return self.mode == self.Mode.NETWORK

    def point_for(self, user_code):
        """The pickup point ``user_code`` set up in this network, or ``None``.

        Only a network has points; elsewhere (and for a dinamizador who has not set
        one) the answer is ``None`` and the collection's own rules apply. Reads
        ``points.all()`` so a caller that prefetched them pays no query.
        """
        if not self.is_network():
            return None
        # One read per collection instance, not one per thing asked about.
        by_user = self.__dict__.get("_points_by_user")
        if by_user is None:
            by_user = self._points_by_user = {p.user_id: p for p in self.points.all()}
        return by_user.get(user_code)

    def rental_rules_for(self, owner_code=None):
        """The LEND/RENT rules that govern a thing of ``owner_code`` in this collection.

        In a network the pickup point of the thing's owner refines the collection's:
        the point's weekdays, when it set any, replace the collection's, and its
        closures add to them; lengths (and the horizon and per-member limit, which
        are not rental rules at all) stay the collection's. Without a point, and
        everywhere outside a network, it is exactly the collection's own. The one
        answer behind the server's refusal, the live availability and the rules the
        thing's payload carries to the request page.
        """
        point = self.point_for(owner_code) if owner_code else None
        weekdays = point.weekdays if point and point.weekdays else self.rental_weekdays
        closed = self.closed_date_set() | (point.closed_date_set() if point else set())
        return RentalRules(sorted(weekdays or []), closed, list(self.rental_durations or []))

    def effective_text(self, field, owner_code=None):
        """A condition of a loan — ``deposit_policy``, ``request_info`` or ``email_note`` —
        as it applies to a thing of ``owner_code``: the pickup point's own when it wrote
        one, else the collection's. Field by field, so a point can set its deposit and
        leave the note to the network. Raw (possibly a ``{lang: text}`` map)."""
        point = self.point_for(owner_code) if owner_code else None
        return (getattr(point, field, "") if point else "") or getattr(self, field)

    def can_rescue(self, user_code):
        """The founder's rescue of a network: reject a pending request on any thing, hide any thing.

        Only ``owner`` — not a co-curator — and only in a network. Rejecting is the
        whole of it for requests: accepting stays the thing owner's, and an accepted
        loan is not touched. It is a method of its own rather than a widening of
        ``Thing.can_manage``: the founder is deliberately outside ``managers()`` (no
        day-to-day email) and cannot edit or accept for another entity, so folding it
        into ``can_manage`` would hand over both. Deleting is a different power and
        not this one's: the owner of a collection deletes any thing of it in every
        mode (``ThingViewSet._can_delete``).
        """
        return self.is_network() and self.is_owner(user_code)

    def owner_member_rows(self, members=None):
        """Every member as **their owner** sees them, demographics gated by mode.

        The one definition of a privacy rule that used to be written twice —
        once in `CollectionSerializer.get_invites`, once in
        `export_service._collection_members` — as two near-identical loops that
        agreed only because somebody kept them agreeing. `age_range` and
        `postal_code` are optional answers a member gave; in a COMMUNITY group
        their owner sees them (it is what the demographics breakdown is for), and
        in every other mode nobody but the member does. An export must not become
        the back door to what the API withholds, and the next mode added must not
        have to be remembered in two files.

        It lives on the model rather than in either caller because the gate is
        `self.mode` — a fact about the group, not about JSON. It builds a row and
        nothing else: **who may ask is the caller's job** (`_requester_is_owner`
        in the serializer, `require_collection_curator` on the export view), and
        calling this does not make anyone a curator.

        `members` defaults to the M2M, so a caller with a prefetched or ordered
        queryset passes it in rather than triggering a second one.
        """
        community = self.is_community()
        rows = []
        for member in self.invites.all() if members is None else members:
            row = {"code": member.code, "name": member.name, "email": member.email}
            if community:
                row["age_range"] = member.age_range
                row["postal_code"] = member.postal_code
            rows.append(row)
        return rows

    def is_public(self):
        """Check if this collection is publicly readable (anonymous-friendly)."""
        return self.visibility == self.Visibility.PUBLIC

    def has_rental_rules(self):
        """True if this collection constrains LEND/RENT booking dates (#7)."""
        return bool(self.rental_durations) or bool(self.rental_weekdays) or bool(self.closed_dates)

    def closed_date_set(self):
        """``closed_dates`` (ISO strings) as a set of ``date`` objects. A bad
        string is skipped rather than raising — the serializer is what keeps the
        column clean, this stays defensive."""
        from datetime import date as _date

        out = set()
        for raw in self.closed_dates or []:
            try:
                out.add(_date.fromisoformat(raw))
            except (TypeError, ValueError):
                continue
        return out

    def is_reservations_collection(self):
        """True if this is a shed (``kind == SHED``): the collection that holds
        RESERVE_THING things. A shed is always PROPRIETARY and takes only that verb."""
        return self.kind == self.Kind.SHED

    def path(self):
        """The SPA route of this collection, ``/{kind}/{code}``."""
        return f"/{self.kind.lower()}/{self.code}"

    def reservation_violation(self, start_date, duration_days, today=None):
        """Return an error string if a RESERVE booking breaks this collection's
        reservation rules, else ``None``. Mirrors ``rental_violation``'s shape.

        ``duration_days`` is how many days the member wants the space, 1 to
        ``reservation_max_days``. The booking occupies ``[start, start + N)`` —
        every one of those days must fall on an allowed weekday
        (``rental_weekdays``, reused; empty = any day), because the space is only
        open on those days. A reservation that would span a closed day is
        refused rather than silently shortened.

        The **pickup day** must land within ``reservation_horizon_days`` of
        ``today`` (default ``timezone.localdate()``) — the owner's "how far
        ahead" limit, and the single backstop the request view relies on. It is
        the pickup day, not the return day: that is what ``RequestThingPage``'s
        date picker caps (``maxDate = today + reservation_horizon_days``) and
        what ``Thing.availability_window`` walks, so judging the exclusive
        ``end_date`` here rejected the last day of the picker's own range
        (horizon 7 ⇒ day 7 selectable, ``end_date`` day 8, refused).
        """
        if duration_days < 1:
            return Refusal("A reservation is at least one day.", "reservation_too_short_days")
        if duration_days > self.reservation_max_days:
            return Refusal(
                f"This collection can be reserved for at most "
                f"{self.reservation_max_days} day(s) at a time.",
                "reservation_too_long_days",
                max=self.reservation_max_days,
            )
        today = today or timezone.localdate()
        if start_date > today + timedelta(days=self.reservation_horizon_days):
            return Refusal(
                f"This collection can only be booked up to "
                f"{self.reservation_horizon_days} days ahead.",
                "reservation_beyond_horizon",
                days=self.reservation_horizon_days,
            )
        weekdays = self.rental_weekdays or []
        closed = self.closed_date_set()
        for offset in range(duration_days):
            day = start_date + timedelta(days=offset)
            if weekdays and day.weekday() not in weekdays:
                return Refusal(
                    "Those dates include a day this collection isn't open for reservations.",
                    "reservation_weekday_closed",
                )
            if day in closed:
                return Refusal(
                    "Those dates include a day this collection is closed.",
                    "reservation_closed_date",
                )
        return None

    def is_hourly_reservations(self):
        """True for a reservations collection booked in HOUR slots rather than
        whole DAYs. Meaningless (and unchecked) on a non-reservations collection —
        callers guard with ``is_reservations_collection()`` first."""
        return self.reservation_unit == self.ReservationUnit.HOUR

    def day_opening_blocks(self, day):
        """The HOUR-unit opening blocks for one date, as a sorted list of
        ``(time, time)`` pairs — e.g. ``[(10:00, 14:00), (16:00, 20:00)]``.

        Empty when the collection is closed that weekday: no entry for it in
        ``opening_hours``, an empty list, or every pair malformed (skipped
        defensively, mirroring ``closed_date_set``).
        """
        from datetime import time as _time

        raw = (self.opening_hours or {}).get(str(day.weekday()), [])
        blocks = []
        for pair in raw:
            try:
                start_h, start_m = (int(x) for x in pair[0].split(":"))
                end_h, end_m = (int(x) for x in pair[1].split(":"))
                blocks.append((_time(start_h, start_m), _time(end_h, end_m)))
            except (TypeError, ValueError, IndexError, AttributeError, KeyError):
                continue
        return sorted(blocks)

    def reservation_hour_violation(self, start_date, start_time, end_time, today=None, now=None):
        """The HOUR-unit twin of ``reservation_violation``: an error string if an
        ``[start_time, end_time)`` reservation on ``start_date`` breaks this
        collection's hourly rules, else ``None``.

        A valid span is either **entirely inside one opening block** for that
        weekday, or **exactly the full day** — from the first block's open to
        the last block's close, gaps (a lunch break) included; that second form
        is what "book the whole day" means for a venue that closes for lunch.
        Anything else — a span crossing a gap without covering the whole day,
        one that starts or ends off a block boundary without being the
        full-day case — is refused rather than silently clipped, the same
        stance ``reservation_violation`` takes on days.

        ``reservation_max_minutes`` is a hard cap with **no exception for the
        full-day form**: a venue whose day adds up to more minutes
        than the cap simply never offers "the whole day" as a choice; the
        owner raises the cap if they want it offered. ``reservation_min_
        minutes`` is the twin floor, configurable since 0150 (it used to be a
        fixed 60). The duration/horizon/closure checks mirror
        ``reservation_violation`` exactly, just in minutes instead of days.

        **The minimum is also the step** (2026-09-18), exactly as
        ``RequestThingPage`` offers it: times are whole minutes, and inside a
        block a reservation starts on the grid that runs every
        ``reservation_min_minutes`` from that block's opening and lasts a
        multiple of it. The picker never produces anything else; without this
        a request made straight to the API could book 10:07:30-11:07:30 and
        leave slivers no member can book, and ``_day_has_a_free_hour`` (which
        also reasons on the grid) would disagree with the calendar about
        whether a day has room. The full-day form is exempt from the grid — it
        is defined by the blocks, not the step.

        **A slot that has already begun today is refused** (2026-09-18) — the
        request page stopped offering one, and this is the backstop for a
        request made any other way. "Today" and "now" are the deployment's
        wall clock (`TIME_ZONE`, from `DJANGO_TIME_ZONE`), the same one
        `opening_hours` is written in. A start in the current minute has not
        begun yet, as on the request page. The check only runs when ``today``
        is the real one: a caller that passes a different ``today`` (a test
        pinning the horizon) is asking about that day, not about the clock.
        """
        if end_time <= start_time:
            return Refusal(
                "A reservation must end after it starts.", "reservation_end_before_start"
            )
        if start_time.second or start_time.microsecond or end_time.second or end_time.microsecond:
            return Refusal(
                "Reservation times are whole minutes (HH:MM).", "reservation_whole_minutes"
            )
        start_minutes = start_time.hour * 60 + start_time.minute
        duration_minutes = end_time.hour * 60 + end_time.minute - start_minutes
        if duration_minutes < self.reservation_min_minutes:
            return Refusal(
                f"A reservation is at least {self.reservation_min_minutes} minutes.",
                "reservation_too_short_minutes",
                min=self.reservation_min_minutes,
            )
        if duration_minutes > self.reservation_max_minutes:
            return Refusal(
                f"This collection can be reserved for at most "
                f"{self.reservation_max_minutes} minutes at a time.",
                "reservation_too_long_minutes",
                max=self.reservation_max_minutes,
            )
        now = now or timezone.localtime()
        today = today or now.date()
        if start_date > today + timedelta(days=self.reservation_horizon_days):
            return Refusal(
                f"This collection can only be booked up to "
                f"{self.reservation_horizon_days} days ahead.",
                "reservation_beyond_horizon",
                days=self.reservation_horizon_days,
            )
        if start_date == today == now.date() and start_minutes < now.hour * 60 + now.minute:
            return Refusal("That time has already begun.", "reservation_already_begun")
        if start_date in self.closed_date_set():
            return Refusal("This collection is closed that day.", "reservation_closed_that_day")
        blocks = self.day_opening_blocks(start_date)
        if not blocks:
            return Refusal("This collection isn't open that day.", "reservation_not_open_that_day")
        if (start_time, end_time) == (blocks[0][0], blocks[-1][1]):
            return None
        step = self.reservation_min_minutes
        for block_start, block_end in blocks:
            if block_start <= start_time and end_time <= block_end:
                if (start_minutes - (block_start.hour * 60 + block_start.minute)) % step:
                    return Refusal(
                        f"Reservations here start every {step} minutes from opening time.",
                        "reservation_off_grid_start",
                        step=step,
                    )
                if duration_minutes % step:
                    return Refusal(
                        f"A reservation here lasts a multiple of {step} minutes.",
                        "reservation_off_grid_length",
                        step=step,
                    )
                return None
        return Refusal(
            "That time falls outside this collection's opening hours.", "reservation_outside_hours"
        )

    def active_reservation_count(self, requester_code, today=None):
        """How many of ``requester_code``'s RESERVE bookings in THIS collection
        are still active — ``ACCEPTED`` and not yet finished (``end_date`` in
        the future). The backstop for ``reservation_max_active_per_member``.

        A courtesy limit, not a locked invariant: unlike ``has_overlap`` (which
        the Thing row's ``select_for_update`` serialises), two simultaneous
        requests on two different things by the same member could both read
        the count before either is created and both land — the same shape as
        every other "how many do you already have" check that isn't itself
        the row being contended for. Good enough to stop one member from
        sitting on the whole calendar; not a security control.
        """
        from core.models.booking import BookingPeriod

        today = today or timezone.localdate()
        return BookingPeriod.objects.filter(
            thing_code__collections=self,
            thing_type="RESERVE_THING",
            requester_code=requester_code,
            status=BookingPeriod.Status.ACCEPTED,
            end_date__gt=today,
        ).count()

    # ---- Mass-upload capacity guards -------------------------------------
    # Two INDEPENDENT counters per collection — things and invitees — because a
    # collection can be abused in either direction (dumping stock, or harvesting
    # a mailing list) and one crossing says nothing about the other. Each has its
    # own thresholds and its own fire-once alarm flag; a single
    # `capacity_unblocked` lifts both ceilings, since the unblock follows one
    # manual review of the account, the owner and the collection.
    #
    # Both counters are inert unless the deployment sets thresholds (see
    # settings) — the standalone default is off.
    _COUNTERS = {
        "things": {
            "alarm_setting": "COLLECTION_THINGS_ALARM",
            "block_setting": "COLLECTION_THINGS_BLOCK",
            "flag": "things_alarm_sent",
            "noun": "things",
            "code": "things_limit",
        },
        "invites": {
            "alarm_setting": "COLLECTION_INVITES_ALARM",
            "block_setting": "COLLECTION_INVITES_BLOCK",
            "flag": "invites_alarm_sent",
            "noun": "members",
            "code": "members_limit",
        },
    }

    def _capacity_count(self, counter):
        return (self.things if counter == "things" else self.invites).count()

    def capacity_ceiling(self, counter="things"):
        """The hard ceiling in force for ``counter``, or ``0`` when there is none.

        ``0`` means either the deployment set no ceiling (the standalone default)
        or a superuser lifted it for this collection. Callers use it as a cheap
        gate: with no ceiling to judge them, working out how many rows a request
        would actually add is wasted effort, so the guard costs not one query.
        """
        if self.capacity_unblocked:
            return 0
        return max(getattr(settings, self._COUNTERS[counter]["block_setting"], 0) or 0, 0)

    def capacity_violation(self, counter="things", adding=1):
        """Return an error string if adding ``adding`` rows to ``counter`` would
        cross this deployment's hard ceiling, else ``None``.

        Mirrors ``rental_violation``'s shape: a string is a refusal the caller
        turns into a 400. A ceiling of 0 (or unset) means no ceiling, which is
        the standalone default. A superuser who has ticked
        ``capacity_unblocked`` lifts it for this collection.

        Checked BEFORE the add and against the WHOLE batch, so a bulk import or
        bulk invite cannot step over the line 100 rows at a time. ``adding`` is
        the number of rows that would genuinely *land* — callers must not count
        rows the request will drop anyway (an invitee who is already a member is
        inside the count the ceiling measures, so counting them again would
        refuse a batch that adds nobody). The message names the ceiling: once it
        actually bites, hiding the number would just leave the owner with an
        unexplained refusal (the thresholds are unpublished, not secret from the
        person hitting one).
        """
        spec = self._COUNTERS[counter]
        ceiling = self.capacity_ceiling(counter)
        if ceiling <= 0:
            return None
        # Adding nothing can never *cross* a line. Without this, a batch whose
        # rows all turn out to be no-ops (already members, or every row invalid)
        # would still be refused on a collection that is already over a ceiling
        # lowered after the fact — a refusal the request could do nothing about.
        if adding <= 0:
            return None
        if self._capacity_count(counter) + adding > ceiling:
            return Refusal(
                f"This collection has reached its limit of {ceiling} "
                f"{spec['noun']}. Contact the site administrator if you need "
                "more room.",
                spec["code"],
                max=ceiling,
            )
        return None

    def note_capacity(self, counter="things"):
        """Email the superusers once if ``counter`` has crossed its alarm line.

        A **silent** tripwire: the owner is told nothing. A legitimate bulk
        import must not be interrupted, and someone probing the endpoint must not
        be told where the line sits — only the hard ceiling is user-visible, and
        only once it bites. Called AFTER a successful add, so the count is real.

        The per-counter flag makes it fire once per collection. Failures are
        swallowed — an alarm that cannot send must never 500 an upload whose rows
        are already committed; the ceiling is the guard that actually stops
        abuse, the alarm is only the early warning.
        """
        spec = self._COUNTERS[counter]
        threshold = getattr(settings, spec["alarm_setting"], 0) or 0
        if threshold <= 0 or getattr(self, spec["flag"]):
            return
        count = self._capacity_count(counter)
        if count < threshold:
            return
        # Claim the alarm with a conditional UPDATE: the `flag=False` in the
        # WHERE is what makes "fire once" hold under concurrency. Two requests
        # crossing the line together both read False above, but only one gets a
        # matched row back — the loser returns without sending, so the operator
        # gets one email rather than one per racing request. Claiming BEFORE the
        # send also means a send that raises can't leave the alarm armed to
        # re-fire on every subsequent add.
        claimed = Collection.objects.filter(code=self.code, **{spec["flag"]: False}).update(
            **{spec["flag"]: True}
        )
        setattr(self, spec["flag"], True)
        if not claimed:
            return
        try:
            from core.services.email_service import send_collection_capacity_alarm

            send_collection_capacity_alarm(self, counter, count, threshold)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Capacity alarm email failed for collection %s", self.code)

    def rental_violation(self, start_date, end_date, owner_code=None):
        """Return an error string if a LEND/RENT booking of ``[start, end]`` breaks
        this collection's rental rules, else ``None``.

        ``start`` is the pickup day and ``end`` the return day, so an allowed
        length of N days means ``end`` is ``start + N`` days — a one-week rental
        picked up on a Wednesday is returned the NEXT Wednesday. (With an
        inclusive span, the return of every 7/14/21-day rental landed on the day
        BEFORE the pickup weekday, so a single allowed weekday could never be
        satisfied.) Weekdays use Python's ``weekday()`` (0=Mon…6=Sun) and gate
        BOTH the pickup (start) and the return (end).
        """
        rules = self.rental_rules_for(owner_code)
        durations = rules.durations
        if durations:
            span_days = (end_date - start_date).days
            if span_days not in durations:
                allowed = ", ".join(str(d) for d in sorted(durations))
                return Refusal(
                    f"This collection only allows rentals of {allowed} day(s).",
                    "rental_length_not_allowed",
                    allowed=allowed,
                )
        weekdays = rules.weekdays
        if weekdays:
            if start_date.weekday() not in weekdays:
                return Refusal(
                    "The pickup day isn't available for this collection.", "rental_pickup_weekday"
                )
            if end_date.weekday() not in weekdays:
                return Refusal(
                    "The return day isn't available for this collection.", "rental_return_weekday"
                )
        # Holidays / closures: only the handoff days matter for a loan or a
        # rental — the item is already out in between, so an interior closure
        # stops nothing.
        closed = rules.closed
        if start_date in closed:
            return Refusal(
                "The pickup day is a closure day for this collection.", "rental_pickup_closed"
            )
        if end_date in closed:
            return Refusal(
                "The return day is a closure day for this collection.", "rental_return_closed"
            )
        return None

    def can_add_thing(self, user_code):
        """Check if the given user can add things to this collection.

        Any curator (owner or co-curator) can always add — a PROPRIETARY
        collection's catalogue is run by its curators collectively (2026-09), and a
        network's is run by its curators, each with their own things. Beyond that,
        an invited member can add in COMMUNITY mode.
        """
        if self.is_curator(user_code):
            return True
        return self.is_community() and self.is_invited(user_code)

    def can_view(self, user_code, invited_to=None):
        """Check if the given user can view this collection.

        Owner always; INACTIVE collections only the owner; PUBLIC collections
        anyone — including anonymous visitors (``user_code=None``); otherwise an
        invited member only.

        ``invited_to`` is for a caller that judges **many** collections for one
        user: the codes of the collections that user is already known to be
        invited to (one query for the lot), so the last rule reads it instead of
        firing an ``is_invited`` per collection. The rules themselves stay in
        this one method — ``None`` (the default) asks the database.
        """
        if self.is_owner(user_code):
            return True
        if self.status == self.Status.INACTIVE:
            return False
        if self.is_public():
            return True
        if invited_to is not None:
            return self.code in invited_to
        return self.is_invited(user_code)
