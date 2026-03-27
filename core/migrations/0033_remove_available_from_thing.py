from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_fix_koro_choices"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="thing",
            name="available",
        ),
    ]
