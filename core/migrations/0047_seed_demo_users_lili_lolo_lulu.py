# Data migration — seed demo users Lili, Lolo, and Lulu for first-time installations.
# Uses get_or_create so it is safe to run on existing databases.

from django.db import migrations


def seed_demo_users(apps, schema_editor):
    User = apps.get_model("core", "User")

    User.objects.get_or_create(
        code="l1l13S",
        defaults={
            "email": "lili@mail.com",
            "name": "Lili",
            "headline": "Hurrah for the Borrow Shelf! Lili's got your gear!",
            "theeeme_id": "BUU331",
            "koro": "basic",
        },
    )

    User.objects.get_or_create(
        code="l0l0oh",
        defaults={
            "email": "lolo@mail.com",
            "name": "Lolo",
            "headline": "Heathcliff's brooding romance calls! Lolo's book club beckons!",
            "theeeme_id": "BUU331",
            "koro": "basic",
        },
    )

    User.objects.get_or_create(
        code="1u1ucs",
        defaults={
            "email": "lulu@mail.com",
            "name": "Lulu",
            "headline": "I know everyone and join every lark – your community spark!",
            "theeeme_id": "BUU331",
            "koro": "basic",
        },
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_remove_thumbnail_from_user_and_collection"),
    ]

    operations = [
        migrations.RunPython(seed_demo_users, noop),
    ]
