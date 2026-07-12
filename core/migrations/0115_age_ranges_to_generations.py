# Age brackets → birth-year generations (2026-07-12)

from django.db import migrations, models


def map_or_clear_retired_age_brackets(apps, schema_editor):
    """Age brackets become birth-year generations. With 2026 as the reference
    year, two retired brackets map faithfully (51_60 → born 1966–1975, fully
    inside Gen X; 31_40 → born 1986–1995, fully inside Millennials). The rest
    straddle two generations, so they reset to unanswered and users re-pick —
    the same policy 0114 applied to its retired brackets."""
    User = apps.get_model("core", "User")
    User.objects.filter(age_range="51_60").update(age_range="GEN_X")
    User.objects.filter(age_range="31_40").update(age_range="GEN_Y")
    User.objects.filter(age_range__in=["UP_TO_21", "22_30", "41_50", "61_PLUS"]).update(
        age_range=""
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0114_expand_age_ranges"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="age_range",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PRE_1946", "1945 or earlier"),
                    ("BOOMER", "Boomers (1946-1964)"),
                    ("GEN_X", "Generation X (1965-1980)"),
                    ("GEN_Y", "Millennials (1981-1996)"),
                    ("GEN_Z", "Generation Z (1997-2012)"),
                    ("GEN_A", "Generation Alpha (2013-2024)"),
                    ("GEN_B", "Generation Beta (2025-2039)"),
                ],
                default="",
                max_length=8,
            ),
        ),
        migrations.RunPython(map_or_clear_retired_age_brackets, migrations.RunPython.noop),
    ]
