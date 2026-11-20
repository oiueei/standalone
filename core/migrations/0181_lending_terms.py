from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0180_seal_reservation_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingperiod',
            name='terms_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bookingperiod',
            name='terms_doc',
            field=models.CharField(blank=True, db_default='', default='', max_length=255),
        ),
        migrations.AddField(
            model_name='collection',
            name='lending_asks_terms',
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
