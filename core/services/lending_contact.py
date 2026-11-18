"""The contact details a library may ask for when it lends, sealed at rest.

A library can ask whoever borrows for a full name, an address, a phone and an identity
document (`Collection.lending_asks_contact`). They are kept in **one** column of the
booking (`BookingPeriod.lending_contact`) as an encrypted token, never as readable text,
so a database dump, a backup or a stray query shows nothing of them.

The key is derived from `SECRET_KEY` (HKDF-SHA256, with an `info` of its own, so it is not
the key anything else is signed with). There is no environment variable of its own to look
after. The price is that **rotating `SECRET_KEY` makes the details still kept unreadable**:
`unseal` answers `None`, the page shows nothing and nothing breaks. That is accepted: they
live 90 days at most (they go when the loan is marked returned, when the request is refused,
cancelled or expires, and 90 days after the return date at the latest).

`seal` and `unseal` are the only two doors; nothing else in the code reads or writes the
token. `unseal` never raises: a token that cannot be opened (tampered, from another key,
not a token at all, not a mapping inside) is `None`.
"""

import base64
import json

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

_INFO = b"oiueei-lending-contact"


def _fernet():
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(
        settings.SECRET_KEY.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def seal(data):
    """The details as an encrypted, URL-safe token (text, for a `TextField`)."""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    return _fernet().encrypt(payload).decode()


def unseal(token):
    """The details a token holds, or `None` for an empty one or one that cannot be opened."""
    if not token:
        return None
    try:
        opened = json.loads(_fernet().decrypt(str(token).encode()))
    except (InvalidToken, ValueError, TypeError):
        return None
    return opened if isinstance(opened, dict) else None
