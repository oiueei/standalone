"""The coded refusals a request can meet, and the promise their codes make.

``core`` has no gettext catalogue, so every refusal the API sends is an English
sentence — and the request page used to show it as-is to a Catalan or Spanish
member. A refusal now also carries a ``code`` (and the ``params`` its sentence
interpolates) that the SPA says in the reader's language, from
``requestErrors.<code>`` in ``frontend/src/i18n/locales``.

A code with no string there silently falls back to English again, which is the
failure this whole change exists to remove — so the last test reads the codes
straight out of the source and fails if one has no translation.
"""

import json
import re
from pathlib import Path

from core.services.booking_service import BookingRequestError
from core.utils import Refusal

ROOT = Path(__file__).resolve().parents[3]
SOURCES = [
    ROOT / "core" / "models" / "collection.py",
    ROOT / "core" / "services" / "booking_service.py",
    ROOT / "core" / "services" / "invitation_service.py",
    ROOT / "core" / "views" / "collections.py",
    ROOT / "core" / "views" / "things.py",
    ROOT / "core" / "views" / "faq.py",
    ROOT / "core" / "views" / "users.py",
    ROOT / "core" / "views" / "report.py",
    ROOT / "core" / "views" / "reservations.py",
    ROOT / "core" / "views" / "auth.py",
    ROOT / "core" / "views" / "booking.py",
    ROOT / "core" / "views" / "_helpers.py",
    ROOT / "core" / "serializers" / "collection.py",
    ROOT / "core" / "serializers" / "booking.py",
]
LOCALES = ROOT / "frontend" / "src" / "i18n" / "locales"


def test_a_refusal_is_still_the_sentence_it_always_was():
    refusal = Refusal("That time has already begun.", "reservation_already_begun")

    assert refusal == "That time has already begun."
    assert isinstance(refusal, str)
    assert refusal.code == "reservation_already_begun"
    assert refusal.params == {}


def test_a_booking_error_raised_on_a_refusal_carries_its_code_and_params():
    exc = BookingRequestError(
        Refusal("Up to 10 days ahead.", "reservation_beyond_horizon", days=10)
    )

    assert exc.as_body() == {
        "error": "Up to 10 days ahead.",
        "code": "reservation_beyond_horizon",
        "params": {"days": 10},
    }


def test_a_plain_message_keeps_the_plain_body():
    assert BookingRequestError("Not a reservation.").as_body() == {"error": "Not a reservation."}


def _codes_in_source():
    codes = set()
    for path in SOURCES:
        text = path.read_text()
        # Refusal("…", "code", …) — the code is the second string literal.
        codes |= set(re.findall(r'Refusal\(\s*(?:f?"[^"]*"\s*)+,\s*"([a-z_]+)"', text))
        # BookingRequestError(…, code="code", …) and the clash's conditional code.
        codes |= set(re.findall(r'code="([a-z_]+)"', text))
        codes |= set(re.findall(r'else "([a-z_]+)"', text))
        # A view's own coded refusal, written as a response body: {"code": "…", …}.
        codes |= set(re.findall(r'"code":\s*"([a-z_]+)"', text))
    return codes


def test_every_code_a_request_can_be_refused_with_is_translated():
    codes = _codes_in_source()
    # The scan itself must be finding things, or this test proves nothing.
    assert {
        "reservation_already_begun",
        "rental_pickup_weekday",
        "time_taken",
        "co_owners_full",
        "no_prices_here",
        "priced_things_remain",
    } <= codes
    for lang in ("en", "es", "ca"):
        table = json.loads((LOCALES / f"{lang}.json").read_text())["requestErrors"]
        # A code whose sentence carries a number is pluralised (`_one`/`_other`).
        missing = sorted(
            code for code in codes if code not in table and f"{code}_other" not in table
        )
        assert not missing, f"{lang}.json requestErrors has no string for: {missing}"


def _refusal_messages():
    """Every ``Refusal`` / ``BookingRequestError`` built in the two rule
    sources, as ``(file, line, the message argument's AST node)``."""
    import ast

    for path in SOURCES:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in {"Refusal", "BookingRequestError"} and node.args:
                yield path.name, node.lineno, node.args[0]


def test_every_refusal_is_built_with_a_sentence():
    """A code tells the SPA which string to show; the message is what an older
    client — and every log line — gets instead, so a refusal built without one
    reaches a member as the word "None". Nothing said it had to be there: the
    mutation sweep of 2026-09-19 blanked message after message and the suite
    stayed green, because the tests had moved to asserting codes.

    Read from the source rather than by calling each rule: a refusal that is
    hard to reach is exactly the one whose message nobody would notice. Only
    literals are judged — a `BookingRequestError(violation)` re-raises a
    sentence some rule already built, and that one is judged where it is.
    """
    import ast

    empty = []
    for filename, line, arg in _refusal_messages():
        if not isinstance(arg, ast.Constant):  # an f-string or a variable
            continue
        if not isinstance(arg.value, str) or not arg.value.strip():
            empty.append(f"{filename}:{line}")
    assert not empty, f"refusals built without a sentence: {empty}"


def test_the_refusal_message_scan_is_finding_things():
    """The guard above proves nothing if the walk comes back empty, or if
    every refusal it found turned out to be one it skips."""
    import ast

    found = list(_refusal_messages())
    assert len(found) > 20
    literals = [arg for _, _, arg in found if isinstance(arg, ast.Constant)]
    assert len(literals) > 15
