# Data migration — Lili's Circuit Swap collection (COMMUNITY, is_swap).
# 8 SWAP_THING components owned by Lala, Lele, Lolo, Lulu, and Lili.
# Includes ThingTransfer history for 4 components that have already been swapped.

from datetime import date

from django.db import migrations


def seed_lili_circuit_swap(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    ThingTransfer = apps.get_model("core", "ThingTransfer")
    User = apps.get_model("core", "User")

    lili = User.objects.get(code="l1l13S")
    lala = User.objects.get(code="La1aN1")
    lele = User.objects.get(code="L3L3oo")
    lolo = User.objects.get(code="l0l0oh")
    lulu = User.objects.get(code="1u1ucs")

    col = Collection.objects.create(
        code="l1l1C2",
        owner=lili,
        headline="Lili's Circuit Swap – Resistance is futile!",
        description=(
            "Lili's coliving runs on jumper wires and half-finished Arduino dreams. "
            "Got a spare Nano gathering dust? A sensor that wasn’t quite the one? "
            "Pop it on the board, eye up what you fancy, propose a swap. "
            "Components only — no cash, no shame, no short circuits."
        ),
        mode="COMMUNITY",
        is_swap=True,
    )
    col.invites.add(lala, lele, lolo, lulu)

    things_data = [
        ("l1sw01", lala, "Grove Shield for Arduino Nano v1.1 (Seeed Studio)", "ARDUINO_001_ogf1sz"),
        ("l1sw02", lele, "Grove - Laser PM2.5 Dust Sensor (HM3301)",          "ARDUINO_002_jvkxd3"),
        ("l1sw03", lolo, "MB102 Breadboard Power Supply Module (HW-131)",      "ARDUINO_003_ace77f"),
        ("l1sw04", lulu, "Arduino Nano Screw Terminal Adapter",                "ARDUINO_004_mdfkm9"),
        ("l1sw05", lili, "Arduino Nano 33 BLE",                               "ARDUINO_005_etbpia"),
        ("l1sw06", lili, "CCS811 Indoor Air Quality Sensor",                  "ARDUINO_006_aoqyik"),
        ("l1sw07", lili, "Grove’s: Temperature & Humidity, Water, Sound, UV, Air", "ARDUINO_007_osnlj1"),
        ("l1sw08", lili, "DFRobot Analogue UV Sensor V2 (Gravity)",           "ARDUINO_008_nc0qwg"),
    ]

    things = {}
    for code, owner, headline, thumbnail in things_data:
        t = Thing.objects.create(
            code=code,
            type="SWAP_THING",
            owner=owner,
            headline=headline,
            thumbnail=thumbnail,
        )
        col.things.add(t)
        things[code] = t

    # Historical swaps — things that have already changed hands before the seed date.
    # l1sw01 (Grove Shield): Lili → Lala
    ThingTransfer.objects.create(
        thing=things["l1sw01"],
        from_user=lili,
        to_user=lala,
        lent_date=date(2026, 3, 20),
        returned_date=None,
    )

    # l1sw02 (Laser Dust Sensor): Lili → Lele
    ThingTransfer.objects.create(
        thing=things["l1sw02"],
        from_user=lili,
        to_user=lele,
        lent_date=date(2026, 3, 25),
        returned_date=None,
    )

    # l1sw05 (Arduino Nano 33 BLE): Lolo → Lili
    ThingTransfer.objects.create(
        thing=things["l1sw05"],
        from_user=lolo,
        to_user=lili,
        lent_date=date(2026, 4, 5),
        returned_date=None,
    )

    # l1sw07 (Grove sensors): Lolo → Lele → Lili (two-hop chain)
    ThingTransfer.objects.create(
        thing=things["l1sw07"],
        from_user=lolo,
        to_user=lele,
        lent_date=date(2026, 1, 20),
        returned_date=None,
    )
    ThingTransfer.objects.create(
        thing=things["l1sw07"],
        from_user=lele,
        to_user=lili,
        lent_date=date(2026, 3, 1),
        returned_date=None,
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0071_seed_updates_round2"),
    ]

    operations = [
        migrations.RunPython(seed_lili_circuit_swap, noop),
    ]
