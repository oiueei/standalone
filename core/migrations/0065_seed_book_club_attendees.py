# Data migration — add Lele and Lili to Lolo's book club and seed event attendance.
# Uses get_or_create-safe patterns; safe to run on existing databases.

from django.db import migrations


INVITES_TO_ADD = [
    {"collection_code": "l0l0C1", "user_code": "L3L3oo"},  # Lele
    {"collection_code": "l0l0C1", "user_code": "l1l13S"},  # Lili
]

ATTENDANCES = [
    {"thing_code": "lltl06", "user_code": "La1aN1"},  # Lala → Wuthering Heights
    {"thing_code": "lltl07", "user_code": "La1aN1"},  # Lala → Jane Eyre
    {"thing_code": "lltl08", "user_code": "La1aN1"},  # Lala → Rebecca
    {"thing_code": "lltl06", "user_code": "L3L3oo"},  # Lele → Wuthering Heights
    {"thing_code": "lltl08", "user_code": "L3L3oo"},  # Lele → Rebecca
    {"thing_code": "lltl06", "user_code": "l1l13S"},  # Lili → Wuthering Heights
    {"thing_code": "lltl07", "user_code": "l1l13S"},  # Lili → Jane Eyre
]


def seed_book_club_attendees(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    for entry in INVITES_TO_ADD:
        collection = Collection.objects.get(code=entry["collection_code"])
        user = User.objects.get(code=entry["user_code"])
        collection.invites.add(user)

    for entry in ATTENDANCES:
        thing = Thing.objects.get(code=entry["thing_code"])
        user = User.objects.get(code=entry["user_code"])
        thing.deal.add(user)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0064_update_lolo_books_to_event_things"),
    ]

    operations = [
        migrations.RunPython(seed_book_club_attendees, noop),
    ]
