# Data migration — Lolo's dulcimer APPOINTMENT collection (1-hour slots, Tue/Wed/Thu 14–18).

from django.db import migrations


def seed_lolo_dulcimer_collection(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    lolo = User.objects.get(code="l0l0oh")
    lala = User.objects.get(code="La1aN1")
    lele = User.objects.get(code="L3L3oo")
    lili = User.objects.get(code="l1l13S")
    lulu = User.objects.get(code="1u1ucs")

    col = Collection.objects.create(
        code="l0l0C2",
        owner=lolo,
        headline="Lolo\u2019s Dulcimer Sessions \u2013 music as meditation!",
        description=(
            "Fancy learning an instrument just for the joy of it? Lolo teaches the hammered dulcimer "
            "\u2013 that dreamy trapezoidal harp played with little mallets. Laid-back lessons, no "
            "recitals, no grades. Just you, two sticks, and the loveliest sound in the world."
        ),
        mode="COMMUNITY",
    )
    col.invites.add(lala, lele, lili, lulu)

    t = Thing.objects.create(
        code="lltl29",
        type="APPOINTMENT_THING",
        owner=lolo,
        headline="Classes every afternoon!",
        description=(
            "Bring your own dulcimer if you have one. If not, don\u2019t sweat it "
            "\u2013 mine\u2019s here for you to borrow!"
        ),
        thumbnail="2.JPG_d4itfz",
        slot_duration=60,
        availability_schedule=[
            {"days": [2, 3, 4], "start_time": "14:00", "end_time": "18:00"},
        ],
    )
    col.things.add(t)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0067_seed_lele_plant_collection"),
    ]

    operations = [
        migrations.RunPython(seed_lolo_dulcimer_collection, noop),
    ]
