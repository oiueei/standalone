"""
Move theeeme FK from Collection to User.
Create new default Theeeme B4s1C0 (code HDS000).
"""

from django.db import migrations, models
import django.db.models.deletion


def create_default_theeeme(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    Theeeme.objects.get_or_create(
        code="HDS000",
        defaults={
            "name": "B4s1C0",
            "color_01": "0072C6",
            "color_02": "00D7A7",
            "color_03": "FFC61E",
            "color_04": "FD4F00",
            "color_05": "9FC9EB",
            "color_06": "F5F5F5",
        },
    )


def backfill_users(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.filter(theeeme__isnull=True).update(theeeme="HDS000")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_remove_rsvp_collection_code"),
    ]

    operations = [
        # 1. Create the new default theeeme HDS000
        migrations.RunPython(create_default_theeeme, migrations.RunPython.noop),
        # 2. Add nullable theeeme FK to User
        migrations.AddField(
            model_name="user",
            name="theeeme",
            field=models.ForeignKey(
                db_column="user_theeeme",
                default="HDS000",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="users",
                to="core.theeeme",
                to_field="code",
            ),
            preserve_default=False,
        ),
        # 3. Backfill all existing users to HDS000
        migrations.RunPython(backfill_users, migrations.RunPython.noop),
        # 4. Make User.theeeme non-nullable with PROTECT
        migrations.AlterField(
            model_name="user",
            name="theeeme",
            field=models.ForeignKey(
                db_column="user_theeeme",
                default="HDS000",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="core.theeeme",
                to_field="code",
            ),
        ),
        # 5. Remove theeeme from Collection
        migrations.RemoveField(
            model_name="collection",
            name="theeeme",
        ),
    ]
