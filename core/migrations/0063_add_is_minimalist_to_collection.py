from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0062_add_newsletter_enabled_to_collection"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="is_minimalist",
            field=models.BooleanField(default=False),
        ),
    ]
