from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0085_user_analytics_opt_out"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="swap_minimum_items",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
