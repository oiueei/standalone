from django.db import migrations

# Vaakuna paired white koros-section text (color_05) with its light-pink
# suomenlinna background (color_03 = #f5a3c7): a 1.92:1 contrast ratio, well
# below WCAG AA. Switch it to black (10.95:1, AAA) — the same choice Kupari
# already makes for the same suomenlinna background.


def fix_vaakuna(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    Theeeme.objects.filter(code="V44K0N", color_05="white").update(color_05="black")


def revert_vaakuna(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    Theeeme.objects.filter(code="V44K0N", color_05="black").update(color_05="white")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0111_dailyactivity"),
    ]

    operations = [
        migrations.RunPython(fix_vaakuna, revert_vaakuna),
    ]
