# Data migration — seed demo FAQs for first-time installations.

from django.db import migrations


FAQS = [
    {"thing_code": "stffa1", "questioner_code": "L3L3oo", "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa2", "questioner_code": "L3L3oo", "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa3", "questioner_code": "L3L3oo", "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa4", "questioner_code": "L3L3oo", "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa5", "questioner_code": "L3L3oo", "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "cksle1", "questioner_code": "La1aN1", "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle2", "questioner_code": "La1aN1", "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle3", "questioner_code": "La1aN1", "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle4", "questioner_code": "La1aN1", "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle5", "questioner_code": "La1aN1", "question": "How long does it last in the fridge?", "answer": "2-3 days"},
]


def seed_demo_faqs(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    for data in FAQS:
        thing = Thing.objects.get(code=data["thing_code"])
        questioner = User.objects.get(code=data["questioner_code"])
        FAQ.objects.get_or_create(
            thing=thing,
            questioner=questioner,
            question=data["question"],
            defaults={"answer": data["answer"], "is_visible": True},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_seed_demo_collection_things"),
    ]

    operations = [
        migrations.RunPython(seed_demo_faqs, noop),
    ]
