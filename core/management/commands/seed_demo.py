"""
Seed demo data for OIUEEI (Lala, Lele, Lili, Lolo, Lulu and all their things).

This command is idempotent — run it as many times as you like. The text content
for each supported language lives in `core/management/commands/seed_data/`; the
command selects one via the `--lang` flag.

Usage:
    python manage.py seed_demo                     # English (default)
    python manage.py seed_demo --lang=es           # Spanish
    python manage.py seed_demo --lang=es --reset   # wipe demos, re-seed in Spanish
    heroku run python manage.py seed_demo --app …  # Heroku one-off dyno

To add a new language, copy `seed_data/en.py` to e.g. `seed_data/ca.py`, translate
the text fields, and add the code to SUPPORTED_LANGS below.
"""

from importlib import import_module

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import FAQ, Collection, Thing, User
from core.models.transfer import ThingTransfer

from .seed_data import common

SUPPORTED_LANGS = ["en", "es"]

# User codes that identify demo accounts — used by --reset to scope deletion.
DEMO_USER_CODES = ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh", "1u1ucs"]


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
        data = import_module(f"core.management.commands.seed_data.{lang}")

        if options["reset"]:
            self._reset()
            self.stdout.write(self.style.WARNING("Deleted existing demo data."))

        self._seed_users(data.USERS)
        self._seed_collections(data.COLLECTIONS)
        self._seed_things(data.THINGS)
        self._seed_faqs(data.FAQS)
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
                "is_swap": data.get("is_swap", False),
                "is_share": data.get("is_share", False),
                "is_minimalist": data.get("is_minimalist", False),
                "is_onboarding": data.get("is_onboarding", False),
                "newsletter_enabled": data.get("newsletter_enabled", False),
                "digest_frequency": data.get("digest_frequency", "NONE"),
                "thumbnail": data.get("thumbnail", ""),
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
                "thumbnail": data.get("thumbnail", ""),
                "documents": data.get("documents", []),
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

    def _seed_transfers(self, transfers):
        for thing_code, from_code, to_code, lent_date, returned_date in transfers:
            ThingTransfer.objects.get_or_create(
                thing=Thing.objects.get(code=thing_code),
                from_user=User.objects.get(code=from_code),
                to_user=User.objects.get(code=to_code),
                lent_date=lent_date,
                defaults={"returned_date": returned_date},
            )
