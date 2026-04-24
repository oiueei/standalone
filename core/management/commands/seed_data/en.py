"""
English demo data — users, collections, things, FAQs with headlines/descriptions
in British English. Use via `python manage.py seed_demo --lang=en` (default).
"""

from datetime import datetime

from .common import TZ_PLUS2

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
        "thumbnail": "La1aC1",
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
        "thumbnail": "La1aC2",
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
        "is_onboarding": True,
        "thumbnail": "L3L3C1",
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
        "thumbnail": "L3L3C2",
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
        "is_onboarding": True,
        "thumbnail": "l0l0C1",
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
        "thumbnail": "l0l0C2",
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
        "thumbnail": "l1l1C1",
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
        "thumbnail": "l1l1C2",
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
        "thumbnail": "1u1uC1",
    },
]

THINGS = [
    # --- Lala: sabbatical sale ---
    {"code": "stffa1", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Shaggy Nordic Rug",
     "description": "Nordic meditation nest! Soft wool like a Highland sheep, hygge vibes with patchouli whiff. Just a tenner!",
     "thumbnail": "stffa1", "fee": "20.00", "condition": "NEW"},
    {"code": "stffa2", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Tea Cup Set",
     "description": "Pagan tea party! 12 mugs with \"Keep Calm and Chai On\". Perfect for hippy brews!",
     "thumbnail": "stffa2", "fee": "30.00", "availability": "IMMEDIATE"},
    {"code": "stffa3", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Retro Blender",
     "description": "Blender McBlenderface! This magic whizzer pulps kale and hippy dreams into cosmic smoothies. Peace & juice for 10 quid!",
     "thumbnail": "stffa3", "fee": "10.00", "condition": "GOOD", "availability": "NEXT_WEEK"},
    {"code": "stffa4", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Steamy Iron",
     "description": "Wrinkle-taming beast! Irons tie-dye tees spotless for festivals. Smooth your karma for a tenner!",
     "thumbnail": "stffa4", "fee": "10.00", "availability": "IMMEDIATE", "location": "Barcelona"},
    {"code": "stffa5", "type": "SELL_THING", "owner_code": "La1aN1", "collections": ["La1aC1"],
     "headline": "Disco Psych Lamp",
     "description": "Rasta fairy light! Spins like a Glastonbury trip, glows for midnight herbal brews. Groovy for 10 quid!",
     "thumbnail": "stffa5", "fee": "20.00", "condition": "NEW"},

    # --- Lele: bakery orders ---
    {"code": "cksle1", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Pistachio Bun Bliss",
     "description": "Three plush brioche buns stuffed with lush pistachio cream, dusted with magic powder and crunchy nuts. Proper green explosion of joy for posh dos! Order your hypnotic batch now.",
     "thumbnail": "cksle1", "fee": "5.00"},
    {"code": "cksle2", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Love Heart Stunner",
     "description": "Round beauty scrawled \"Love\" in choc, with a lush red rose and sparkly pearls. Creamy, romantic to bits. For Valentines, anniversaries or just 'cause – fall for the taste!",
     "thumbnail": "cksle2", "fee": "40.00"},
    {"code": "cksle3", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Raspberry Layer Dream",
     "description": "Pink raspberry layers over white cream, on a crystal stand. Fresh, zingy and blooming addictive. The birthday or brunch star – order and win hearts!",
     "thumbnail": "cksle3", "fee": "60.00"},
    {"code": "cksle4", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Macaron Majesty",
     "description": "Posh creamy cake topped with grey-gold macarons, pink blooms and swirly perfection. Spot-on for weddings or high tea: French luxe with your twist. Your event, your dream flavour!",
     "thumbnail": "cksle4", "fee": "45.00"},
    {"code": "cksle5", "type": "ORDER_THING", "owner_code": "L3L3oo", "collections": ["L3L3C1"],
     "headline": "Carrot Cake Cosy",
     "description": "Chunky carrot squares with velvety frosting, on a pink plate with Marimekko mug and brew. Proper Nordic hug in cake form – pure hygge! Ideal for cosy cafés or post-cycle nibbles.",
     "thumbnail": "cksle5", "fee": "5.00"},

    # --- Lili: tool library ---
    {"code": "lltl01", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Sturdy Drill Kit",
     "description": "Cordless beast for DIY disasters! Powers through walls like butter, full bits included. Borrow for your next home hack!",
     "condition": "NEW",
     "documents": [{"public_id": "lltl01", "filename": "Sturdy Drill Kit.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl02", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Steam Cleaner Wizard",
     "description": "Sizzles grime off ovens and sofas! Eco-magic wand leaves everything sparkling. Perfect for pre-party spruce-ups!",
     "condition": "GOOD",
     "documents": [{"public_id": "lltl02", "filename": "Steam Cleaner Wizard.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl03", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Rock-Solid Ladder",
     "description": "Six-foot safety champ, wobble-free! Reach those pesky loft cobwebs or high shelves. Steady as a vicar's handshake!",
     "condition": "NEW",
     "documents": [{"public_id": "lltl03", "filename": "Rock-Solid Ladder.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl04", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Muffin Mega-Kit",
     "description": "Silicone moulds, trays and piping bags! Bake blueberry bombs or vegan wonders. Full bake-off kit for kitchen newbies!",
     "condition": "USED",
     "documents": [{"public_id": "lltl04", "filename": "Muffin Mega-Kit.pdf", "content_type": "application/pdf"}]},
    {"code": "lltl05", "type": "LEND_THING", "owner_code": "l1l13S", "collections": ["l1l1C1"],
     "headline": "Luggage Scale Pro",
     "description": "Pocket hero saves airport fines! Digital whizzer weighs bags up to 50kg. Essential for cheap flight chancers!",
     "condition": "FAIR",
     "documents": [{"public_id": "lltl05", "filename": "Luggage Scale Pro.pdf", "content_type": "application/pdf"}]},

    # --- Lolo: book club events ---
    {"code": "lltl06", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Wuthering Heights Classic",
     "description": "Brontë's stormy masterpiece! Heathcliff's wild heart on windswept moors. Grab for our next brooding chat!",
     "thumbnail": "lltl06", "condition": "NEW",
     "event_date": datetime(2027, 1, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl07", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Jane Eyre Gothic",
     "description": "Orphan to obsession – pure Brontë fire! Madwoman in the attic awaits. Perfect for our dark romance dive!",
     "thumbnail": "lltl07", "condition": "GOOD",
     "event_date": datetime(2027, 2, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl08", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Rebecca Timeless",
     "description": "Du Maurier's Manderley mystery! Second wife vs ghostly first – chills and thrills. Join the tea-spilling session!",
     "thumbnail": "lltl08", "condition": "NEW",
     "event_date": datetime(2027, 3, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl09", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Pride & Prejudice Spark",
     "description": "Austen's witty Darcy dance! Bennet sisters vs eligible bachelors. Lightens our gothic with Regency banter!",
     "thumbnail": "lltl09", "condition": "USED",
     "event_date": datetime(2027, 4, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},
    {"code": "lltl10", "type": "EVENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C1"],
     "headline": "Book Club session – Tess of the D'Urbervilles",
     "description": "Hardy's tragic rural beauty! Pure woman wrongly blamed. Deep, devastating – ideal for our emotional book bash!",
     "thumbnail": "lltl10", "condition": "FAIR",
     "event_date": datetime(2027, 5, 5, 16, 0, 0, tzinfo=TZ_PLUS2)},

    # --- Lulu: share collection (ownership transferred below in TRANSFERS) ---
    {"code": "lltl11", "type": "SHARE_THING", "owner_code": "La1aN1", "collections": ["1u1uC1"],
     "headline": "Forgotten Fondue Set",
     "description": "Six-person cheese melter from '98! Complete with forks and standby. Snap it up before it ghosts again!",
     "thumbnail": "lltl11", "condition": "NEW"},
    {"code": "lltl12", "type": "SHARE_THING", "owner_code": "L3L3oo", "collections": ["1u1uC1"],
     "headline": "Vintage Suitcase Stack",
     "description": "Three leather beauties, minor scuffs! Perfect for weekend escapes or storage chic. Claim before they vanish!",
     "thumbnail": "lltl12", "condition": "GOOD"},
    {"code": "lltl13", "type": "SHARE_THING", "owner_code": "l1l13S", "collections": ["1u1uC1"],
     "headline": "Exercise Bike Beast",
     "description": "Silent spinner with 8 resistance levels! Post-lockdown guilt-free cardio. Gone in a flash – pedal power!",
     "thumbnail": "lltl13", "condition": "NEW"},
    {"code": "lltl14", "type": "SHARE_THING", "owner_code": "l0l0oh", "collections": ["1u1uC1"],
     "headline": "Ceramic Plant Pots",
     "description": "Hand-thrown terracotta trio, saucer included! Revive your sad succulents. Weekly roundup star – hurry!",
     "thumbnail": "lltl14", "condition": "USED"},
    {"code": "lltl15", "type": "SHARE_THING", "owner_code": "1u1ucs", "collections": ["1u1uC1"],
     "headline": "Board Game Bonanza",
     "description": "Monopoly, Cluedo and Pictionary complete! Rainy night coliving classics. First come, first served – they fly!",
     "thumbnail": "lltl15", "condition": "FAIR"},

    # --- Lele: succulent gifts (minimalist, is_endless) ---
    {"code": "lltl22", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Zebra, Rosie & Jade – my terracotta trio needs new homes!",
     "thumbnail": "lltl22", "is_endless": True},
    {"code": "lltl23", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Her Majesty the Echeveria – dusty pink crown, free pups!",
     "thumbnail": "lltl23", "is_endless": True},
    {"code": "lltl24", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Sunset in a pot – peachy-lilac pup ready to adopt!",
     "thumbnail": "lltl24", "is_endless": True},
    {"code": "lltl25", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "The fuzzy dumpling – velvety leaves, zero fuss, free pup!",
     "thumbnail": "lltl25", "is_endless": True},
    {"code": "lltl26", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Straight from my hands to yours – pick your pup!",
     "thumbnail": "lltl26", "is_endless": True},
    {"code": "lltl27", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "My mini meadow – five succulent sisters under one roof!",
     "thumbnail": "lltl27", "is_endless": True},
    {"code": "lltl28", "type": "GIFT_THING", "owner_code": "L3L3oo", "collections": ["L3L3C2"],
     "headline": "Too many babies, not enough pots – come rescue one!",
     "thumbnail": "lltl28", "is_endless": True},

    # --- Lolo: dulcimer appointment ---
    {"code": "lltl29", "type": "APPOINTMENT_THING", "owner_code": "l0l0oh", "collections": ["l0l0C2"],
     "headline": "Classes every afternoon!",
     "description": "Bring your own dulcimer if you have one. If not, don't sweat it – mine's here for you to borrow!",
     "thumbnail": "lltl29",
     "slot_duration": 60,
     "availability_schedule": [{"days": [2, 3, 4], "start_time": "14:00", "end_time": "18:00"}],
     "location": "At Lolo's flat, Zona Franca, BCN"},

    # --- Lala: shared van (hourly asset) ---
    {"code": "lltl30", "type": "ASSET_THING", "owner_code": "La1aN1", "collections": ["La1aC2"],
     "headline": "Wherever you're going, she makes it prettier!",
     "thumbnail": "lltl30",
     "booking_unit": "HOUR"},

    # --- Lulu's wish posted by Lala ---
    {"code": "La1aW1", "type": "WISH_THING", "owner_code": "La1aN1", "collections": ["1u1uC1"],
     "headline": "Hey! Maybe a small ladder, anyone? The top shelf is winning! 🪜"},

    # --- Lili's circuit swap ---
    {"code": "l1sw01", "type": "SWAP_THING", "owner_code": "La1aN1", "collections": ["l1l1C2"],
     "headline": "Grove Shield for Arduino Nano v1.1 (Seeed Studio)",
     "thumbnail": "l1sw01"},
    {"code": "l1sw02", "type": "SWAP_THING", "owner_code": "L3L3oo", "collections": ["l1l1C2"],
     "headline": "Grove - Laser PM2.5 Dust Sensor (HM3301)",
     "thumbnail": "l1sw02"},
    {"code": "l1sw03", "type": "SWAP_THING", "owner_code": "l0l0oh", "collections": ["l1l1C2"],
     "headline": "MB102 Breadboard Power Supply Module (HW-131)",
     "thumbnail": "l1sw03"},
    {"code": "l1sw04", "type": "SWAP_THING", "owner_code": "1u1ucs", "collections": ["l1l1C2"],
     "headline": "Arduino Nano Screw Terminal Adapter",
     "thumbnail": "l1sw04"},
    {"code": "l1sw05", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "Arduino Nano 33 BLE",
     "thumbnail": "l1sw05"},
    {"code": "l1sw06", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "CCS811 Indoor Air Quality Sensor",
     "thumbnail": "l1sw06"},
    {"code": "l1sw07", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "Grove's: Temperature & Humidity, Water, Sound, UV, Air",
     "thumbnail": "l1sw07"},
    {"code": "l1sw08", "type": "SWAP_THING", "owner_code": "l1l13S", "collections": ["l1l1C2"],
     "headline": "DFRobot Analogue UV Sensor V2 (Gravity)",
     "thumbnail": "l1sw08"},
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
