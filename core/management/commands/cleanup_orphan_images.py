"""
Management command to delete orphaned Cloudinary images (#9).

An "orphan" is an image that was uploaded (a signed direct-to-Cloudinary upload
from a form) but whose form was never submitted, so no DB row ever referenced
its public_id. Deleting on record-delete is already handled by
``core.services.cloudinary_cleanup``; this command catches the *other* leak —
uploads that never became a record at all.

**Dry-run is the default.** It only lists what it *would* delete; pass
``--commit`` to actually delete. Safe to run on Heroku:

    heroku run --app <app> "python manage.py cleanup_orphan_images"           # dry-run
    heroku run --app <app> "python manage.py cleanup_orphan_images --commit"  # delete

(Quote the inner command so the Heroku CLI doesn't eat ``--commit``.)

Safety rails:
- Cross-references **every** DB image field — Thing.thumbnail + Thing.gallery,
  User.photo, Collection.thumbnail — so anything in use is kept.
- Never touches the ``oiueei/seed/`` folder (the demo's shared image pool).
- Only considers assets **older than --min-age-hours** (default 24h) so an
  in-flight upload mid-form isn't mistaken for an orphan, and **younger than
  --max-age-days** (default 30) so it stays a recent-window sweep. Run it
  regularly (e.g. weekly) and every orphan is caught within its window.
"""

from datetime import datetime, timezone

import cloudinary.api
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dj_timezone

from core.models import Collection, Thing, User

SEED_PREFIX = "oiueei/seed/"
PAGE_SIZE = 500
DELETE_BATCH = 100


class Command(BaseCommand):
    help = "Delete orphaned Cloudinary images (uploaded but never saved to a record)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually delete. Without this flag the command is a dry-run (default).",
        )
        parser.add_argument(
            "--min-age-hours",
            type=int,
            default=24,
            help="Ignore assets newer than this — skips in-flight uploads (default 24h).",
        )
        parser.add_argument(
            "--max-age-days",
            type=int,
            default=30,
            help="Ignore assets older than this — keeps it a recent-window sweep (default 30).",
        )
        parser.add_argument(
            "--prefix",
            default="oiueei/",
            help="Cloudinary public_id prefix to scan (default 'oiueei/').",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        prefix = options["prefix"]
        now = dj_timezone.now()
        min_age = dj_timezone.timedelta(hours=options["min_age_hours"])
        max_age = dj_timezone.timedelta(days=options["max_age_days"])

        referenced = self._referenced_public_ids()
        self.stdout.write(f"Referenced by DB: {len(referenced)} image(s).")

        scanned = seed_skipped = referenced_skipped = window_skipped = 0
        orphans = []

        for asset in self._iter_cloudinary(prefix):
            scanned += 1
            public_id = asset["public_id"]

            if public_id.startswith(SEED_PREFIX):
                seed_skipped += 1
                continue
            if public_id in referenced:
                referenced_skipped += 1
                continue

            created = self._parse_created(asset.get("created_at"))
            # Too new (maybe mid-form) or too old (outside the recent window) → leave it.
            if created is None or created > now - min_age or created < now - max_age:
                window_skipped += 1
                continue

            orphans.append((public_id, created))

        self._report_scan(scanned, seed_skipped, referenced_skipped, window_skipped, orphans)

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphans to remove."))
            return

        if not commit:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {len(orphans)} orphan(s) would be deleted. "
                    "Re-run with --commit to delete."
                )
            )
            return

        deleted = self._delete([pid for pid, _ in orphans])
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} orphan image(s)."))

    def _referenced_public_ids(self):
        """Every Cloudinary public_id referenced by any DB record."""
        referenced = set()
        for thumbnail, gallery in Thing.objects.values_list("thumbnail", "gallery"):
            if thumbnail:
                referenced.add(thumbnail)
            for public_id in gallery or []:
                if public_id:
                    referenced.add(public_id)
        referenced.update(p for p in User.objects.values_list("photo", flat=True) if p)
        referenced.update(t for t in Collection.objects.values_list("thumbnail", flat=True) if t)
        return referenced

    def _iter_cloudinary(self, prefix):
        """Yield every upload-type Cloudinary asset under ``prefix``, paginated."""
        cursor = None
        while True:
            try:
                resp = cloudinary.api.resources(
                    type="upload",
                    prefix=prefix,
                    max_results=PAGE_SIZE,
                    next_cursor=cursor,
                )
            except Exception as exc:  # noqa: BLE001 — surface any Cloudinary/config error cleanly
                raise CommandError(f"Could not list Cloudinary resources: {exc}") from exc
            yield from resp.get("resources", [])
            cursor = resp.get("next_cursor")
            if not cursor:
                break

    @staticmethod
    def _parse_created(value):
        """Parse Cloudinary's ISO ``created_at`` (e.g. '2026-06-20T12:34:56Z') to aware UTC."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except (ValueError, AttributeError):
            return None

    def _delete(self, public_ids):
        """Delete in batches of 100 (Cloudinary's per-call limit). Returns the count."""
        deleted = 0
        for i in range(0, len(public_ids), DELETE_BATCH):
            batch = public_ids[i : i + DELETE_BATCH]
            try:
                cloudinary.api.delete_resources(batch, invalidate=True)
                deleted += len(batch)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"Failed to delete batch: {exc}"))
        return deleted

    def _report_scan(self, scanned, seed_skipped, referenced_skipped, window_skipped, orphans):
        self.stdout.write(
            f"Scanned {scanned} asset(s): "
            f"{referenced_skipped} in use, {seed_skipped} seed, "
            f"{window_skipped} outside the age window, {len(orphans)} orphan(s)."
        )
        for public_id, created in orphans:
            self.stdout.write(f"  orphan: {public_id}  (uploaded {created:%Y-%m-%d %H:%M} UTC)")
