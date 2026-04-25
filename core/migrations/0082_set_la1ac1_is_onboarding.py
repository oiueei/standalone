from django.db import migrations


def set_la1ac1_onboarding(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Collection.objects.filter(code="La1aC1").update(is_onboarding=True)


def unset_la1ac1_onboarding(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Collection.objects.filter(code="La1aC1").update(is_onboarding=False)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0081_update_theeeme_color02_medium_light"),
    ]

    operations = [
        migrations.RunPython(set_la1ac1_onboarding, reverse_code=unset_la1ac1_onboarding),
    ]
