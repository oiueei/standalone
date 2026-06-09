# Removes the EVENT_THING and APPOINTMENT_THING types and their dedicated fields.

from django.db import migrations, models


def delete_event_appointment_things(apps, schema_editor):
    """Delete any remaining Things of the removed types.

    Runs before the schema changes so the max_length reduction below does not
    fail on PostgreSQL against rows still holding "APPOINTMENT_THING" (17 chars).
    Cascades clear their bookings, FAQs and transfers.
    """
    Thing = apps.get_model("core", "Thing")
    Thing.objects.filter(type__in=["EVENT_THING", "APPOINTMENT_THING"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0092_create_cache_table"),
    ]

    operations = [
        migrations.RunPython(
            delete_event_appointment_things, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="thing",
            name="event_date",
        ),
        migrations.RemoveField(
            model_name="thing",
            name="slot_duration",
        ),
        migrations.RemoveField(
            model_name="thing",
            name="availability_schedule",
        ),
        migrations.AlterField(
            model_name="thing",
            name="type",
            field=models.CharField(
                choices=[
                    ("GIFT_THING", "Gift Thing"),
                    ("SELL_THING", "Sell Thing"),
                    ("ORDER_THING", "Order Thing"),
                    ("RENT_THING", "Rent Thing"),
                    ("LEND_THING", "Lend Thing"),
                    ("SHARE_THING", "Share Thing"),
                    ("WISH_THING", "Wish Thing"),
                    ("ASSET_THING", "Asset Thing"),
                    ("SWAP_THING", "Swap Thing"),
                ],
                default="GIFT_THING",
                max_length=11,
            ),
        ),
    ]
