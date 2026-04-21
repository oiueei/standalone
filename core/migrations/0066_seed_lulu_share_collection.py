# Data migration — convert Lulu's collection to COMMUNITY+SHARE, add invites,
# transfer SHARE_THING ownership, and seed ThingTransfer history.

from datetime import date

from django.db import migrations


def seed_lulu_share_collection(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    ThingTransfer = apps.get_model("core", "ThingTransfer")
    User = apps.get_model("core", "User")

    lulu = User.objects.get(code="1u1ucs")
    lala = User.objects.get(code="La1aN1")
    lele = User.objects.get(code="L3L3oo")
    lili = User.objects.get(code="l1l13S")
    lolo = User.objects.get(code="l0l0oh")

    # 1. Update collection to COMMUNITY + is_share
    col = Collection.objects.get(code="1u1uC1")
    col.mode = "COMMUNITY"
    col.is_share = True
    col.save()

    # 2. Invite Lele, Lili and Lolo (Lala already invited from 0048)
    col.invites.add(lele, lili, lolo)

    # 3. Single transfers — Lulu → new owner (thing stays active)
    lltl11 = Thing.objects.get(code="lltl11")
    lltl11.owner = lala
    lltl11.save()
    ThingTransfer.objects.get_or_create(
        thing=lltl11,
        from_user=lulu,
        to_user=lala,
        defaults={"lent_date": date(2026, 3, 1), "returned_date": None},
    )

    lltl12 = Thing.objects.get(code="lltl12")
    lltl12.owner = lele
    lltl12.save()
    ThingTransfer.objects.get_or_create(
        thing=lltl12,
        from_user=lulu,
        to_user=lele,
        defaults={"lent_date": date(2026, 3, 15), "returned_date": None},
    )

    lltl13 = Thing.objects.get(code="lltl13")
    lltl13.owner = lili
    lltl13.save()
    ThingTransfer.objects.get_or_create(
        thing=lltl13,
        from_user=lulu,
        to_user=lili,
        defaults={"lent_date": date(2026, 4, 1), "returned_date": None},
    )

    # 4. Full chain lltl14: Lulu → Lolo → Lala → Lele → Lili → Lolo
    lltl14 = Thing.objects.get(code="lltl14")
    lltl14.owner = lolo
    lltl14.save()

    chain = [
        (lulu, lolo, date(2026, 1, 10), date(2026, 1, 31)),
        (lolo, lala, date(2026, 2,  1), date(2026, 2, 28)),
        (lala, lele, date(2026, 3,  1), date(2026, 3, 31)),
        (lele, lili, date(2026, 4,  1), date(2026, 4, 15)),
        (lili, lolo, date(2026, 4, 16), None),               # current holder
    ]
    for from_user, to_user, lent_date, returned_date in chain:
        ThingTransfer.objects.get_or_create(
            thing=lltl14,
            from_user=from_user,
            to_user=to_user,
            lent_date=lent_date,
            defaults={"returned_date": returned_date},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0065_seed_book_club_attendees"),
    ]

    operations = [
        migrations.RunPython(seed_lulu_share_collection, noop),
    ]
