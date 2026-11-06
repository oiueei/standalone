"""
Seed demo data for OIUEEI (Lala, Lele, Lili, Lolo, Lulu and all their things).

This command is idempotent — run it as many times as you like. The text content
for each supported language lives in `core/management/commands/seed_data/`.

**Collection and thing text is seeded in every language at once**: each
headline/description is stored as a localized ``{"es": …, "ca": …, "en": …}``
map built from all the language files, so every reader sees the demo in their
own language — one seeding serves every deployment. Tag labels are localized
too (as constants in ``common.py``). The ``--lang`` flag only chooses the
language of the **non-localizable** text: user bios, FAQ questions/answers
and locations (plain columns).

Usage:
    python manage.py seed_demo                     # non-localizable text in English
    python manage.py seed_demo --lang=es           # … in Spanish
    python manage.py seed_demo --lang=ca --reset   # wipe demos, re-seed, Catalan FAQs
    heroku run --app … "python manage.py seed_demo --lang=es"

To add a new language, copy `seed_data/en.py` to e.g. `seed_data/pt.py`, translate
the text fields, and add the code to SUPPORTED_LANGS below.
"""

import json
from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import FAQ, RSVP, BookingPeriod, Collection, NetworkPoint, Thing, User
from core.models.transfer import ThingTransfer
from core.services import storage

from .seed_data import common

SUPPORTED_LANGS = ["en", "es", "ca"]

# Entities whose text every reader should get in their own language, and the
# fields the {lang: text} maps are built for. Everything else (user bios, FAQs)
# is plain-column text and follows --lang.
_LOCALIZED_FIELDS = {
    "COLLECTIONS": ("headline", "description"),
    "THINGS": ("headline", "description"),
    # A pickup point's hours are plain text and follow --lang; its about and the
    # conditions it writes are owner text like any other.
    "NETWORK_POINTS": ("about", "deposit_policy", "request_info", "email_note"),
}
_LOCALIZED_ENTITIES = tuple(_LOCALIZED_FIELDS)

# Key order inside a stored map — es first mirrors resolve_localized's fallback.
_LANG_ORDER = ["es", "ca", "en"]

# User codes that identify demo accounts — used by --reset to scope deletion.
DEMO_USER_CODES = ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh", "1u1ucs"]


def _place_characters(relation, wanted_codes):
    """Make the demo characters in ``relation`` exactly ``wanted_codes``, touching no one else."""
    wanted = set(wanted_codes)
    relation.add(*User.objects.filter(code__in=wanted))
    relation.remove(*relation.filter(code__in=DEMO_USER_CODES).exclude(code__in=wanted))


# Demo fixture images live in their own storage folder, cleanly separated from
# real user uploads (which land in oiueei/{users,things,collections,documents}/).
# The seed stores bare ids (see common.py); this prefix is applied at seed time so
# the stored public_id resolves to the fixture.
#
# Defined in `storage` because two sweeps have to agree with it about which keys
# are untouchable — the orphan sweep and the delete-time cleanup. It was written
# out by hand in three places, which is one drift away from a demo that deletes
# its own photographs.
SEED_IMAGE_FOLDER = storage.SEED_PREFIX


def _seed_image(public_id):
    """Prefix a bare demo image id with its storage folder (empty stays empty)."""
    return f"{SEED_IMAGE_FOLDER}{public_id}" if public_id else public_id


# The field each entity is matched on when merging skeleton + localised text.
_MERGE_KEYS = {
    "USERS": "code",
    "COLLECTIONS": "code",
    "THINGS": "code",
    "FAQS": "thing_code",
    "NETWORK_POINTS": "code",
}


def _merge_by(key, skeleton, localised):
    """Merge each structural skeleton row with its localised text, matched on `key`."""
    text_by_key = {item[key]: item for item in localised}
    return [{**row, **text_by_key.get(row[key], {})} for row in skeleton]


def _localize(values_by_lang):
    """One stored value from a text's per-language variants.

    All present variants identical (or just one) → the plain string, so the
    localized machinery stays invisible where it buys nothing. Distinct →
    the serialized strict ``{lang: text}`` map that ``core.utils.parse_localized``
    recognises, so each reader resolves their own language.
    """
    present = {lang: values_by_lang[lang] for lang in _LANG_ORDER if values_by_lang.get(lang)}
    distinct = set(present.values())
    if len(distinct) <= 1:
        return next(iter(distinct), "")
    return json.dumps(present, ensure_ascii=False)


def load_seed_data(lang):
    """Build the seed data: the shared structural skeleton (``common``) with
    ``lang``'s text merged on top — and, for collections/things, the
    headline/description rebuilt as localized maps across ALL languages."""
    texts = {
        code: import_module(f"core.management.commands.seed_data.{code}")
        for code in SUPPORTED_LANGS
    }
    merged = {
        entity: _merge_by(key, getattr(common, entity), getattr(texts[lang], entity))
        for entity, key in _MERGE_KEYS.items()
    }
    for entity in _LOCALIZED_ENTITIES:
        key = _MERGE_KEYS[entity]
        rows_by_lang = {
            code: {row[key]: row for row in getattr(texts[code], entity)}
            for code in SUPPORTED_LANGS
        }
        for row in merged[entity]:
            for field in _LOCALIZED_FIELDS[entity]:
                row[field] = _localize(
                    {
                        code: rows_by_lang[code].get(row[key], {}).get(field, "")
                        for code in SUPPORTED_LANGS
                    }
                )
    return SimpleNamespace(**merged)


class Command(BaseCommand):
    help = "Populate demo data (users, collections, things, FAQs, transfers). Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lang",
            default="en",
            choices=SUPPORTED_LANGS,
            help="Language variant for text content (default: en).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all demo data before seeding (leaves other data intact).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        lang = options["lang"]
        data = load_seed_data(lang)

        if options["reset"]:
            self._reset()
            self.stdout.write(self.style.WARNING("Deleted existing demo data."))

        self._seed_users(data.USERS)
        self._seed_collections(data.COLLECTIONS)
        self._seed_points(data.NETWORK_POINTS)
        self._seed_invitations(common.PENDING_INVITATIONS)
        self._seed_things(data.THINGS)
        self._seed_faqs(data.FAQS)
        self._seed_bookings(common.BOOKINGS)
        self._seed_transfers(common.TRANSFERS)
        self._seed_transfers(common.COMMUNITY_TRANSFERS)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded [{lang}] {len(data.USERS)} users, {len(data.COLLECTIONS)} collections, "
                f"{len(data.THINGS)} things, {len(data.NETWORK_POINTS)} pickup points, "
                f"{len(data.FAQS)} FAQs, "
                f"{len(common.PENDING_INVITATIONS)} pending invitations, "
                f"{len(common.BOOKINGS)} bookings, "
                f"{len(common.TRANSFERS) + len(common.COMMUNITY_TRANSFERS)} transfers."
            )
        )

    # ---- helpers ----

    def _reset(self):
        # The demo reuses fixed, shared storage keys — suspend the delete-time
        # cleanup so wiping demo rows doesn't destroy the images the immediate
        # re-seed points back at.
        from core.services import asset_cleanup
        from core.services.deletion_events import deletion_events_suppressed

        # Nor is the demo's history real: no deletion event for what is wiped.
        with asset_cleanup.suspended(), deletion_events_suppressed():
            Thing.objects.filter(owner_id__in=DEMO_USER_CODES).delete()
            Collection.objects.filter(owner_id__in=DEMO_USER_CODES).delete()
            User.objects.filter(code__in=DEMO_USER_CODES).delete()

    def _seed_users(self, users):
        for data in users:
            User.objects.update_or_create(
                code=data["code"],
                defaults={
                    "email": f"{data['email_local']}@{settings.SEED_EMAIL_DOMAIN}",
                    "name": data["name"],
                    "headline": data["headline"],
                    "photo": _seed_image(data.get("photo", "")),
                    "about": data.get("about", ""),
                    # Optional profile fields. `age_range` and `postal_code` are
                    # shown to the owner of a COMMUNITY collection and to nobody
                    # else (see CollectionSerializer.get_invites) — the demo needs
                    # them filled for that view to have anything to render, and
                    # Lili leaves both blank so the "not declared" case shows too.
                    #
                    # `language` is the strongest link in the email hierarchy
                    # (deployment default → collection → recipient), so Lele reads
                    # her mail in Catalan and Lulu in English whatever the
                    # deployment speaks.
                    "age_range": data.get("age_range", ""),
                    "postal_code": data.get("postal_code", ""),
                    "language": data.get("language", ""),
                    # Demos opt INTO news so the digest collection in
                    # seed_data/common.py keeps landing in an inbox regardless of
                    # the model default (which is OFF for real new users — DESIGN §6).
                    "notify_news": True,
                },
            )

    def _seed_collections(self, collections):
        for data in collections:
            defaults = {
                "owner": User.objects.get(code=data["owner_code"]),
                "headline": data["headline"],
                "description": data["description"],
                "status": "ACTIVE",
                "kind": data["kind"],
                # The collection's own palette (the characters have none): a
                # demo collection looks the way its founder's always did.
                "theeeme_id": data["theeeme_id"],
                "koro": data.get("koro", "basic"),
                "mode": data.get("mode", "PROPRIETARY"),
                "visibility": data.get("visibility", "PRIVATE"),
                "is_onboarding": data.get("is_onboarding", False),
                "digest_frequency": data.get("digest_frequency", "NONE"),
                "thumbnail": _seed_image(data.get("thumbnail", "")),
                "tags": data.get("tags", []),
                "allowed_thing_types": data.get("allowed_thing_types", []),
                "deposit_policy": data.get("deposit_policy", ""),
                # Empty is the "no fixed rule" default the model documents, so a
                # collection that says nothing keeps the free date range.
                "rental_durations": data.get("rental_durations", []),
                "rental_weekdays": data.get("rental_weekdays", []),
                "reservation_max_days": data.get("reservation_max_days", 1),
                "reservation_horizon_days": data.get("reservation_horizon_days", 90),
                "closed_dates": data.get("closed_dates", []),
            }
            col, _ = Collection.objects.update_or_create(code=data["code"], defaults=defaults)
            # Only the demo characters are the seed's to place: on a deployment
            # where real people joined a demo collection, replacing the whole
            # list would put every one of them out of a group they belong to.
            # Add the characters it should hold, take out the ones it should not,
            # and leave anybody else exactly where they are.
            _place_characters(col.invites, data.get("invites", []))
            # A subset of invites, promoted — co_owners ⊆ invites is the invariant
            # the promote endpoint enforces, and re-running the seed must not
            # violate it either.
            _place_characters(col.co_owners, data.get("co_owners", []))
            col.co_owners.remove(
                *col.co_owners.filter(code__in=DEMO_USER_CODES).exclude(pk__in=col.invites.all())
            )

    def _seed_points(self, points):
        """The pickup points of the demo network, one per dinamizador, and the identity card
        of a co-curator outside it.

        Like the rest of the group, only the demo characters' points are the seed's:
        one it no longer places is taken out, and a point of anybody else is left
        where it is.
        """
        for data in points:
            NetworkPoint.objects.update_or_create(
                collection=Collection.objects.get(code=data["collection_code"]),
                user=User.objects.get(code=data["user_code"]),
                defaults={
                    "entity_name": data["entity_name"],
                    "address": data["address"],
                    "hours_note": data["hours_note"],
                    "contact": data["contact"],
                    "about": data["about"],
                    "weekdays": data["weekdays"],
                    "closed_dates": data["closed_dates"],
                    "deposit_policy": data["deposit_policy"],
                    "request_info": data["request_info"],
                    "email_note": data["email_note"],
                },
            )
        wanted = {(p["collection_code"], p["user_code"]) for p in points}
        for point in NetworkPoint.objects.filter(user_id__in=DEMO_USER_CODES):
            if (point.collection_id, point.user_id) not in wanted:
                point.delete()

    def _seed_invitations(self, invitations):
        """Invitations the guest has not answered yet (COLLECTION_INVITE RSVPs).

        `created` is set on every run — the row's whole meaning is "still waiting",
        and its 30-day lifetime is measured from here, so a re-seed has to restart
        the clock or the demo would ship invitations already half-expired.
        """
        for code, collection_code, user_code, days_ago in invitations:
            user = User.objects.get(code=user_code)
            RSVP.objects.update_or_create(
                code=code,
                defaults={
                    "user_code": user,
                    "user_email": user.email,
                    "action": RSVP.Action.COLLECTION_INVITE,
                    "target_code": collection_code,
                    "created": timezone.now() - timedelta(days=days_ago),
                },
            )

    def _seed_things(self, things):
        for data in things:
            owner = User.objects.get(code=data["owner_code"])
            defaults = {
                "type": data["type"],
                "owner": owner,
                "headline": data["headline"],
                "description": data.get("description", ""),
                "status": "ACTIVE",
                "fee": data.get("fee", None),
                "deposit": data.get("deposit", None),
                "condition": data.get("condition", ""),
                "availability": data.get("availability", ""),
                "location": data.get("location", ""),
                "thumbnail": _seed_image(data.get("thumbnail", "")),
                "gallery": [_seed_image(g) for g in data.get("gallery", [])],
                "tags": data.get("tags", []),
                "is_endless": data.get("is_endless", False),
                "units": data.get("units", 1),
            }
            thing, _ = Thing.objects.update_or_create(code=data["code"], defaults=defaults)
            for col_code in data.get("collections", []):
                Collection.objects.get(code=col_code).things.add(thing)

    def _seed_faqs(self, faqs):
        for data in faqs:
            FAQ.objects.update_or_create(
                thing=Thing.objects.get(code=data["thing_code"]),
                questioner=User.objects.get(code=data["questioner_code"]),
                question=data["question"],
                defaults={"answer": data["answer"], "is_visible": True},
            )

    def _seed_bookings(self, bookings):
        for code, thing_code, owner_code, requester_code, start, end, status in bookings:
            requester = User.objects.get(code=requester_code)
            thing = Thing.objects.get(code=thing_code)
            BookingPeriod.objects.update_or_create(
                code=code,
                defaults={
                    "thing_code": thing,
                    # Read off the thing rather than written per row: the column is
                    # a snapshot of what was agreed, and a seed that could disagree
                    # with the thing it points at is a snapshot of nothing. LEND and
                    # RENT carry dates; GIFT and SELL are single-use and carry none.
                    "thing_type": thing.type,
                    "owner_code": User.objects.get(code=owner_code),
                    "requester_code": requester,
                    # Copied, not looked up, for the same reason the column is:
                    # what the request said stays what it said.
                    "requester_email": requester.email,
                    "start_date": start,
                    "end_date": end,
                    "status": status,
                },
            )

    def _seed_transfers(self, transfers):
        # Rows are five- or six-element: the sixth is the booking this handover
        # came from. Older rows have none — those are manual transfers, which the
        # model allows (`booking` is nullable) and which say nothing about a
        # request, because there wasn't one.
        for thing_code, from_code, to_code, lent_date, returned_date, *rest in transfers:
            booking = BookingPeriod.objects.get(code=rest[0]) if rest else None
            ThingTransfer.objects.get_or_create(
                thing=Thing.objects.get(code=thing_code),
                from_user=User.objects.get(code=from_code),
                to_user=User.objects.get(code=to_code),
                lent_date=lent_date,
                defaults={"returned_date": returned_date, "booking": booking},
            )
