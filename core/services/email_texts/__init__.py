"""Per-language text catalogues for the outbound emails.

Which language a given email speaks is decided by a three-level hierarchy,
weakest to strongest: the **deployment default** (``EMAIL_LANGUAGE``, env var,
default ``en`` — the open-source standalone stays English, www.oiueei.com sets
``es``), then the **collection's** language (the owner's choice for their group),
then the **recipient's own** preference. ``core/services/email_service.py``
resolves it per recipient (``resolve_email_language``) and passes the result down
as ``lang`` — so one digest to a bilingual group leaves in two languages.

This mirrors the ``seed_data/{lang}.py`` pattern — one flat ``TEXTS`` dict per
module, same keys everywhere; ``en`` is the reference catalogue and the fallback
for an unknown language or a missing key (guarded by the parity test in
``test_email_language.py``).

To add a language: copy ``en.py`` → ``{lang}.py`` and translate only the values
(keep the keys and the ``{placeholders}``), then add it to ``Language`` in
``core/models/language.py`` so owners and users can pick it.
"""

from importlib import import_module

from django.conf import settings

from core.services.email_texts import en as _en

_CATALOGUES = {"en": _en.TEXTS}


def _catalogue(lang):
    if lang not in _CATALOGUES:
        try:
            _CATALOGUES[lang] = import_module(f"{__name__}.{lang}").TEXTS
        except ImportError:
            _CATALOGUES[lang] = _en.TEXTS
    return _CATALOGUES[lang]


def _default_lang():
    return getattr(settings, "EMAIL_LANGUAGE", "en")


def T(key, lang=None):
    """The text for ``key`` in ``lang``, or the deployment's language (en fallback).

    ``lang`` is what the language hierarchy resolved for *this recipient*; senders
    pass it to every ``T()`` of the email they are composing. Without it, the
    deployment default is read from ``settings.EMAIL_LANGUAGE`` on every call, so
    ``override_settings`` works in tests and a config change needs no process-wide
    cache reset beyond the restart Heroku already does.
    """
    return _catalogue(lang or _default_lang()).get(key) or _en.TEXTS[key]


def viral_lines(lang=None):
    """The ``VIRAL_LINES`` growth blurbs in ``lang`` (or the deployment's language).

    Mirrors ``T``: falls back to the English list for an unknown language or a
    catalogue without one.
    """
    lang = lang or _default_lang()
    if lang == "en":
        return _en.VIRAL_LINES
    try:
        return import_module(f"{__name__}.{lang}").VIRAL_LINES
    except (ImportError, AttributeError):
        return _en.VIRAL_LINES
