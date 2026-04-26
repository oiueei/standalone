from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0084_user_last_activity_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="analytics_opt_out",
            field=models.BooleanField(default=False),
        ),
    ]
