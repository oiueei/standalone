# Data migration — seed demo things for first-time installations.
# Uses get_or_create so it is safe to run on existing databases.

from django.db import migrations


THINGS = [
    {
        "code": "stffa1",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
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
        "owner_code": "La1aN1",
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
        "owner_code": "La1aN1",
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
        "owner_code": "La1aN1",
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
        "owner_code": "La1aN1",
        "headline": "Disco Psych Lamp",
        "description": "Rasta fairy light! Spins like a Glastonbury trip, glows for midnight herbal brews. Groovy for 10 quid!",
        "fee": "20.00",
        "condition": "NEW",
        "availability": "",
        "location": "",
    },
    {
        "code": "cksle1",
        "type": "ORDER_THING",
        "owner_code": "L3L3oo",
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
        "owner_code": "L3L3oo",
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
        "owner_code": "L3L3oo",
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
        "owner_code": "L3L3oo",
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
        "owner_code": "L3L3oo",
        "headline": "Carrot Cake Cosy",
        "description": "Chunky carrot squares with velvety frosting, on a pink plate with Marimekko mug and brew. Proper Nordic hug in cake form – pure hygge! Ideal for cosy cafés or post-cycle nibbles.",
        "fee": "5.00",
        "condition": "",
        "availability": "",
        "location": "",
    },
]


def seed_demo_things(apps, schema_editor):
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")

    for data in THINGS:
        owner = User.objects.get(code=data["owner_code"])
        Thing.objects.get_or_create(
            code=data["code"],
            defaults={
                "type": data["type"],
                "owner": owner,
                "headline": data["headline"],
                "description": data["description"],
                "fee": data["fee"],
                "condition": data["condition"],
                "availability": data["availability"],
                "location": data["location"],
                "status": "ACTIVE",
            },
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0038_seed_demo_collections"),
    ]

    operations = [
        migrations.RunPython(seed_demo_things, noop),
    ]
