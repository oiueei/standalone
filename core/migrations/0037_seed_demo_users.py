# Data migration — seed demo users for first-time installations.
# Uses get_or_create so it is safe to run on existing databases.

from django.db import migrations


def seed_demo_users(apps, schema_editor):
    User = apps.get_model("core", "User")

    User.objects.get_or_create(
        code="La1aN1",
        defaults={
            "email": "lala@mail.com",
            "name": "Lala",
            "headline": "Three cheers for second-hand!",
            "theeeme_id": "BUU331",
            "koro": "basic",
        },
    )

    User.objects.get_or_create(
        code="L3L3oo",
        defaults={
            "email": "lele@mail.com",
            "name": "Lele",
            "headline": "Here! Now!! Sharing!!!",
            "theeeme_id": "K0P4R1",
            "koro": "basic",
        },
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_seed_default_theeemes"),
    ]

    operations = [
        migrations.RunPython(seed_demo_users, noop),
    ]
