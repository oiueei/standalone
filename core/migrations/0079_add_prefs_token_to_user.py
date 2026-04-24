from django.db import migrations, models

from core.utils import generate_id


def populate_prefs_tokens(apps, schema_editor):
    User = apps.get_model("core", "User")
    used = set()
    for user in User.objects.all():
        token = generate_id()
        while token in used or User.objects.filter(prefs_token=token).exists():
            token = generate_id()
        used.add(token)
        user.prefs_token = token
        user.save(update_fields=["prefs_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0078_add_inapp_notification"),
    ]

    operations = [
        # Step 1: add nullable, no unique constraint yet
        migrations.AddField(
            model_name="user",
            name="prefs_token",
            field=models.CharField(max_length=6, null=True),
        ),
        # Step 2: populate every existing user with a unique token
        migrations.RunPython(populate_prefs_tokens, migrations.RunPython.noop),
        # Step 3: enforce unique + non-null
        migrations.AlterField(
            model_name="user",
            name="prefs_token",
            field=models.CharField(max_length=6, unique=True, default=generate_id),
        ),
    ]
