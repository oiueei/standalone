from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0079_add_prefs_token_to_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="pause_message",
            field=models.CharField(blank=True, default="", max_length=256),
        ),
    ]
