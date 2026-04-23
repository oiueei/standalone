# Retired: demo data now lives in core/management/commands/seed_demo.py.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0064_update_lolo_books_to_event_things"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
