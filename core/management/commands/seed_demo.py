"""
Seed demo data for OIUEEI (Lala, Lele, Lili, Lolo, Lulu and all their things).

This command is idempotent — run it as many times as you like. It replaces the
chain of seed migrations (0037–0076) so that fresh test databases stay empty
and demo data is only populated when explicitly requested.

Usage:
    python manage.py seed_demo                    # local
    heroku run python manage.py seed_demo --app … # Heroku one-off dyno

The data is organised in constants at the top of this file so it's easy to
edit and review. Helper functions below execute the creation/updates in the
right order.
"""

from datetime import date, datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import FAQ, Collection, Thing, User
from core.models.transfer import ThingTransfer

# ---------------------------------------------------------------------------
# Demo data — edit freely, then re-run the command to apply.
# ---------------------------------------------------------------------------

TZ_PLUS2 = timezone(timedelta(hours=2))

USERS = [
    {
        "code": "La1aN1",
        "email": "lala@mail.com",
        "name": "Lala",
        "headline": "Three cheers for second-hand!",
        "theeeme_id": "BUU331",
    },
    {
        "code": "L3L3oo",
        "email": "lele@mail.com",
        "name": "Lele",
        "headline": "Here! Now!! Sharing!!!",
        "theeeme_id": "K0P4R1",
    },
    {
        "code": "l1l13S",
        "email": "lili@mail.com",
        "name": "Lili",
        "headline": "Hurrah for the Borrow Shelf! Lili's got your gear!",
        "theeeme_id": "BUU331",
    },
    {
        "code": "l0l0oh",
        "email": "lolo@mail.com",
        "name": "Lolo",
        "headline": "Heathcliff's brooding romance calls! Lolo's book club beckons!",
        "theeeme_id": "BUU331",
    },
    {
        "code": "1u1ucs",
        "email": "lulu@mail.com",
        "name": "Lulu",
        "headline": "I know everyone and join every lark – your community spark!",
        "theeeme_id": "BUU331",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "owner_code": "La1aN1",
        "headline": "Lala's off on sabbatical, flogging it all for a tenner!",
        "description": (
            "Three rules, mate: cash only, you come fetch it yerself, deadline's the 25th. "
            "Anything left? Straight to the local orphanage!"
        ),
        "invites": ["L3L3oo"],
        "is_onboarding": False,
        "thumbnail": "La1aC1_afuutc",
    },
    {
        "code": "La1aC2",
        "owner_code": "La1aN1",
        "headline": "Vanlife on tap – our shared hippie wheels await!",
        "description": (
            "Need to shift a sofa? Chasing a sunset? Our beloved communal van is ready to roll. "
            "Book her for errands, road trips or spontaneous adventures. Diesel's on you, "
            "good vibes are on the house. Just don't leave sandy towels on the seats, yeah?"
        ),
        "mode": "COMMUNITY",
        "invites": ["L3L3oo", "l1l13S", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "thumbnail": "La1aC2_dodvhm",
    },
    {
        "code": "L3L3C1",
        "owner_code": "L3L3oo",
        "headline": "Lele's Cakes!",
        "description": (
            "I craft stunning homemade cakes using only 100% natural, healthy ingredients. "
            "Perfect for mindful celebrations like birthdays, adaptable to vegan, gluten-free "
            "or low-sugar diets—contact me to personalise yours!"
        ),
        "invites": ["La1aN1"],
        "is_onboarding": False,
        "thumbnail": "L3L3C1_rbvkm2",
    },
    {
        "code": "L3L3C2",
        "owner_code": "L3L3oo",
        "headline": "Lele's Leafy Lounge – Snag a free succulent baby!",
        "description": (
            "Plant mum with too many green babies! Drop by to meet my succulent squad "
            "– echeverias, jades, sedums – and I'll gift you a cutting. "
            "Easy-peasy care guide thrown in. Only rule: name your new leafy friend!"
        ),
        "is_minimalist": True,
        "invites": ["La1aN1", "l1l13S", "l0l0oh"],
        "is_onboarding": True,
        "thumbnail": "L3L3C2_nngsy2",
    },
    {
        "code": "l0l0C1",
        "owner_code": "l0l0oh",
        "headline": "The melancholic Heathcliff calls! Lolo's book club!",
        "description": (
            "Craving windswept moors and tortured lovers? Dive into English romances like "
            "Wuthering Heights with Lolo's cosy book club. Borrow classics, share feels over "
            "tea – new members welcome, grab your spot for the next stormy read!"
        ),
        "invites": ["La1aN1", "L3L3oo", "l1l13S"],
        "is_onboarding": False,
        "thumbnail": "l0l0C1_stookm",
    },
    {
        "code": "l0l0C2",
        "owner_code": "l0l0oh",
        "headline": "Lolo's Dulcimer Sessions – music as meditation!",
        "description": (
            "Fancy learning an instrument just for the joy of it? Lolo teaches the hammered dulcimer "
            "– that dreamy trapezoidal harp played with little mallets. Laid-back lessons, no "
            "recitals, no grades. Just you, two sticks, and the loveliest sound in the world."
        ),
        "mode": "PROPRIETARY",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "1u1ucs"],
        "is_onboarding": True,
        "thumbnail": "l0l0C2_jbrjgl",
    },
    {
        "code": "l1l1C1",
        "owner_code": "l1l13S",
        "headline": "Lili's Borrow Borrow – Tool Time Tenants!",
        "description": (
            "Need a drill, steam cleaner, sturdy ladder, luggage scale or muffin mega-kit? "
            "Lili's lending library has your back – borrow free for coliving chores, return "
            "clean, first come first served. Sorted!"
        ),
        "invites": ["La1aN1"],
        "is_onboarding": True,
        "thumbnail": "l1l1C1_ozv2my",
    },
    {
        "code": "l1l1C2",
        "owner_code": "l1l13S",
        "headline": "Lili's Circuit Swap – Resistance is futile!",
        "description": (
            "Lili's coliving runs on jumper wires and half-finished Arduino dreams. "
            "Got a spare Nano gathering dust? A sensor that wasn't quite the one? "
            "Pop it on the board, eye up what you fancy, propose a swap. "
            "Components only — no cash, no shame, no short circuits."
        ),
        "mode": "COMMUNITY",
        "is_swap": True,
        "invites": ["La1aN1", "L3L3oo", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "thumbnail": "l1l1C2_g8rbjc",
    },
    {
        "code": "1u1uC1",
        "owner_code": "1u1ucs",
        "headline": "Lulu's Phantom Shelf – Haunt it with your clutter!",
        "description": (
            "Spot something gathering dust? Snap a pic, drop it on Lulu's ghostly online shelf "
            "– no faff, no prices, just a simple feed of coliving cast-offs. Weekly email with "
            "all the new goodies! But be quick, stuff vanishes fast!!"
        ),
        "mode": "COMMUNITY",
        "is_share": True,
        "newsletter_enabled": True,
        "digest_frequency": "WEEKLY",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh"],
        "is_onboarding": True,
        "thumbnail": "1u1uC1_j4pous",
    },
]

# Every THING is keyed by code. owner_code is the *initial* owner at seed time
# (SHARE_THING ownership is later transferred via TRANSFERS below).
THINGS = [
    # --- Lala: sabbatical sale ---
    {"code": "stffa1", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Shaggy Nordic Rug",
     "description": "Nordic meditation nest! Soft wool like a Highland sheep, hygge vibes with patchouli whiff. Just a tenner!",
     "fee": "20.00", "condition": "NEW"},
    {"code": "stffa2", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Tea Cup Set",
     "description": "Pagan tea party! 12 mugs with \"Keep Calm and Chai On\". Perfect for hippy brews!",
     "fee": "30.00", "availability": "IMMEDIATE"},
    {"code": "stffa3", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Retro Blender",
     "description": "Blender McBlenderface! This magic whizzer pulps kale and hippy dreams into cosmic smoothies. Peace & juice for 10 quid!",
     "fee": "10.00", "condition": "GOOD", "availability": "NEXT_WEEK"},
    {"code": "stffa4", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Steamy Iron",
     "description": "Wrinkle-taming beast! Irons tie-dye tees spotless for festivals. Smooth your karma for a tenner!",
     "fee": "10.00", "availability": "IMMEDIATE", "location": "Barcelona"},
    {"code": "stffa5", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Disco Psych Lamp",
     "description": "Rasta fairy light! Spins like a Glastonbury trip, glows for midnight herbal brews. Groovy for 10 quid!",
     "fee": "20.00", "condition": "NEW"},

    # --- Lele: bakery orders ---
    {"code": "cksle1", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Pistachio Bun Bliss",
     "description": "Three plush brioche buns stuffed with lush pistachio cream, dusted with magic powder and crunchy nuts. Proper green explosion of joy for posh dos! Order your hypnotic batch now.",
     "fee": "5.00"},
    {"code": "cksle2", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Love Heart Stunner",
     "description": "Round beauty scrawled \"Love\" in choc, with a lush red rose and sparkly pearls. Creamy, romantic to bits. For Valentines, anniversaries or just 'cause – fall for the taste!",
     "fee": "40.00"},
    {"code": "cksle3", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Raspberry Layer Dream",
     "description": "Pink raspberry layers over white cream, on a crystal stand. Fresh, zingy and blooming addictive. The birthday or brunch star – order and win hearts!",
     "fee": "60.00"},
    {"code": "cksle4", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Macaron Majesty",
     "description": "Posh creamy cake topped with grey-gold macarons, pink blooms and swirly perfection. Spot-on for weddings or high tea: French luxe with your twist. Your event, your dream flavour!",
     "fee": "45.00"},
    {"code": "cksle5", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Carrot Cake Cosy",
     "description": "Chunky carrot squares with velvety frosting, on a pink plate with Marimekko mug and brew. Proper Nordic hug in cake form – pure hygge! Ideal for cosy cafés or post-cycle nibbles.",
     "fee": "5.00"},

    # --- Lili: tool library ---
    {"code": "lltl01", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Sturdy Drill Kit",
     "description": "Cordless beast for DIY disasters! Powers through walls like butter, full bits included. Borrow for your next home hack!",
     "condition": "NEW",
     "documents": [{"public_id": "01_Sturdy_Drill_Kit_z61seh", "filename": "Sturdy Drill Kit.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl02", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Steam Cleaner Wizard",
     "description": "Sizzles grime off ovens and sofas! Eco-magic wand leaves everything sparkling. Perfect for pre-party spruce-ups!",
     "condition": "GOOD",
     "documents": [{"public_id": "02_Steam_Cleaner_Wizard_sisdnh", "filename": "Steam Cleaner Wizard.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl03", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Rock-Solid Ladder",
     "description": "Six-foot safety champ, wobble-free! Reach those pesky loft cobwebs or high shelves. Steady as a vicar's handshake!",
     "condition": "NEW",
     "documents": [{"public_id": "03_Rock_Solid_Ladder_mtcph7", "filename": "Rock-Solid Ladder.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl04", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Muffin Mega-Kit",
     "description": "Silicone moulds, trays and piping bags! Bake blueberry bombs or vegan wonders. Full bake-off kit for kitchen newbies!",
     "condition": "USED",
     "documents": [{"public_id": "04_Muffin_Mega_Kit_uzomdq", "filename": "Muffin Mega-Kit.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl05", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Luggage Scale Pro",
     "description": "Pocket hero saves airport fines! Digital whizzer weighs bags up to 50kg. Essential for cheap flight chancers!",
     "condition": "FAIR",
     "documents": [{"public_id": "05_Luggage_Scale_Pro_j4lboz", "filename": "Luggage Scale Pro.pdf", "content_type": "application/pdf"}]},

    # --- Lolo: book club events ---
    {"code": "lltl06", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Wuthering Heights Classic",
     "description": "Brontë's stormy masterpiece! Heathcliff's wild heart on windswept moors. Grab for our next brooding chat!",
     "condition": "NEW",
     "event_date": datetime(2027, 1, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl07", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Jane Eyre Gothic",
     "description": "Orphan to obsession – pure Brontë fire! Madwoman in the attic awaits. Perfect for our dark romance dive!",
     "condition": "GOOD",
     "event_date": datetime(2027, 2, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl08", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Rebecca Timeless",
     "description": "Du Maurier's Manderley mystery! Second wife vs ghostly first – chills and thrills. Join the tea-spilling session!",
     "condition": "NEW",
     "event_date": datetime(2027, 3, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl09", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Pride & Prejudice Spark",
     "description": "Austen's witty Darcy dance! Bennet sisters vs eligible bachelors. Lightens our gothic with Regency banter!",
     "condition": "USED",
     "event_date": datetime(2027, 4, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl10", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Tess of the D'Urbervilles",
     "description": "Hardy's tragic rural beauty! Pure woman wrongly blamed. Deep, devastating – ideal for our emotional book bash!",
     "condition": "FAIR",
     "event_date": datetime(2027, 5, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},

    # --- Lulu: share collection (ownership transferred below in TRANSFERS) ---
    {"code": "lltl11", "type": "SHARE_THING", "owner_code": "La1aN1", "collections": ["1u1uC1"],
     "headline": "Forgotten Fondue Set",
     "description": "Six-person cheese melter from '98! Complete with forks and standby. Snap it up before it ghosts again!",
     "condition": "NEW"},
    {"code": "lltl12", "type": "SHARE_THING", "owner_code": "L3L3oo", "collections": ["1u1uC1"],
     "headline": "Vintage Suitcase Stack",
     "description": "Three leather beauties, minor scuffs! Perfect for weekend escapes or storage chic. Claim before they vanish!",
     "condition": "GOOD"},
    {"code": "lltl13", "type": "SHARE_THING", "owner_code": "l1l13S", "collections": ["1u1uC1"],
     "headline": "Exercise Bike Beast",
     "description": "Silent spinner with 8 resistance levels! Post-lockdown guilt-free cardio. Gone in a flash – pedal power!",
     "condition": "NEW"},
    {"code": "lltl14", "type": "SHARE_THING", "owner_code": "l0l0oh", "collections": ["1u1uC1"],
     "headline": "Ceramic Plant Pots",
     "description": "Hand-thrown terracotta trio, saucer included! Revive your sad succulents. Weekly roundup star – hurry!",
     "condition": "USED"},
    {"code": "lltl15", "type": "SHARE_THING", "owner_code": "1u1ucs", "collections": ["1u1uC1"],
     "headline": "Board Game Bonanza",
     "description": "Monopoly, Cluedo and Pictionary complete! Rainy night coliving classics. First come, first served – they fly!",
     "condition": "FAIR"},

    # --- Lela: succulent gifts (minimalist, is_endless) ---
    {"code": "lltl22", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Zebra, Rosie & Jade – my terracotta trio needs new homes!",
     "thumbnail": "001_esszlo", "is_endless": True},
    {"code": "lltl23", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Her Majesty the Echeveria – dusty pink crown, free pups!",
     "thumbnail": "003_fmvqfb", "is_endless": True},
    {"code": "lltl24", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Sunset in a pot – peachy-lilac pup ready to adopt!",
     "thumbnail": "005_ehlynl", "is_endless": True},
    {"code": "lltl25", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "The fuzzy dumpling – velvety leaves, zero fuss, free pup!",
     "thumbnail": "007_hshqhk", "is_endless": True},
    {"code": "lltl26", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Straight from my hands to yours – pick your pup!",
     "thumbnail": "009_awlaxr", "is_endless": True},
    {"code": "lltl27", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "My mini meadow – five succulent sisters under one roof!",
     "thumbnail": "008_ugfkw0", "is_endless": True},
    {"code": "lltl28", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Too many babies, not enough pots – come rescue one!",
     "thumbnail": "004_byjjmi", "is_endless": True},

    # --- Lolo: dulcimer appointment ---
    {"code": "lltl29", "type": "APPOINTMENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C2"],
     "headline": "Classes every afternoon!",
     "description": "Bring your own dulcimer if you have one. If not, don't sweat it – mine's here for you to borrow!",
     "thumbnail": "2.JPG_d4itfz",
     "slot_duration": 60,
     "availability_schedule": [{"days": [2, 3, 4], "start_time": "14:00", "end_time": "18:00"}],
     "location": "At Lolo's flat, Zona Franca, BCN"},

    # --- Lala: shared van (hourly asset) ---
    {"code": "lltl30", "type": "ASSET_THING", "owner_code": "La1aN1", "collections": ["La1aC2"],
     "headline": "Wherever you're going, she makes it prettier!",
     "thumbnail": "volkswagen-id-buzz_hd_131851.jpg_hkc49z",
     "booking_unit": "HOUR"},

    # --- Lulu's wish posted by Lala ---
    {"code": "La1aW1", "type": "WISH_THING", "owner_code": "La1aN1", "collections": ["1u1uC1"],
     "headline": "Hey! Maybe a small ladder, anyone? The top shelf is winning! 🪜"},

    # --- Lili's circuit swap ---
    {"code": "l1sw01", "type": "SWAP_THING", "owner_code": "La1aN1", "collections": ["l1l1C2"],
     "headline": "Grove Shield for Arduino Nano v1.1 (Seeed Studio)",
     "thumbnail": "ARDUINO_001_ogf1sz"},
    {"code": "l1sw02", "type": "SWAP_THING", "owner_code": "L3L3oo", "collections": ["l1l1C2"],
     "headline": "Grove - Laser PM2.5 Dust Sensor (HM3301)",
     "thumbnail": "ARDUINO_002_jvkxd3"},
    {"code": "l1sw03", "type": "SWAP_THING", "owner_code": "l0l0oh", "collections": ["l1l1C2"],
     "headline": "MB102 Breadboard Power Supply Module (HW-131)",
     "thumbnail": "ARDUINO_003_ace77f"},
    {"code": "l1sw04", "type": "SWAP_THING", "owner_code": "1u1ucs", "collections": ["l1l1C2"],
     "headline": "Arduino Nano Screw Terminal Adapter",
     "thumbnail": "ARDUINO_004_mdfkm9"},
    {"code": "l1sw05", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "Arduino Nano 33 BLE",
     "thumbnail": "ARDUINO_005_etbpia"},
    {"code": "l1sw06", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "CCS811 Indoor Air Quality Sensor",
     "thumbnail": "ARDUINO_006_aoqyik"},
    {"code": "l1sw07", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "Grove's: Temperature & Humidity, Water, Sound, UV, Air",
     "thumbnail": "ARDUINO_007_osnlj1"},
    {"code": "l1sw08", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "DFRobot Analogue UV Sensor V2 (Gravity)",
     "thumbnail": "ARDUINO_008_nc0qwg"},
]

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

# Event attendees: user_code attends thing_code
EVENT_ATTENDANCES = [
    ("lltl06", "La1aN1"),  # Lala → Wuthering Heights
    ("lltl07", "La1aN1"),  # Lala → Jane Eyre
    ("lltl08", "La1aN1"),  # Lala → Rebecca
    ("lltl06", "L3L3oo"),  # Lele → Wuthering Heights
    ("lltl08", "L3L3oo"),  # Lele → Rebecca
    ("lltl06", "l1l13S"),  # Lili → Wuthering Heights
    ("lltl07", "l1l13S"),  # Lili → Jane Eyre
]

# ThingTransfer chain — (thing_code, from_code, to_code, lent_date, returned_date)
TRANSFERS = [
    # Lulu's share collection — single transfers
    ("lltl11", "1u1ucs", "La1aN1", date(2026, 3, 1), None),
    ("lltl12", "1u1ucs", "L3L3oo", date(2026, 3, 15), None),
    ("lltl13", "1u1ucs", "l1l13S", date(2026, 4, 1), None),
    # lltl14 — full chain ending at Lolo
    ("lltl14", "1u1ucs", "l0l0oh", date(2026, 1, 10), date(2026, 1, 31)),
    ("lltl14", "l0l0oh", "La1aN1", date(2026, 2, 1), date(2026, 2, 28)),
    ("lltl14", "La1aN1", "L3L3oo", date(2026, 3, 1), date(2026, 3, 31)),
    ("lltl14", "L3L3oo", "l1l13S", date(2026, 4, 1), date(2026, 4, 15)),
    ("lltl14", "l1l13S", "l0l0oh", date(2026, 4, 16), None),
    # Lili's circuit swap — historical swaps
    ("l1sw01", "l1l13S", "La1aN1", date(2026, 3, 20), None),
    ("l1sw02", "l1l13S", "L3L3oo", date(2026, 3, 25), None),
    ("l1sw05", "l0l0oh", "l1l13S", date(2026, 4, 5), None),
    ("l1sw07", "l0l0oh", "L3L3oo", date(2026, 1, 20), None),
    ("l1sw07", "L3L3oo", "l1l13S", date(2026, 3, 1), None),
]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Populate demo data (users, collections, things, FAQs, transfers). Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all demo data before seeding (leaves other data intact).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()
            self.stdout.write(self.style.WARNING("Deleted existing demo data."))

        self._seed_users()
        self._seed_collections()
        self._seed_things()
        self._seed_faqs()
        self._seed_event_attendances()
        self._seed_transfers()

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(USERS)} users, {len(COLLECTIONS)} collections, "
            f"{len(THINGS)} things, {len(FAQS)} FAQs, "
            f"{len(EVENT_ATTENDANCES)} attendances, {len(TRANSFERS)} transfers."
        ))

    # ---- helpers ----

    def _reset(self):
        user_codes = [u["code"] for u in USERS]
        Thing.objects.filter(owner_id__in=user_codes).delete()
        Collection.objects.filter(owner_id__in=user_codes).delete()
        User.objects.filter(code__in=user_codes).delete()

    def _seed_users(self):
        for data in USERS:
            User.objects.update_or_create(
                code=data["code"],
                defaults={
                    "email": data["email"],
                    "name": data["name"],
                    "headline": data["headline"],
                    "theeeme_id": data["theeeme_id"],
                    "koro": data.get("koro", "basic"),
                },
            )

    def _seed_collections(self):
        for data in COLLECTIONS:
            defaults = {
                "owner": User.objects.get(code=data["owner_code"]),
                "headline": data["headline"],
                "description": data["description"],
                "status": "ACTIVE",
                "mode": data.get("mode", "PROPRIETARY"),
                "is_swap": data.get("is_swap", False),
                "is_share": data.get("is_share", False),
                "is_minimalist": data.get("is_minimalist", False),
                "is_onboarding": data.get("is_onboarding", False),
                "newsletter_enabled": data.get("newsletter_enabled", False),
                "digest_frequency": data.get("digest_frequency", "NONE"),
                "thumbnail": data.get("thumbnail", ""),
            }
            col, _ = Collection.objects.update_or_create(code=data["code"], defaults=defaults)
            col.invites.set(User.objects.filter(code__in=data.get("invites", [])))

    def _seed_things(self):
        for data in THINGS:
            owner = User.objects.get(code=data["owner_code"])
            defaults = {
                "type": data["type"],
                "owner": owner,
                "headline": data["headline"],
                "description": data.get("description", ""),
                "status": "ACTIVE",
                "fee": data.get("fee", None),
                "condition": data.get("condition", ""),
                "availability": data.get("availability", ""),
                "location": data.get("location", ""),
                "thumbnail": data.get("thumbnail", ""),
                "event_date": data.get("event_date"),
                "booking_unit": data.get("booking_unit", ""),
                "slot_duration": data.get("slot_duration"),
                "availability_schedule": data.get("availability_schedule", []),
                "documents": data.get("documents", []),
                "is_endless": data.get("is_endless", False),
            }
            thing, _ = Thing.objects.update_or_create(code=data["code"], defaults=defaults)
            for col_code in data.get("collections", []):
                Collection.objects.get(code=col_code).things.add(thing)

    def _seed_faqs(self):
        for data in FAQS:
            FAQ.objects.get_or_create(
                thing=Thing.objects.get(code=data["thing_code"]),
                questioner=User.objects.get(code=data["questioner_code"]),
                question=data["question"],
                defaults={"answer": data["answer"], "is_visible": True},
            )

    def _seed_event_attendances(self):
        for thing_code, user_code in EVENT_ATTENDANCES:
            Thing.objects.get(code=thing_code).deal.add(User.objects.get(code=user_code))

    def _seed_transfers(self):
        for thing_code, from_code, to_code, lent_date, returned_date in TRANSFERS:
            ThingTransfer.objects.get_or_create(
                thing=Thing.objects.get(code=thing_code),
                from_user=User.objects.get(code=from_code),
                to_user=User.objects.get(code=to_code),
                lent_date=lent_date,
                defaults={"returned_date": returned_date},
            )
