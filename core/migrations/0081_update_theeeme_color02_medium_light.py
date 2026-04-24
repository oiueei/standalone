from django.db import migrations

REPLACEMENTS = {
    "suomenlinna-light": "suomenlinna-medium-light",
    "bus-light": "bus-medium-light",
    "engel-light": "engel-medium-light",
    "fog-light": "fog-medium-light",
}


def update_color02(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    for old, new in REPLACEMENTS.items():
        Theeeme.objects.filter(color_02=old).update(color_02=new)


def revert_color02(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    for old, new in REPLACEMENTS.items():
        Theeeme.objects.filter(color_02=new).update(color_02=old)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0080_add_pause_message_to_collection"),
    ]

    operations = [
        migrations.RunPython(update_color02, revert_color02),
    ]
