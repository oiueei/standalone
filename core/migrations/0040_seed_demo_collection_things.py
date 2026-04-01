# Data migration — assign demo things to demo collections.
# Uses get_or_create-safe M2M add so it is safe to run on existing databases.

from django.db import migrations


def seed_demo_collection_things(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")

    lala_collection = Collection.objects.get(code="La1aC1")
    for code in ["stffa1", "stffa2", "stffa3", "stffa4", "stffa5"]:
        lala_collection.things.add(Thing.objects.get(code=code))

    lele_collection = Collection.objects.get(code="L3L3C1")
    for code in ["cksle1", "cksle2", "cksle3", "cksle4", "cksle5"]:
        lele_collection.things.add(Thing.objects.get(code=code))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_seed_demo_things"),
    ]

    operations = [
        migrations.RunPython(seed_demo_collection_things, noop),
    ]
