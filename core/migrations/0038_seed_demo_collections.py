# Data migration — seed demo collections for first-time installations.
# Uses get_or_create so it is safe to run on existing databases.

from django.db import migrations


def seed_demo_collections(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    User = apps.get_model("core", "User")

    lala = User.objects.get(code="La1aN1")
    lele = User.objects.get(code="L3L3oo")

    lala_collection, _ = Collection.objects.get_or_create(
        code="La1aC1",
        defaults={
            "owner": lala,
            "headline": "Lala's off on sabbatical, flogging it all for a tenner!",
            "description": (
                "Three rules, mate: cash only, you come fetch it yerself, deadline's the 25th. "
                "Anything left? Straight to the local orphanage!"
            ),
            "status": "ACTIVE",
        },
    )
    lala_collection.invites.add(lele)

    lele_collection, _ = Collection.objects.get_or_create(
        code="L3L3C1",
        defaults={
            "owner": lele,
            "headline": "Lele's Cakes!",
            "description": (
                "I craft stunning homemade cakes using only 100% natural, healthy ingredients. "
                "Perfect for mindful celebrations like birthdays, adaptable to vegan, gluten-free "
                "or low-sugar diets—contact me to personalise yours!"
            ),
            "status": "ACTIVE",
        },
    )
    lele_collection.invites.add(lala)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_seed_demo_users"),
    ]

    operations = [
        migrations.RunPython(seed_demo_collections, noop),
    ]
