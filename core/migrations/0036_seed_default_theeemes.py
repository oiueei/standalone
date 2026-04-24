# Data migration — replace all theeemes with the canonical set.
# Migrates any users pointing to removed theeemes to BUU331 (Bussi)
# before deleting old records, to respect the FK PROTECT constraint.

from django.db import migrations

THEEEMES = [
    {"code": "BUU331", "name": "Bussi",       "color_01": "bus",            "color_02": "suomenlinna-medium-light", "color_03": "copper",      "color_04": "black", "color_05": "black", "color_06": "white"},
    {"code": "3NNG31", "name": "Engel",       "color_01": "engel",          "color_02": "bus-medium-light",         "color_03": "copper",      "color_04": "black", "color_05": "black", "color_06": "black"},
    {"code": "H00774", "name": "Hopea",       "color_01": "gold",           "color_02": "bus-medium-light",         "color_03": "silver",      "color_04": "black", "color_05": "black", "color_06": "black"},
    {"code": "K3SS44", "name": "Kesä",        "color_01": "summer",         "color_02": "engel-medium-light",       "color_03": "tram",        "color_04": "black", "color_05": "white", "color_06": "black"},
    {"code": "K0P4R1", "name": "Kupari",      "color_01": "copper",         "color_02": "fog-medium-light",         "color_03": "suomenlinna", "color_04": "black", "color_05": "black", "color_06": "black"},
    {"code": "KU11T4", "name": "Kulta",       "color_01": "gold",           "color_02": "fog-medium-light",         "color_03": "metro",       "color_04": "black", "color_05": "black", "color_06": "black"},
    {"code": "M377RO", "name": "Metro",       "color_01": "metro",          "color_02": "suomenlinna-medium-light", "color_03": "gold",        "color_04": "black", "color_05": "black", "color_06": "black"},
    {"code": "S0M0UU", "name": "Sumu",        "color_01": "fog",            "color_02": "engel-medium-light",       "color_03": "metro",       "color_04": "black", "color_05": "black", "color_06": "black"},
    {"code": "SP4740", "name": "Spåra",       "color_01": "tram",           "color_02": "engel-medium-light",       "color_03": "summer",      "color_04": "black", "color_05": "black", "color_06": "white"},
    {"code": "SU0M3N", "name": "Suomenlinna", "color_01": "suomenlinna",    "color_02": "bus-medium-light",         "color_03": "bus",         "color_04": "black", "color_05": "white", "color_06": "black"},
    {"code": "V44K0N", "name": "Vaakuna",     "color_01": "summer",         "color_02": "fog-medium-light",         "color_03": "suomenlinna", "color_04": "black", "color_05": "white", "color_06": "black"},
    {"code": "5BC8W6", "name": "M&V",         "color_01": "summer",         "color_02": "black-5",           "color_03": "black",       "color_04": "black", "color_05": "white", "color_06": "black"},
]

CANONICAL_CODES = {t["code"] for t in THEEEMES}


def replace_theeemes(apps, schema_editor):
    Theeeme = apps.get_model("core", "Theeeme")
    User = apps.get_model("core", "User")

    # Ensure BUU331 exists before migrating users to it
    bussi_data = next(t for t in THEEEMES if t["code"] == "BUU331")
    bussi, _ = Theeeme.objects.update_or_create(code="BUU331", defaults=bussi_data)

    # Move any users pointing to a theeeme not in the canonical set to BUU331
    User.objects.exclude(theeeme__in=CANONICAL_CODES).update(theeeme=bussi)

    # Delete theeemes not in the canonical set
    Theeeme.objects.exclude(code__in=CANONICAL_CODES).delete()

    # Upsert the full canonical set
    for data in THEEEMES:
        Theeeme.objects.update_or_create(code=data["code"], defaults=data)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_remove_color_06_default"),
    ]

    operations = [
        migrations.RunPython(replace_theeemes, noop),
    ]
