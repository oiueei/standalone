"""
Centralized email service for OIUEEI.

All email composition and sending is handled here to avoid
duplicating email logic across views.

Each email belongs to one of three categories (see `_should_send`):
- CATEGORY_MANDATORY: magic links, invitations, revocations — always sent.
- CATEGORY_ACTIVITY: user↔user events (bookings, FAQs, reminders, broadcast)
  — opt-out via User.notify_activity.
- CATEGORY_NEWS: digests — opt-out via User.notify_news.

Cat. 2 and Cat. 3 emails include a footer with a tokenised link to /me/notifications
that lets recipients change preferences without logging in.

HTML bodies are rendered from the autoescaping ``email/layout.html`` template via
small block builders (``_para``/``_strong``/``_field``/``_list``/``_links``/
``_heading``/``_cta``/``_ctas``), so user-supplied values are escaped by the template
engine — no manual ``escape()`` in the body composition. Plain-text bodies (no
XSS surface) stay as plain strings.

Visual design: every message is a white, rounded card
(``EMAIL_BODY_SIZE``/``EMAIL_HEADER_SIZE``/``EMAIL_FOOTER_SIZE``, the card
itself in ``layout.html``). Every email names one **parent** — the thing it is
about — as an ``<h1>``: a thing's own headline for thing-scoped mail, a
collection's for collection-scoped mail, the FAQ question itself for the three
FAQ emails, or "OIUEEI" for the few with no natural parent. Every CTA is a
button with its own link spelled out below it as plain text (``_cta``/
``_ctas`` — the earlier, lighter ``_button`` with no fallback link is gone).
"""

import functools
import logging
import random
import re
import smtplib
from datetime import date, datetime, timedelta
from email.mime.image import MIMEImage
from html import unescape as html_unescape
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe

from core.models.braaanding import braaanding
from core.services.email_texts import T, viral_lines
from core.services.palette_contrast import AA_NORMAL, WHITE, contrast_ratio
from core.utils import parse_localized, redact_email, resolve_localized

logger = logging.getLogger(__name__)

CATEGORY_MANDATORY = "mandatory"
CATEGORY_ACTIVITY = "activity"
CATEGORY_NEWS = "news"


_PREFS_TOKEN_SALT = "notifications-prefs"
# ~1 year, and deliberately long — this is the shortest TTL of any bearer
# credential we hand out, judged the other way round from the rest.
#
# It looks like a token that should expire fast: it sits in a URL path, in the
# footer of every Cat. 2 / Cat. 3 email, and it authenticates without a login.
# But weigh the two sides. Stolen, it can flip exactly two booleans — turn news
# on, or turn activity off so someone misses a hold request. A nuisance, not a
# breach; there is nothing to read and nothing to spend. Expired, it breaks the
# link somebody clicks *to stop receiving email from us* — this is the
# unsubscribe link, whatever the page calls it. A dead one turns withdrawing
# consent into "log in, find the profile editor, scroll to preferences", which
# is friction on a right, in a product that ships an RGPD notice.
#
# So the long TTL is the user-protective choice here, not the lax one. Rotating
# SECRET_KEY still invalidates every outstanding token at once, which is the
# revocation path that matters. Reviewed and kept.
_PREFS_TOKEN_MAX_AGE = 60 * 60 * 24 * 365  # ~1 year — see above before shortening


def make_notifications_token(user):
    """Return a signed, expiring token for the email-footer preferences link.

    A ``TimestampSigner`` signature over the user's code (salt
    ``notifications-prefs``) rather than a stored column: it carries a ~1-year
    TTL (deliberately — see ``_PREFS_TOKEN_MAX_AGE``) and needs no DB lookup or
    per-user secret to mint. Its blast radius is limited to toggling the two
    notification booleans (see NotificationsByTokenView).
    """
    return TimestampSigner(salt=_PREFS_TOKEN_SALT).sign(user.code)


def verify_notifications_token(token):
    """Return the user_code for a valid, unexpired token, else None."""
    from core.models import User

    try:
        user_code = TimestampSigner(salt=_PREFS_TOKEN_SALT).unsign(
            token, max_age=_PREFS_TOKEN_MAX_AGE
        )
    except (BadSignature, SignatureExpired):
        return None
    return user_code if User.objects.filter(code=user_code).exists() else None


_DIGEST_MUTE_SALT = "digest-mute"


def make_digest_mute_token(user, collection):
    """Signed token for the digest footer's one-click 'stop these' link.

    Carries ``{user_code}:{collection_code}`` under its own salt, so it cannot be
    swapped for a preferences token and vice versa. Its blast radius is one row
    in one M2M: at worst someone silences a digest for a member who can turn it
    straight back on from the collection page.

    Same long TTL as the preferences token, for the same reason (see
    ``_PREFS_TOKEN_MAX_AGE``): this is an unsubscribe link, and an expired one
    turns "stop emailing me" into a support request.
    """
    return TimestampSigner(salt=_DIGEST_MUTE_SALT).sign(f"{user.code}:{collection.code}")


def verify_digest_mute_token(token):
    """Return ``(user_code, collection_code)`` for a valid token, else ``None``."""
    try:
        payload = TimestampSigner(salt=_DIGEST_MUTE_SALT).unsign(
            token, max_age=_PREFS_TOKEN_MAX_AGE
        )
    except (BadSignature, SignatureExpired):
        return None
    user_code, _, collection_code = payload.partition(":")
    if not user_code or not collection_code:
        return None
    return user_code, collection_code


# Sentinel for "no prefetched value" — distinct from a looked-up None (the
# recipient has no User row). Lets the multi-recipient senders pass a resolved
# user (or a known-absent None) so _send doesn't re-query _lookup_user per
# recipient.
_UNSET = object()


def _lookup_user(email):
    from django.db.models import Exists, OuterRef, Q

    from core.models import Collection, User

    return (
        User.objects.annotate(
            _curates_collection=Exists(
                Collection.objects.filter(Q(owner=OuterRef("pk")) | Q(co_owners=OuterRef("pk")))
            )
        )
        .filter(email=email)
        .only("code", "language", "notify_activity", "notify_news")
        .first()
    )


def _lookup_users(emails):
    """Bulk-resolve users for a recipient list — one query, not N.

    Returns ``{email: user}`` for the emails that match a User; addresses with no
    User (not-yet-registered invitees) are simply absent, so callers pass
    ``users.get(email)`` (None) and ``_send`` treats them as opted-in non-users
    without firing another lookup.
    """
    from django.db.models import Exists, OuterRef, Q

    from core.models import Collection, User

    return {
        u.email: u
        for u in User.objects.annotate(
            _curates_collection=Exists(
                Collection.objects.filter(Q(owner=OuterRef("pk")) | Q(co_owners=OuterRef("pk")))
            )
        )
        .filter(email__in=list(emails))
        .only("code", "email", "language", "notify_activity", "notify_news")
    }


def resolve_email_language(user=None, collection=None):
    """Which language an email to this recipient speaks.

    Weakest to strongest: the **deployment default** (``EMAIL_LANGUAGE``), the
    **collection's** language (the owner's choice for their group), the
    **recipient's own** preference. Blank means "inherit", so a level only speaks
    when it was actually set. Thing-scoped 1:1 emails (bookings, FAQs, reminders)
    pass no collection — there is no group to speak for — so they are
    the recipient's preference or the deployment default.
    """
    return (
        (getattr(user, "language", "") or "")
        or (getattr(collection, "language", "") or "")
        or getattr(settings, "EMAIL_LANGUAGE", "en")
    )


def _texts(lang):
    """``T`` bound to one language.

    Senders shadow the module-level ``T`` with it (``T = _texts(lang)``), so every
    ``T("key")`` in the body below speaks the recipient's language without
    threading the argument through each call.
    """
    return functools.partial(T, lang=lang)


def _local(lang):
    """``resolve_localized`` bound to one language.

    Senders bind it as ``L`` next to ``T`` and pass **every owner-written value**
    through it — a headline may carry one text per language (inline JSON, see
    ``core.utils.parse_localized``), and the recipient must read theirs rather than
    the raw map. Plain headlines, which is nearly all of them, come back untouched.
    """
    return functools.partial(resolve_localized, lang=lang)


def _recipient(email, collection=None):
    """Resolve the recipient User once, plus the language their email speaks.

    The User is then handed to ``_send`` so the preference check, the footer link
    and the viral-line gate don't look it up all over again.
    """
    user = _lookup_user(email)
    return user, resolve_email_language(user=user, collection=collection)


def _member_name(name, lang, *, inline=False):
    """A person's name as somebody else may be told it — never their address.

    ``User.display_name`` falls back to the email when ``name`` is empty, which is
    right where the reader is the person themselves or somebody who already holds
    the address (a collection owner sees their members' emails; a thing owner sees
    a requester's, via ``BookingPeriodSerializer.requester_email``). It is wrong
    everywhere else, and "everywhere else" is most of this module: a co-member, an
    invitee, a stranger being invited for the first time.

    The fallback is not an edge case — ``name`` is empty for **every** account
    created by ``get_or_create(email=email)``, which is everyone who joined by
    magic link or invitation and never filled in their profile. So a group owner
    who never set a name broadcast their address to the whole group.

    Where the name sits on a line of its own, dropping the line is better still
    and the callers do exactly that (``proposer_name`` in
    ``send_collection_invite_email``). This is for the rest: a name interpolated
    mid-sentence, where the sentence needs *a* subject and the honest one is a
    noun rather than an address. It mirrors the frontend's ``common.aMember``,
    which ``ThingLinkbox`` has always used for the same reason.

    ``inline=True`` is for a name that falls in the middle of a sentence or in a
    list ("Message from a member", "Lala, a member and Lolo"): the stand-in is then
    written in lower case. The default is for a name that opens its sentence.
    """
    return name or _texts(lang)("a_member_inline" if inline else "a_member")


def _template(T, key, lang, *, nameless, field):
    """The template ``key``, ready to take the stand-in for a person with no name.

    Catalan writes "d'un membre", not "de un membre": for a nameless person the
    template's own "de {field}" becomes "d'{field}" before anything is put in it,
    so what the user wrote (a message, a thing's headline) is never touched.
    """
    template = T(key)
    if nameless and lang == "ca":
        template = template.replace(f"de {{{field}}}", f"d'{{{field}}}")
    return template


def _muted_codes(collection):
    """User codes that have silenced this collection's digest (empty set if none).

    Only consulted for CATEGORY_NEWS: the mute is per group and about *this
    group's news*, so it must not reach the activity emails — a member who
    silences a chatty collection still gets told when their own hold is
    confirmed there.
    """
    if collection is None:
        return set()
    # Memoised on the instance: `_send_per_language` calls `_send` (and so
    # `_should_send`) once per recipient, and without this the belt-and-braces
    # re-check would cost one query per member of the group — the N+1 that a
    # digest to a 200-member collection would notice.
    cached = getattr(collection, "_digest_muted_codes", None)
    if cached is None:
        cached = set(collection.digest_muted.values_list("code", flat=True))
        collection._digest_muted_codes = cached
    return cached


def _should_send(email, category, user=_UNSET, collection=None):
    """True unless the recipient has opted out of this category.

    ``user`` may be prefetched by a multi-recipient sender (a User, or None once
    it is known the recipient has no User row); leave it as ``_UNSET`` for the
    single-recipient path, which looks the user up here.

    ``collection`` narrows CATEGORY_NEWS by the per-collection mute. The check
    lives here, beside the global one, so it holds for any future single-
    recipient news sender rather than only for the bulk path digests use today.
    """
    if category == CATEGORY_MANDATORY:
        return True
    if user is _UNSET:
        user = _lookup_user(email)
    if not user:
        return True
    if category == CATEGORY_ACTIVITY:
        return user.notify_activity
    if category == CATEGORY_NEWS:
        return user.notify_news and user.code not in _muted_codes(collection)
    return True


def _filter_recipients(emails, category, collection=None):
    """Filter a bulk recipient list, removing users who have opted out.

    Two independent opt-outs for news: the global ``notify_news`` switch and,
    when the mail belongs to a collection, that collection's own mute list.
    """
    if category == CATEGORY_MANDATORY:
        return list(emails)
    from core.models import User

    field = "notify_activity" if category == CATEGORY_ACTIVITY else "notify_news"
    opted_out = set(
        User.objects.filter(email__in=list(emails), **{field: False}).values_list(
            "email", flat=True
        )
    )
    if category == CATEGORY_NEWS and collection is not None:
        muted = set(
            collection.digest_muted.filter(email__in=list(emails)).values_list("email", flat=True)
        )
        opted_out |= muted
    return [e for e in emails if e not in opted_out]


def _send_per_language(
    emails, category, compose, collection=None, reply_to=None, extra_footer=None
):
    """Send one bulk email (digest, broadcast) to a list of
    recipients, **each in their own language**.

    A group can be bilingual, so the body can't be composed once up front:
    ``compose(lang)`` builds ``(subject, plain, html)`` and is called once per
    distinct language present among the recipients (not once per recipient — a
    50-member group in one language still composes once). Opt-outs are dropped
    first, and the users are bulk-resolved in a single query so ``_send`` doesn't
    re-look-up anyone.
    """
    recipients = _filter_recipients(emails, category, collection=collection)
    users = _lookup_users(recipients)
    composed = {}
    for email in recipients:
        user = users.get(email)
        lang = resolve_email_language(user=user, collection=collection)
        if lang not in composed:
            composed[lang] = compose(lang)
        subject, plain, html = composed[lang]
        # The card is composed once per language and reused for many
        # recipients, but the footer varies per person (a collection owner
        # gets no viral line; extra_footer — the digest's per-collection mute
        # link — carries a token signed for *this* user). _send appends it,
        # per recipient, via _bottom().
        _send(
            email,
            subject,
            plain,
            html,
            category,
            reply_to=reply_to,
            user=user,
            lang=lang,
            collection=collection,
            extra_footer=extra_footer,
        )


# Three text sizes for a message, replacing the single
# EMAIL_FONT_SIZE an earlier version had: EMAIL_BODY_SIZE for everything that is
# the message's own words — paragraphs, buttons, a CTA's fallback link —
# EMAIL_HEADER_SIZE for the one <h1> "parent" title, EMAIL_FOOTER_SIZE for the
# rule-separated block at the foot (the mark, "manage your preferences", the
# legal link). Set explicitly rather than left to the client, which is what
# let the same message read at a different size in Gmail and in Apple Mail.
EMAIL_BODY_SIZE = "14px"
EMAIL_HEADER_SIZE = "18px"
EMAIL_FOOTER_SIZE = "12px"

# The <h1> for an email with no thing, collection or FAQ question to be its
# parent — the app itself, named the same untranslated way
# every locale names it ("OIUEEI" is not a word to translate). Used with
# ``generic_parent_pitch``, the one-line "what is this" the reader gets right
# under it — added only where the reader may genuinely not know
# (send_magic_link_email's generic branch). It is not added to
# account-deletion, inactivity or operator mail: "OIUEEI" still names them as
# the parent, but a pitch sentence has no place next to "delete my account" or
# in a support ticket the operator already knows the product behind.
GENERIC_PARENT = "OIUEEI"


def _frontend_base_url():
    return settings.MAGIC_LINK_BASE_URL.rsplit("/", 1)[0]


def _notifications_link(email, user=_UNSET):
    if user is _UNSET:
        user = _lookup_user(email)
    base = _frontend_base_url()
    if user:
        return f"{base}/me/notifications/{make_notifications_token(user)}"
    return f"{base}/me/notifications"


@functools.lru_cache(maxsize=None)
def _viral_provider(dotted_path):
    """The deployment's growth-line function, imported once per dotted path.

    Cached on the path, not on the setting, as ``get_creator_policy`` does, so
    ``override_settings`` works in tests and a live deployment never re-imports.
    """
    return import_string(dotted_path)


def _provided_line(user, lang):
    """The growth line the deployment's ``VIRAL_LINE_PROVIDER`` picks, else ``None``.

    The function gets this recipient's ``User`` (``None`` for an address with no
    account) and the language the email is written in, and answers
    ``{"text", "cta", "path"}``. Anything else — ``None``, a line missing a part, a
    ``path`` that is not a path on this site — means no line. A provider that
    raises costs the email its line and nothing more: a deployment's mistake must
    not cost anyone their magic link. Only the setting's path is logged, never the
    recipient.
    """
    path = settings.VIRAL_LINE_PROVIDER
    try:
        line = _viral_provider(path)(user, lang)
    except Exception as exc:  # noqa: BLE001 — a deployment's bug never costs an email.
        logger.warning(
            "VIRAL_LINE_PROVIDER %s failed (%s); sending without a line", path, type(exc).__name__
        )
        return None
    if not isinstance(line, dict):
        return None
    text, cta, target = line.get("text"), line.get("cta"), line.get("path")
    if not (isinstance(text, str) and text and isinstance(cta, str) and cta):
        return None
    # A path on this site: "//host" and "/\host" are how a browser is sent elsewhere.
    if not (
        isinstance(target, str)
        and target.startswith("/")
        and not target.startswith("//")
        and not target.startswith("/\\")
    ):
        return None
    return {"text": text, "cta": cta, "path": target}


def _catalogue_line(lang):
    lines = viral_lines(lang)
    return random.choice(lines) if lines else None


def _bottom(
    plain,
    html,
    to_email,
    category,
    user=_UNSET,
    lang=None,
    collection=None,
    include_viral=True,
    extra_footer=None,
    header=None,
):
    """Everything after the message's own words, in one fixed order: a rule,
    the OIUEEI mark, the viral line (eligible recipients
    only — see below), "manage your preferences" (Cat. 2/3 mail; Cat. 1 has
    nothing to opt out of), a sender-specific extra line if any (the digest's
    per-collection mute link), and always last the legal-notice link — art. 14
    GDPR, a disclosure and not a preference, so it shows on mandatory mail
    too. Closes the two ``<div>``\\s the card opened in ``layout.html`` and
    left open (see the comment there for why), and the document itself: the
    template stops short of ``</html>`` so the footer lands inside it.

    Replaces the earlier, separate ``_with_viral_line`` + ``_with_footer``:
    their pieces now interleave in one fixed visual order — the mark used to
    sit inside the card's own template render, ahead of a viral line that
    *prepended* itself above a footer that was itself an independent
    *append* — rather than being two composable prepend/append steps.

    Viral-line eligibility: recipients who don't own a collection — the
    audience for "create your own" — including not-yet-registered invitees
    (``user`` is ``None``). Suppressed for collection owners and when
    ``VIRAL_LINES`` is empty. Its CTA is the plain URL of the line's ``path``
    (the form of the kind it names, or ``/new``), never tracking-wrapped (DESIGN §9).
    With ``VIRAL_LINE_PROVIDER`` set, the deployment's function picks the line for
    this recipient instead of the catalogue, after the suppression above (see
    ``_provided_line``).
    """
    lang = lang or getattr(settings, "EMAIL_LANGUAGE", "en")
    legal_url = f"{_frontend_base_url()}/legal"
    legal_label = T("footer_legal", lang)

    plain_parts = [plain, "---"]
    html_parts = ['<hr style="border:none;border-top:1px solid #ddd;margin-top:24px;">']

    # The mark already led this message as its <h1> — GENERIC_PARENT's own
    # branch in layout.html — so it does not also close it.
    if _logo_bytes() is not None and header != GENERIC_PARENT:
        html_parts.append(
            '<p style="margin:16px 0 8px;"><img src="cid:oiueei-logo" alt="OIUEEI" '
            'height="17" width="60" style="display:block;width:60px;height:17px;'
            'margin-bottom:15px;border:0;"></p>'
        )

    def footer_line(label, link):
        html_parts.append(
            f'<p style="font-size:{EMAIL_FOOTER_SIZE};color:#888888;margin-top:8px;">'
            f'<a href="{escape(link)}" style="{link_style()}">'
            f"{escape(label)}</a></p>"
        )

    if include_viral:
        # A co-curator gets it suppressed too (2026-09-28): since 2026-09 they
        # have the founder's whole reach minus deletion, so inviting them to
        # "start a collection" is a letter to someone who already runs one. The
        # flag is one Exists over both paths (owner or co-owner), folded into
        # the lookup queries — no extra round-trip. It comes **first**: a
        # deployment's provider is never asked about someone who gets no line.
        curates_collection = (
            user is not _UNSET and user and getattr(user, "_curates_collection", False)
        )
        line = None
        if not curates_collection:
            if settings.VIRAL_LINE_PROVIDER:
                line = _provided_line(None if user is _UNSET else user, lang)
            else:
                line = _catalogue_line(lang)
        if line:
            url = f"{_frontend_base_url()}{line.get('path', '/new')}"
            plain_parts.append(f"{line['text']}\n{line['cta']}: {url}")
            # A highlighted callout, not plain footer prose:
            # a pale-yellow background + padding sets the growth line apart
            # from the grey preferences/legal lines around it, and its own
            # text is black rather than the footer's muted grey — only the
            # CTA link inside keeps the accent colour (`email_style()['link_style']`).
            html_parts.append(
                f'<p style="font-size:{EMAIL_FOOTER_SIZE};color:#000000;'
                'background-color:#fff1a8;padding:10px;margin-top:16px;">'
                f"{escape(line['text'])} "
                f'<a href="{escape(url)}" style="{link_style()}">'
                f"{escape(line['cta'])}</a></p>"
            )

    if category != CATEGORY_MANDATORY:
        manage = T("footer_manage", lang)
        link = _notifications_link(to_email, user=user)
        plain_parts.append(f"{manage}: {link}")
        footer_line(manage, link)

    if extra_footer:
        extra = extra_footer(user, lang)
        if extra:
            label, link = extra
            plain_parts.append(f"{label}: {link}")
            footer_line(label, link)

    plain_parts.append(f"{legal_label}: {legal_url}")
    footer_line(legal_label, legal_url)
    html_parts.append("</div></div></html>")

    return "\n\n".join(plain_parts), html + "".join(html_parts)


@functools.lru_cache(maxsize=1)
def _logo_bytes():
    """Read the inline email logo once; None if the asset is missing.

    Cached across the process lifetime — the file never changes at runtime, so
    every send after the first skips the filesystem hit. A missing/corrupt
    asset degrades to "no logo" everywhere (attachment and ``<img>`` both
    skipped) rather than failing the send.
    """
    try:
        return (settings.BASE_DIR / "frontend/public/oiueei-logo.png").read_bytes()
    except OSError:
        return None


def _logo_attachment():
    """Return the logo as an inline MIMEImage (Content-ID ``oiueei-logo``), or None."""
    data = _logo_bytes()
    if data is None:
        return None
    image = MIMEImage(data, "png")
    image.add_header("Content-ID", "<oiueei-logo>")
    image.add_header("Content-Disposition", "inline", filename="oiueei-logo.png")
    return image


def _send(
    to_email,
    subject,
    plain,
    html,
    category,
    reply_to=None,
    user=_UNSET,
    include_viral=True,
    lang=None,
    collection=None,
    header=None,
    extra_footer=None,
):
    """Send a single email through the category + footer + viral pipeline.

    Returns True if the email was dispatched, False if the recipient opted out
    or the send failed. A failed send (SMTP error / timeout / socket error / bad
    header) is logged and swallowed — it never propagates, so it cannot 500 a
    user action whose DB work has already committed, nor abort a multi-recipient
    loop or a nightly cron.

    ``user`` lets a multi-recipient sender (broadcast/digest) pass a
    batch-resolved User (or a known-absent None) so the preference + footer
    lookups don't fire a query per recipient. Single-recipient callers leave it
    as ``_UNSET`` and the lookup happens here, as before.

    ``include_viral`` prepends a growth CTA above the footer (suppressed for
    anyone who curates a collection — owner or co-curator; the gate is the
    ``_curates_collection`` flag folded into the lookup queries). The operator's
    own ops mail is the one sender that passes ``False`` (an operator report,
    not growth copy); everything else, including ``send_magic_link_email``,
    uses the default — so magic-link sends now do the one recipient
    lookup they used to skip (see that function's docstring for why the extra
    query is still timing-safe).

    ``lang`` is the language the sender composed this email in (see
    ``resolve_email_language``); the footer and the viral line follow it, so the
    whole message speaks one language.

    ``header`` is the email's "parent" (a thing, a collection, an FAQ
    question, or "OIUEEI") — the HTML side is already in ``html`` (the sender
    passed it to ``_render_email``); this is where its plain-text counterpart
    is prepended, so a sender only states it once per call site.

    ``extra_footer(user, lang) -> (label, url) | None`` adds one more footer
    line, between "manage your preferences" and the legal link — only the
    digest uses it today, for its per-collection mute link (a token signed for
    *this* recipient, so it cannot be composed once and reused like the rest
    of a multi-recipient send's body — see ``_send_per_language``).
    """
    plain = _headline_prefix(header, plain)
    # Resolve the recipient User once when something downstream needs it: the
    # preference check (non-mandatory) or the viral-line ownership gate. Only
    # the mandatory + include_viral=False send (stats summary) skips it.
    if (category != CATEGORY_MANDATORY or include_viral) and user is _UNSET:
        user = _lookup_user(to_email)
    if not _should_send(to_email, category, user=user, collection=collection):
        return False
    plain, html = _bottom(
        plain,
        html,
        to_email,
        category,
        user=user,
        lang=lang,
        collection=collection,
        include_viral=include_viral,
        extra_footer=extra_footer,
        header=header,
    )
    try:
        # Always EmailMultiAlternatives (not the send_mail() shortcut) — the
        # inline logo needs .attach() on the message object, which send_mail()
        # never exposes.
        msg = EmailMultiAlternatives(
            subject=subject, body=plain, from_email=None, to=[to_email], reply_to=reply_to
        )
        msg.attach_alternative(html, "text/html")
        logo = _logo_attachment()
        if logo:
            # The logo is a CID reference, not a loose file: wrap the
            # alternative + image in multipart/related (not the default
            # multipart/mixed). Apple Mail treats a mixed sibling as a normal
            # attachment even when the HTML references its CID, so it rendered
            # the 30px inline logo AND a full-size copy + paperclip at the end
            # (user-reported on iOS Apple Mail).
            msg.mixed_subtype = "related"
            msg.attach(logo)
        msg.send()
    except (smtplib.SMTPException, OSError, BadHeaderError) as exc:
        # OSError covers socket.timeout/connection errors (socket.timeout is an
        # OSError subclass). BadHeaderError (a ValueError) guards against a CR/LF
        # that slipped into the subject — caught here so one tainted row can never
        # abort a multi-recipient loop or a nightly digest cron.
        # Log the exception class only — str(exc) (e.g. SMTPRecipientsRefused)
        # can carry the raw recipient address, which would defeat redaction.
        logger.error(
            "Email send failed (to=%s, subject=%r): %s",
            redact_email(to_email),
            subject,
            type(exc).__name__,
        )
        return False
    return True


# --- HTML body composition (autoescaped via email/layout.html) -----------------


def _para(text):
    """A paragraph of (autoescaped) text."""
    return {"type": "para", "text": text}


def _strong(text):
    """A paragraph holding a single bold value (used for the focal headline)."""
    return {"type": "strong", "text": text}


def _field(label, value, email=False):
    """A ``Label: value`` line. ``email=True`` renders the value as a real
    ``mailto:`` link, bus blue and NOT bold — a client's own auto-linkification
    (Gmail, iOS/Android "data detectors") wraps a bare address that looks like one
    in ITS OWN default blue regardless of whatever inline style sits on an enclosing ``<span>``;
    making it a real ``<a>`` up front, in our own colour, is what keeps the
    client from re-wrapping it its own way."""
    return {"type": "field", "label": label, "value": value, "email": email}


def _named_email_field(label, name, email):
    """A ``Label: Name (email)`` line where the name is plain black text and
    only the parenthesised address is a bus-blue ``mailto:`` link —
    the capacity alarm's Owner row used to
    colour the whole "Name (email)" string as if the name itself were a
    link too."""
    return {"type": "named_email_field", "label": label, "name": name, "email": email}


def _email(value):
    """An email address shown as its own value, as a real ``mailto:`` link in
    bus blue, NOT bold (it used to be
    bold, unlike ``_field(email=True)``'s value, which read as two different
    treatments for the same kind of thing). See ``_field``'s docstring for
    why this is a real link now rather than just a coloured ``<strong>``.
    """
    return {"type": "email", "value": value}


def _heading(text):
    """A section heading (``<h3>``)."""
    return {"type": "heading", "text": text}


def _list(items):
    """A bullet list."""
    return {"type": "list", "items": list(items)}


def _links(*links):
    """A row of links, each ``(url, label)``, joined by ``|``."""
    return {"type": "links", "links": [{"url": url, "label": label} for url, label in links]}


def _cta(url, label, fallback):
    """An email's single action as a button, with its own link spelled out
    below it as plain text.

    The layout renders an inline-styled ``<a>`` (bus blue, literal hex) rather
    than a ``<button>``: email clients strip forms and buttons, and none of
    them resolves a CSS custom property, so the app's primary button can only
    travel as a styled link. The ``fallback`` sentence and the raw URL cover
    the clients — and the moments — where the button cannot be clicked at all.
    **Every CTA carries this now**: it used to be only the
    ones whose whole job was that one click (the magic link, a yes/no pair);
    the lighter, fallback-less ``_button`` this function replaced is gone.
    """
    return {"type": "cta", "url": url, "label": label, "fallback": fallback}


# The app's two button roles as inline CSS, literal hex (email clients resolve no
# `var()`), **in the app's own palette** (`Braaanding`, edited in the Django admin and
# read here each time an email is composed — `braaanding()` remembers it in the
# process, so that costs no query): the PRIMARY is filled with `color_01` and
# labelled in `color_06`, the SECONDARY its outlined counterpart — a white fill, a
# border and a label in the accent (below). The secondary's padding is two pixels
# short of the primary's on every side so its border brings both to the same outer
# size. `email_style()` defines them once and hands them to the layout, so the three
# button blocks cannot drift apart. The two hover states are what the `<style>`
# block in layout.html switches to on `:hover` — a progressive enhancement: clients
# that strip `<style>` (most mobile mail apps) simply never see it, and the resting,
# inline-styled look is what they show instead. The primary hovers to the hero's pair
# (`color_03` fill, `color_05` label) and the secondary to a `color_02` fill; the
# admin refuses a palette where either label would not read (`Braaanding.clean`).
_BTN_TYPE = (
    f"font-family:Arial,Helvetica,sans-serif;font-size:{EMAIL_BODY_SIZE};font-weight:600;"
    "line-height:1.4;text-decoration:none;"
)


def email_style():
    """The colours of an email's buttons and links, from the app's palette.

    Returns a dict of ready-to-use strings: ``btn_primary``, ``btn_secondary``,
    ``link_style`` (inline styles), ``primary_hover`` and ``secondary_hover`` (the
    declarations of the two ``:hover`` rules).

    **The accent** — the colour of the links, of the secondary button's border and of its
    label — is ``color_01`` where that reads at 4.5:1 on white and on the page colour
    (``color_02``), else ``color_04``: the rule the web app's content links follow
    (``frontend/src/utils/linkColor.js``), so an email and the page agree.
    """
    palette = braaanding()
    c = {role: palette[role].lower() for role in palette if role.startswith("color_")}
    reads = (
        contrast_ratio(c["color_01"], WHITE) >= AA_NORMAL
        and contrast_ratio(c["color_01"], c["color_02"]) >= AA_NORMAL
    )
    accent = c["color_01"] if reads else c["color_04"]
    return {
        "btn_primary": (
            f"display:inline-block;background-color:{c['color_01']};color:{c['color_06']};"
            f"{_BTN_TYPE}padding:14px 24px;"
        ),
        "btn_secondary": (
            f"display:inline-block;background-color:#ffffff;color:{accent};"
            f"border:2px solid {accent};{_BTN_TYPE}padding:12px 22px;"
        ),
        # Every plain-text link and every "this is data worth noticing" value (an email
        # address shown via `_email`/`_field(..., email=True)`) — the accent, underlined,
        # `!important` on both (seen not to apply in real Gmail). A client's own
        # stylesheet — Gmail webmail forces its own link blue in places, and an
        # unstyled `color-scheme` leaves auto-dark-mode free to recolour inline styles
        # that lack it — can otherwise beat a plain inline style; `!important` on the
        # inline style outranks anything but another `!important` later in the
        # cascade, which nothing here is.
        "link_style": f"color:{accent} !important;text-decoration:underline !important;",
        "primary_hover": (
            f"background-color:{c['color_03']} !important;color:{c['color_05']} !important;"
        ),
        "secondary_hover": f"background-color:{c['color_02']} !important;",
    }


def link_style():
    return email_style()["link_style"]


def _ctas(primary, secondary, fallback):
    """Two actions as buttons — a primary and a secondary — with both URLs
    spelled out under them.

    The two-answer sibling of ``_cta``, for the one email that asks a yes/no
    question (the collection invitation: accept or decline). Same reasons as
    there — an inline-styled anchor, literal hex, no ``<button>`` — with the
    app's own split between the two roles: the primary is the filled bus-blue
    button, the secondary the white one with a bus-blue border and black text.
    ``primary`` and ``secondary`` are ``(url, label)`` pairs,
    like ``_links``; the ``fallback`` sentence and both raw URLs cover the
    clients, and the moments, where a button cannot be clicked.
    """
    return {
        "type": "ctas",
        "primary": {"url": primary[0], "label": primary[1]},
        "secondary": {"url": secondary[0], "label": secondary[1]},
        "fallback": fallback,
    }


# The owner's email note (Collection.email_note) renders a small Markdown subset
# into an ``md`` block — the ONE block type whose html arrives pre-built and
# mark_safe()d rather than autoescaped. See _note_blocks for the invariant.
_MD_LINK_OPEN = re.compile(r"\[([^\]]+)\]\(")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_EM = re.compile(r"(?<!\w)\*(.+?)\*(?!\w)")
_MD_BULLET = re.compile(r"^- ")
_MD_ORDERED = re.compile(r"^\d+\. ")
_MD_URL = re.compile(r"^https?://", re.IGNORECASE)


def _link_host(escaped_url):
    """The host an (escaped) http(s) link really goes to, in ASCII — or
    ``None`` when there isn't a usable one.

    ASCII means IDNA (punycode): a lookalike host written with a Cyrillic
    ``е`` reads ``xn--…`` rather than passing for the real name.
    """
    try:
        host = urlsplit(html_unescape(escaped_url)).hostname
        return host.encode("idna").decode("ascii") if host else None
    except (ValueError, UnicodeError):
        return None


def _resolve_link(escaped_url):
    """``(href, host)`` for the target of a ``[text](url)``, or ``None`` when it is
    no link. The twin of the frontend's ``resolveLink`` (the two read the cases of
    ``frontend/src/test/markdownLinkParity.json`` alike): ``www.…`` is read as
    ``https://www.…``, ``mailto:`` is allowed (it has no host to name), anything
    that is not http(s) with a host stays text. In an email every link is
    external: there is no "internal" one.
    """
    url = escaped_url.strip()
    if re.fullmatch(r"mailto:\S+", url, re.IGNORECASE):
        return url, None
    candidate = f"https://{url}" if re.match(r"www\.", url, re.IGNORECASE) else url
    host = _link_host(candidate) if _MD_URL.match(candidate) else None
    return (candidate, host) if host else None


def _md_links(text, park):
    """``[text](url)`` spans, the url taking **balanced parentheses** (an address
    like ``…/wiki/Foo_(bar)`` used to be cut at the first ``)``). ``park`` turns a
    link into its placeholder; anything that is not a link stays as written."""
    out, start = [], 0
    for opening in _MD_LINK_OPEN.finditer(text):
        if opening.start() < start:
            continue
        depth, i = 1, opening.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        if depth:
            continue  # never closed
        url = text[opening.end() : i - 1]
        replaced = None if re.search(r"\s", url) else park(opening.group(1), url)
        if replaced is None:
            continue
        out.append(text[start : opening.start()])
        out.append(replaced)
        start = i
    out.append(text[start:])
    return "".join(out)


def _md_inline(escaped_text):
    """Inline Markdown spans over ALREADY-escaped text — never escapes again.

    Links are parked behind NUL-delimited placeholders while the bold/italic
    passes run (an ``*`` or ``_`` inside an href must not become <em>), the
    same fix MarkdownText.jsx carries on the frontend. A URL that is not
    http(s), or has no host, stays as literal (escaped) text: a dead
    ``href="#"`` in an email client confuses more than the raw link does.

    **A link whose text is not its own URL names its host after it** —
    ``carnet (example.com)``. These emails leave from the operator's own
    domain, and the owner chooses both halves of the link: without the host,
    ``[https://www.your-domain.test/verify/…](https://elsewhere.example)`` reads as
    the operator's own sign-in link. The host is
    the one value here derived from unescaped text, so it is escaped once,
    itself.
    """
    text = escaped_text.replace("\x00", "")  # typed NUL can't forge a placeholder
    anchors = []

    def park(label, url):
        resolved = _resolve_link(url)
        if not resolved:
            return None
        href, host = resolved
        anchor = f'<a href="{href}" style="{link_style()}">{label}</a>'
        if host and html_unescape(label).strip() != html_unescape(url.strip()):
            anchor += f" ({escape(host)})"
        anchors.append(anchor)
        return f"\x00{len(anchors) - 1}\x00"

    text = _md_links(text, park)
    text = _MD_BOLD.sub(r"<strong>\1</strong>", text)
    text = _MD_EM.sub(r"<em>\1</em>", text)
    for index, anchor in enumerate(anchors):
        text = text.replace(f"\x00{index}\x00", anchor)
    return text


def _note_blocks(resolved_text):
    """The owner's email note as ``(plain addition, html blocks)``.

    ``("", [])`` when the note is empty. The plain half is the **raw
    Markdown** — the standard shape for a text/plain alternative — and the
    html half is exactly ONE ``md`` block holding the whole note, rendered
    verbatim by ``email/layout.html`` after the senders' last link block (so
    it lands after "view the listing", before the legal footer, with no
    positional logic anywhere).

    Subset: paragraphs (a lone newline inside one is a <br />), ``-`` and
    ``1.`` lists, ``**bold**``, ``*italic*``, ``[text](url)`` http(s) only, its
    real host after it unless the text is the URL (``_md_inline``).
    No headings, no tables: a ≤512-character note doesn't carry a document's
    hierarchy, and in these emails that is the layout's voice, not the
    owner's — ``#`` and ``|`` lines render as literal text. Emojis are plain
    UTF-8 and pass through untouched.

    **ESCAPE-ONCE invariant** (the backend twin of MarkdownText.jsx's): every
    line is escape()d BEFORE any transform, and ``_md_inline`` never escapes
    again — a ``&`` in a link's URL would come out as ``&amp;amp;`` and send
    readers to a different address. NUL is stripped here and again inside
    ``_md_inline``.
    """
    raw = (resolved_text or "").replace("\x00", "").strip()
    if not raw:
        return "", []
    html = []
    open_list = None
    paragraph = []

    def close_list():
        nonlocal open_list
        if open_list:
            html.append(f"</{open_list}>")
            open_list = None

    def flush_paragraph():
        if paragraph:
            joined = "<br />".join(_md_inline(escape(line.strip())) for line in paragraph)
            html.append(f"<p>{joined}</p>")
            paragraph.clear()

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if _MD_BULLET.match(stripped) or _MD_ORDERED.match(stripped):
            flush_paragraph()
            wanted = "ul" if _MD_BULLET.match(stripped) else "ol"
            if open_list != wanted:
                close_list()
                html.append(f"<{wanted}>")
                open_list = wanted
            item = _MD_BULLET.sub("", _MD_ORDERED.sub("", stripped))
            html.append(f"<li>{_md_inline(escape(item))}</li>")
        else:
            close_list()
            paragraph.append(stripped)
    flush_paragraph()
    close_list()
    return raw, [{"type": "md", "html": mark_safe("".join(html))}]


def _thing_collection(thing):
    """The first collection a thing belongs to, or ``None`` for a standalone
    thing. Not checked against any reader — ``_thing_url`` no longer uses it for
    that reason — so it may only name a group the recipient is known to be in, or
    stand in for a ``collection`` the caller was meant to pass.
    """
    return thing.collections.first() if thing else None


def _headline_prefix(header, plain):
    """Put the collection name on its own first line of the plain-text body —
    the plain-text half of the layout's HTML header. A no-op without a header,
    and harmless to call unconditionally.
    """
    return f"{header}\n\n{plain}" if header else plain


def _render_email(blocks, lang=None, header=None):
    """Render the card's top half through the autoescaping layout: the ``<h1>``
    parent title (see the module docstring) and the body blocks, inside the
    white rounded card ``layout.html`` opens. The card's bottom half — a rule,
    the OIUEEI mark, the viral line, preferences, the legal link, and the two
    closing ``</div>``\\s — is appended once per actual recipient by
    ``_bottom()``, called from ``_send()``; see the comment at the top of
    ``layout.html`` for why that split exists (a digest or broadcast composes
    its card once per LANGUAGE and reuses it for many recipients, whose
    footers still have to differ — a collection owner gets no viral line).

    ``header``, when set, leads the message as the ``<h1>``; the plain-text
    counterpart is ``_headline_prefix``, applied at the ``_send`` call.

    The resolved ``lang`` lands on ``<html lang="...">`` itself — a
    screen reader picks its pronunciation from that attribute, and every email
    already speaks a specific, known language (``resolve_email_language``), so
    leaving the tag blank was never "unknown", only unstated.
    """
    resolved_lang = lang or getattr(settings, "EMAIL_LANGUAGE", "en")
    style = email_style()
    return render_to_string(
        "email/layout.html",
        {
            "blocks": blocks,
            "header": header or "",
            "header_is_logo": header == GENERIC_PARENT,
            "has_logo": _logo_bytes() is not None,
            "lang": resolved_lang,
            "size_body": EMAIL_BODY_SIZE,
            "size_header": EMAIL_HEADER_SIZE,
            **style,
        },
    )


def _fmt_date(value):
    """A date for a reader: ``DD/MM/YYYY``, the convention the SPA and the date
    pickers use (a plain ``str(date)`` gives ISO ``YYYY-MM-DD``). Accepts a
    ``date``/``datetime``, an ISO string, or ``None`` (→ ``""``). An unrecognised
    string is passed through rather than dropped.
    """
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _fmt_dates(start, end):
    """The value of the "Dates" line: ``start - end``, or the day **once** when
    they are the same one. A loan or a rental for a single day read
    "13/10/2026 - 13/10/2026" in a confirmation email.
    Takes the strings the caller already formatted, so an HOUR-unit reservation's
    "05/10/2026 10:00" and "13:00" stay a range."""
    return start if start == end else f"{start} - {end}"


def _when_phrase(booking, T):
    """The dates of a booking as a phrase inside a sentence, in the reader's
    language: "from the 5th to the 8th", or "on the 5th" for a single day."""
    return _phrase_for(T, _fmt_date(booking.start_date), _fmt_date(booking.end_date))


def _phrase_for(T, start, end):
    """``start``/``end`` as the phrase of a sentence: "from A to B", or "on A" when
    they are the same, already formatted, day (a one-day reservation read "from
    05/10/2026 to 05/10/2026"). An hourly reservation's start carries its time, so
    it is never equal to its end and stays a range. Same catalogue phrases as
    ``_when_phrase``, which does it for a booking's own dates."""
    if start == end:
        return T("when_day").format(start=start)
    return T("when_range").format(start=start, end=end)


def _fmt_when(booking):
    """``(start, end)`` strings for the four RESERVE_THING emails' ``{start}``/
    ``{end}`` and ``dates_label`` field — every template already reads
    "{start} to {end}" / "del {start} al {end}", so this is the one place an
    HOUR-unit reservation differs from a whole-day one, with no catalogue
    changes needed in any of the three languages.

    Whole-day (``start_time`` NULL — every DAY-unit RESERVE; this is never
    called for LEND/RENT) renders two full dates, the second being the
    reservation's **last day, inclusive**. ``end_date`` is ``start + duration``,
    the day the space is free again — right for overlap checks and for the
    calendar export (Google's all-day End Date is exclusive too), wrong to hand
    a member as the end of their booking: a one-day reservation on the 5th read
    "from the 5th to the 6th". An HOUR-unit reservation renders the date once,
    on the start, then both HH:MM times — "05/10/2026 10:00" to "13:00" — since
    same-day start and end make a second date redundant.
    """
    if booking.start_time is None:
        last_day = booking.end_date - timedelta(days=1)
        return _fmt_date(booking.start_date), _fmt_date(last_day)
    return (
        f"{_fmt_date(booking.start_date)} {booking.start_time.strftime('%H:%M')}",
        booking.end_time.strftime("%H:%M"),
    )


def _with_demo_note(collection, T, blocks, plain):
    """Put the "this group is a demo" line first in a message about a demo collection.

    ``collection`` is the one the sender was handed: nothing is looked up here, so a
    sender that only knows a thing (a reminder, a question, a report) or a code, not
    the collection itself, carries no line — the collection's title already says
    "DEMO ·". A real group (or none) returns ``blocks`` and ``plain`` untouched. The
    line is the first block, right under the ``<h1>``, and the first line of the plain
    text after the header ``_send`` puts on top.
    """
    if not getattr(collection, "is_onboarding", False):
        return blocks, plain
    note = T("demo_note")
    return [_para(note), *blocks], f"{note}\n\n{plain}"


def _network_point(thing, collection=None):
    """``(network, point)`` for a thing that sits in a network, else ``(None, None)``.

    ``collection`` is the one the caller resolved for this reader; without it (or when
    it is not a network) the thing's own collections are looked at, which the daily
    commands load with the thing. ``point`` is ``None`` for a dinamizador who set none.
    """
    if collection is None or not collection.is_network():
        collection = next((c for c in thing.collections.all() if c.is_network()), None)
    if collection is None:
        return None, None
    return collection, collection.point_for(thing.owner_id)


def _point_name(thing, point):
    """Who lends it, as the emails say it: the entity of the pickup point, else the
    dinamizador's bare name (``""`` when they set none; the caller says "a member")."""
    return (point.display_name if point else "") or thing.owner.name


def _point_details(point, lang):
    """The pickup point as email blocks and plain lines: name, address, hours, contact.

    Only what is filled in; the values are autoescaped by the template like every field
    (the contact is shown as typed, never made a link). Empty for no point."""
    if point is None:
        return [], []
    T = _texts(lang)
    rows = [
        (T("point_name_label"), point.entity_name),
        (T("point_address_label"), point.address),
        (T("point_hours_label"), point.hours_note),
        (T("point_contact_label"), point.contact),
    ]
    rows = [(label, value) for label, value in rows if value]
    blocks = [_field(label, value) for label, value in rows]
    return blocks, [f"{label}: {value}" for label, value in rows]


def _loan_email_note(thing, collection):
    """The owner's note for a requester's emails: in a network the pickup point's own,
    else the collection's (``Collection.effective_text``); none without a collection."""
    if collection is None:
        return ""
    return collection.effective_text("email_note", thing.owner_id)


def _booking_detail_blocks(booking, lang=None):
    """Date/quantity detail blocks shared by the three booking emails."""
    if booking.start_date and booking.end_date:
        dates = _fmt_dates(_fmt_date(booking.start_date), _fmt_date(booking.end_date))
        return [_field(T("dates_label", lang), dates)]
    return []


def _first_collection_readable_by(thing, reader):
    """The first collection of ``thing`` (by code, so the choice is the same every
    time) that ``reader`` may open, or ``None``.

    Their membership is settled in **one** query for the whole list instead of an
    ``is_invited`` per collection — the shape of
    ``booking_service._readable_collections`` — and the visibility rules stay in
    ``Collection.can_view``. Iterates ``.all()``, so a caller that prefetched the
    thing's collections pays nothing for the list itself.
    """
    collections = sorted(thing.collections.all(), key=lambda c: c.code)
    if not collections:
        return None
    invited_to = set(
        reader.invited_to_collections.filter(code__in=[c.code for c in collections]).values_list(
            "code", flat=True
        )
    )
    return next((c for c in collections if c.can_view(reader.code, invited_to=invited_to)), None)


def _collection_path(collection_code, collection=None):
    """The SPA route of a collection, ``/{kind}/{code}``.

    A caller that holds the collection passes it; otherwise one query reads its
    kind — made once per send, never per recipient. A code that names nothing
    falls back to the old address, which the server redirects.
    """
    if collection is None:
        from core.models import Collection

        collection = Collection.objects.filter(code=collection_code).only("code", "kind").first()
    return collection.path() if collection else f"/collections/{collection_code}"


def _thing_url(thing, reader=None, collection=None):
    """Build the frontend URL for a thing, through a collection **its reader may open**.

    The link's path carries a collection code, and a thing can sit in a private
    group its reader was never invited to: naming it would hand them that group's
    code and land them on a 403. So the collection is one of these, in order:

    1. ``collection``, when the caller passed one — it already resolved it *for
       this reader* (``resolve_request_collection(..., requester)``), so it is
       the group the request was made through;
    2. the first of the thing's collections that ``reader`` can open;
    3. none — the bare ``/things/{code}`` route, which is what a reader with no
       group in common gets, and what a call with no ``reader`` gets: a collection
       nobody has checked for the person reading is never named.
    """
    base = _frontend_base_url()
    if collection is None and reader is not None:
        collection = _first_collection_readable_by(thing, reader)
    if collection:
        return f"{base}{collection.path()}/things/{thing.code}"
    return f"{base}/things/{thing.code}"


def _counted(headline, quantity, lang):
    """A thing's title as a request for several of it names it: "6 × Arduino kit".
    With one it is the title as it was."""
    if not quantity or quantity <= 1:
        return headline
    return _texts(lang)("quantity_times").format(count=quantity, headline=headline)


def _action_noun(thing, lang=None):
    """The per-type action noun for the booking emails (e.g. 'purchase', 'compra').

    Mirrors the frontend's per-type vocabulary (``thingCard.action`` / ``types``)
    so a SELL request reads 'solicitud de compra' / 'purchase request', a LEND
    request 'solicitud de préstamo' / 'loan request', etc. Every bookable type
    carries a noun — a missing one would be a KeyError mid-decision, after the
    booking already committed.
    """
    return T(f"action_noun_{thing.type}", lang)


# --- Category 1: Mandatory -----------------------------------------------------


def send_magic_link_email(email, magic_link, collection_headline=None, lang=None):
    """Send magic link authentication email.

    When ``collection_headline`` is given (a pop-in / share-link join), the
    subject names the collection the visitor is joining; without it the generic
    welcome subject is used (``/login`` and the plain onboarding pop-in).

    ``lang`` is resolved by the caller (the auth views know the user and, on a
    join, the collection) so language resolution never looks the recipient up
    on its own (email-enumeration timing oracle). The viral-line gate does
    add one ``User`` lookup inside ``_send()`` — safe here because both
    callers only reach this function after already resolving the recipient
    (``RequestLinkView`` only for a confirmed-registered address; ``JoinView``
    after ``get_or_create``), so the extra query carries no new
    registered/unregistered timing signal.
    """
    T = _texts(lang)
    if collection_headline:
        name = resolve_localized(collection_headline, lang)
        subject = T("magic_subject_collection").format(collection=name)
        greeting = T("magic_greeting_collection").format(collection=name)
        header = name
        blocks = [_para(greeting), _cta(magic_link, T("magic_cta"), T("cta_fallback"))]
    else:
        subject = T("magic_subject")
        greeting = T("magic_greeting")
        # No collection to be the parent: OIUEEI is, with its own one-line
        # pitch as the intro — the one case in the catalogue where the reader
        # may genuinely not know what this is.
        header = GENERIC_PARENT
        blocks = [
            _para(T("generic_parent_pitch")),
            _para(greeting),
            _cta(magic_link, T("magic_cta"), T("cta_fallback")),
        ]
    # The subject's greeting opens the plain body too, in both formats: an
    # inbox preview shows only the subject, and a body that starts at "click
    # here" without naming what was joined reads as a form letter.
    plain = f"{greeting}\n\n{T('magic_plain').format(link=magic_link)}"
    html = _render_email(blocks, lang=lang, header=header)
    _send(email, subject, plain, html, CATEGORY_MANDATORY, lang=lang, header=header)


def send_collection_invite_email(
    inviter_name,
    collection_headline,
    email,
    accept_link,
    reject_link,
    collection=None,
    proposer_name=None,
):
    """Send collection invitation email with accept and reject links.

    ``proposer_name`` names the member who suggested this person, when the
    invitation came from an approved proposal. It matters more than it looks: the
    invitee usually knows *them*, not the owner, so without it a warm
    recommendation arrives as an email from a stranger. The invitation is still
    the owner's — this is context, not authorship.

    **Neither name is ever `display_name`.** The fallback in `display_name` is the
    email address, and this message goes to a third party — somebody outside the
    group who has not agreed to anything yet. The two are handled
    differently because they sit differently in the copy:

    - ``proposer_name`` has a line to itself, so **no name, no line**: the caller
      passes the bare ``name`` and an empty one simply drops the sentence.
    - ``inviter_name`` is interpolated mid-sentence ("{inviter} has invited
      you…"), which needs *a* subject, so it goes through ``_member_name`` and an
      owner who never set a name is "A member" rather than an address.
    """
    user, lang = _recipient(email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection_headline)
    inviter_name = _member_name(inviter_name, lang)
    subject = T("invite_subject").format(collection=headline)
    plain = T("invite_plain").format(collection=headline, accept=accept_link, reject=reject_link)
    # The collection name is the layout's header now (top of the message, where
    # the logo was), so the body no longer repeats it as a bold line.
    blocks = [_para(T("invite_intro").format(inviter=inviter_name))]
    if proposer_name:
        recommended = T("invite_recommended_by").format(proposer=proposer_name)
        blocks.append(_para(recommended))
        plain = f"{plain} {recommended}"
    # Accepting is the primary button, declining the secondary one, and both
    # links follow as text for the clients that will not draw a button.
    blocks.append(
        _ctas(
            (accept_link, T("invite_accept_cta")),
            (reject_link, T("invite_decline_cta")),
            T("ctas_fallback"),
        )
    )
    # Art. 14 GDPR: this address did not come from its owner, it came from
    # whoever invited them, so the first message they get from us has to say
    # so — where the email came from, what it is used for, and that doing
    # nothing ends it. This is the one email in the catalogue that has to
    # carry this sentence, because it is the one email sent to somebody OIUEEI
    # never asked anything of directly.
    source_note = T("invite_source_note")
    blocks.append(_para(source_note))
    plain = f"{plain} {source_note}"
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    _send(
        email,
        subject,
        plain,
        _render_email(blocks, lang=lang, header=headline),
        CATEGORY_MANDATORY,
        user=user,
        lang=lang,
        header=headline,
    )


def send_invitation_proposal_email(
    owner_email,
    proposer_name,
    collection_headline,
    proposed_email,
    note,
    approve_link,
    reject_link,
    collection=None,
):
    """Ask the owner whether a member's suggested guest should be invited.

    Cat. 2: it is one member asking another to act, exactly like a hold request,
    and it is answerable — an owner who has switched activity mail off has
    switched off every other decision they are asked to make too, and the
    proposal still waits for them in the app.

    The proposed address is named because the owner cannot decide without it, and
    the proposer's note travels with it — an owner asked to admit a stranger has
    nothing else to go on. Neither is ever shown to the proposed person, who has
    not been contacted at all at this point.
    """
    user, lang = _recipient(owner_email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection_headline)
    subject = T("proposal_subject").format(collection=headline)
    plain = T("proposal_plain").format(
        proposer=proposer_name,
        collection=headline,
        email=proposed_email,
        approve=approve_link,
        reject=reject_link,
    )
    blocks = [
        _para(T("proposal_intro").format(proposer=proposer_name, collection=headline)),
        _email(proposed_email),
    ]
    if note:
        blocks.append(_para(T("proposal_note").format(note=note)))
    blocks.append(_para(T("proposal_nobody_told")))
    # Approving is the primary button, rejecting the secondary one, and both links
    # follow as text — the same two-answer shape as the invitation and the hold
    # request.
    blocks.append(
        _ctas(
            (approve_link, T("proposal_approve_cta")),
            (reject_link, T("proposal_reject_cta")),
            T("ctas_fallback"),
        )
    )
    _send(
        owner_email,
        subject,
        plain,
        _render_email(blocks, lang=lang, header=headline),
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
    )


def send_proposal_declined_email(
    proposer_email, owner_name, collection_headline, proposed_email, collection=None
):
    """Tell the member their suggestion wasn't taken up. **No reason given.**

    Saying nothing at all would be worse — they would wait, and probably ask
    again — but the owner owes nobody a justification: the group may run on rules
    (a subscription, papers, a waiting list) that are none of the product's
    business. So the copy is deliberately soft and final, and carries no cause.
    """
    user, lang = _recipient(proposer_email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection_headline)
    subject = T("proposal_declined_subject").format(collection=headline)
    # The plain body stays one flowing sentence (proposal_declined_body,
    # unchanged); the HTML pulls the address out into its own blue block
    # — the same treatment the proposal itself gives it.
    body = T("proposal_declined_body").format(
        owner=owner_name, collection=headline, email=proposed_email
    )
    html_blocks = [
        _para(T("proposal_declined_intro").format(owner=owner_name, collection=headline)),
        _email(proposed_email),
        _para(T("proposal_declined_outro")),
    ]
    _send(
        proposer_email,
        subject,
        body,
        _render_email(html_blocks, lang=lang, header=headline),
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
    )


def send_collection_welcome_doc_email(collection_headline, doc_url, email, collection=None):
    """Send the collection's welcome & rules PDF to a member who has just joined.

    A **link**, never an attachment: the file lives in the bucket, and mailing a
    5 MB PDF to every joiner would be a good way to get the domain filtered.
    Membership lifecycle, so it is mandatory (Cat. 1) like the invitation itself —
    a member who never sees the rules can't follow them. Sent once, on the first
    join (see ``core/views/auth.py::_join_collection``).
    """
    user, lang = _recipient(email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection_headline)
    subject = T("welcome_doc_subject").format(collection=headline)
    plain = T("welcome_doc_plain").format(collection=headline, url=doc_url)
    blocks = [
        _para(T("welcome_doc_intro")),
        _cta(doc_url, T("welcome_doc_link_label"), T("cta_fallback")),
        _para(T("welcome_doc_outro")),
    ]
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    html = _render_email(blocks, lang=lang, header=headline)
    _send(email, subject, plain, html, CATEGORY_MANDATORY, user=user, lang=lang, header=headline)


def send_account_delete_email(user, delete_link):
    """Send the right-to-erasure confirmation link (Cat. 1).

    The safety step of account deletion: the in-app button only *requests*
    deletion; nothing is deleted until the recipient opens this link and
    confirms once more on the page it lands on (the link previews on GET and
    commits on POST, like a booking decision — a mail scanner can't erase an
    account). ``include_viral=False``: a growth CTA on an erasure email would
    be grotesque.
    """
    lang = resolve_email_language(user=user)
    T = _texts(lang)
    subject = T("account_delete_subject")
    plain = T("account_delete_plain").format(link=delete_link)
    html = _render_email(
        [
            _para(T("account_delete_intro")),
            _para(T("account_delete_deletes")),
            _para(T("account_delete_keeps")),
            _cta(delete_link, T("account_delete_cta"), T("cta_fallback")),
            _para(T("account_delete_outro")),
        ],
        lang=lang,
        header=GENERIC_PARENT,
    )
    _send(
        user.email,
        subject,
        plain,
        html,
        CATEGORY_MANDATORY,
        user=user,
        include_viral=False,
        lang=lang,
        header=GENERIC_PARENT,
    )


def send_inactivity_warning_email(user, months, days, will_delete=True):
    """Tell somebody their account has gone quiet, before anything happens (Cat. 1).

    Mandatory, like the erasure confirmation and for the same reason: it is
    about whether the account continues to exist, so it has to reach people who
    opted out of everything else. ``include_viral=False`` too — a growth line on
    "we are about to delete you" would be grotesque.

    **Two bodies, because two things can happen.** Most accounts are deleted
    when the grace period runs out. An account that owns a group other people
    are still using never is, so it must not be told that it will be: it gets
    the true version instead — nothing is being taken away, but nobody has
    looked after this in two years, and leaving is yours to choose.

    Nothing here nags. The version that ends "if you would rather it went, you
    don't have to do anything at all" is the honest one (DESIGN §6): the exit
    must not be made harder than the entrance, and an inactive account is
    somebody who already left.
    """
    lang = resolve_email_language(user=user)
    T = _texts(lang)
    login_url = f"{_frontend_base_url()}/login"
    if will_delete:
        plain = T("inactivity_plain").format(months=months, days=days, link=login_url)
        blocks = [
            _para(T("inactivity_intro").format(months=months)),
            _para(T("inactivity_deletes").format(days=days)),
            _para(T("inactivity_keep")),
            _cta(login_url, T("inactivity_cta"), T("cta_fallback")),
            _para(T("inactivity_outro")),
        ]
    else:
        plain = T("inactivity_kept_plain").format(months=months, link=login_url)
        blocks = [
            _para(T("inactivity_intro").format(months=months)),
            _para(T("inactivity_kept")),
            _cta(login_url, T("inactivity_cta"), T("cta_fallback")),
            _para(T("inactivity_kept_outro")),
        ]
    _send(
        user.email,
        T("inactivity_subject"),
        plain,
        _render_email(blocks, lang=lang, header=GENERIC_PARENT),
        CATEGORY_MANDATORY,
        user=user,
        include_viral=False,
        lang=lang,
        header=GENERIC_PARENT,
    )


def send_contact_email(name, email, message, kind="support"):
    """Forward a contact-form message to the operator (the support channel).

    Recipient: ``CONTACT_EMAIL`` env var, defaulting to ``DEFAULT_FROM_EMAIL``
    (the operator mails themselves). ``Reply-To`` is the sender, so answering
    is one click. ``kind`` labels the subject — ``support`` (contact page) or
    ``collab`` (collaborate page) — same pipe, different inbox label. Operator
    mail: mandatory category, no viral CTA, deployment language.
    """
    import os

    recipient = os.environ.get("CONTACT_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
    lang = resolve_email_language()
    T = _texts(lang)
    sender = name or email
    subject_key = "collab_subject" if kind == "collab" else "contact_subject"
    subject = T(subject_key).format(sender=sender)
    plain = T("contact_plain").format(name=name or "-", email=email, message=message)
    html = _render_email(
        [
            _para(T("contact_intro")),
            _field(T("contact_name_label"), name or "-"),
            _field(T("contact_email_label"), email, email=True),
            _para(message),
        ],
        lang=lang,
        header=GENERIC_PARENT,
    )
    _send(
        recipient,
        subject,
        plain,
        html,
        CATEGORY_MANDATORY,
        reply_to=[email],
        include_viral=False,
        lang=lang,
        header=GENERIC_PARENT,
    )


def send_collection_revoke_email(
    owner_name, collection_headline, email, collection=None, things=()
):
    """Send collection access revoked notification email.

    ``things`` are the headlines of the removed member's things that went with them;
    when there are any, one more line names them.
    """
    user, lang = _recipient(email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection_headline)
    owner_name = _member_name(owner_name, lang)
    subject = T("revoke_subject")
    plain = T("revoke_plain").format(owner=owner_name, collection=headline)
    blocks = [
        _para(T("revoke_intro").format(owner=owner_name)),
        _para(T("revoke_outro")),
    ]
    if things:
        deleted = T("revoke_things").format(things=", ".join(L(t) for t in things))
        plain = f"{plain} {deleted}"
        blocks.append(_para(deleted))
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    html = _render_email(blocks, lang=lang, header=headline)
    _send(email, subject, plain, html, CATEGORY_MANDATORY, user=user, lang=lang, header=headline)


# --- Category 2: Activity ------------------------------------------------------


def _requester_contact(T, requester):
    """The requester's address, for the emails that tell whoever manages a thing that
    somebody asked for it.

    The address travels **with the request**, not when it is accepted: whoever sells a
    thing to a stranger can agree on price, place and time before committing the thing.
    It goes one way only — requester to manager; the manager's address is never shown to
    the requester, who will have it if they are written to. The rule against naming
    anyone by their address allows it because the reader of these emails is whoever
    manages the thing and already reads the same address in the app
    (``BookingPeriodSerializer.requester_email``, shown on the "Requests to me" page).
    The sender sets ``Reply-To`` to the same address, so "Reply" reaches the requester;
    there is no sentence saying so.

    Returns ``(plain, blocks)``: the plain-text line (``Email: …``) and the HTML blocks
    (one ``email=True`` field).
    """
    label = T("requester_email_label")
    return (
        f"{label}: {requester.email}",
        [_field(label, requester.email, email=True)],
    )


def send_booking_request_email(requester, thing, booking, manager_email, accept_link, reject_link):
    """Send a booking request email to one manager of the thing — its owner, or a
    curator of a PROPRIETARY collection it sits in — with **their own**
    accept/reject links (see ``send_booking_request_notifications``). Language and
    the preference check follow the recipient."""
    user, lang = _recipient(manager_email)
    T, L = _texts(lang), _local(lang)
    requester_name = requester.display_name
    action = _action_noun(thing, lang)
    headline = _counted(L(thing.headline), booking.quantity, lang)
    header = headline  # the thing being requested is this email's parent

    if booking.start_date and booking.end_date:
        plain = T("booking_request_plain_dated").format(
            requester=requester_name,
            action=action,
            thing=headline,
            when=_when_phrase(booking, T),
            accept=accept_link,
            reject=reject_link,
        )
    else:
        plain = T("booking_request_plain").format(
            requester=requester_name,
            action=action,
            thing=headline,
            accept=accept_link,
            reject=reject_link,
        )

    # Their address, right under the entry sentence in the HTML and after the sentence in
    # the plain text; "Reply" reaches them through the Reply-To below.
    contact_plain, contact_blocks = _requester_contact(T, requester)
    plain += "\n\n" + contact_plain

    subject = T("booking_request_subject").format(action=action)
    html = _render_email(
        [
            _para(T("booking_request_intro").format(requester=requester_name, action=action)),
            *contact_blocks,
            *_booking_detail_blocks(booking, lang),
            # Confirming is the primary button, cancelling the secondary one, and
            # both links follow as text — the same two-answer shape as the
            # collection invitation.
            _ctas(
                (accept_link, T("hold_confirm_cta")),
                (reject_link, T("hold_cancel_cta")),
                T("ctas_fallback"),
            ),
        ],
        lang=lang,
        header=header,
    )
    _send(
        manager_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        reply_to=[requester.email],
        user=user,
        lang=lang,
        header=header,
    )


def send_booking_decision_email(booking, thing, accepted=True, collection=None, decided_by=None):
    """Send booking accept/reject notification email to requester.

    ``collection`` feeds the owner's ``email_note`` on an accepted decision and
    nothing else — ``finalize_booking_decision`` passes the one
    ``resolve_request_collection`` picks **among the collections the requester
    may read**. Without it there is no note: the thing's first collection may be
    a PRIVATE group the requester was never in, and its note is written for
    that group's members.

    In a network the decision is the entity's: "{point} has accepted your loan", with
    the pickup point (name, address, hours, contact) on an acceptance. When the
    founder declines a request on another dinamizador's thing (the rescue), it is the
    network that declines, not the entity of the thing's owner, who did not decide.
    """
    user, lang = _recipient(booking.requester_email)
    T, L = _texts(lang), _local(lang)
    network, point = _network_point(thing, collection)
    if network is not None:
        return _send_network_decision_email(
            booking, thing, accepted, collection, network, point, decided_by, user, lang
        )
    decision_word = T("decision_confirmed") if accepted else T("decision_cancelled")
    action = _action_noun(thing, lang)
    headline = _counted(L(thing.headline), booking.quantity, lang)
    header = headline  # the thing this decision is about is the parent

    # The reader is the requester, and this is the one booking email that used to
    # carry no link at all: it announced a decision and left them with nothing to
    # press, at the moment the hold either becomes real or stops. The request
    # email has accept/reject, the FAQ ones link the thing; this one now does too.
    thing_url = _thing_url(thing, reader=user, collection=collection)

    if booking.start_date and booking.end_date:
        plain = T("decision_plain_dated").format(
            action=action,
            thing=headline,
            when=_when_phrase(booking, T),
            decision=decision_word,
            url=thing_url,
        )
    else:
        plain = T("decision_plain").format(
            action=action, thing=headline, decision=decision_word, url=thing_url
        )

    # One subject per decision. A single "We have news" for both an accepted and
    # a refused hold is unscannable in an inbox, and reads as a teaser rather
    # than as news (DESIGN §2 direct, §6 no curiosity gaps).
    subject = T("decision_subject_confirmed") if accepted else T("decision_subject_cancelled")
    html_blocks = [
        _para(T("decision_intro").format(action=action, decision=decision_word)),
        *_booking_detail_blocks(booking, lang),
        _cta(thing_url, T("view_thing_cta"), T("cta_fallback")),
    ]
    # The owner's note rides an ACCEPTED decision only — that is the moment
    # the hold becomes real and the note's "how to collect / where we are"
    # prose is finally actionable; a refusal has no next steps for it to
    # describe. From the collection the caller resolved for this requester,
    # never the thing's first one (see the docstring).
    if accepted:
        note_plain, note_blocks = _note_blocks(L(collection.email_note) if collection else "")
        if note_plain:
            plain += "\n\n" + note_plain
            html_blocks.extend(note_blocks)
    html_blocks, plain = _with_demo_note(collection, T, html_blocks, plain)
    html = _render_email(html_blocks, lang=lang, header=header)
    _send(
        booking.requester_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def _send_network_decision_email(
    booking, thing, accepted, collection, network, point, decided_by, user, lang
):
    """The decision email of a thing in a network (see ``send_booking_decision_email``)."""
    T, L = _texts(lang), _local(lang)
    action = _action_noun(thing, lang)
    headline = _counted(L(thing.headline), booking.quantity, lang)
    thing_url = _thing_url(thing, reader=user, collection=collection)
    rescued = decided_by is not None and decided_by.code != thing.owner_id
    who = L(network.headline) if rescued else _member_name(_point_name(thing, point), lang)
    intro = T("decision_by_confirmed" if accepted else "decision_by_declined").format(
        who=who, action=action
    )
    subject = T("decision_subject_confirmed") if accepted else T("decision_subject_cancelled")
    detail_blocks = _booking_detail_blocks(booking, lang)
    point_blocks, point_lines = _point_details(point, lang) if accepted else ([], [])
    html_blocks = [
        _para(intro),
        *detail_blocks,
        *point_blocks,
        _cta(thing_url, T("view_thing_cta"), T("cta_fallback")),
    ]
    plain_lines = [intro, f"'{headline}'"]
    if booking.start_date and booking.end_date:
        dates = _fmt_dates(_fmt_date(booking.start_date), _fmt_date(booking.end_date))
        plain_lines.append(f"{T('dates_label')}: {dates}")
    plain = "\n".join([*plain_lines, *point_lines, "", thing_url])
    if accepted:
        note_plain, note_blocks = _note_blocks(L(_loan_email_note(thing, network)))
        if note_plain:
            plain += "\n\n" + note_plain
            html_blocks.extend(note_blocks)
    html_blocks, plain = _with_demo_note(network, T, html_blocks, plain)
    html = _render_email(html_blocks, lang=lang, header=headline)
    _send(
        booking.requester_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=headline,
    )


def send_invite_rejected_email(invitee_name, collection_headline, owner_email, collection=None):
    """Send notification to collection owner that an invite was declined."""
    user, lang = _recipient(owner_email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection_headline)
    subject = T("invite_rejected_subject")
    plain = T("invite_rejected_plain").format(invitee=invitee_name, collection=headline)
    blocks = [_para(T("invite_rejected_intro").format(invitee=invitee_name))]
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    html = _render_email(blocks, lang=lang, header=headline)
    _send(
        owner_email, subject, plain, html, CATEGORY_ACTIVITY, user=user, lang=lang, header=headline
    )


def send_booking_confirmation_email(requester, thing, booking, collection=None, informed=None):
    """Send booking confirmation email to the requester.

    ``informed`` is how many people the request told: the thing's managers bar the
    requester, which is what ``send_booking_request_notifications`` fans out to and
    passes in. The email says "the person who runs it" for one and "the people who
    run it" for more. It does not name the owner (with a team the request reaches
    everyone who runs the thing, so naming one person would be untrue) nor say
    "curator" (in a COMMUNITY the one who runs a thing is its owner, a member, not
    whoever curates the group), so it reads as the request page does. Without it,
    the count is worked out here the same way.

    ``collection`` is the collection the request was made through
    (``booking_service.resolve_request_collection``) and feeds exactly one
    thing: the owner's ``email_note``, appended after the listing link. It
    deliberately never reaches ``_recipient`` — a thing-scoped email follows
    only the recipient's language.
    """
    user, lang = _recipient(requester.email)
    T, L = _texts(lang), _local(lang)
    if informed is None:
        informed = len([m for m in thing.managers() if m.code != requester.code])
    # One person, or more than one: the sentence is a whole phrase per number, not a
    # word swapped in, because Spanish and Catalan change the verb too ("responderá"
    # / "responderán"). Nobody told cannot happen (the owner is always a manager and
    # a requester is never the owner); it is read as one rather than as "the people".
    outro = T("confirmation_outro_one" if informed <= 1 else "confirmation_outro_other")
    # And where they will be written to: the address they sign in
    # with, which the managers now hold. Behind the outro in both halves; never printed
    # — the email already arrives there.
    contact_shared = T("contact_shared_request")
    thing_url = _thing_url(thing, reader=user, collection=collection)
    action = _action_noun(thing, lang)
    headline = _counted(L(thing.headline), booking.quantity, lang)
    header = headline  # the thing this confirms is this email's parent

    if booking.start_date and booking.end_date:
        plain = T("confirmation_plain_dated").format(
            action=action,
            thing=headline,
            when=_when_phrase(booking, T),
            outro=f"{outro} {contact_shared}",
            url=thing_url,
        )
    else:
        plain = T("confirmation_plain").format(
            action=action, thing=headline, outro=f"{outro} {contact_shared}", url=thing_url
        )

    note_plain, note_blocks = _note_blocks(L(_loan_email_note(thing, collection)))
    if note_plain:
        plain += "\n\n" + note_plain

    subject = T("confirmation_subject").format(action=action)
    blocks = [
        _para(T("confirmation_intro").format(action=action)),
        *_booking_detail_blocks(booking, lang),
        _para(outro),
        _para(contact_shared),
        _cta(thing_url, T("view_thing_cta"), T("cta_fallback")),
        *note_blocks,
    ]
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        requester.email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


# Endonyms, like the SPA's language picker: a language is named in itself.
_LANGUAGE_NAMES = {"es": "Español", "ca": "Català", "en": "English"}


def send_email_note_test_email(curator, collection, note):
    """Send a curator their own ``email_note`` draft, rendered as members get it.

    The note is written blind otherwise: it only ever appears in the emails a
    *requester* receives, and a curator can't request their own things. The
    request page's Markdown preview would lie about it — this subset has no
    headings or tables and prints a link's host after it — so the test uses the
    real renderer (``_note_blocks``) inside the real layout, and a note written
    per language shows every version, each under its language's own name.

    ``note`` is the draft as typed (unsaved). Mandatory category: it goes only
    to the person who asked for it, the moment they asked, so an activity
    opt-out must not swallow it.
    """
    user, lang = _recipient(curator.email, collection)
    T, L = _texts(lang), _local(lang)
    headline = L(collection.headline)
    versions = parse_localized(note)
    if versions:
        parts = [
            (_LANGUAGE_NAMES.get(code, code), _note_blocks(text)) for code, text in versions.items()
        ]
    else:
        parts = [(None, _note_blocks(note))]

    plain_parts, blocks = [T("email_note_test_intro").format(collection=headline)], []
    blocks.append(_para(T("email_note_test_intro").format(collection=headline)))
    for name, (note_plain, note_blocks) in parts:
        if name:
            plain_parts.append(f"— {name} —")
            blocks.append(_strong(name))
        plain_parts.append(note_plain)
        blocks.extend(note_blocks)
    plain = "\n\n".join(plain_parts)
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    _send(
        curator.email,
        T("email_note_test_subject").format(collection=headline),
        plain,
        _render_email(blocks, lang=lang, header=headline),
        CATEGORY_MANDATORY,
        user=user,
        lang=lang,
        header=headline,
    )


def send_faq_question_email(questioner_name, thing, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    user, lang = _recipient(owner_email)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user)
    headline = L(thing.headline)
    questioner_name = _member_name(questioner_name, lang)

    subject = T("faq_question_subject")
    # The question itself is this email's parent — it is what
    # the owner opened the message to read, ahead of which thing it was asked
    # about.
    header = question
    plain = T("faq_question_plain").format(
        questioner=questioner_name, thing=headline, question=question, url=thing_url
    )
    html = _render_email(
        [
            _para(T("faq_question_intro").format(questioner=questioner_name)),
            _strong(headline),
            _cta(thing_url, T("faq_view_reply_cta"), T("cta_fallback")),
        ],
        lang=lang,
        header=header,
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY, user=user, lang=lang, header=header)


def send_faq_answer_email(owner_name, thing, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner, linking the thing."""
    user, lang = _recipient(questioner_email)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user)
    headline = L(thing.headline)
    owner_name = _member_name(owner_name, lang)
    subject = T("faq_answer_subject")
    header = question
    plain = T("faq_answer_plain").format(
        owner=owner_name, answer=answer, thing=headline, url=thing_url
    )
    html = _render_email(
        [
            _para(T("faq_answer_intro").format(owner=owner_name)),
            _strong(headline),
            _field(T("reply_label"), answer),
            _cta(thing_url, T("view_thing_cta"), T("cta_fallback")),
        ],
        lang=lang,
        header=header,
    )
    _send(
        questioner_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_faq_answered_to_team_email(answerer, thing, question, answer, manager_email):
    """Tell a curator who didn't answer that a teammate did (Cat. 2).

    A question asks **every** manager of the thing, so its answer is team news:
    without this, the co-curator's inbox kept a FAQ_QUESTION asking for a
    decision the founder had already made — and the other way round. The
    questioner is not this email's business (they get ``send_faq_answer_email``)
    and neither is whoever answered.
    """
    user, lang = _recipient(manager_email)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user)
    headline = L(thing.headline)
    answerer = _member_name(answerer, lang)
    subject = T("faq_answered_team_subject").format(thing=headline)
    header = question
    plain = T("faq_answered_team_plain").format(
        answerer=answerer, thing=headline, answer=answer, url=thing_url
    )
    html = _render_email(
        [
            _para(T("faq_answered_team_intro").format(answerer=answerer)),
            _strong(headline),
            _field(T("reply_label"), answer),
            _cta(thing_url, T("view_thing_cta"), T("cta_fallback")),
        ],
        lang=lang,
        header=header,
    )
    _send(
        manager_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_faq_hidden_to_team_email(hider, thing, question, manager_email):
    """Tell a curator who didn't hide it that a teammate did (Cat. 2).

    The hide-side twin of ``send_faq_answered_to_team_email``: a teammate
    retired a question the others may still have been holding as pending —
    without this they never learn it was deliberate, and an unanswered one kept
    asking them for a reply nobody owed any more. The questioner is not this
    email's business (they get ``send_faq_hide_email``) and neither is whoever
    hid it.
    """
    user, lang = _recipient(manager_email)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user)
    headline = L(thing.headline)
    hider = _member_name(hider, lang)
    subject = T("faq_hidden_team_subject").format(thing=headline)
    header = question
    plain = T("faq_hidden_team_plain").format(hider=hider, thing=headline, url=thing_url)
    html = _render_email(
        [
            _para(T("faq_hidden_team_intro").format(hider=hider)),
            _strong(headline),
            _cta(thing_url, T("view_thing_cta"), T("cta_fallback")),
        ],
        lang=lang,
        header=header,
    )
    _send(
        manager_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_faq_hide_email(owner_name, thing, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    user, lang = _recipient(questioner_email)
    T, L = _texts(lang), _local(lang)
    owner_name = _member_name(owner_name, lang)
    subject = T("faq_hide_subject")
    header = question
    plain = T("faq_hide_plain").format(owner=owner_name, question=question)
    html = _render_email(
        [
            _para(T("faq_hide_intro").format(owner=owner_name)),
            _strong(L(thing.headline)),
        ],
        lang=lang,
        header=header,
    )
    _send(
        questioner_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_thing_reported_email(thing, owner_email):
    """Notify a thing owner that someone reported their listing.

    The reporter's identity is deliberately never included — the owner learns
    only *that* it was reported and *which* listing, so they can go and check it.
    """
    user, lang = _recipient(owner_email)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user)
    headline = L(thing.headline)

    subject = T("reported_subject")
    header = headline
    plain = T("reported_plain").format(thing=headline, url=thing_url)
    html = _render_email(
        [
            _para(T("reported_intro")),
            _para(T("reported_outro")),
            _cta(thing_url, T("reported_review_cta"), T("cta_fallback")),
        ],
        lang=lang,
        header=header,
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY, user=user, lang=lang, header=header)


def send_thing_hidden_by_founder_email(
    thing, founder, group_headline, owner_email, collection=None
):
    """Tell the owner of a thing in a network that the founder hid it.

    The founder's rescue power: the thing is still its owner's, who can show it
    again. Names the founder by bare ``name`` ("A member" when there is none),
    never their address.
    """
    user, lang = _recipient(owner_email, collection)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user, collection=collection)
    headline, group = L(thing.headline), L(group_headline)
    who = _member_name(founder.name, lang)
    subject = T("thing_hidden_subject").format(founder=who)
    plain = T("thing_hidden_plain").format(founder=who, thing=headline, group=group, url=thing_url)
    html = _render_email(
        [
            _para(T("thing_hidden_intro").format(founder=who, group=group)),
            _para(T("thing_hidden_outro")),
            _cta(thing_url, T("thing_hidden_cta"), T("cta_fallback")),
        ],
        lang=lang,
        header=headline,
    )
    _send(
        owner_email, subject, plain, html, CATEGORY_ACTIVITY, user=user, lang=lang, header=headline
    )


def send_broadcast_email(
    owner_name, owner_email, collection_headline, collection_code, message, emails, collection=None
):
    """Send a broadcast email from a collection owner to all invitees.

    The subject is auto-generated as "Hey! {collection}" (the owner only writes
    the message). Carries a reply-to header (the owner) and a link to the
    collection — the object that originated the message — so recipients can open
    it in-app. Composed per recipient language (see ``_compose_per_language``).
    """
    collection_url = f"{_frontend_base_url()}{_collection_path(collection_code, collection)}"

    def compose(lang):
        T, L = _texts(lang), _local(lang)
        headline = L(collection_headline)
        owner = _member_name(owner_name, lang)
        owner_inline = _member_name(owner_name, lang, inline=True)
        blocks, plain = _with_demo_note(
            collection,
            T,
            [
                _para(T("broadcast_intro").format(owner=owner)),
                _para(message),
                _cta(collection_url, T("broadcast_open_cta"), T("cta_fallback")),
            ],
            _template(T, "broadcast_plain", lang, nameless=not owner_name, field="owner").format(
                owner=owner_inline, message=message, url=collection_url
            ),
        )
        return (
            T("broadcast_subject").format(collection=headline),
            _headline_prefix(headline, plain),
            _render_email(blocks, lang=lang, header=headline),
        )

    _send_per_language(
        emails, CATEGORY_ACTIVITY, compose, collection=collection, reply_to=[owner_email]
    )


def send_return_reminder_email(requester_name, thing, end_date, owner_email, quantity=1):
    """Remind the owner that a booking ends tomorrow."""
    user, lang = _recipient(owner_email)
    T, L = _texts(lang), _local(lang)
    headline = _counted(L(thing.headline), quantity, lang)
    header = headline
    subject = T("reminder_subject").format(thing=headline)
    end = _fmt_date(end_date)
    plain = T("reminder_plain").format(requester=requester_name, thing=headline, end=end)
    body = T("reminder_body").format(requester=requester_name, thing=headline, end=end)
    html = _render_email([_para(body)], lang=lang, header=header)
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY, user=user, lang=lang, header=header)


def send_thing_left_with_owner_email(
    thing_headline, group_headline, requester_email, *, holding, collection=None
):
    """Tell whoever asked for a thing that its owner left the group and took it along.

    The thing is already deleted, so it is named by headline. The second sentence, about
    returning it, goes only to somebody who has it in hand now (``holding``). Neither the
    leaving member's nor the curator's address appears: the requester is told a
    membership ended, not who ended it.
    """
    user, lang = _recipient(requester_email, collection)
    T, L = _texts(lang), _local(lang)
    thing, group = L(thing_headline), L(group_headline)
    subject = T("thing_left_subject").format(thing=thing, group=group)
    intro = T("thing_left_intro").format(thing=thing, group=group)
    paragraphs = [intro, T("thing_left_holding")] if holding else [intro]
    html = _render_email([_para(p) for p in paragraphs], lang=lang, header=group)
    _send(
        requester_email,
        subject,
        " ".join(paragraphs),
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=group,
    )


def send_thing_withdrawn_email(
    thing_headline, group_headline, requester_email, *, holding, collection=None, point=None
):
    """Tell whoever had a live request on a thing that it was deleted and the request with it.

    The thing is already gone, so it is named by headline. Whoever has it in hand now
    (``holding``) is told to return it; in a network ``point`` (the pickup point of the
    thing's owner) gives them where. Neither the address nor the name of whoever deleted
    it appears: the requester is told the thing was withdrawn, not who did it.
    """
    user, lang = _recipient(requester_email, collection)
    T, L = _texts(lang), _local(lang)
    thing, group = L(thing_headline), L(group_headline)
    subject = T("thing_withdrawn_subject").format(thing=thing, group=group)
    intro = T("thing_withdrawn_intro").format(thing=thing, group=group)
    paragraphs = [intro, T("thing_left_holding")] if holding else [intro]
    point_blocks, point_lines = _point_details(point, lang) if holding else ([], [])
    html = _render_email([*[_para(p) for p in paragraphs], *point_blocks], lang=lang, header=group)
    _send(
        requester_email,
        subject,
        "\n".join([" ".join(paragraphs), *point_lines]),
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=group,
    )


def send_return_due_email(owner_name, thing, end_date, requester_email, quantity=1):
    """Remind the **borrower** that they hand the thing back tomorrow.

    The counterpart of ``send_return_reminder_email``, and the half that was
    missing: only the owner was ever told a loan was ending, so the one person
    who has to actually do something — carry the drill back — heard nothing. A
    lending library runs on this message.

    It names the owner rather than "the owner": returning something is a promise
    made to a person, and the borrower may be in several groups at once. The
    caller passes the owner's bare ``name``: the borrower does not hold the
    owner's address, so an owner with no name is "a member", never their email.
    """
    user, lang = _recipient(requester_email)
    T, L = _texts(lang), _local(lang)
    network, point = _network_point(thing)
    if network is not None:
        owner_name = _point_name(thing, point)
    owner_name = _member_name(owner_name, lang, inline=True)
    headline = _counted(L(thing.headline), quantity, lang)
    header = headline
    thing_url = _thing_url(thing, reader=user)
    subject = T("return_due_subject").format(thing=headline)
    end = _fmt_date(end_date)
    plain = T("return_due_plain").format(owner=owner_name, thing=headline, end=end)
    body = T("return_due_body").format(owner=owner_name, thing=headline, end=end)
    point_blocks, point_lines = _point_details(point, lang)
    if point_lines:
        plain += "\n" + "\n".join(point_lines)
    blocks = [_para(body), *point_blocks, _cta(thing_url, T("view_thing_cta"), T("cta_fallback"))]
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        requester_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_pickup_due_email(owner_name, thing, start_date, requester_email, quantity=1):
    """Remind the **borrower** they pick the thing up tomorrow (LEND/RENT).

    The arrival nudge of a loan or rental: the only pickup email before this
    was the acceptance, sent when the dates were agreed — weeks can pass
    between that and the day, and the one person who has to be somewhere at a
    time heard nothing meanwhile. The pickup twin of ``send_return_due_email``
    (same reader, same CTA to the listing, the other end of the loan), and the
    same rule for the owner's name: bare ``name``, "a member" when there is none.
    """
    user, lang = _recipient(requester_email)
    T, L = _texts(lang), _local(lang)
    network, point = _network_point(thing)
    if network is not None:
        owner_name = _point_name(thing, point)
    raw_owner_name = owner_name
    owner_name = _member_name(owner_name, lang, inline=True)
    headline = _counted(L(thing.headline), quantity, lang)
    header = headline
    thing_url = _thing_url(thing, reader=user)
    subject = T("pickup_due_subject").format(thing=headline)
    start = _fmt_date(start_date)
    nameless = not raw_owner_name
    plain = _template(T, "pickup_due_plain", lang, nameless=nameless, field="owner").format(
        owner=owner_name, thing=headline, start=start
    )
    body = _template(T, "pickup_due_body", lang, nameless=nameless, field="owner").format(
        owner=owner_name, thing=headline, start=start
    )
    point_blocks, point_lines = _point_details(point, lang)
    if point_lines:
        plain += "\n" + "\n".join(point_lines)
    blocks = [_para(body), *point_blocks, _cta(thing_url, T("view_thing_cta"), T("cta_fallback"))]
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        requester_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_pickup_reminder_email(requester_name, thing, start_date, owner_email, quantity=1):
    """Remind the owner they hand the thing over tomorrow (LEND/RENT).

    The owner's half of the pickup nudge — the same reader the return reminder
    reaches, told about the day the thing *leaves* rather than the day it comes
    back. Nothing is asked of them (the requester is the one who has to turn
    up), so like ``send_return_reminder_email`` there is no button.
    """
    user, lang = _recipient(owner_email)
    T, L = _texts(lang), _local(lang)
    headline = _counted(L(thing.headline), quantity, lang)
    header = headline
    subject = T("pickup_reminder_subject").format(thing=headline)
    start = _fmt_date(start_date)
    plain = T("pickup_reminder_plain").format(requester=requester_name, thing=headline, start=start)
    body = T("pickup_reminder_body").format(requester=requester_name, thing=headline, start=start)
    html = _render_email([_para(body)], lang=lang, header=header)
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY, user=user, lang=lang, header=header)


def send_return_overdue_email(manager, thing, end_date, requester_email, quantity=1):
    """Nudge the **borrower** whose loan or rental is past its return date.

    The one return email that is sent by a person rather than by the daily
    command: whoever manages the thing pressed "remind them to return it" on
    ``/owner-bookings``, so the message names them (by bare ``name``, through
    ``_member_name`` — never the address ``display_name`` falls back to) and
    ``Reply-To`` is their address, which ``/owner-bookings`` says before the
    press — the borrower's natural answer ("I'll bring it tomorrow") goes
    straight to the person who asked. The wording leaves room for a return that
    simply was never recorded, since OIUEEI only assumes a loan comes back.
    """
    user, lang = _recipient(requester_email)
    T, L = _texts(lang), _local(lang)
    headline = _counted(L(thing.headline), quantity, lang)
    header = headline
    thing_url = _thing_url(thing, reader=user)
    subject = T("return_overdue_subject").format(thing=headline)
    end = _fmt_date(end_date)
    # The bare name: `display_name` falls back to the address. The address does
    # reach the borrower — as `Reply-To`, which the page tells the manager before
    # they press — but it is no name to put in a sentence.
    name = _member_name(manager.name, lang)
    plain = T("return_overdue_plain").format(manager=name, thing=headline, end=end)
    body = T("return_overdue_body").format(manager=name, thing=headline, end=end)
    blocks = [_para(body), _cta(thing_url, T("view_thing_cta"), T("cta_fallback"))]
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        requester_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        reply_to=[manager.email],
        user=user,
        lang=lang,
        header=header,
    )


def send_reservation_confirmed_email(requester, thing, booking, collection=None):
    """Tell the requester their on-site reservation is confirmed (RESERVE_THING).

    There is no owner decision to wait for, so this is not "request sent" — it
    is "you have it". Names the space, the dates, and the fee if the owner set
    one.
    """
    user, lang = _recipient(requester.email, collection)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user, collection=collection)
    headline = L(thing.headline)
    header = headline  # the space being reserved is this email's parent

    start, end = _fmt_when(booking)
    subject = T("reservation_confirmed_subject").format(thing=headline)
    plain = T("reservation_confirmed_plain").format(
        thing=headline, when=_phrase_for(T, start, end), url=thing_url
    )
    blocks = [
        _para(T("reservation_confirmed_intro")),
        _field(T("dates_label"), _fmt_dates(start, end)),
    ]
    if thing.fee:
        blocks.append(_field(T("reservation_fee_label"), str(thing.fee)))
    if thing.location:
        blocks.append(_field(T("reservation_where_label"), thing.location))
    # Where they will be written to: said, not printed.
    contact_shared = T("contact_shared_reservation")
    plain += "\n\n" + contact_shared
    blocks.append(_para(contact_shared))
    blocks.append(_cta(thing_url, T("view_thing_cta"), T("cta_fallback")))
    # The owner's note for whoever books here — after the listing link, before
    # the legal footer (which _render_email appends itself). Same collection
    # fallback the header line above uses, so the note always belongs to the
    # group this email names at its top.
    note_collection = collection or _thing_collection(thing)
    note_plain, note_blocks = _note_blocks(L(note_collection.email_note) if note_collection else "")
    if note_plain:
        plain += "\n\n" + note_plain
        blocks.extend(note_blocks)
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        requester.email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_reservation_notice_email(owner_email, requester, thing, booking, collection=None):
    """Tell the owner a member reserved their space (RESERVE_THING).

    Carries the requester's optional project note verbatim (escaped) — it is the
    whole reason the note exists.
    """
    user, lang = _recipient(owner_email, collection)
    T, L = _texts(lang), _local(lang)
    requester_name = requester.display_name
    headline = L(thing.headline)
    header = headline

    start, end = _fmt_when(booking)
    subject = T("reservation_notice_subject").format(requester=requester_name, thing=headline)
    plain = T("reservation_notice_plain").format(
        requester=requester_name, thing=headline, when=_phrase_for(T, start, end)
    )
    # The requester's own address, so the owner can reach them directly: a
    # RESERVE_THING requester is always a collection member by
    # the time this fires (403 otherwise, see request_reservation), so a real
    # address is guaranteed here. The owner reads the same address in the app —
    # "Requests to me" shows it as a link (it is
    # BookingPeriodSerializer.requester_email) — which is the exception to never
    # naming anyone by their address: the
    # reader already holds it. "Reply" reaches them: the
    # Reply-To below is the requester's.
    contact_plain, contact_blocks = _requester_contact(T, requester)
    plain += "\n\n" + contact_plain
    blocks = [
        _para(T("reservation_notice_intro").format(requester=requester_name)),
        *contact_blocks,
        _field(T("dates_label"), _fmt_dates(start, end)),
    ]
    if booking.project_note:
        plain += "\n\n" + T("reservation_note_label") + ": " + booking.project_note
        blocks.append(_field(T("reservation_note_label"), booking.project_note))
    if booking.contact_phone:
        # Only that there is one. The number itself lives in the app until the day
        # after the booking and is then deleted; an email copy would outlive that.
        plain += "\n\n" + T("reservation_notice_phone")
        blocks.append(_para(T("reservation_notice_phone")))
    blocks, plain = _with_demo_note(collection, T, blocks, plain)
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        owner_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        reply_to=[requester.email],
        user=user,
        lang=lang,
        header=header,
    )


def send_reservation_cancelled_email(
    recipient_email, other_name, thing, booking, cancelled_by_owner
):
    """Tell the party who didn't cancel that a reservation is off (RESERVE_THING).

    ``cancelled_by_owner`` picks the wording: the guest reads "X cancelled *your*
    reservation", the owner reads "X cancelled *their* reservation".
    """
    user, lang = _recipient(recipient_email)
    T, L = _texts(lang), _local(lang)
    other = _member_name(other_name, lang)
    headline = L(thing.headline)
    header = headline
    side = "to_guest" if cancelled_by_owner else "to_owner"

    start, end = _fmt_when(booking)
    subject = T("reservation_cancelled_subject").format(thing=headline)
    plain = T(f"reservation_cancelled_{side}_plain").format(
        other=other, thing=headline, when=_phrase_for(T, start, end)
    )
    html = _render_email(
        [
            _para(T(f"reservation_cancelled_{side}_intro").format(other=other)),
            _field(T("dates_label"), _fmt_dates(start, end)),
        ],
        lang=lang,
        header=header,
    )
    _send(
        recipient_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_reservation_cancel_confirmation_email(
    canceller_email, thing, booking, *, is_own_reservation, member_name=None
):
    """Confirm a cancellation to whoever just made it (RESERVE_THING).

    The member who booked got "your reservation is confirmed" at the time; a
    cancellation with no reply to them leaves that email as the last word in
    their inbox, describing a reservation that no longer stands. No button, no
    ``email_note`` — there is nothing left to do about this reservation.

    ``is_own_reservation`` picks the wording: the member who cancelled their
    own reads "your reservation is cancelled"; a curator who cancelled someone
    else's reads "you cancelled {member}'s reservation" — ``member_name`` is
    that person's bare ``name`` (never ``display_name``, whose fallback is
    their email address).
    """
    user, lang = _recipient(canceller_email)
    T, L = _texts(lang), _local(lang)
    headline = L(thing.headline)
    header = headline
    side = "self" if is_own_reservation else "other"
    member = None if is_own_reservation else _member_name(member_name, lang, inline=True)

    start, end = _fmt_when(booking)
    subject = T(f"reservation_cancel_confirmation_subject_{side}").format(thing=headline)
    intro_key = f"reservation_cancel_confirmation_intro_{side}"
    plain_key = f"reservation_cancel_confirmation_plain_{side}"
    if is_own_reservation:
        intro = T(intro_key)
        plain = T(plain_key).format(thing=headline, when=_phrase_for(T, start, end))
    else:
        nameless = not member_name
        intro = _template(T, intro_key, lang, nameless=nameless, field="member").format(
            member=member
        )
        plain = _template(T, plain_key, lang, nameless=nameless, field="member").format(
            member=member, thing=headline, when=_phrase_for(T, start, end)
        )

    html = _render_email(
        [
            _para(intro),
            _field(T("dates_label"), _fmt_dates(start, end)),
        ],
        lang=lang,
        header=header,
    )
    _send(
        canceller_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


def send_reservation_reminder_email(requester_email, thing, booking):
    """Remind the member their on-site reservation starts tomorrow (RESERVE_THING).

    The return reminder is nonsense for a reservation — nothing is carried
    anywhere — so ``send_reminders`` excludes RESERVE from it. What a
    reservation does need is the *arrival* nudge: a member can book a slot up to
    a year ahead and hear nothing between the confirmation and the day, and a
    no-show costs a real slot. Requester-only — they are the one who has to
    turn up.
    """
    user, lang = _recipient(requester_email)
    T, L = _texts(lang), _local(lang)
    thing_url = _thing_url(thing, reader=user)
    headline = L(thing.headline)
    header = headline
    start, end = _fmt_when(booking)
    subject = T("reservation_reminder_subject").format(thing=headline)
    plain = T("reservation_reminder_plain").format(
        thing=headline, when=_phrase_for(T, start, end), url=thing_url
    )
    blocks = [
        _para(T("reservation_reminder_intro")),
        _field(T("dates_label"), _fmt_dates(start, end)),
    ]
    if thing.location:
        blocks.append(_field(T("reservation_where_label"), thing.location))
    blocks.append(_cta(thing_url, T("view_thing_cta"), T("cta_fallback")))
    html = _render_email(blocks, lang=lang, header=header)
    _send(
        requester_email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        header=header,
    )


# --- Category 3: News / broadcast ---------------------------------------------


def send_digest_email(
    collection_headline,
    collection_code,
    thing_headlines,
    emails,
    collection=None,
    new_members=0,
):
    """Send a digest email listing new things added to a collection.

    ``new_members`` is how many people joined the group in the digest's window and
    still belong to it: a **number and nothing else**, because the digest reaches
    every member and a list of names would hand out the member list. With 0 the
    line is not written, and nobody who left is ever mentioned.
    """
    base_url = _frontend_base_url()
    collection_url = f"{base_url}{_collection_path(collection_code, collection)}"

    def compose(lang):
        T, L = _texts(lang), _local(lang)
        headline = L(collection_headline)
        headlines = [L(h) for h in thing_headlines]
        things_plain = "\n".join(f"  - {h}" for h in headlines)
        members_line = (
            T("digest_new_members_one" if new_members == 1 else "digest_new_members_other").format(
                count=new_members
            )
            if new_members > 0
            else ""
        )
        blocks, plain = _with_demo_note(
            collection,
            T,
            [
                _para(T("digest_intro")),
                _list(headlines),
                *([_para(members_line)] if members_line else []),
                _cta(collection_url, T("view_collection_cta"), T("cta_fallback")),
            ],
            T("digest_plain").format(
                things=things_plain,
                members=f"{members_line}\n\n" if members_line else "",
                url=collection_url,
            ),
        )
        return (
            T("digest_subject").format(collection=headline),
            _headline_prefix(headline, plain),
            _render_email(blocks, lang=lang, header=headline),
        )

    # The per-collection unsubscribe, appended after the generic preferences
    # footer. It is what lets `notify_news` default to on (DESIGN §6): the way to
    # stop *these* emails is one click in the email itself, and it costs the
    # reader none of the transactional mail they actually want. `_send`'s footer
    # can't build it — it is scoped to a collection, and only this sender has one.
    def per_recipient_footer(user, lang):
        if user is None or collection is None:
            return None
        link = f"{base_url}/digest/mute/{make_digest_mute_token(user, collection)}"
        return T("digest_mute_cta", lang), link

    _send_per_language(
        emails,
        CATEGORY_NEWS,
        compose,
        collection=collection,
        extra_footer=per_recipient_footer,
    )


JOIN_SUMMARY_MAX_NAMES = 10


def send_join_summary_email(collection, curator, names):
    """Tell one curator who joined their group: ``names`` are the members' ``name``
    values, each replaced by the member's address when they never set one (the
    caller does it: this email goes only to the team, who read every member's
    address in the members list). An empty entry still reads as "a member".

    At most ``JOIN_SUMMARY_MAX_NAMES`` are named, then "and N more". Activity mail,
    so whoever silenced activity gets nothing. The footer carries the same
    one-click "stop the summaries from this group" link as the digest's, and
    silencing a group (``Collection.digest_muted``) stops this email too — the
    command does not send it to a curator who did.
    """
    user, lang = _recipient(curator.email, collection)
    T, L = _texts(lang), _local(lang)
    group = L(collection.headline)
    count = len(names)
    shown = [_member_name(n, lang, inline=True) for n in names[:JOIN_SUMMARY_MAX_NAMES]]
    if count > JOIN_SUMMARY_MAX_NAMES:
        # "more" carries its own conjunction ("y 1 más"), so it closes the list
        # in the conjunction's place.
        more = T("join_summary_more").format(count=count - JOIN_SUMMARY_MAX_NAMES)
        listed = f"{', '.join(shown)} {more}"
    elif len(shown) == 1:
        listed = shown[0]
    else:
        listed = f"{', '.join(shown[:-1])} {T('join_summary_and')} {shown[-1]}"
    one = count == 1
    subject = T("join_summary_subject_one" if one else "join_summary_subject_other").format(
        group=group, count=count
    )
    intro = T("join_summary_intro_one" if one else "join_summary_intro_other").format(
        group=group, names=listed
    )
    url = f"{_frontend_base_url()}{_collection_path(collection.code, collection)}/invites"
    cta = T("join_summary_cta")
    plain = f"{intro}\n\n{cta}: {url}"
    html = _render_email([_para(intro), _cta(url, cta, T("cta_fallback"))], lang=lang, header=group)

    def mute_footer(footer_user, _lang):
        if footer_user is None:
            return None
        token = make_digest_mute_token(footer_user, collection)
        return T("digest_mute_cta"), f"{_frontend_base_url()}/digest/mute/{token}"

    _send(
        curator.email,
        subject,
        plain,
        html,
        CATEGORY_ACTIVITY,
        user=user,
        lang=lang,
        collection=collection,
        header=group,
        extra_footer=mute_footer,
    )


def send_collection_capacity_alarm(collection, counter, count, threshold):
    """Alert the operator that a collection crossed the mass-upload alarm line.

    Ops mail: operator-only, so it carries no i18n catalogue, no footer and no
    viral CTA.

    **Recipients are the superusers**, not a config var. The spec says this
    alert reaches the operator alone, and on the deploy branch the operator *is*
    the superuser — so deriving the address from `is_superuser` keeps the two
    definitions from drifting, and a deployment that adds a second admin gets
    them included without touching config. Falls back to ``CONTACT_EMAIL`` /
    ``DEFAULT_FROM_EMAIL`` if no superuser has an email, because an abuse signal
    that silently goes nowhere is worse than no signal.

    **The owner is never copied.** The alarm is a tripwire, not a warning: a
    legitimate bulk import must not be interrupted, and someone probing the
    endpoint must not be told where the line sits. Only the hard ceiling
    (``COLLECTION_THINGS_BLOCK``) is user-visible, and only once it bites.
    """
    import os

    from core.models import User

    recipients = list(
        User.objects.filter(is_superuser=True).exclude(email="").values_list("email", flat=True)
    ) or [os.environ.get("CONTACT_EMAIL", "") or settings.DEFAULT_FROM_EMAIL]
    owner = collection.owner
    headline = resolve_localized(collection.headline)
    noun = "things" if counter == "things" else "members"
    subject = f"[OIUEEI] Collection {collection.code} passed {threshold} {noun}"
    rows = [
        ("Collection", f"{headline} ({collection.code})"),
        ("Counter", noun),
        (noun.capitalize(), str(count)),
        ("Alarm threshold", str(threshold)),
        ("Owner code", owner.code if owner else "-"),
        ("Created", collection.created.isoformat()),
    ]
    # The alert's own explanation is its <h1> — it used to be the one email with
    # no parent at all; ops mail gets the same title treatment as everything
    # else, even though this makes for an unusually long heading (three
    # sentences, not a short name).
    header = (
        "A collection has crossed the mass-upload alarm threshold. This is "
        "informational — nothing has been blocked and the owner has not been "
        "notified. Review it if the volume looks wrong for this account."
    )
    blocks = []
    # `_send` puts `header` on the first line of the plain text; repeating it here
    # printed it twice.
    plain_lines = []
    for label, value in rows:
        blocks.append(_field(label, value))
        plain_lines.append(f"  {label}: {value}")
        if label == "Alarm threshold":
            # The owner's name is plain text; only their address is a link,
            # bus blue (the whole "Name
            # (email)" string used to be coloured as if the name were a link
            # too).
            if owner:
                blocks.append(_named_email_field("Owner", owner.display_name, owner.email))
                plain_lines.append(f"  Owner: {owner.display_name} ({owner.email})")
            else:
                blocks.append(_field("Owner", "-"))
                plain_lines.append("  Owner: -")

    # One send per superuser: _send takes a single address, and a per-recipient
    # send keeps a bad address from costing the others their alert.
    plain = "\n".join(plain_lines)
    # No lang var here on purpose (see the docstring): this is operator-only
    # ops mail with no i18n catalogue, so the legal footer speaks the deployment
    # default rather than any particular recipient's preference.
    html = _render_email(blocks, lang=None, header=header)
    for recipient in recipients:
        _send(
            recipient,
            subject,
            plain,
            html,
            CATEGORY_MANDATORY,
            include_viral=False,
            header=header,
        )
