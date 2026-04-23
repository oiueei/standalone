# Generated for notification preferences feature.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0076_seed_collection_thumbnails"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="notify_activity",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="notify_news",
            field=models.BooleanField(default=True),
        ),
    ]
