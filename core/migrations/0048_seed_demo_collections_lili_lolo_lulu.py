# Data migration — seed demo collections for Lili, Lolo, and Lulu.
# Uses get_or_create so it is safe to run on existing databases.

from django.db import migrations


def seed_demo_collections(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    User = apps.get_model("core", "User")

    lala = User.objects.get(code="La1aN1")
    lili = User.objects.get(code="l1l13S")
    lolo = User.objects.get(code="l0l0oh")
    lulu = User.objects.get(code="1u1ucs")

    lili_collection, _ = Collection.objects.get_or_create(
        code="l1l1C1",
        defaults={
            "owner": lili,
            "headline": "Lili's Borrow Borrow – Tool Time Tenants!",
            "description": (
                "Need a drill, steam cleaner, sturdy ladder, luggage scale or muffin mega-kit? "
                "Lili's lending library has your back – borrow free for coliving chores, return "
                "clean, first come first served. Sorted!"
            ),
        },
    )
    lili_collection.invites.add(lala)

    lolo_collection, _ = Collection.objects.get_or_create(
        code="l0l0C1",
        defaults={
            "owner": lolo,
            "headline": "The melancholic world of Heathcliff calls! Lolo's book club invites you!",
            "description": (
                "Craving windswept moors and tortured lovers? Dive into English romances like "
                "Wuthering Heights with Lolo's cosy book club. Borrow classics, share feels over "
                "tea – new members welcome, grab your spot for the next stormy read!"
            ),
        },
    )
    lolo_collection.invites.add(lala)

    lulu_collection, _ = Collection.objects.get_or_create(
        code="1u1uC1",
        defaults={
            "owner": lulu,
            "headline": "Lulu's Phantom Shelf – Haunt it with your clutter!",
            "description": (
                "Spot something gathering dust? Snap a pic, drop it on Lulu's ghostly online shelf "
                "– no faff, no prices, just a simple feed of coliving cast-offs. Weekly email with "
                "all the new goodies! But be quick, stuff vanishes fast!!"
            ),
        },
    )
    lulu_collection.invites.add(lala)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0047_seed_demo_users_lili_lolo_lulu"),
    ]

    operations = [
        migrations.RunPython(seed_demo_collections, noop),
    ]
