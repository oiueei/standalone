from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0176_booking_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='accepts_donations',
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name='collection',
            name='donations_info',
            field=models.TextField(blank=True, db_default='', default=''),
        ),
    ]
