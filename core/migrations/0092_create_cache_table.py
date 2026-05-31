"""Create the database cache table backing DatabaseCache.

The cache table is the shared store for django-ratelimit counters (and any
future response caching). Running it as a migration means Heroku's
`release: migrate` phase creates it automatically — no manual
`createcachetable` step — and the test database gets it too.
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # Idempotent: createcachetable skips tables that already exist.
    # The table name is read from CACHES["default"]["LOCATION"].
    call_command("createcachetable", database=schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0091_thingtransfer_uniq_transfer_per_booking_thing"),
    ]

    operations = [
        # Reverse is a no-op: leaving an unused cache table behind is harmless.
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
