# Data migration — Lala's communal van COMMUNITY collection (ASSET_THING, hourly booking).

from django.db import migrations


def seed_lala_vanlife_collection(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    lala = User.objects.get(code="La1aN1")
    lele = User.objects.get(code="L3L3oo")
    lili = User.objects.get(code="l1l13S")
    lolo = User.objects.get(code="l0l0oh")
    lulu = User.objects.get(code="1u1ucs")

    col = Collection.objects.create(
        code="La1aC2",
        owner=lala,
        headline="Vanlife on tap \u2013 our shared hippie wheels await!",
        description=(
            "Need to shift a sofa? Chasing a sunset? Our beloved communal van is ready to roll. "
            "Book her for errands, road trips or spontaneous adventures. Diesel\u2019s on you, "
            "good vibes are on the house. Just don\u2019t leave sandy towels on the seats, yeah?"
        ),
        mode="COMMUNITY",
    )
    col.invites.add(lele, lili, lolo, lulu)

    t = Thing.objects.create(
        code="lltl30",
        type="ASSET_THING",
        owner=lala,
        headline="Wherever you\u2019re going, she makes it prettier!",
        thumbnail="volkswagen-id-buzz_hd_131851.jpg_hkc49z",
        booking_unit="HOUR",
    )
    col.things.add(t)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0068_seed_lolo_dulcimer_collection"),
    ]

    operations = [
        migrations.RunPython(seed_lala_vanlife_collection, noop),
    ]
