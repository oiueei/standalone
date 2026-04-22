# Data migration — set Cloudinary thumbnails for all 9 seeded collections.

from django.db import migrations

THUMBNAILS = {
    "1u1uC1": "1u1uC1_j4pous",
    "L3L3C1": "L3L3C1_rbvkm2",
    "L3L3C2": "L3L3C2_nngsy2",
    "La1aC1": "La1aC1_afuutc",
    "La1aC2": "La1aC2_dodvhm",
    "l0l0C1": "l0l0C1_stookm",
    "l0l0C2": "l0l0C2_jbrjgl",
    "l1l1C1": "l1l1C1_ozv2my",
    "l1l1C2": "l1l1C2_g8rbjc",
}


def seed_thumbnails(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    for code, thumbnail in THUMBNAILS.items():
        Collection.objects.filter(code=code).update(thumbnail=thumbnail)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_add_thumbnail_to_collection"),
    ]

    operations = [
        migrations.RunPython(seed_thumbnails, noop),
    ]
