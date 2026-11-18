from django.db import migrations, models

from core.services.contact_seal import is_sealed_phone, seal_phone, unseal_phone


def seal_phones(apps, schema_editor):
    """Seals every phone still kept as readable text. Idempotent: a token is left alone."""
    BookingPeriod = apps.get_model("core", "BookingPeriod")
    for pk, value in list(
        BookingPeriod.objects.exclude(contact_phone="").values_list("pk", "contact_phone")
    ):
        if not is_sealed_phone(value):
            BookingPeriod.objects.filter(pk=pk).update(contact_phone=seal_phone(value))


def unseal_phones(apps, schema_editor):
    """Back to readable text, so the previous release (which shows the column as is, in a
    column of 32) finds no token. One that cannot be opened is emptied: it would not fit."""
    BookingPeriod = apps.get_model("core", "BookingPeriod")
    for pk, value in list(
        BookingPeriod.objects.exclude(contact_phone="").values_list("pk", "contact_phone")
    ):
        if is_sealed_phone(value) or len(value) > 32:
            BookingPeriod.objects.filter(pk=pk).update(contact_phone=unseal_phone(value))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0179_lending_contact"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookingperiod",
            name="contact_phone",
            field=models.TextField(blank=True, db_default="", default=""),
        ),
        migrations.RunPython(seal_phones, unseal_phones),
    ]
