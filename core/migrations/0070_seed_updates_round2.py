# Schema migration: add is_endless BooleanField to Thing model.
#
# is_endless is for GIFT_THING and SELL_THING only. When True, the thing
# never becomes TAKEN or INACTIVE on hold requests. Multiple simultaneous
# PENDING bookings from different users are allowed, no ThingTransfer is
# created on acceptance, and thing status stays ACTIVE forever.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0069_seed_lala_vanlife_collection"),
    ]

    operations = [
        migrations.AddField(
            model_name="thing",
            name="is_endless",
            field=models.BooleanField(default=False),
        ),
    ]
