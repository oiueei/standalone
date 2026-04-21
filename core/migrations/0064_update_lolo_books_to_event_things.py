# Data migration — convert Lolo's book club things to EVENT_THING with dates and updated headlines.
# Safe to run on existing databases (things may already exist with new values).

from datetime import datetime, timedelta, timezone

from django.db import migrations

TZ_PLUS2 = timezone(timedelta(hours=2))

UPDATES = [
    {
        "code": "lltl06",
        "headline": "Book Club session – Wuthering Heights Classic",
        "event_date": datetime(2027, 1, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl07",
        "headline": "Book Club session – Jane Eyre Gothic",
        "event_date": datetime(2027, 2, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl08",
        "headline": "Book Club session – Rebecca Timeless",
        "event_date": datetime(2027, 3, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl09",
        "headline": "Book Club session – Pride & Prejudice Spark",
        "event_date": datetime(2027, 4, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl10",
        "headline": "Book Club session – Tess of the D'Urbervilles",
        "event_date": datetime(2027, 5, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
]


def update_book_club_events(apps, schema_editor):
    Thing = apps.get_model("core", "Thing")
    for data in UPDATES:
        Thing.objects.filter(code=data["code"]).update(
            type="EVENT_THING",
            headline=data["headline"],
            event_date=data["event_date"],
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_add_is_minimalist_to_collection"),
    ]

    operations = [
        migrations.RunPython(update_book_club_events, noop),
    ]
