"""The languages OIUEEI speaks, shared by every model that stores a preference.

One list, so ``User.language`` and ``Collection.language`` can never drift from
each other — or from the email catalogues in ``core/services/email_texts/`` and
the UI locales in ``frontend/src/i18n/locales/``.

Blank (``""``) is always a valid stored value and means **inherit**: the email
language hierarchy is deployment default → collection → recipient, weakest to
strongest (see ``core/services/email_service.py::resolve_email_language``).
"""

from django.db import models


class Language(models.TextChoices):
    ES = "es", "Español"
    CA = "ca", "Català"
    EN = "en", "English"
