# Retired: demo data now lives in core/management/commands/seed_demo.py.
# This migration is kept as a no-op to preserve migration history — existing
# deployments that already ran it will see no change; fresh deployments will
# not create any demo data until `manage.py seed_demo` is run explicitly.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_seed_default_theeemes"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
