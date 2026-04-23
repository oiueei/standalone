"""
Non-translatable demo data shared across all language variants.

EVENT_ATTENDANCES and TRANSFERS have no user-facing text, so they live here
instead of being duplicated in each language file.
"""

from datetime import date, timedelta, timezone

TZ_PLUS2 = timezone(timedelta(hours=2))

# Event attendees: (thing_code, user_code)
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
