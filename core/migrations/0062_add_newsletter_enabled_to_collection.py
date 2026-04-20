from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_add_documents_to_thing"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="newsletter_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
