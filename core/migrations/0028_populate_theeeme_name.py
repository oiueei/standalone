from django.db import migrations


def copy_code_to_name(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    for t in Theeeme.objects.filter(name=""):
        t.name = t.code[:16]
        t.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0027_add_theeeme_name"),
    ]

    operations = [
        migrations.RunPython(copy_code_to_name, migrations.RunPython.noop),
    ]
