"""Contact details kept sealed at rest: a library's borrower details and a reservation's phone.

Two kinds of personal contact data are stored as an encrypted token, never as readable
text, so a database dump, a backup or a stray query shows nothing of them:

* the details a library may ask a borrower for (`Collection.lending_asks_contact`): a full
  name, an address, a phone and an identity document, in **one** column
  (`BookingPeriod.lending_contact`) — `seal` / `unseal`;
* the optional phone a shed may ask for when someone reserves (`BookingPeriod.contact_phone`)
  — `seal_phone` / `unseal_phone`. A shed takes reservations up to a year ahead, so the
  number can wait months in the database and in its copies.

The keys are derived from `SECRET_KEY` (HKDF-SHA256, each with an `info` of its own, so
neither is the key anything else is signed with, and the two never open each other's
tokens). There is no environment variable of its own to look after. The price is that
**rotating `SECRET_KEY` makes the data still kept unreadable**: `unseal` answers `None` and
`unseal_phone` `""`, the page shows nothing and nothing breaks. That is accepted: a loan's
details live 90 days at most (they go when the loan is marked returned, when the request is
refused, cancelled or expires, and 90 days after the return date at the latest), and a
phone goes the day after the booking.

`seal` / `unseal` and `seal_phone` / `unseal_phone` are the only doors; nothing else in the
code reads or writes a token. None of the `unseal`s ever raises: a token that cannot be
opened (tampered, from another key, not a token at all, not a mapping inside) is `None`
(the details) or `""` (the phone).

**Transition exception.** `unseal_phone` also reads a phone **left in plain text**: a value
that is not a token but looks like a phone (`CONTACT_PHONE_PATTERN`, at least
`CONTACT_PHONE_MIN_DIGITS` digits) is returned as it is. Those are the rows the previous
release's dynos write while a release phase runs, before the migration's pass and the
nightly purge seal them. A token never looks like a phone (it is base64 letters), so the
two cannot be mistaken for each other.
"""

import base64
import json
import re

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

LENDING_INFO = b"oiueei-lending-contact"
PHONE_INFO = b"oiueei-reservation-phone"

# A contact phone: digits and the punctuation people type around them, at least six
# digits, at most the 32 characters the request accepts.
CONTACT_PHONE_PATTERN = re.compile(r"^[0-9 +().-]{6,32}$")
CONTACT_PHONE_MIN_DIGITS = 6


def _fernet(info):
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(
        settings.SECRET_KEY.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def seal(data):
    """The details as an encrypted, URL-safe token (text, for a `TextField`)."""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    return _fernet(LENDING_INFO).encrypt(payload).decode()


def unseal(token):
    """The details a token holds, or `None` for an empty one or one that cannot be opened."""
    if not token:
        return None
    try:
        opened = json.loads(_fernet(LENDING_INFO).decrypt(str(token).encode()))
    except (InvalidToken, ValueError, TypeError):
        return None
    return opened if isinstance(opened, dict) else None


def looks_like_phone(value):
    """Whether a text is a phone as the request accepts it (the plain-text shape)."""
    value = str(value or "")
    digits = sum(ch.isdigit() for ch in value)
    return bool(CONTACT_PHONE_PATTERN.match(value)) and digits >= CONTACT_PHONE_MIN_DIGITS


def seal_phone(text):
    """A reservation's phone as an encrypted token, or `""` when there is none."""
    text = (text or "").strip()
    if not text:
        return ""
    return _fernet(PHONE_INFO).encrypt(text.encode()).decode()


def is_sealed_phone(value):
    """Whether the value is a token this key opens (so it is not plain text, nor foreign)."""
    if not value:
        return False
    try:
        _fernet(PHONE_INFO).decrypt(str(value).encode())
    except (InvalidToken, ValueError, TypeError):
        return False
    return True


def unseal_phone(value):
    """The phone a value holds, or `""` for an empty one or one that cannot be opened.

    A phone still in plain text (see the module's transition exception) is returned as is.
    """
    if not value:
        return ""
    try:
        return _fernet(PHONE_INFO).decrypt(str(value).encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return str(value) if looks_like_phone(value) else ""
