from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0083_add_share_token_to_collection"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="last_activity",
            field=models.DateField(blank=True, default=None, null=True),
        ),
    ]
