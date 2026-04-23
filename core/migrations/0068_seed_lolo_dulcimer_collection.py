# Retired: demo data now lives in core/management/commands/seed_demo.py.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0067_seed_lele_plant_collection"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
