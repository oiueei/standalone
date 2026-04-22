# Data migration:
#   - Mark l1l1C2 (Lili's Circuit Swap) as an onboarding collection.
#   - Add a WISH_THING by Lala to 1u1uC1 (Lulu's share collection).

from django.db import migrations


def seed(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    Collection.objects.filter(code="l1l1C2").update(is_onboarding=True)

    lala = User.objects.get(code="La1aN1")
    col = Collection.objects.get(code="1u1uC1")
    t = Thing.objects.create(
        code="La1aW1",
        type="WISH_THING",
        owner=lala,
        headline="Hey! Maybe a small ladder, anyone? The top shelf is winning! 🪜",
    )
    col.things.add(t)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0072_seed_lili_circuit_swap"),
    ]

    operations = [
        migrations.RunPython(seed, noop),
    ]
