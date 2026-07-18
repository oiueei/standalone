"""
Seed demo data for OIUEEI (Lala, Lele, Lili, Lolo, Lulu and all their things).

This command is idempotent — run it as many times as you like. The text content
for each supported language lives in `core/management/commands/seed_data/`.

**Collection and thing text is seeded in every language at once** (O6): each
headline/description is stored as a localized ``{"es": …, "ca": …, "en": …}``
map built from all the language files, so every reader sees the demo in their
own language — one seeding serves every deployment. Tag labels are localized
too (as constants in ``common.py``). The ``--lang`` flag only chooses the
language of the **non-localizable** text: user bios, FAQ questions/answers,
wish-response messages and locations (plain columns).

Usage:
    python manage.py seed_demo                     # non-localizable text in English
    python manage.py seed_demo --lang=es           # … in Spanish
    python manage.py seed_demo --lang=ca --reset   # wipe demos, re-seed, Catalan FAQs
    heroku run --app … "python manage.py seed_demo --lang=es"

To add a new language, copy `seed_data/en.py` to e.g. `seed_data/pt.py`, translate
the text fields, and add the code to SUPPORTED_LANGS below.
"""

import json
from importlib import import_module
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import FAQ, Collection, Thing, User, WishResponse
from core.models.transfer import ThingTransfer

from .seed_data import common

SUPPORTED_LANGS = ["en", "es", "ca"]

# Entities whose text every reader should get in their own language, and the
# fields the {lang: text} maps are built for. Everything else (user bios, FAQs,
# wish responses) is plain-column text and follows --lang.
_LOCALIZED_ENTITIES = ("COLLECTIONS", "THINGS")
_LOCALIZED_FIELDS = ("headline", "description")

# Key order inside a stored map — es first mirrors resolve_localized's fallback.
_LANG_ORDER = ["es", "ca", "en"]

# User codes that identify demo accounts — used by --reset to scope deletion.
DEMO_USER_CODES = ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh", "1u1ucs"]

# Demo fixture images live in their own Cloudinary folder, cleanly separated from
# real user uploads (which land in oiueei/{users,things,collections,documents}/).
# The seed stores bare ids (see common.py); this prefix is applied at seed time so
# the stored public_id resolves to the fixture. Re-point here if the folder moves.
SEED_IMAGE_FOLDER = "oiueei/seed/"


def _seed_image(public_id):
    """Prefix a bare demo image id with its Cloudinary folder (empty stays empty)."""
    return f"{SEED_IMAGE_FOLDER}{public_id}" if public_id else public_id


# The field each entity is matched on when merging skeleton + localised text.
_MERGE_KEYS = {
    "USERS": "code",
    "COLLECTIONS": "code",
    "THINGS": "code",
    "FAQS": "thing_code",
    "WISH_RESPONSES": "wish_code",
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
            for field in _LOCALIZED_FIELDS:
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
        self._seed_things(data.THINGS)
        self._seed_faqs(data.FAQS)
        self._seed_wish_responses(data.WISH_RESPONSES)
        self._seed_transfers(common.TRANSFERS)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded [{lang}] {len(data.USERS)} users, {len(data.COLLECTIONS)} collections, "
                f"{len(data.THINGS)} things, {len(data.FAQS)} FAQs, "
                f"{len(common.TRANSFERS)} transfers."
            )
        )

    # ---- helpers ----

    def _reset(self):
        # The demo reuses fixed, shared Cloudinary public ids — suspend the
        # delete-time cleanup so wiping demo rows doesn't destroy the images the
        # immediate re-seed points back at.
        from core.services import cloudinary_cleanup

        with cloudinary_cleanup.suspended():
            Thing.objects.filter(owner_id__in=DEMO_USER_CODES).delete()
            Collection.objects.filter(owner_id__in=DEMO_USER_CODES).delete()
            User.objects.filter(code__in=DEMO_USER_CODES).delete()

    def _seed_users(self, users):
        for data in users:
            User.objects.update_or_create(
                code=data["code"],
                defaults={
                    "email": data["email"],
                    "name": data["name"],
                    "headline": data["headline"],
                    "theeeme_id": data["theeeme_id"],
                    "koro": data.get("koro", "basic"),
                    "photo": _seed_image(data.get("photo", "")),
                    "about": data.get("about", ""),
                    # Demos opt INTO news so the newsletter/digest collection in
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
                "mode": data.get("mode", "PROPRIETARY"),
                "visibility": data.get("visibility", "PRIVATE"),
                "is_swap": data.get("is_swap", False),
                "is_share": data.get("is_share", False),
                "is_onboarding": data.get("is_onboarding", False),
                "newsletter_enabled": data.get("newsletter_enabled", False),
                "digest_frequency": data.get("digest_frequency", "NONE"),
                "thumbnail": _seed_image(data.get("thumbnail", "")),
                "tags": data.get("tags", []),
                "allowed_thing_types": data.get("allowed_thing_types", []),
            }
            col, _ = Collection.objects.update_or_create(code=data["code"], defaults=defaults)
            col.invites.set(User.objects.filter(code__in=data.get("invites", [])))

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
                "condition": data.get("condition", ""),
                "availability": data.get("availability", ""),
                "location": data.get("location", ""),
                "thumbnail": _seed_image(data.get("thumbnail", "")),
                "gallery": [_seed_image(g) for g in data.get("gallery", [])],
                "tags": data.get("tags", []),
                "is_endless": data.get("is_endless", False),
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

    def _seed_wish_responses(self, responses):
        for data in responses:
            WishResponse.objects.update_or_create(
                wish=Thing.objects.get(code=data["wish_code"]),
                responder=User.objects.get(code=data["responder_code"]),
                kind=data["kind"],
                defaults={
                    "message": data.get("message", ""),
                    "url": data.get("url", ""),
                    "fee": data.get("fee"),
                },
            )

    def _seed_transfers(self, transfers):
        for thing_code, from_code, to_code, lent_date, returned_date in transfers:
            ThingTransfer.objects.get_or_create(
                thing=Thing.objects.get(code=thing_code),
                from_user=User.objects.get(code=from_code),
                to_user=User.objects.get(code=to_code),
                lent_date=lent_date,
                defaults={"returned_date": returned_date},
            )
