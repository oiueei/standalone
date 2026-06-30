# Removes the ASSET_THING type, the booking_unit field and the hourly
# booking time fields (start_time/end_time were only ever populated by
# ASSET_THING hourly bookings).

from django.db import migrations, models


def delete_asset_things(apps, schema_editor):
    """Delete any remaining ASSET_THING things (cascades to their bookings)."""
    Thing = apps.get_model("core", "Thing")
    Thing.objects.filter(type="ASSET_THING").delete()


class Migration(migrations.Migration):
    # Non-atomic: same reason as 0093 — the ASSET_THING delete cascades to bookings,
    # queuing deferred FK trigger events that block a same-transaction ALTER TABLE on
    # PostgreSQL. Letting the delete commit first clears them before the schema ops.
    atomic = False

    dependencies = [
        ("core", "0093_remove_event_appointment_things"),
    ]

    operations = [
        migrations.RunPython(delete_asset_things, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="thing",
            name="booking_unit",
        ),
        migrations.RemoveField(
            model_name="bookingperiod",
            name="start_time",
        ),
        migrations.RemoveField(
            model_name="bookingperiod",
            name="end_time",
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
                    ("SWAP_THING", "Swap Thing"),
                ],
                default="GIFT_THING",
                max_length=11,
            ),
        ),
    ]
