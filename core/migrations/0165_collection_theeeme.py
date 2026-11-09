"""Move the palette from the user to the collection.

A collection's pages are painted with the palette (and the Koros wave) its
curators chose, not with that of whoever is reading. So `Collection` gains
`theeeme` and `koro`, each existing collection takes its **founder's** current
choice (nobody sees their own groups change), and the same two fields leave
`User`.

The user's columns leave in two releases, the pattern of 0152/0153. Heroku's
release phase runs `migrate` while the previous release's dynos are still
serving, and they name `koro` and `user_theeeme` in every User query and INSERT;
dropping the columns now would break exactly that until they restart. So this
release does the half that is safe with both codebases running:

1. Each column gets a **database-level** default (`db_default`): the new code,
   which no longer knows the fields, inserts a user without them and the database
   fills them in — a theeeme code that exists, so the foreign key holds — while the
   old code keeps writing its own values.
2. The two fields leave Django's **state only** (`SeparateDatabaseAndState`, no
   database operation), so the model, the serializers and every query stop
   naming them.

The next release drops the columns (`0166`). Reversible: backwards, the fields return
to the state, the database defaults go, and the collections keep the columns this
migration added until they are removed in turn.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery

import core.models.theeeme

# Bussi, seeded in 0036. The database default of a retired user column has to be
# a palette that exists, because `user_theeeme` is a foreign key.
RETIRED_USER_THEEEME_DEFAULT = "BUU331"


def copy_founders_palette(apps, schema_editor):
    """Each collection starts with the theeeme and the koro its founder had."""
    User = apps.get_model("core", "User")
    Collection = apps.get_model("core", "Collection")
    founder = User.objects.filter(code=OuterRef("owner_id"))
    Collection.objects.update(
        theeeme=Subquery(founder.values("theeeme_id")[:1]),
        koro=Subquery(founder.values("koro")[:1]),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0164_braaanding"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="koro",
            field=models.CharField(
                choices=[
                    ("basic", "Basic"),
                    ("beat", "Beat"),
                    ("calm", "Calm"),
                    ("pulse", "Pulse"),
                    ("vibration", "Vibration"),
                    ("wave", "Wave"),
                ],
                default="basic",
                max_length=9,
            ),
        ),
        migrations.AddField(
            model_name="collection",
            name="theeeme",
            field=models.ForeignKey(
                default=core.models.theeeme.random_theeeme,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="collections",
                to="core.theeeme",
            ),
        ),
        migrations.RunPython(copy_founders_palette, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="koro",
            field=models.CharField(
                choices=[
                    ("basic", "Basic"),
                    ("beat", "Beat"),
                    ("calm", "Calm"),
                    ("pulse", "Pulse"),
                    ("vibration", "Vibration"),
                    ("wave", "Wave"),
                ],
                db_default="basic",
                default="basic",
                max_length=9,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="theeeme",
            field=models.ForeignKey(
                db_column="user_theeeme",
                db_default=RETIRED_USER_THEEEME_DEFAULT,
                default=core.models.theeeme.random_theeeme,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="core.theeeme",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="user", name="koro"),
                migrations.RemoveField(model_name="user", name="theeeme"),
            ],
        ),
    ]
