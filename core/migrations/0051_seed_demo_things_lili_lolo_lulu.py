# Data migration — seed demo things for Lili, Lolo, and Lulu's collections.
# Uses get_or_create so it is safe to run on existing databases.

from django.db import migrations


THINGS = [
    # --- Lili's collection (l1l1C1) ---
    {
        "code": "lltl01",
        "collection_code": "l1l1C1",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "headline": "Sturdy Drill Kit",
        "description": "Cordless beast for DIY disasters! Powers through walls like butter, full bits included. Borrow for your next home hack!",
        "condition": "NEW",
    },
    {
        "code": "lltl02",
        "collection_code": "l1l1C1",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "headline": "Steam Cleaner Wizard",
        "description": "Sizzles grime off ovens and sofas! Eco-magic wand leaves everything sparkling. Perfect for pre-party spruce-ups!",
        "condition": "GOOD",
    },
    {
        "code": "lltl03",
        "collection_code": "l1l1C1",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "headline": "Rock-Solid Ladder",
        "description": "Six-foot safety champ, wobble-free! Reach those pesky loft cobwebs or high shelves. Steady as a vicar's handshake!",
        "condition": "NEW",
    },
    {
        "code": "lltl04",
        "collection_code": "l1l1C1",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "headline": "Muffin Mega-Kit",
        "description": "Silicone moulds, trays and piping bags! Bake blueberry bombs or vegan wonders. Full bake-off kit for kitchen newbies!",
        "condition": "USED",
    },
    {
        "code": "lltl05",
        "collection_code": "l1l1C1",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "headline": "Luggage Scale Pro",
        "description": "Pocket hero saves airport fines! Digital whizzer weighs bags up to 50kg. Essential for cheap flight chancers!",
        "condition": "FAIR",
    },
    # --- Lolo's collection (l0l0C1) ---
    {
        "code": "lltl06",
        "collection_code": "l0l0C1",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "headline": "Wuthering Heights Classic",
        "description": "Brontë's stormy masterpiece! Heathcliff's wild heart on windswept moors. Grab for our next brooding chat!",
        "condition": "NEW",
    },
    {
        "code": "lltl07",
        "collection_code": "l0l0C1",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "headline": "Jane Eyre Gothic",
        "description": "Orphan to obsession – pure Brontë fire! Madwoman in the attic awaits. Perfect for our dark romance dive!",
        "condition": "GOOD",
    },
    {
        "code": "lltl08",
        "collection_code": "l0l0C1",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "headline": "\u201cRebecca Timeless\u201d",
        "description": "Du Maurier's Manderley mystery! Second wife vs ghostly first – chills and thrills. Join the tea-spilling session!",
        "condition": "NEW",
    },
    {
        "code": "lltl09",
        "collection_code": "l0l0C1",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "headline": "Pride & Prejudice Spark",
        "description": "Austen's witty Darcy dance! Bennet sisters vs eligible bachelors. Lightens our gothic with Regency banter!",
        "condition": "USED",
    },
    {
        "code": "lltl10",
        "collection_code": "l0l0C1",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "headline": "Tess of the D'Urbervilles",
        "description": "Hardy's tragic rural beauty! Pure woman wrongly blamed. Deep, devastating – ideal for our emotional book bash!",
        "condition": "FAIR",
    },
    # --- Lulu's collection (1u1uC1) ---
    {
        "code": "lltl11",
        "collection_code": "1u1uC1",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "headline": "Forgotten Fondue Set",
        "description": "Six-person cheese melter from '98! Complete with forks and standby. Snap it up before it ghosts again!",
        "condition": "NEW",
    },
    {
        "code": "lltl12",
        "collection_code": "1u1uC1",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "headline": "Vintage Suitcase Stack",
        "description": "Three leather beauties, minor scuffs! Perfect for weekend escapes or storage chic. Claim before they vanish!",
        "condition": "GOOD",
    },
    {
        "code": "lltl13",
        "collection_code": "1u1uC1",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "headline": "Exercise Bike Beast",
        "description": "Silent spinner with 8 resistance levels! Post-lockdown guilt-free cardio. Gone in a flash – pedal power!",
        "condition": "NEW",
    },
    {
        "code": "lltl14",
        "collection_code": "1u1uC1",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "headline": "Ceramic Plant Pots",
        "description": "Hand-thrown terracotta trio, saucer included! Revive your sad succulents. Weekly roundup star – hurry!",
        "condition": "USED",
    },
    {
        "code": "lltl15",
        "collection_code": "1u1uC1",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "headline": "Board Game Bonanza",
        "description": "Monopoly, Cluedo and Pictionary complete! Rainy night coliving classics. First come, first served – they fly!",
        "condition": "FAIR",
    },
]


def seed_demo_things(apps, schema_editor):
    Thing = apps.get_model("core", "Thing")
    User = apps.get_model("core", "User")
    Collection = apps.get_model("core", "Collection")

    for data in THINGS:
        owner = User.objects.get(code=data["owner_code"])
        thing, _ = Thing.objects.get_or_create(
            code=data["code"],
            defaults={
                "type": data["type"],
                "owner": owner,
                "headline": data["headline"],
                "description": data["description"],
                "condition": data["condition"],
                "status": "ACTIVE",
            },
        )
        collection = Collection.objects.get(code=data["collection_code"])
        collection.things.add(thing)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_mark_onboarding_collections"),
    ]

    operations = [
        migrations.RunPython(seed_demo_things, noop),
    ]
