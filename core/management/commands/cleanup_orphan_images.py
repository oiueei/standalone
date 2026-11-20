"""
Management command to delete orphaned images from object storage (#9).

An "orphan" is an image that was uploaded (a ticketed direct-to-bucket upload
from a form) but whose form was never submitted, so no DB row ever referenced
its key. Deleting on record-delete — and, since 2026-10-02, on a save that
replaces or removes a key — is handled by ``core.services.asset_cleanup``; this
command catches the *other* leak — uploads that never became a record at all,
and anything that changed a row without going through ``save()``.

**Dry-run is the default.** It only lists what it *would* delete; pass
``--commit`` to actually delete. Safe to run on Heroku:

    # dry-run
    heroku run --app <app> "python manage.py cleanup_orphan_images"
    # delete — the bucket must be named, and must be the configured one
    heroku run --app <app> "python manage.py cleanup_orphan_images --bucket <bucket> --commit"

(Quote the inner command so the Heroku CLI doesn't eat ``--commit``.)

Safety rails:
- **Names its target.** ``--commit`` refuses to run unless ``--bucket`` names
  the very bucket this deployment has configured (``OBJECT_STORAGE_BUCKET``),
  and a ``--bucket`` that does not match is refused even on a dry-run — so a
  ``.env`` pointing at another deployment's storage is a refusal, never a
  deletion from that deployment's bucket.
- **Only lists the upload folders** (``storage.ASSET_FOLDERS``: things,
  collections, users, documents — the folders a ticketed upload may write to).
  Scanning the whole ``oiueei/`` tree treated everything unreferenced as an
  orphan, and the production dry-run of 2026-09-28 duly listed
  ``oiueei/assets/Curiosa-Variable.woff2`` — the variable font the Heroku
  build downloads in ``heroku-postbuild`` (not in git, licence): deleting it
  would have broken every deploy after it. Any other prefix — ``assets/`` and
  whatever comes next — is out by construction, not by an exception list, and
  a ``--prefix`` that does not fall inside an upload folder is refused with a
  ``CommandError`` before anything is listed.
- Cross-references **every** DB asset field — Thing.thumbnail + Thing.gallery,
  User.photo, Collection.thumbnail, Collection.welcome_doc and BookingPeriod.terms_doc
  (the document a borrower accepted), the one table in
  ``asset_cleanup.ASSET_FIELDS`` — so anything in use is kept. The welcome PDF
  matters here: it is an object in the same tree as the photos, so it turns up
  in this sweep like any of them, and a missing cross-reference would delete a
  live document. Welcome docs live in ``oiueei/documents/``, one of the
  upload folders, so they are swept alongside every other folder and
  cross-referenced the same way.
- Never touches the ``oiueei/seed/`` folder (the demo's shared image pool) —
  structurally now, since the seed folder is not an upload folder and is never
  listed; the explicit prefix check stays as a second lock.
- Only considers assets **older than --min-age-hours** (default 24h) so an
  in-flight upload mid-form isn't mistaken for an orphan, and **younger than
  --max-age-days** (default 30) so it stays a recent-window sweep. Run it
  regularly (e.g. weekly) and every orphan is caught within its window.

The age comes from S3's ``LastModified``, which for these objects is the upload
time: a key is random, written once and never rewritten, so nothing else can
move it. That is the property the window relies on, and the reason an object
must never be overwritten in place — doing so would reset its clock and hide it
from the sweep for another day.

**On checksums**, because this is the command that would break first: botocore
1.36 began sending ``x-amz-checksum-crc32`` by default and dropping
``Content-MD5``, and several S3-compatible providers reject it on
``DeleteObjects`` specifically. Verified accepted on Hetzner with botocore
1.43.78. If a future bump makes deletion start failing here, the rescue is in
``core/services/storage.py``, not in this file.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dj_timezone

from core.services import asset_cleanup, storage

SEED_PREFIX = storage.SEED_PREFIX
DELETE_BATCH = 100


class Command(BaseCommand):
    help = "Delete orphaned images from object storage (uploaded but never saved to a record)."

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
            default=None,
            help=(
                "Narrow the sweep to one upload folder (e.g. 'oiueei/things/'). Default: "
                "every upload folder. A prefix outside the upload folders is refused — "
                "the sweep only considers uploaded assets."
            ),
        )
        parser.add_argument(
            "--bucket",
            default=None,
            help=(
                "The bucket you mean to delete from. With --commit it is required and must "
                "equal this deployment's OBJECT_STORAGE_BUCKET; a mismatched value is "
                "refused even on a dry-run."
            ),
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        bucket = options["bucket"]
        prefix = options["prefix"]
        configured_bucket = settings.OBJECT_STORAGE_BUCKET

        # The wrong .env has happened (the local one once
        # carried the production key), and against the wrong bucket this
        # command is not an error — it is a deletion. So a delete has to name
        # its target, and even a dry-run refuses a mismatched name, so the
        # mistake surfaces before --commit is ever added.
        if bucket is not None and bucket != configured_bucket:
            raise CommandError(
                f"Refusing to run: --bucket {bucket!r} does not match this deployment's "
                f"OBJECT_STORAGE_BUCKET ({configured_bucket!r})."
            )
        if commit and bucket is None:
            raise CommandError(
                "--commit requires --bucket, so the deletion names its target. This "
                f"deployment's OBJECT_STORAGE_BUCKET is {configured_bucket!r} — pass "
                "exactly that."
            )
        now = dj_timezone.now()
        min_age = dj_timezone.timedelta(hours=options["min_age_hours"])
        max_age = dj_timezone.timedelta(days=options["max_age_days"])

        scan_prefixes = self._scan_prefixes(prefix)
        referenced = self._referenced_keys()
        self.stdout.write(f"Referenced by DB: {len(referenced)} image(s).")

        scanned = seed_skipped = referenced_skipped = window_skipped = 0
        orphans = []

        for asset in self._iter_objects(scan_prefixes):
            scanned += 1
            key = asset["key"]

            if key.startswith(SEED_PREFIX):
                seed_skipped += 1
                continue
            if key in referenced:
                referenced_skipped += 1
                continue

            created = asset["last_modified"]
            # Too new (maybe mid-form) or too old (outside the recent window) → leave it.
            if created is None or created > now - min_age or created < now - max_age:
                window_skipped += 1
                continue

            orphans.append((key, created))

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

        deleted = self._delete([key for key, _ in orphans])
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} orphan image(s)."))

    def _scan_prefixes(self, prefix):
        """The prefixes to list: every upload folder, or the one a --prefix narrows to.

        The sweep only ever considers ``storage.ASSET_FOLDERS`` — the folders a
        ticketed upload may write to. Everything else under ``oiueei/`` is out
        by construction, not by an exception list: the production dry-run of
        2026-09-28 listed the build's own font (``oiueei/assets/``, not in
        git), and deleting it would have broken every deploy after it. So a
        --prefix that does not fall inside an upload folder is a mistake about
        what this command may even look at — refused before anything is listed.
        """
        folders = sorted(storage.ASSET_FOLDERS)
        # Listed with their trailing slash: an object store's prefix is a plain
        # string match, so a bare "oiueei/users" would also list a sibling like
        # "oiueei/users-old/".
        if prefix is None:
            return [f"{folder}/" for folder in folders]
        normalized = prefix.rstrip("/")
        if normalized in folders:
            return [f"{normalized}/"]
        if not any(normalized.startswith(folder + "/") for folder in folders):
            raise CommandError(
                f"Refusing to run: --prefix {prefix!r} is not inside any upload folder "
                f"({', '.join(folders)}). The sweep only considers uploaded assets."
            )
        return [prefix]

    def _referenced_keys(self):
        """Every storage key referenced by any DB record.

        Read from ``asset_cleanup.ASSET_FIELDS``, the one table of key-holding
        columns that the delete handlers use too. The welcome PDF is in it: it
        lives in the same tree as the photos, so this sweep sees it, and it has to
        be protected like any other asset.
        """
        return asset_cleanup.referenced_keys()

    def _iter_objects(self, prefixes):
        """Yield every stored object under each prefix, paginated.

        Wrapped so a misconfigured or unreachable bucket surfaces as a clean
        CommandError rather than a traceback — this is run by hand, usually on a
        dyno, and the first thing to get wrong is the credentials.
        """
        try:
            for prefix in prefixes:
                yield from storage.iter_objects(prefix)
        except Exception as exc:  # noqa: BLE001 — surface any storage/config error cleanly
            raise CommandError(f"Could not list stored objects: {exc}") from exc

    def _delete(self, keys):
        """Delete in batches. Returns the count actually handed over.

        The batch size is well inside S3's own limit of 1000 per DeleteObjects
        call; it is kept at 100 so one failed batch costs a hundred orphans and
        not a thousand.
        """
        deleted = 0
        for i in range(0, len(keys), DELETE_BATCH):
            batch = keys[i : i + DELETE_BATCH]
            try:
                deleted += storage.delete_many(batch)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"Failed to delete batch: {exc}"))
        return deleted

    def _report_scan(self, scanned, seed_skipped, referenced_skipped, window_skipped, orphans):
        self.stdout.write(
            f"Scanned {scanned} asset(s): "
            f"{referenced_skipped} in use, {seed_skipped} seed, "
            f"{window_skipped} outside the age window, {len(orphans)} orphan(s)."
        )
        for key, created in orphans:
            self.stdout.write(f"  orphan: {key}  (uploaded {created:%Y-%m-%d %H:%M} UTC)")
