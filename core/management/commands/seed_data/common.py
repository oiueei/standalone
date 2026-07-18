"""
Structural demo-data skeleton shared across all language variants.

Only fields that DON'T change between languages live here (codes, types,
ownership, relationships, flags, prices, image ids, tags, …). The translatable
text for each entity lives in the per-locale modules (en.py, es.py) and is
merged onto this skeleton by `seed_demo.load_seed_data`. Adding a language means
translating text only — never re-declaring structure (R17).

Image ids (photo/thumbnail/gallery) are stored BARE here; `seed_demo` prefixes
them with ``SEED_IMAGE_FOLDER`` (oiueei/seed/) at seed time — that's the Cloudinary
folder the demo fixtures actually live in, kept apart from real user uploads.
"""

import json
from datetime import date


def _localized_tag(**texts):
    """A tag label carrying one text per language (O6).

    The stored value is the serialized ``{lang: text}`` map. Things reference
    their collection's vocabulary **by raw string**, so each label is defined
    once as a constant below and reused byte-identically everywhere it appears.
    A label that reads the same in every language stays a plain string instead.
    """
    return json.dumps(texts, ensure_ascii=False)


# Lili's lending library vocabulary.
TAG_COCINA = _localized_tag(es="Cocina", ca="Cuina", en="Kitchen")
TAG_JARDIN = _localized_tag(es="Jardín", ca="Jardí", en="Garden")
TAG_BRICOLAJE = _localized_tag(es="Bricolaje", ca="Bricolatge", en="DIY")
TAG_CRIANZA = _localized_tag(es="Crianza", ca="Criança", en="Parenting")
TAG_HOGAR = _localized_tag(es="Hogar", ca="Llar", en="Home")
TAG_LIMPIEZA = _localized_tag(es="Limpieza", ca="Neteja", en="Cleaning")
TAG_DEPORTE = _localized_tag(es="Deporte", ca="Esport", en="Sports")
TAG_OCIO = _localized_tag(es="Ocio", ca="Lleure", en="Leisure")
TAG_ELECTRONICA = _localized_tag(es="Electrónica", ca="Electrònica", en="Electronics")

# Lele's circuit-swap vocabulary. "shields" is the same jargon everywhere → plain.
TAG_SENSORES = _localized_tag(es="sensores", ca="sensors", en="sensors")
TAG_PLACAS = _localized_tag(es="placas", ca="plaques", en="boards")
TAG_SHIELDS = "shields"
TAG_MODULOS = _localized_tag(es="módulos", ca="mòduls", en="modules")

USERS = [
    {
        "code": "La1aN1",
        "email": "lala@mail.com",
        "name": "Lala",
        "theeeme_id": "BUU331",
        "photo": "La1aPH",
    },
    {
        "code": "L3L3oo",
        "email": "lele@mail.com",
        "name": "Lele",
        "theeeme_id": "K0P4R1",
        "photo": "L3L3PH",
    },
    {
        "code": "l1l13S",
        "email": "lili@mail.com",
        "name": "Lili",
        "theeeme_id": "BUU331",
        "photo": "l1l1PH",
    },
    {
        "code": "l0l0oh",
        "email": "lolo@mail.com",
        "name": "Lolo",
        "theeeme_id": "BUU331",
        "photo": "l0l0PH",
    },
    {
        "code": "1u1ucs",
        "email": "lulu@mail.com",
        "name": "Lulu",
        "theeeme_id": "BUU331",
        "photo": "1u1uPH",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "owner_code": "La1aN1",
        "visibility": "PRIVATE",
        "invites": ["L3L3oo"],
        "is_onboarding": True,
        "allowed_thing_types": ["SELL_THING"],
        "thumbnail": "La1aC1",
    },
    {
        "code": "l0l0C1",
        "owner_code": "l0l0oh",
        "visibility": "PUBLIC",
        "invites": ["La1aN1", "l1l13S", "L3L3oo"],
        "is_onboarding": True,
        "allowed_thing_types": ["GIFT_THING"],
        "thumbnail": "L3L3C2",
    },
    {
        "code": "l1l1C1",
        "owner_code": "l1l13S",
        "visibility": "PUBLIC",
        "invites": ["La1aN1"],
        "is_onboarding": True,
        "allowed_thing_types": ["RENT_THING"],
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
    },
    {
        "code": "L3L3C1",
        "owner_code": "L3L3oo",
        "visibility": "PUBLIC",
        "mode": "COMMUNITY",
        "is_swap": True,
        "invites": ["La1aN1", "l1l13S", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "allowed_thing_types": ["SWAP_THING"],
        "tags": [TAG_SENSORES, TAG_PLACAS, TAG_SHIELDS, TAG_MODULOS],
        "thumbnail": "l1l1C2",
    },
    {
        "code": "1u1uC1",
        "owner_code": "1u1ucs",
        "visibility": "PUBLIC",
        "mode": "COMMUNITY",
        "is_share": True,
        "newsletter_enabled": True,
        "digest_frequency": "WEEKLY",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh"],
        "is_onboarding": True,
        "allowed_thing_types": ["SHARE_THING"],
        "thumbnail": "1u1uC1",
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
        "tags": [TAG_ELECTRONICA],
    },
    {
        "code": "l1l108",
        "type": "RENT_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "thumbnail": "l1l108",
        "fee": "3.00",
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
        "code": "1u1u01",
        "type": "SHARE_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u01",
        "condition": "NEW",
    },
    {
        "code": "1u1u02",
        "type": "SHARE_THING",
        "owner_code": "L3L3oo",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u02",
        "condition": "GOOD",
    },
    {
        "code": "1u1u03",
        "type": "SHARE_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u03",
        "condition": "NEW",
    },
    {
        "code": "1u1u04",
        "type": "SHARE_THING",
        "owner_code": "l0l0oh",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u04",
        "condition": "USED",
    },
    {
        "code": "1u1u05",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uC1"],
        "thumbnail": "1u1u05",
        "condition": "FAIR",
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
        "code": "La1a00",
        "type": "WISH_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
    },
    {
        "code": "L3L301",
        "type": "SWAP_THING",
        "owner_code": "La1aN1",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L301",
        "tags": [TAG_SHIELDS],
    },
    {
        "code": "L3L302",
        "type": "SWAP_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L302",
        "tags": [TAG_SENSORES],
    },
    {
        "code": "L3L303",
        "type": "SWAP_THING",
        "owner_code": "l0l0oh",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L303",
        "tags": [TAG_MODULOS],
    },
    {
        "code": "L3L304",
        "type": "SWAP_THING",
        "owner_code": "1u1ucs",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L304",
        "tags": [TAG_SHIELDS],
    },
    {
        "code": "L3L305",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L305",
        "tags": [TAG_PLACAS],
    },
    {
        "code": "L3L306",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L306",
        "tags": [TAG_SENSORES],
    },
    {
        "code": "L3L307",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L307",
        "tags": [TAG_SENSORES],
    },
    {
        "code": "L3L308",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["L3L3C1"],
        "thumbnail": "L3L308",
        "tags": [TAG_SENSORES],
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

WISH_RESPONSES = [
    {
        "wish_code": "La1a00",
        "responder_code": "L3L3oo",
        "kind": "KNOW_WHERE",
    },
]

# ThingTransfer chain — (thing_code, from_code, to_code, lent_date, returned_date)
TRANSFERS = [
    # Lulu's share collection — single transfers
    ("1u1u01", "1u1ucs", "La1aN1", date(2026, 3, 1), None),
    ("1u1u02", "1u1ucs", "L3L3oo", date(2026, 3, 15), None),
    ("1u1u03", "1u1ucs", "l1l13S", date(2026, 4, 1), None),
    # lltl14 — full chain ending at Lolo
    ("1u1u04", "1u1ucs", "l0l0oh", date(2026, 1, 10), date(2026, 1, 31)),
    ("1u1u04", "l0l0oh", "La1aN1", date(2026, 2, 1), date(2026, 2, 28)),
    ("1u1u04", "La1aN1", "L3L3oo", date(2026, 3, 1), date(2026, 3, 31)),
    ("1u1u04", "L3L3oo", "l1l13S", date(2026, 4, 1), date(2026, 4, 15)),
    ("1u1u04", "l1l13S", "l0l0oh", date(2026, 4, 16), None),
    # Lili's circuit swap — historical swaps
    ("L3L301", "l1l13S", "La1aN1", date(2026, 3, 20), None),
    ("L3L302", "l1l13S", "L3L3oo", date(2026, 3, 25), None),
    ("L3L305", "l0l0oh", "l1l13S", date(2026, 4, 5), None),
    ("L3L307", "l0l0oh", "L3L3oo", date(2026, 1, 20), None),
    ("L3L307", "L3L3oo", "l1l13S", date(2026, 3, 1), None),
]
