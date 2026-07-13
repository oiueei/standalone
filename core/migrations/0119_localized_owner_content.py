"""Widen the fields an owner may localize, so the same text can be stored in
every language OIUEEI speaks (see core.utils.parse_localized).

Widening a varchar is a metadata-only change in PostgreSQL — no table rewrite, no
long lock — and no row changes meaning: 64/256 remain the limits an owner sees per
language, now enforced by the serializer rather than the column. Report's headline
snapshot follows Thing's, or reporting a thing with a localized headline would
fail at write time.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0118_collection_language_user_language'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='description',
            field=models.CharField(blank=True, default='', max_length=1024),
        ),
        migrations.AlterField(
            model_name='collection',
            name='headline',
            field=models.CharField(max_length=256),
        ),
        migrations.AlterField(
            model_name='report',
            name='thing_headline',
            field=models.CharField(blank=True, max_length=256),
        ),
        migrations.AlterField(
            model_name='thing',
            name='description',
            field=models.CharField(blank=True, default='', max_length=1024),
        ),
        migrations.AlterField(
            model_name='thing',
            name='headline',
            field=models.CharField(max_length=256),
        ),
    ]
