"""
Structural demo-data skeleton shared across all language variants.

Only fields that DON'T change between languages live here (codes, types,
ownership, relationships, flags, prices, image ids, tags, …). The translatable
text for each entity lives in the per-locale modules (en.py, es.py) and is
merged onto this skeleton by `seed_demo.load_seed_data`. Adding a language means
translating text only — never re-declaring structure.

Image ids (photo/thumbnail/gallery) are stored BARE here; `seed_demo` prefixes
them with ``SEED_IMAGE_FOLDER`` (oiueei/seed/) at seed time — that's the storage
folder the demo fixtures actually live in, kept apart from real user uploads.
"""

import json
from datetime import date


def _localized_tag(**texts):
    """A tag label carrying one text per language.

    The stored value is the serialized ``{lang: text}`` map. Things reference
    their collection's vocabulary **by raw string**, so each label is defined
    once as a constant below and reused byte-identically everywhere it appears.
    A label that reads the same in every language stays a plain string instead.
    """
    return json.dumps(texts, ensure_ascii=False)


# Shared vocabulary. Lili's lending library defined these first; Lele's Sunday
# swap-meet reuses the same constants, which is correct precisely because the
# labels mean the same thing in both — a thing references its collection's
# vocabulary by raw string, so one constant is one label everywhere.
TAG_COCINA = _localized_tag(es="Cocina", ca="Cuina", en="Kitchen")
TAG_JARDIN = _localized_tag(es="Jardín", ca="Jardí", en="Garden")
TAG_BRICOLAJE = _localized_tag(es="Bricolaje", ca="Bricolatge", en="DIY")
TAG_CRIANZA = _localized_tag(es="Crianza", ca="Criança", en="Parenting")
TAG_HOGAR = _localized_tag(es="Hogar", ca="Llar", en="Home")
TAG_LIMPIEZA = _localized_tag(es="Limpieza", ca="Neteja", en="Cleaning")
TAG_DEPORTE = _localized_tag(es="Deporte", ca="Esport", en="Sports")
TAG_OCIO = _localized_tag(es="Ocio", ca="Lleure", en="Leisure")
TAG_ELECTRONICA = _localized_tag(es="Electrónica", ca="Electrònica", en="Electronics")

# The community workshop's vocabulary (Lulu's group). Kept separate from Lili's
# labels above even where they rhyme: TAG_BRICOLAJE is her one-word "DIY", while
# this group tags maintenance alongside it, and a thing references its collection's
# label by raw string — one shared constant would silently merge two vocabularies.
TAG_BRICO_MANT = _localized_tag(
    es="Bricolaje y mantenimiento", ca="Bricolatge i manteniment", en="DIY & maintenance"
)
TAG_CARPINTERIA = _localized_tag(es="Carpintería", ca="Fusteria", en="Woodworking")
TAG_ELECTRICAS = _localized_tag(
    es="Herramientas eléctricas", ca="Eines elèctriques", en="Power tools"
)
TAG_METALISTERIA = _localized_tag(es="Metalistería", ca="Metal·listeria", en="Metalwork")
TAG_ARTESANIA = _localized_tag(es="Oficios artesanales", ca="Oficis artesanals", en="Craft trades")
TAG_PRECISION = _localized_tag(es="Precisión", ca="Precisió", en="Precision")

# Lili's deposit policy — reuses `_localized_tag`'s serialization: the
# stored value is still just a {lang: text} map, on a different field. Written
# here rather than split across the per-language files because, like a tag
# label, it is small, structural-adjacent owner content rather than the kind
# of long-form prose the per-language merge exists for.
DEPOSIT_POLICY_LILI = _localized_tag(
    es="La fianza es igual al precio del alquiler. Se devuelve al traer la cosa de vuelta en buen estado.",
    ca="La fiança és igual al preu del lloguer. Es retorna en tornar la cosa en bon estat.",
    en="The deposit equals the rental fee. Refunded when the thing comes back in good shape.",
)

USERS = [
    {
        "code": "La1aN1",
        "email_local": "lala",
        "name": "Lala",
        "photo": "La1aPH",
        "postal_code": "08040",
        "age_range": "GEN_Y",
    },
    {
        "code": "L3L3oo",
        "email_local": "lele",
        "name": "Lele",
        "photo": "L3L3PH",
        "postal_code": "08905",
        "age_range": "GEN_Z",
        "language": "ca",
    },
    {
        "code": "l1l13S",
        "email_local": "lili",
        "name": "Lili",
        "photo": "l1l1PH",
        "postal_code": "08038",
    },
    {
        "code": "l0l0oh",
        "email_local": "lolo",
        "name": "Lolo",
        "photo": "l0l0PH",
        "postal_code": "08901",
        "age_range": "GEN_X",
    },
    {
        "code": "1u1ucs",
        "email_local": "lulu",
        "name": "Lulu",
        "photo": "1u1uPH",
        "postal_code": "08906",
        "age_range": "GEN_Z",
        "language": "en",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "theeeme_id": "BUU331",
        "koro": "basic",
        "owner_code": "La1aN1",
        "visibility": "PRIVATE",
        "invites": ["L3L3oo"],
        "is_onboarding": True,
        "kind": "STALL",
        "allowed_thing_types": ["GIFT_THING", "SELL_THING"],
        "thumbnail": "La1aC1",
    },
    {
        "code": "l0l0C1",
        "theeeme_id": "BUU331",
        "koro": "beat",
        "owner_code": "l0l0oh",
        "visibility": "PUBLIC",
        "invites": ["La1aN1", "l1l13S", "L3L3oo", "1u1ucs"],
        "is_onboarding": True,
        "kind": "STALL",
        "allowed_thing_types": ["GIFT_THING", "SELL_THING"],
        "thumbnail": "L3L3C2",
    },
    {
        "code": "l1l1C1",
        "theeeme_id": "BUU331",
        "koro": "wave",
        "owner_code": "l1l13S",
        "visibility": "PUBLIC",
        "invites": ["La1aN1", "L3L3oo", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "kind": "LIBRARY",
        "allowed_thing_types": ["LEND_THING", "RENT_THING"],
        # Lili closes the tool library over the winter holidays — no pickup or
        # return on these days. (Re-entered each year; stale ones drop on edit.)
        "closed_dates": ["2026-12-25", "2026-12-26", "2027-01-01", "2027-01-06"],
        "tags": [
            TAG_COCINA,
            TAG_JARDIN,
            TAG_BRICOLAJE,
            TAG_CRIANZA,
            TAG_HOGAR,
            TAG_LIMPIEZA,
            TAG_DEPORTE,
            TAG_OCIO,
            TAG_ELECTRONICA,
        ],
        "thumbnail": "l1l1C1",
        "deposit_policy": DEPOSIT_POLICY_LILI,
    },
    {
        "code": "1u1uC1",
        "theeeme_id": "BUU331",
        "koro": "calm",
        "owner_code": "1u1ucs",
        "mode": "COMMUNITY",
        "visibility": "PRIVATE",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh"],
        # Lala is promoted alongside Lulu — the demo's one visible co-curator, so
        # the feature is reachable without seeding a whole second scenario for it.
        "co_owners": ["La1aN1"],
        "is_onboarding": True,
        "kind": "LIBRARY",
        "allowed_thing_types": ["LEND_THING"],
        # One of two COMMUNITY collections in the demo (the other is Lele's
        # market below): every member uploads and every member lends, so the 21
        # things below are owned by all five, not by Lulu. It also carries the
        # demo's first rental rules: a loan runs one to five days and changes
        # hands on a working day. rental_weekdays applies to BOTH ends, so a
        # Thursday pickup cannot be a three-day loan — it would come back on
        # Sunday. The dates below are all picked to satisfy that.
        "rental_durations": [1, 2, 3, 4, 5],
        "rental_weekdays": [0, 1, 2, 3, 4],
        "tags": [
            TAG_BRICO_MANT,
            TAG_CARPINTERIA,
            TAG_ELECTRICAS,
            TAG_METALISTERIA,
            TAG_ARTESANIA,
            TAG_PRECISION,
        ],
        "thumbnail": "1u1uC1",
    },
    {
        "code": "L3L3C1",
        "theeeme_id": "K0P4R1",
        "koro": "pulse",
        "owner_code": "L3L3oo",
        "mode": "COMMUNITY",
        "visibility": "PRIVATE",
        "invites": ["La1aN1", "l1l13S", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "kind": "STALL",
        "allowed_thing_types": ["GIFT_THING"],
        # No rental rules: a gift has no dates to constrain. Its bookings are the
        # single-use kind — start_date/end_date stay null.
        "tags": [TAG_COCINA, TAG_OCIO, TAG_ELECTRONICA, TAG_HOGAR, TAG_CRIANZA],
        "thumbnail": "L3L3C1",
    },
    {
        # The demo's one reservations collection: Lulu runs a workshop space, and
        # members book a bench or the meeting corner to *use on site* — nothing is
        # carried away. RESERVE forces PROPRIETARY, holds only RESERVE things, and
        # reuses rental_weekdays as "days the space is open". Bookings auto-confirm.
        "code": "1u1uRe",
        "theeeme_id": "BUU331",
        "koro": "vibration",
        "owner_code": "1u1ucs",
        "mode": "PROPRIETARY",
        "visibility": "PRIVATE",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh"],
        "is_onboarding": True,
        "kind": "SHED",
        "allowed_thing_types": ["RESERVE_THING"],
        "reservation_max_days": 3,
        "reservation_horizon_days": 30,
        "rental_weekdays": [0, 1, 2, 3, 4],
        "thumbnail": "1u1uC1",
    },
    {
        # The demo's one network: Lulu founds it and, with Lele and Lolo, runs it. Each
        # of the three lends its own things from a pickup point of its own (see
        # NETWORK_POINTS): Lulu's and Lele's answer for an invented entity, with days
        # of their own and a closure; Lolo set no entity, so the network shows him by his
        # own name. A network is always a library: it holds loans and rentals.
        "code": "N3t0C1",
        "theeeme_id": "BUU331",
        "koro": "calm",
        "owner_code": "1u1ucs",
        "mode": "NETWORK",
        "visibility": "PRIVATE",
        "invites": ["La1aN1", "l1l13S", "L3L3oo", "l0l0oh"],
        "co_owners": ["L3L3oo", "l0l0oh"],
        "is_onboarding": True,
        "kind": "LIBRARY",
        "allowed_thing_types": ["LEND_THING", "RENT_THING"],
        # The network's own days; a point's replace them where it sets some.
        "rental_weekdays": [0, 1, 2, 3, 4],
        "tags": [TAG_BRICOLAJE, TAG_JARDIN, TAG_COCINA],
    },
]

THINGS = [
    {
        "code": "La1a01",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "thumbnail": "La1a01_a",
        "gallery": ["La1a01_b"],
        "fee": "10.00",
        "condition": "NEW",
    },
    {
        "code": "La1a02",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "thumbnail": "La1a02",
        "fee": "10.00",
        "availability": "IMMEDIATE",
    },
    {
        "code": "La1a03",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "thumbnail": "La1a03",
        "fee": "10.00",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
    },
    {
        "code": "La1a04",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "thumbnail": "La1a04",
        "fee": "10.00",
        "availability": "IMMEDIATE",
        "location": "Barcelona",
    },
    {
        "code": "La1a05",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "thumbnail": "La1a05",
        "fee": "10.00",
        "condition": "NEW",
    },
    {
        "code": "l1l101",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l101",
        "fee": "1.00",
        "tags": [TAG_CRIANZA],
    },
    {
        "code": "l1l102",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l102",
        "fee": "3.00",
        "tags": [TAG_CRIANZA],
    },
    {
        "code": "l1l103",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l103",
        "fee": "1.00",
        "tags": [TAG_OCIO, TAG_CRIANZA],
    },
    {
        "code": "l1l104",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l104",
        "fee": "5.00",
        "tags": [TAG_CRIANZA, TAG_JARDIN],
    },
    {
        "code": "l1l105",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l105",
        "fee": "1.00",
        "tags": [TAG_CRIANZA],
    },
    {
        "code": "l1l106",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l106",
        "fee": "3.00",
        "tags": [TAG_JARDIN],
    },
    {
        "code": "l1l107",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l107",
        "fee": "3.00",
        "deposit": "20.00",
        "tags": [TAG_ELECTRONICA],
    },
    {
        "code": "l1l108",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l108",
        "fee": "3.00",
        "deposit": "15.00",
        "tags": [TAG_OCIO, TAG_ELECTRONICA],
    },
    {
        "code": "l1l109",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l109",
        "fee": "1.00",
        "tags": [TAG_LIMPIEZA],
    },
    {
        "code": "l1l110",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l110",
        "fee": "3.00",
        "tags": [TAG_LIMPIEZA],
    },
    {
        "code": "l1l111",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l111",
        "fee": "5.00",
        "tags": [TAG_LIMPIEZA],
    },
    {
        "code": "l1l112",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l112",
        "fee": "3.00",
        "deposit": "30.00",
        "tags": [TAG_BRICOLAJE],
    },
    {
        "code": "l1l113",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l113",
        "fee": "3.00",
        "tags": [TAG_BRICOLAJE],
    },
    {
        "code": "l1l114",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l114",
        "fee": "1.00",
        "tags": [TAG_DEPORTE],
    },
    {
        "code": "l1l115",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l115",
        "fee": "1.00",
        "tags": [TAG_DEPORTE],
    },
    {
        "code": "l1l116",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l116",
        "fee": "1.00",
        "tags": [TAG_DEPORTE],
    },
    {
        "code": "l1l117",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l117",
        "fee": "1.00",
        "tags": [TAG_DEPORTE],
    },
    {
        "code": "l1l118",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l118",
        "fee": "5.00",
        "tags": [TAG_DEPORTE],
    },
    {
        "code": "l1l119",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l119",
        "fee": "1.00",
        "tags": [TAG_COCINA],
    },
    {
        "code": "l1l120",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l120",
        "fee": "3.00",
        "tags": [TAG_COCINA],
    },
    {
        "code": "l1l121",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l121",
        "fee": "3.00",
        "tags": [TAG_COCINA],
    },
    {
        "code": "l1l122",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l122",
        "fee": "3.00",
        "tags": [TAG_COCINA],
    },
    {
        "code": "l1l123",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l123",
        "fee": "1.00",
        "tags": [TAG_COCINA],
    },
    {
        "code": "l0l001",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l001",
        "is_endless": True,
    },
    {
        "code": "l0l002",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l002",
        "is_endless": True,
    },
    {
        "code": "l0l003",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l003",
        "is_endless": True,
    },
    {
        "code": "l0l004",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l004",
        "is_endless": True,
    },
    {
        "code": "l0l005",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l005",
        "is_endless": True,
    },
    {
        "code": "l0l006",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l006",
        "is_endless": True,
    },
    {
        "code": "l0l007",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "thumbnail": "l0l007",
        "is_endless": True,
    },
    {
        "code": "1u1u01",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u01",
        "condition": "GOOD",
        "location": "08038",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u02",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u02",
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08038",
        "tags": [TAG_PRECISION],
    },
    {
        "code": "1u1u03",
        "type": "LEND_THING",
        "owner_code": "L3L3oo",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u03",
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08905",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u04",
        "type": "LEND_THING",
        "owner_code": "L3L3oo",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u04",
        "condition": "USED",
        "location": "08905",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u05",
        "type": "LEND_THING",
        "owner_code": "L3L3oo",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u05",
        "condition": "NEW",
        "availability": "IMMEDIATE",
        "location": "08905",
        "tags": [TAG_ELECTRICAS],
    },
    {
        "code": "1u1u06",
        "type": "LEND_THING",
        "owner_code": "L3L3oo",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u06",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
        "location": "08905",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u07",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u07",
        "condition": "GOOD",
        "location": "08038",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u08",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u08",
        "availability": "NEXT_MONTH",
        "location": "08038",
        "tags": [TAG_ARTESANIA],
    },
    {
        "code": "1u1u09",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u09",
        "condition": "GOOD",
        "location": "08038",
        "tags": [TAG_BRICO_MANT],
    },
    {
        "code": "1u1u10",
        "type": "LEND_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u10",
        "condition": "FAIR",
        "location": "08040",
        "tags": [TAG_METALISTERIA],
    },
    {
        "code": "1u1u11",
        "type": "LEND_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u11",
        "condition": "GOOD",
        "availability": "END_OF_MONTH",
        "location": "08040",
        "tags": [TAG_ARTESANIA],
    },
    {
        "code": "1u1u12",
        "type": "LEND_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u12",
        "condition": "WELL_USED",
        "location": "08906",
        "tags": [TAG_BRICO_MANT],
    },
    {
        "code": "1u1u13",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u13",
        "condition": "USED",
        "availability": "NEXT_WEEK",
        "location": "08901",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u14",
        "type": "LEND_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u14",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
        "location": "08040",
        "tags": [TAG_METALISTERIA],
    },
    {
        "code": "1u1u15",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u15",
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08901",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u16",
        "type": "LEND_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u16",
        "condition": "USED",
        "location": "08040",
        "tags": [TAG_CARPINTERIA],
    },
    {
        "code": "1u1u17",
        "type": "LEND_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u17",
        "location": "08906",
        "tags": [TAG_BRICO_MANT],
    },
    {
        "code": "1u1u18",
        "type": "LEND_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u18",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
        "location": "08906",
        "tags": [TAG_ELECTRICAS],
    },
    {
        "code": "1u1u19",
        "type": "LEND_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u19",
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08906",
        "tags": [TAG_BRICO_MANT],
    },
    {
        "code": "1u1u20",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u20",
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08901",
        "tags": [TAG_BRICO_MANT],
    },
    {
        "code": "1u1u21",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u21",
        "condition": "GOOD",
        "location": "08901",
        "tags": [TAG_BRICO_MANT, TAG_ARTESANIA],
    },
    {
        "code": "L3L301",
        "type": "GIFT_THING",
        "owner_code": "La1aN1",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L301",
        "gallery": ["L3L301_b"],
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08040",
        "tags": [TAG_COCINA],
    },
    {
        "code": "L3L302",
        "type": "GIFT_THING",
        "owner_code": "1u1ucs",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L302",
        "condition": "GOOD",
        "location": "08906",
        "tags": [TAG_CRIANZA],
    },
    {
        "code": "L3L303",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L303",
        "gallery": ["L3L303_b", "L3L303_c"],
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08905",
        "tags": [TAG_OCIO, TAG_ELECTRONICA],
    },
    {
        "code": "L3L304",
        "type": "GIFT_THING",
        "owner_code": "1u1ucs",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L304",
        "gallery": ["L3L304_b"],
        "condition": "NEW",
        "availability": "IMMEDIATE",
        "location": "08906",
        "tags": [TAG_ELECTRONICA, TAG_OCIO],
    },
    {
        "code": "L3L305",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L305",
        "condition": "GOOD",
        "location": "08901",
        "tags": [TAG_OCIO],
    },
    {
        "code": "L3L306",
        "type": "GIFT_THING",
        "owner_code": "l0l0oh",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L306",
        "condition": "FAIR",
        "location": "08901",
        "tags": [TAG_ELECTRONICA],
    },
    {
        "code": "L3L307",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L307",
        "gallery": ["L3L307_b"],
        "condition": "WELL_USED",
        "location": "08905",
        "tags": [TAG_COCINA, TAG_HOGAR],
    },
    {
        "code": "L3L308",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L308",
        "condition": "USED",
        "availability": "IMMEDIATE",
        "location": "08905",
        "tags": [TAG_COCINA],
    },
    {
        "code": "L3L309",
        "type": "GIFT_THING",
        "owner_code": "La1aN1",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L309",
        "condition": "GOOD",
        "location": "08040",
        "tags": [TAG_COCINA],
    },
    {
        "code": "L3L310",
        "type": "GIFT_THING",
        "owner_code": "l1l13S",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L310",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
        "location": "08038",
        "tags": [TAG_COCINA],
    },
    {
        "code": "L3L311",
        "type": "GIFT_THING",
        "owner_code": "l1l13S",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L311",
        "condition": "GOOD",
        "availability": "IMMEDIATE",
        "location": "08038",
        "tags": [TAG_HOGAR],
    },
    # RESERVE things — Lulu's workshop space. Owned by Lulu (PROPRIETARY), used
    # on site, never carried away: no deposit, and the meeting corner is free
    # while the good workbench carries a small upkeep fee.
    {
        "code": "1u1uRa",
        "type": "RESERVE_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uRe"],
        "thumbnail": "1u1uC1",
        "fee": "3.00",
        # Three identical workbenches, so up to three can be booked at once.
        "units": 3,
        "location": "Taller de Lulu, banc gran",
    },
    {
        "code": "1u1uRb",
        "type": "RESERVE_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uRe"],
        "thumbnail": "1u1uC1",
        "location": "Taller de Lulu, racó de reunions",
    },
    {
        "code": "N3t001",
        "type": "LEND_THING",
        "owner_code": "1u1ucs",
        "collections": ["N3t0C1"],
        "condition": "GOOD",
        "tags": [TAG_BRICOLAJE],
    },
    {
        "code": "N3t002",
        "type": "RENT_THING",
        "owner_code": "1u1ucs",
        "collections": ["N3t0C1"],
        "fee": "3.00",
        "condition": "GOOD",
        "tags": [TAG_BRICOLAJE],
    },
    {
        "code": "N3t003",
        "type": "LEND_THING",
        "owner_code": "L3L3oo",
        "collections": ["N3t0C1"],
        "deposit": "20.00",
        "condition": "USED",
        "tags": [TAG_JARDIN],
    },
    {
        "code": "N3t004",
        "type": "RENT_THING",
        "owner_code": "L3L3oo",
        "collections": ["N3t0C1"],
        "fee": "2.00",
        "deposit": "20.00",
        "condition": "GOOD",
        "tags": [TAG_COCINA],
    },
    {
        "code": "N3t005",
        "type": "LEND_THING",
        "owner_code": "L3L3oo",
        "collections": ["N3t0C1"],
        "deposit": "20.00",
        "condition": "GOOD",
        "tags": [TAG_JARDIN],
    },
    {
        "code": "N3t006",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "collections": ["N3t0C1"],
        "condition": "GOOD",
        "tags": [TAG_COCINA],
    },
    {
        "code": "N3t007",
        "type": "LEND_THING",
        "owner_code": "l0l0oh",
        "collections": ["N3t0C1"],
        "condition": "USED",
        "tags": [TAG_BRICOLAJE],
    },
]

FAQS = [
    {
        "thing_code": "La1a01",
        "questioner_code": "L3L3oo",
    },
    {
        "thing_code": "La1a02",
        "questioner_code": "L3L3oo",
    },
    {
        "thing_code": "La1a03",
        "questioner_code": "L3L3oo",
    },
    {
        "thing_code": "La1a04",
        "questioner_code": "L3L3oo",
    },
    {
        "thing_code": "La1a05",
        "questioner_code": "L3L3oo",
    },
]

# ThingTransfer chain — (thing_code, from_code, to_code, lent_date, returned_date)
#
# Lili's lending library: a thing goes out from Lili and comes back, so each row
# is one loan. A null returned_date means it is still out — that thing renders as
# "currently with X", and its journey lists every borrower before them. Rows are
# oldest-first per thing; the model's -lent_date ordering shows the newest on top.
TRANSFERS = [
    # The drill is the library's workhorse — three borrowers, still out.
    ("l1l112", "l1l13S", "l0l0oh", date(2026, 1, 15), date(2026, 2, 2)),
    ("l1l112", "l1l13S", "La1aN1", date(2026, 3, 10), date(2026, 3, 24)),
    ("l1l112", "l1l13S", "L3L3oo", date(2026, 5, 5), None),
    # Steam cleaner — spring cleaning, both returned.
    ("l1l110", "l1l13S", "La1aN1", date(2026, 2, 20), date(2026, 2, 27)),
    ("l1l110", "l1l13S", "l0l0oh", date(2026, 4, 11), date(2026, 4, 18)),
    # Wet & dry vacuum — one long loan, back on the shelf.
    ("l1l111", "l1l13S", "L3L3oo", date(2026, 3, 1), date(2026, 3, 20)),
    # Game Boy — passed around the neighbourhood, still out.
    ("l1l108", "l1l13S", "l0l0oh", date(2026, 1, 8), date(2026, 2, 14)),
    ("l1l108", "l1l13S", "L3L3oo", date(2026, 4, 2), None),
    # Toolkit — a single afternoon.
    ("l1l113", "l1l13S", "La1aN1", date(2026, 4, 25), date(2026, 4, 26)),
    # Laser printer — the tax-return loan.
    ("l1l107", "l1l13S", "L3L3oo", date(2026, 6, 1), date(2026, 6, 8)),
]

# Reservations for the community workshop. Every past loan reaches this table
# through its transfer's `booking`, which is how the real flow builds them
# (`accept_booking` creates the pair together) — a transfer with no booking is
# the manual kind and says nothing about the request that preceded it.
#
# The last five carry no transfer on purpose: two requests still waiting on their
# owner, one accepted loan that has not started yet, one turned down and one the
# requester called off. That is the set of states an inbox has to render.
#
# Every start and end is a working day and every span is one to five days, which
# is exactly what the collection's rental rules allow. A demo whose own history
# breaks its own booking rule teaches the rule wrong.
#
# (code, thing_code, owner_code, requester_code, start_date, end_date, status)
BOOKINGS = [
    ("BK0001", "1u1u19", "1u1ucs", "L3L3oo", date(2026, 7, 1), date(2026, 7, 3), "ACCEPTED"),
    ("BK0002", "1u1u19", "1u1ucs", "l0l0oh", date(2026, 7, 20), date(2026, 7, 23), "ACCEPTED"),
    ("BK0003", "1u1u19", "1u1ucs", "La1aN1", date(2026, 8, 10), date(2026, 8, 14), "ACCEPTED"),
    ("BK0004", "1u1u20", "l0l0oh", "1u1ucs", date(2026, 7, 6), date(2026, 7, 10), "ACCEPTED"),
    ("BK0005", "1u1u18", "1u1ucs", "La1aN1", date(2026, 6, 16), date(2026, 6, 18), "ACCEPTED"),
    ("BK0006", "1u1u18", "1u1ucs", "l1l13S", date(2026, 8, 24), date(2026, 8, 28), "ACCEPTED"),
    ("BK0007", "1u1u17", "1u1ucs", "l0l0oh", date(2026, 6, 23), date(2026, 6, 26), "ACCEPTED"),
    ("BK0008", "1u1u17", "1u1ucs", "L3L3oo", date(2026, 7, 28), date(2026, 7, 30), "ACCEPTED"),
    ("BK0009", "1u1u12", "1u1ucs", "l1l13S", date(2026, 8, 4), date(2026, 8, 7), "ACCEPTED"),
    ("BK0010", "1u1u06", "L3L3oo", "l0l0oh", date(2026, 7, 14), date(2026, 7, 17), "ACCEPTED"),
    ("BK0011", "1u1u05", "L3L3oo", "La1aN1", date(2026, 7, 7), date(2026, 7, 8), "ACCEPTED"),
    ("BK0012", "1u1u09", "l1l13S", "L3L3oo", date(2026, 6, 9), date(2026, 6, 12), "ACCEPTED"),
    ("BK0013", "1u1u01", "l1l13S", "l0l0oh", date(2026, 7, 21), date(2026, 7, 23), "ACCEPTED"),
    ("BK0014", "1u1u14", "La1aN1", "l0l0oh", date(2026, 8, 25), date(2026, 8, 28), "ACCEPTED"),
    ("BK0015", "1u1u13", "l0l0oh", "La1aN1", date(2026, 8, 21), date(2026, 8, 25), "ACCEPTED"),
    ("BK0016", "1u1u19", "1u1ucs", "La1aN1", date(2026, 8, 31), date(2026, 9, 3), "PENDING"),
    ("BK0017", "1u1u10", "La1aN1", "L3L3oo", date(2026, 9, 1), date(2026, 9, 3), "PENDING"),
    ("BK0018", "1u1u02", "l1l13S", "l0l0oh", date(2026, 9, 7), date(2026, 9, 11), "ACCEPTED"),
    ("BK0019", "1u1u05", "L3L3oo", "l0l0oh", date(2026, 8, 3), date(2026, 8, 5), "REJECTED"),
    ("BK0020", "1u1u16", "La1aN1", "l1l13S", date(2026, 7, 13), date(2026, 7, 16), "CANCELLED"),
    # Gifts, so no dates: a single-use booking carries none. Left PENDING on
    # purpose — accepting one turns the thing INACTIVE in the real flow, and a
    # seeded ACCEPTED row would contradict the ACTIVE status seeded beside it.
    ("BK0021", "L3L304", "1u1ucs", "L3L3oo", None, None, "PENDING"),
    ("BK0022", "L3L311", "l1l13S", "l0l0oh", None, None, "PENDING"),
]

# ThingTransfer chain for the community workshop — (thing_code, from_code,
# to_code, lent_date, returned_date, booking_code). Lili's rows above keep the
# five-element shape: hers are manual transfers with no booking behind them.
#
# Three tools are still out (a null returned_date renders as "currently with X"),
# and the loans do NOT all start from the collection's owner — Lolo, Lele, Lili
# and Lala each lend their own. That is the shape a COMMUNITY group has and a
# PROPRIETARY one cannot produce.
COMMUNITY_TRANSFERS = [
    ("1u1u19", "1u1ucs", "L3L3oo", date(2026, 7, 1), date(2026, 7, 3), "BK0001"),
    ("1u1u19", "1u1ucs", "l0l0oh", date(2026, 7, 20), date(2026, 7, 23), "BK0002"),
    ("1u1u19", "1u1ucs", "La1aN1", date(2026, 8, 10), date(2026, 8, 14), "BK0003"),
    ("1u1u20", "l0l0oh", "1u1ucs", date(2026, 7, 6), date(2026, 7, 10), "BK0004"),
    ("1u1u18", "1u1ucs", "La1aN1", date(2026, 6, 16), date(2026, 6, 18), "BK0005"),
    ("1u1u18", "1u1ucs", "l1l13S", date(2026, 8, 24), None, "BK0006"),
    ("1u1u17", "1u1ucs", "l0l0oh", date(2026, 6, 23), date(2026, 6, 26), "BK0007"),
    ("1u1u17", "1u1ucs", "L3L3oo", date(2026, 7, 28), date(2026, 7, 30), "BK0008"),
    ("1u1u12", "1u1ucs", "l1l13S", date(2026, 8, 4), date(2026, 8, 7), "BK0009"),
    ("1u1u06", "L3L3oo", "l0l0oh", date(2026, 7, 14), date(2026, 7, 17), "BK0010"),
    ("1u1u05", "L3L3oo", "La1aN1", date(2026, 7, 7), date(2026, 7, 8), "BK0011"),
    ("1u1u09", "l1l13S", "L3L3oo", date(2026, 6, 9), date(2026, 6, 12), "BK0012"),
    ("1u1u01", "l1l13S", "l0l0oh", date(2026, 7, 21), date(2026, 7, 23), "BK0013"),
    ("1u1u14", "La1aN1", "l0l0oh", date(2026, 8, 25), None, "BK0014"),
    ("1u1u13", "l0l0oh", "La1aN1", date(2026, 8, 21), None, "BK0015"),
]

# Invitations still waiting on the guest — the state `Collection.invites` cannot
# hold, because that list IS membership: being in it means you already accepted.
# A pending invitation is a COLLECTION_INVITE RSVP, and the owner sees it as
# `pending_invites` (CollectionSerializer.get_pending_invites).
#
# **These expire.** COLLECTION_INVITE_EXPIRY_HOURS defaults to 720 (30 days) and
# `cleanup_rsvps` runs daily, so a demo left un-reseeded for a month loses them
# and Lala's pending list quietly empties. `days_ago` is subtracted from seed
# time rather than being a fixed date, so every re-seed restarts the clock and
# the three arrive staggered instead of all bearing the same timestamp.
#
# Nobody here may also sit in the collection's `invites`: accepted and pending
# are mutually exclusive, and a row in both would render the same person twice.
#
# (code, collection_code, user_code, days_ago)
PENDING_INVITATIONS = [
    ("INV001", "La1aC1", "l1l13S", 2),
    ("INV002", "La1aC1", "l0l0oh", 5),
    ("INV003", "La1aC1", "1u1ucs", 9),
]


# The pickup points of the demo network (`NetworkPoint`): one per dinamizador, each
# answering for an entity that does not exist (the names and streets are invented).
# Structure only; the hours of each point and the conditions it writes (deposit, request
# note, email note) are text, in the per-language files. Lolo sets no entity so the
# network shows him by his own name; he sets no days either, so the network's apply.
NETWORK_POINTS = [
    {
        "code": "N3tP01",
        "collection_code": "N3t0C1",
        "user_code": "1u1ucs",
        "entity_name": "Cooperativa Brúixola Menuda",
        "address": "Carrer del Rellotge Aturat 7",
        "contact": "",
        "weekdays": [1, 3],
        "closed_dates": ["2026-12-24", "2026-12-31"],
    },
    {
        "code": "N3tP02",
        "collection_code": "N3t0C1",
        "user_code": "L3L3oo",
        "entity_name": "Associació del Passatge dels Gats Sords",
        "address": "Passatge dels Gats Sords 3",
        "contact": "www.gatssords.example",
        "weekdays": [5],
        "closed_dates": ["2026-12-26", "2027-01-02"],
    },
    {
        "code": "N3tP03",
        "collection_code": "N3t0C1",
        "user_code": "l0l0oh",
        "entity_name": "",
        "address": "Plaça de l'Arbre Fosc 2",
        "contact": "",
        "weekdays": [],
        "closed_dates": [],
    },
]
