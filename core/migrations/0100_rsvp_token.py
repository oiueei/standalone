from django.db import migrations, models

import core.utils


def populate_tokens(apps, schema_editor):
    """Backfill a unique high-entropy token for every existing RSVP.

    Done per-row (not via a column default) because a single AddField default is
    evaluated once and would assign the same value to every row, violating the
    unique constraint added in the following step.
    """
    RSVP = apps.get_model("core", "RSVP")
    seen = set()
    for rsvp in RSVP.objects.filter(token__isnull=True).iterator():
        tok = core.utils.generate_token()
        while tok in seen:
            tok = core.utils.generate_token()
        seen.add(tok)
        rsvp.token = tok
        rsvp.save(update_fields=["token"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0099_alter_inappnotification_type"),
    ]

    operations = [
        # 1. Add nullable so existing rows don't need a value yet.
        migrations.AddField(
            model_name="rsvp",
            name="token",
            field=models.CharField(max_length=26, null=True),
        ),
        # 2. Give every existing row a distinct token.
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        # 3. Lock it down: unique, non-null, with the generator as default.
        migrations.AlterField(
            model_name="rsvp",
            name="token",
            field=models.CharField(default=core.utils.generate_token, max_length=26, unique=True),
        ),
    ]
