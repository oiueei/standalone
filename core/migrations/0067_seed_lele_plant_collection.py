# Data migration — Lele's minimalist gift collection (is_minimalist=True, 7 succulent gifts).

from django.db import migrations


def seed_lele_plant_collection(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    lele = User.objects.get(code="L3L3oo")
    lala = User.objects.get(code="La1aN1")
    lili = User.objects.get(code="l1l13S")
    lolo = User.objects.get(code="l0l0oh")

    col = Collection.objects.create(
        code="L3L3C2",
        owner=lele,
        headline="Lele's Leafy Lounge \u2013 Snag a free succulent baby!",
        description=(
            "Plant mum with too many green babies! Drop by to meet my succulent squad "
            "\u2013 echeverias, jades, sedums \u2013 and I\u2019ll gift you a cutting. "
            "Easy-peasy care guide thrown in. Only rule: name your new leafy friend!"
        ),
        is_minimalist=True,
    )
    col.invites.add(lala, lili, lolo)

    things_data = [
        ("lltl22", "Zebra, Rosie & Jade \u2013 my terracotta trio needs new homes!", "001_esszlo"),
        ("lltl23", "Her Majesty the Echeveria \u2013 dusty pink crown, free pups!", "003_fmvqfb"),
        ("lltl24", "Sunset in a pot \u2013 peachy-lilac pup ready to adopt!", "005_ehlynl"),
        ("lltl25", "The fuzzy dumpling \u2013 velvety leaves, zero fuss, free pup!", "007_hshqhk"),
        ("lltl26", "Straight from my hands to yours \u2013 pick your pup!", "009_awlaxr"),
        ("lltl27", "My mini meadow \u2013 five succulent sisters under one roof!", "008_ugfkw0"),
        ("lltl28", "Too many babies, not enough pots \u2013 come rescue one!", "004_byjjmi"),
    ]

    for code, headline, thumbnail in things_data:
        t = Thing.objects.create(
            code=code,
            type="GIFT_THING",
            owner=lele,
            headline=headline,
            thumbnail=thumbnail,
        )
        col.things.add(t)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0066_seed_lulu_share_collection"),
    ]

    operations = [
        migrations.RunPython(seed_lele_plant_collection, noop),
    ]
