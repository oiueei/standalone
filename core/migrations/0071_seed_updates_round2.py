# Data migration: demo data updates round 2.
#
# Collections:
#   1u1uC1  — newsletter_enabled=True, digest_frequency=WEEKLY (valid: is_share=True)
#   L3L3C2  — is_onboarding=True
#   l0l0C2  — is_onboarding=True, mode=PROPRIETARY
#   La1aC2  — is_onboarding=True
#
# Things:
#   lltl22–28 — is_endless=True (stay GIFT_THING; multiple simultaneous holds, stays ACTIVE forever)
#   lltl29    — location="At Lolo's flat, Zona Franca, BCN" (32 chars, within max_length)
#   lltl01–05 — documents (instruction manuals as Cloudinary raw uploads)

from django.db import migrations


def update_demo_data(apps, schema_editor):
    Collection = apps.get_model("core", "Collection")
    Thing = apps.get_model("core", "Thing")

    # --- 1u1uC1: weekly newsletter (is_share=True, so valid) ---
    Collection.objects.filter(code="1u1uC1").update(
        newsletter_enabled=True,
        digest_frequency="WEEKLY",
    )

    # --- Collections: new onboarding entries ---
    Collection.objects.filter(code__in=["L3L3C2", "l0l0C2", "La1aC2"]).update(
        is_onboarding=True,
    )

    # --- l0l0C2: COMMUNITY → PROPRIETARY ---
    Collection.objects.filter(code="l0l0C2").update(mode="PROPRIETARY")

    # --- lltl22–28: is_endless=True (GIFT_THING, accept multiple holds, stay ACTIVE) ---
    Thing.objects.filter(
        code__in=["lltl22", "lltl23", "lltl24", "lltl25", "lltl26", "lltl27", "lltl28"]
    ).update(is_endless=True)

    # --- lltl29: location ---
    Thing.objects.filter(code="lltl29").update(
        location="At Lolo's flat, Zona Franca, BCN",
    )

    # --- lltl01–05: instruction manual documents (Cloudinary raw) ---
    documents = {
        "lltl01": [{"public_id": "01_Sturdy_Drill_Kit_z61seh",    "filename": "Sturdy Drill Kit.pdf",    "content_type": "application/pdf"}],
        "lltl02": [{"public_id": "02_Steam_Cleaner_Wizard_sisdnh", "filename": "Steam Cleaner Wizard.pdf", "content_type": "application/pdf"}],
        "lltl03": [{"public_id": "03_Rock_Solid_Ladder_mtcph7",   "filename": "Rock-Solid Ladder.pdf",   "content_type": "application/pdf"}],
        "lltl04": [{"public_id": "04_Muffin_Mega_Kit_uzomdq",     "filename": "Muffin Mega-Kit.pdf",     "content_type": "application/pdf"}],
        "lltl05": [{"public_id": "05_Luggage_Scale_Pro_j4lboz",   "filename": "Luggage Scale Pro.pdf",   "content_type": "application/pdf"}],
    }
    for code, doc_list in documents.items():
        Thing.objects.filter(code=code).update(documents=doc_list)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0070_seed_updates_round2"),
    ]

    operations = [
        migrations.RunPython(update_demo_data, noop),
    ]
