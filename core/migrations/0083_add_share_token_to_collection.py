from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0082_set_la1ac1_is_onboarding"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="share_token",
            field=models.CharField(blank=True, max_length=22, null=True, unique=True),
        ),
    ]
