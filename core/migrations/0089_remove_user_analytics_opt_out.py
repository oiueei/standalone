from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0088_add_swap_minimum_items_to_collection"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="analytics_opt_out",
        ),
    ]
