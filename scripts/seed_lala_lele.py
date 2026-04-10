"""
Seed script for lala and lele's missing collections, things, and FAQs.

Run with:
    python scripts/seed_lala_lele.py

Safe to re-run — uses get_or_create throughout.
"""

import os
import sys

# Allow running from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from core.models import Collection, FAQ, Thing, User  # noqa: E402

# ── Users ────────────────────────────────────────────────────────────────────

lala = User.objects.get(code="La1aN1")
lele = User.objects.get(code="L3L3oo")

# ── Collections ───────────────────────────────────────────────────────────────

lala_col, created = Collection.objects.get_or_create(
    code="La1aC1",
    defaults={
        "owner": lala,
        "headline": "Lala's off on sabbatical, flogging it all for a tenner!",
        "description": (
            "Three rules, mate: cash only, you come fetch it yerself, deadline's the 25th. "
            "Anything left? Straight to the local orphanage!"
        ),
        "status": "ACTIVE",
        "is_onboarding": True,
    },
)
lala_col.invites.add(lele)
print(f"lala collection {'created' if created else 'already exists'}: {lala_col.code}")

lele_col, created = Collection.objects.get_or_create(
    code="L3L3C1",
    defaults={
        "owner": lele,
        "headline": "Lele's Cakes!",
        "description": (
            "I craft stunning homemade cakes using only 100% natural, healthy ingredients. "
            "Perfect for mindful celebrations like birthdays, adaptable to vegan, gluten-free "
            "or low-sugar diets—contact me to personalise yours!"
        ),
        "status": "ACTIVE",
        "is_onboarding": True,
    },
)
lele_col.invites.add(lala)
print(f"lele collection {'created' if created else 'already exists'}: {lele_col.code}")

# Ensure is_onboarding is set even if collections already existed
Collection.objects.filter(code__in=["La1aC1", "L3L3C1"]).update(is_onboarding=True)

# ── Things ────────────────────────────────────────────────────────────────────

THINGS = [
    # lala's things
    {
        "code": "stffa1",
        "type": "SELL_THING",
        "owner": lala,
        "headline": "Shaggy Nordic Rug",
        "description": "Nordic meditation nest! Soft wool like a Highland sheep, hygge vibes with patchouli whiff. Just a tenner!",
        "fee": "20.00",
        "condition": "NEW",
        "availability": "",
        "location": "",
    },
    {
        "code": "stffa2",
        "type": "SELL_THING",
        "owner": lala,
        "headline": "Tea Cup Set",
        "description": "Pagan tea party! 12 mugs with \"Keep Calm and Chai On\". Perfect for hippy brews!",
        "fee": "30.00",
        "condition": "",
        "availability": "IMMEDIATE",
        "location": "",
    },
    {
        "code": "stffa3",
        "type": "SELL_THING",
        "owner": lala,
        "headline": "Retro Blender",
        "description": "Blender McBlenderface! This magic whizzer pulps kale and hippy dreams into cosmic smoothies. Peace & juice for 10 quid!",
        "fee": "10.00",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
        "location": "",
    },
    {
        "code": "stffa4",
        "type": "SELL_THING",
        "owner": lala,
        "headline": "Steamy Iron",
        "description": "Wrinkle-taming beast! Irons tie-dye tees spotless for festivals. Smooth your karma for a tenner!",
        "fee": "10.00",
        "condition": "",
        "availability": "IMMEDIATE",
        "location": "Barcelona",
    },
    {
        "code": "stffa5",
        "type": "SELL_THING",
        "owner": lala,
        "headline": "Disco Psych Lamp",
        "description": "Rasta fairy light! Spins like a Glastonbury trip, glows for midnight herbal brews. Groovy for 10 quid!",
        "fee": "20.00",
        "condition": "NEW",
        "availability": "",
        "location": "",
    },
    # lele's things
    {
        "code": "cksle1",
        "type": "ORDER_THING",
        "owner": lele,
        "headline": "Pistachio Bun Bliss",
        "description": "Three plush brioche buns stuffed with lush pistachio cream, dusted with magic powder and crunchy nuts. Proper green explosion of joy for posh dos! Order your hypnotic batch now.",
        "fee": "5.00",
        "condition": "",
        "availability": "",
        "location": "",
    },
    {
        "code": "cksle2",
        "type": "ORDER_THING",
        "owner": lele,
        "headline": "Love Heart Stunner",
        "description": "Round beauty scrawled \"Love\" in choc, with a lush red rose and sparkly pearls. Creamy, romantic to bits. For Valentines, anniversaries or just 'cause – fall for the taste!",
        "fee": "40.00",
        "condition": "",
        "availability": "",
        "location": "",
    },
    {
        "code": "cksle3",
        "type": "ORDER_THING",
        "owner": lele,
        "headline": "Raspberry Layer Dream",
        "description": "Pink raspberry layers over white cream, on a crystal stand. Fresh, zingy and blooming addictive. The birthday or brunch star – order and win hearts!",
        "fee": "60.00",
        "condition": "",
        "availability": "",
        "location": "",
    },
    {
        "code": "cksle4",
        "type": "ORDER_THING",
        "owner": lele,
        "headline": "Macaron Majesty",
        "description": "Posh creamy cake topped with grey-gold macarons, pink blooms and swirly perfection. Spot-on for weddings or high tea: French luxe with your twist. Your event, your dream flavour!",
        "fee": "45.00",
        "condition": "",
        "availability": "",
        "location": "",
    },
    {
        "code": "cksle5",
        "type": "ORDER_THING",
        "owner": lele,
        "headline": "Carrot Cake Cosy",
        "description": "Chunky carrot squares with velvety frosting, on a pink plate with Marimekko mug and brew. Proper Nordic hug in cake form – pure hygge! Ideal for cosy cafés or post-cycle nibbles.",
        "fee": "5.00",
        "condition": "",
        "availability": "",
        "location": "",
    },
]

for data in THINGS:
    owner = data.pop("owner")
    thing, created = Thing.objects.get_or_create(
        code=data["code"],
        defaults={**data, "owner": owner, "status": "ACTIVE"},
    )
    print(f"  thing {'created' if created else 'already exists'}: {thing.code} — {thing.headline}")

# ── Link things to collections ────────────────────────────────────────────────

for code in ["stffa1", "stffa2", "stffa3", "stffa4", "stffa5"]:
    lala_col.things.add(Thing.objects.get(code=code))

for code in ["cksle1", "cksle2", "cksle3", "cksle4", "cksle5"]:
    lele_col.things.add(Thing.objects.get(code=code))

# ── FAQs ─────────────────────────────────────────────────────────────────────

FAQS = [
    {"thing_code": "stffa1", "questioner": lele, "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa2", "questioner": lele, "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa3", "questioner": lele, "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa4", "questioner": lele, "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "stffa5", "questioner": lele, "question": "Can I pick it up at the end of the month?", "answer": "Abso-bloody-lutely!"},
    {"thing_code": "cksle1", "questioner": lala, "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle2", "questioner": lala, "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle3", "questioner": lala, "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle4", "questioner": lala, "question": "How long does it last in the fridge?", "answer": "2-3 days"},
    {"thing_code": "cksle5", "questioner": lala, "question": "How long does it last in the fridge?", "answer": "2-3 days"},
]

for data in FAQS:
    faq, created = FAQ.objects.get_or_create(
        thing=Thing.objects.get(code=data["thing_code"]),
        questioner=data["questioner"],
        question=data["question"],
        defaults={"answer": data["answer"], "is_visible": True},
    )
    print(f"  faq {'created' if created else 'already exists'}: {faq.thing.code} — {faq.questioner.code}")

print("\nDone!")
print(f"Collections: {Collection.objects.count()}")
print(f"Things: {Thing.objects.count()}")
print(f"FAQs: {FAQ.objects.count()}")
