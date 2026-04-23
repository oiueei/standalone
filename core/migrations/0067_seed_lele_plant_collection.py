# Retired: demo data now lives in core/management/commands/seed_demo.py.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0066_seed_lulu_share_collection"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
