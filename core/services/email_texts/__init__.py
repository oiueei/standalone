"""Per-language text catalogues for the outbound emails.

A deployment speaks ONE language in email, picked by the ``EMAIL_LANGUAGE``
setting (env var, default ``en``): the open-source standalone stays English,
www.oiueei.com sets ``EMAIL_LANGUAGE=es``. This mirrors the ``seed_data/{lang}.py``
pattern — one flat ``TEXTS`` dict per module, same keys everywhere; ``en`` is the
reference catalogue and the fallback for an unknown language or a missing key
(guarded by the parity test in ``test_email_language.py``).

To add a language: copy ``en.py`` → ``{lang}.py`` and translate only the values
(keep the keys and the ``{placeholders}``), then set ``EMAIL_LANGUAGE={lang}``.
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


def T(key):
    """The text for ``key`` in the deployment's email language (en fallback).

    Reads ``settings.EMAIL_LANGUAGE`` on every call, so ``override_settings``
    works in tests and a config change needs no process-wide cache reset beyond
    the restart Heroku already does.
    """
    lang = getattr(settings, "EMAIL_LANGUAGE", "en")
    return _catalogue(lang).get(key) or _en.TEXTS[key]


def viral_lines():
    """The ``VIRAL_LINES`` growth blurbs in the deployment's email language.

    Mirrors ``T``: reads ``settings.EMAIL_LANGUAGE`` per call and falls back to
    the English list for an unknown language or a catalogue without one.
    """
    lang = getattr(settings, "EMAIL_LANGUAGE", "en")
    if lang == "en":
        return _en.VIRAL_LINES
    try:
        return import_module(f"{__name__}.{lang}").VIRAL_LINES
    except (ImportError, AttributeError):
        return _en.VIRAL_LINES
