# Data migration — mark the 5 demo collections as onboarding collections.
# These are the collections every new user joining via /popin is added to.

from django.db import migrations

ONBOARDING_CODES = ["La1aC1", "L3L3C1", "l1l1C1", "l0l0C1", "1u1uC1"]


def mark_onboarding_collections(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Collection.objects.filter(code__in=ONBOARDING_CODES).update(is_onboarding=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_add_is_onboarding_to_collection"),
    ]

    operations = [
        migrations.RunPython(mark_onboarding_collections, noop),
    ]
