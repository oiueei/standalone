"""
Centralized email service for OIUEEI.

All email composition and sending is handled here to avoid
duplicating email logic across views.

Each email belongs to one of three categories (see `_should_send`):
- CATEGORY_MANDATORY: magic links, invitations, revocations — always sent.
- CATEGORY_ACTIVITY: user↔user events (bookings, FAQs, reminders, broadcast)
  — opt-out via User.notify_activity.
- CATEGORY_NEWS: digest/newsletter — opt-out via User.notify_news.

Cat. 2 and Cat. 3 emails include a footer with a tokenised link to /me/notifications
that lets recipients change preferences without logging in.

HTML bodies are rendered from the autoescaping ``email/layout.html`` template via
small block builders (``_para``/``_strong``/``_field``/``_list``/``_links``/
``_heading``), so user-supplied values are escaped by the template engine — no
manual ``escape()`` in the body composition. Plain-text bodies (no XSS surface)
stay as plain strings.
"""

import functools
import logging
import random
import smtplib
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.utils.html import escape

from core.services.email_texts import T, viral_lines
from core.utils import redact_email

logger = logging.getLogger(__name__)

CATEGORY_MANDATORY = "mandatory"
CATEGORY_ACTIVITY = "activity"
CATEGORY_NEWS = "news"


_PREFS_TOKEN_SALT = "notifications-prefs"
_PREFS_TOKEN_MAX_AGE = 60 * 60 * 24 * 365  # ~1 year


def make_notifications_token(user):
    """Return a signed, expiring token for the email-footer preferences link.

    A ``TimestampSigner`` signature over the user's code (salt
    ``notifications-prefs``) rather than a stored column: it carries a ~1-year
    TTL and needs no DB lookup or per-user secret to mint. Its blast radius is
    limited to toggling the two notification booleans (see NotificationsByTokenView).
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


# Sentinel for "no prefetched value" — distinct from a looked-up None (the
# recipient has no User row). Lets the multi-recipient senders pass a resolved
# user (or a known-absent None) so _send doesn't re-query _lookup_user per
# recipient.
_UNSET = object()


def _lookup_user(email):
    from django.db.models import Exists, OuterRef

    from core.models import Collection, User

    return (
        User.objects.annotate(
            _owns_collection=Exists(Collection.objects.filter(owner=OuterRef("pk")))
        )
        .filter(email=email)
        .only("code", "notify_activity", "notify_news")
        .first()
    )


def _lookup_users(emails):
    """Bulk-resolve users for a recipient list — one query, not N.

    Returns ``{email: user}`` for the emails that match a User; addresses with no
    User (not-yet-registered invitees) are simply absent, so callers pass
    ``users.get(email)`` (None) and ``_send`` treats them as opted-in non-users
    without firing another lookup.
    """
    from django.db.models import Exists, OuterRef

    from core.models import Collection, User

    return {
        u.email: u
        for u in User.objects.annotate(
            _owns_collection=Exists(Collection.objects.filter(owner=OuterRef("pk")))
        )
        .filter(email__in=list(emails))
        .only("code", "email", "notify_activity", "notify_news")
    }


def _should_send(email, category, user=_UNSET):
    """True unless the recipient has opted out of this category.

    ``user`` may be prefetched by a multi-recipient sender (a User, or None once
    it is known the recipient has no User row); leave it as ``_UNSET`` for the
    single-recipient path, which looks the user up here.
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
        return user.notify_news
    return True


def _filter_recipients(emails, category):
    """Filter a bulk recipient list, removing users who have opted out."""
    if category == CATEGORY_MANDATORY:
        return list(emails)
    from core.models import User

    field = "notify_activity" if category == CATEGORY_ACTIVITY else "notify_news"
    opted_out = set(
        User.objects.filter(email__in=list(emails), **{field: False}).values_list(
            "email", flat=True
        )
    )
    return [e for e in emails if e not in opted_out]


def _frontend_base_url():
    return settings.MAGIC_LINK_BASE_URL.rsplit("/", 1)[0]


def _notifications_link(email, user=_UNSET):
    if user is _UNSET:
        user = _lookup_user(email)
    base = _frontend_base_url()
    if user:
        return f"{base}/me/notifications/{make_notifications_token(user)}"
    return f"{base}/me/notifications"


def _with_footer(plain, html, email, category, user=_UNSET):
    """Append the 'manage your emails' footer for Cat. 2 / Cat. 3 emails."""
    if category == CATEGORY_MANDATORY:
        return plain, html
    link = _notifications_link(email, user=user)
    manage = T("footer_manage")
    footer_plain = f"\n\n---\n{manage}: {link}"
    footer_html = (
        '<hr style="border:none;border-top:1px solid #ddd;margin-top:24px;">'
        '<p style="color:#666;font-size:12px;">'
        f'{escape(manage)}: <a href="{escape(link)}">{escape(link)}</a>'
        "</p>"
    )
    return plain + footer_plain, html + footer_html


def _with_viral_line(plain, html, user=_UNSET):
    """Prepend one random growth blurb above the preferences footer.

    Shown to recipients who don't own a collection — the audience for "create
    your own" — including not-yet-registered invitees (``user`` is None).
    Suppressed for collection owners and when ``VIRAL_LINES`` is empty. The CTA
    is the plain ``/collections/new`` URL, never tracking-wrapped (DESIGN §9).
    """
    lines = viral_lines()
    if not lines:
        return plain, html
    if user is not _UNSET and user and getattr(user, "_owns_collection", False):
        return plain, html
    line = random.choice(lines)
    url = f"{_frontend_base_url()}/collections/new"
    plain += f"\n\n{line['text']}\n{line['cta']}: {url}"
    html += (
        '<p style="margin-top:24px;font-size:13px;">'
        f"{escape(line['text'])} "
        f'<a href="{escape(url)}">{escape(line["cta"])}</a>'
        "</p>"
    )
    return plain, html


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


def _send(to_email, subject, plain, html, category, reply_to=None, user=_UNSET, include_viral=True):
    """Send a single email through the category + footer + viral pipeline.

    Returns True if the email was dispatched, False if the recipient opted out
    or the send failed. A failed send (SMTP error / timeout / socket error / bad
    header) is logged and swallowed — it never propagates, so it cannot 500 a
    user action whose DB work has already committed, nor abort a multi-recipient
    loop or a nightly cron.

    ``user`` lets a multi-recipient sender (broadcast/digest/newsletter) pass a
    batch-resolved User (or a known-absent None) so the preference + footer
    lookups don't fire a query per recipient. Single-recipient callers leave it
    as ``_UNSET`` and the lookup happens here, as before.

    ``include_viral`` prepends a growth CTA above the footer (suppressed for
    collection owners — see ``_with_viral_line``). The two marketing-free
    senders — ``send_magic_link_email`` and ``send_stats_summary_email`` — pass
    ``False``; everything else uses the default.
    """
    # Resolve the recipient User once when something downstream needs it: the
    # preference check (non-mandatory) or the viral-line ownership gate. A
    # mandatory + include_viral=False send (magic link, stats summary) never
    # triggers a lookup here.
    if (category != CATEGORY_MANDATORY or include_viral) and user is _UNSET:
        user = _lookup_user(to_email)
    if not _should_send(to_email, category, user=user):
        return False
    if include_viral:
        plain, html = _with_viral_line(plain, html, user=user)
    plain, html = _with_footer(plain, html, to_email, category, user=user)
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
            msg.attach(logo)
        msg.send()
    except (smtplib.SMTPException, OSError, BadHeaderError) as exc:
        # OSError covers socket.timeout/connection errors (socket.timeout is an
        # OSError subclass). BadHeaderError (a ValueError) guards against a CR/LF
        # that slipped into the subject — caught here so one tainted row can never
        # abort a multi-recipient loop or a nightly digest/newsletter cron.
        # Log the exception class only — str(exc) (e.g. SMTPRecipientsRefused)
        # can carry the raw recipient address, which would defeat redaction (M5).
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


def _field(label, value):
    """A ``Label: value`` line."""
    return {"type": "field", "label": label, "value": value}


def _heading(text):
    """A section heading (``<h3>``)."""
    return {"type": "heading", "text": text}


def _list(items):
    """A bullet list."""
    return {"type": "list", "items": list(items)}


def _links(*links):
    """A row of links, each ``(url, label)``, joined by ``|``."""
    return {"type": "links", "links": [{"url": url, "label": label} for url, label in links]}


def _render_email(blocks):
    """Render the HTML body from a list of blocks through the autoescaping layout.

    ``has_logo`` mirrors whether ``_send()`` will find the asset to attach —
    the ``cid:`` reference is only rendered when there's a matching attachment
    coming, so a missing file never leaves a broken image in the email.
    """
    return render_to_string(
        "email/layout.html", {"blocks": blocks, "has_logo": _logo_bytes() is not None}
    )


def _booking_detail_blocks(booking):
    """Date/quantity detail blocks shared by the three booking emails."""
    if booking.start_date and booking.end_date:
        return [_field(T("dates_label"), f"{booking.start_date} - {booking.end_date}")]
    return []


def _thing_url(thing):
    """Build the frontend URL for a thing (collection-scoped when possible)."""
    base = _frontend_base_url()
    collection = thing.collections.first()
    if collection:
        return f"{base}/collections/{collection.code}/things/{thing.code}"
    return f"{base}/things/{thing.code}"


def _action_noun(thing):
    """The per-type action noun for the booking emails (e.g. 'purchase', 'compra').

    Mirrors the frontend's per-type vocabulary (``thingCard.action`` / ``types``)
    so a SELL request reads 'solicitud de compra' / 'purchase request', a LEND
    request 'solicitud de préstamo' / 'loan request', etc. Only the five bookable
    non-swap types carry a noun — SWAP has its own dedicated templates and WISH
    never books, so this is never called for them.
    """
    return T(f"action_noun_{thing.type}")


# --- Category 1: Mandatory -----------------------------------------------------


def send_magic_link_email(email, magic_link, collection_headline=None):
    """Send magic link authentication email.

    When ``collection_headline`` is given (a pop-in / share-link join), the
    subject names the collection the visitor is joining; without it the generic
    welcome subject is used (``/login`` and the plain onboarding pop-in).
    """
    if collection_headline:
        subject = T("magic_subject_collection").format(collection=collection_headline)
    else:
        subject = T("magic_subject")
    plain = T("magic_plain").format(link=magic_link)
    html = _render_email(
        [
            _para(T("magic_intro")),
            _links((magic_link, T("magic_cta"))),
        ]
    )
    _send(email, subject, plain, html, CATEGORY_MANDATORY, include_viral=False)


def send_collection_invite_email(
    inviter_name, collection_headline, email, accept_link, reject_link
):
    """Send collection invitation email with accept and reject links."""
    subject = T("invite_subject").format(collection=collection_headline)
    plain = T("invite_plain").format(
        collection=collection_headline, accept=accept_link, reject=reject_link
    )
    html = _render_email(
        [
            _para(T("invite_intro").format(inviter=inviter_name)),
            _strong(collection_headline),
            _links((accept_link, T("invite_accept_cta")), (reject_link, T("invite_decline_cta"))),
        ]
    )
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


def send_collection_revoke_email(owner_name, collection_headline, email):
    """Send collection access revoked notification email."""
    subject = T("revoke_subject")
    plain = T("revoke_plain").format(owner=owner_name, collection=collection_headline)
    html = _render_email(
        [
            _para(T("revoke_intro").format(owner=owner_name)),
            _strong(collection_headline),
            _para(T("revoke_outro")),
        ]
    )
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


# --- Category 2: Activity ------------------------------------------------------


def send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link):
    """Send booking request email to owner with accept/reject links."""
    requester_name = requester.display_name
    action = _action_noun(thing)

    if booking.start_date and booking.end_date:
        plain = T("booking_request_plain_dated").format(
            requester=requester_name,
            action=action,
            thing=thing.headline,
            start=booking.start_date,
            end=booking.end_date,
            accept=accept_link,
            reject=reject_link,
        )
    else:
        plain = T("booking_request_plain").format(
            requester=requester_name,
            action=action,
            thing=thing.headline,
            accept=accept_link,
            reject=reject_link,
        )

    subject = T("booking_request_subject").format(action=action)
    html = _render_email(
        [
            _para(T("booking_request_intro").format(requester=requester_name, action=action)),
            _strong(thing.headline),
            *_booking_detail_blocks(booking),
            _links((accept_link, T("hold_confirm_cta")), (reject_link, T("hold_cancel_cta"))),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_decision_email(booking, thing, accepted=True):
    """Send booking accept/reject notification email to requester."""
    decision_word = T("decision_confirmed") if accepted else T("decision_cancelled")
    action = _action_noun(thing)

    if booking.start_date and booking.end_date:
        plain = T("decision_plain_dated").format(
            action=action,
            thing=thing.headline,
            start=booking.start_date,
            end=booking.end_date,
            decision=decision_word,
        )
    else:
        plain = T("decision_plain").format(
            action=action, thing=thing.headline, decision=decision_word
        )

    subject = T("decision_subject")
    html = _render_email(
        [
            _para(T("decision_intro").format(action=action, decision=decision_word)),
            _strong(thing.headline),
            *_booking_detail_blocks(booking),
        ]
    )
    _send(booking.requester_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_unavailable_email(booking, thing):
    """Tell a requester their pending request can no longer be fulfilled.

    Sent when the owner gave or swapped the thing to someone else, so this
    requester's PENDING booking was auto-declined. Warm, non-blaming tone.
    """
    subject = T("unavailable_subject")
    plain = T("unavailable_plain").format(thing=thing.headline)
    html = _render_email(
        [
            _para(T("unavailable_intro").format(thing=thing.headline)),
            _para(T("unavailable_outro")),
        ]
    )
    _send(booking.requester_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_invite_rejected_email(invitee_name, collection_headline, owner_email):
    """Send notification to collection owner that an invite was declined."""
    subject = T("invite_rejected_subject")
    plain = T("invite_rejected_plain").format(invitee=invitee_name, collection=collection_headline)
    html = _render_email(
        [
            _para(T("invite_rejected_intro").format(invitee=invitee_name)),
            _strong(collection_headline),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_confirmation_email(requester, thing, booking):
    """Send booking confirmation email to the requester."""
    owner_name = thing.owner.display_name
    thing_url = _thing_url(thing)
    collection = thing.collections.first()
    action = _action_noun(thing)

    if booking.start_date and booking.end_date:
        plain = T("confirmation_plain_dated").format(
            action=action,
            thing=thing.headline,
            start=booking.start_date,
            end=booking.end_date,
            owner=owner_name,
            url=thing_url,
        )
    else:
        plain = T("confirmation_plain").format(
            action=action, thing=thing.headline, owner=owner_name, url=thing_url
        )

    subject = T("confirmation_subject").format(action=action)
    html = _render_email(
        [
            _para(T("confirmation_intro").format(action=action)),
            _strong(thing.headline),
            *([_field(T("part_of_label"), collection.headline)] if collection else []),
            *_booking_detail_blocks(booking),
            _para(T("confirmation_outro").format(owner=owner_name)),
            _links((thing_url, thing.headline)),
        ]
    )
    _send(requester.email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_question_email(questioner_name, thing, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    thing_url = _thing_url(thing)

    subject = T("faq_question_subject")
    plain = T("faq_question_plain").format(
        questioner=questioner_name, thing=thing.headline, question=question, url=thing_url
    )
    html = _render_email(
        [
            _para(T("faq_question_intro").format(questioner=questioner_name)),
            _strong(thing.headline),
            _field(T("question_label"), question),
            _links((thing_url, T("faq_view_reply_cta"))),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_answer_email(owner_name, thing, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner, linking the thing."""
    thing_url = _thing_url(thing)
    subject = T("faq_answer_subject")
    plain = T("faq_answer_plain").format(
        owner=owner_name, answer=answer, thing=thing.headline, url=thing_url
    )
    html = _render_email(
        [
            _para(T("faq_answer_intro").format(owner=owner_name)),
            _strong(thing.headline),
            _field(T("your_question_label"), question),
            _field(T("reply_label"), answer),
            _links((thing_url, thing.headline)),
        ]
    )
    _send(questioner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_hide_email(owner_name, thing_headline, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    subject = T("faq_hide_subject")
    plain = T("faq_hide_plain").format(owner=owner_name, question=question)
    html = _render_email(
        [
            _para(T("faq_hide_intro").format(owner=owner_name)),
            _strong(thing_headline),
            _field(T("question_label"), question),
        ]
    )
    _send(questioner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_thing_reported_email(thing, owner_email):
    """Notify a thing owner that someone reported their listing.

    The reporter's identity is deliberately never included — the owner learns
    only *that* it was reported and *which* listing, so they can go and check it.
    """
    thing_url = _thing_url(thing)

    subject = T("reported_subject")
    plain = T("reported_plain").format(thing=thing.headline, url=thing_url)
    html = _render_email(
        [
            _para(T("reported_intro")),
            _strong(thing.headline),
            _para(T("reported_outro")),
            _links((thing_url, T("reported_review_cta"))),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_broadcast_email(
    owner_name, owner_email, collection_headline, collection_code, message, emails
):
    """Send a broadcast email from a collection owner to all invitees.

    The subject is auto-generated as "Hey! {collection}" (the owner only writes
    the message). Carries a reply-to header (the owner) and a link to the
    collection — the object that originated the message — so recipients can open
    it in-app.
    """
    collection_url = f"{_frontend_base_url()}/collections/{collection_code}"

    full_subject = T("broadcast_subject").format(collection=collection_headline)
    plain = T("broadcast_plain").format(
        owner=owner_name, collection=collection_headline, message=message, url=collection_url
    )
    html = _render_email(
        [
            _para(T("broadcast_intro").format(owner=owner_name, collection=collection_headline)),
            _para(message),
            _links((collection_url, T("broadcast_help_cta"))),
        ]
    )

    recipients = _filter_recipients(emails, CATEGORY_ACTIVITY)
    users = _lookup_users(recipients)
    for email in recipients:
        _send(
            email,
            full_subject,
            plain,
            html,
            CATEGORY_ACTIVITY,
            reply_to=[owner_email],
            user=users.get(email),
        )


def send_wish_posted_email(creator_name, wish, emails):
    """Notify a community that a member posted a new wish (pedido).

    ``emails`` is the list of group members. Respects each recipient's
    activity opt-out via ``_filter_recipients``.
    """
    wish_url = _thing_url(wish)

    subject = T("wish_posted_subject")
    plain = T("wish_posted_plain").format(creator=creator_name, wish=wish.headline, url=wish_url)
    html = _render_email(
        [
            _para(T("wish_posted_intro").format(creator=creator_name)),
            _strong(wish.headline),
            _links((wish_url, T("wish_posted_cta"))),
        ]
    )
    for email in _filter_recipients(emails, CATEGORY_ACTIVITY):
        _send(email, subject, plain, html, CATEGORY_ACTIVITY)


def send_wish_response_email(responder_name, wish, creator_email):
    """Notify a wish creator that someone answered their pedido."""
    wish_url = _thing_url(wish)

    subject = T("wish_response_subject")
    plain = T("wish_response_plain").format(
        responder=responder_name, wish=wish.headline, url=wish_url
    )
    html = _render_email(
        [
            _para(T("wish_response_intro").format(responder=responder_name)),
            _strong(wish.headline),
            _links((wish_url, T("wish_response_cta"))),
        ]
    )
    _send(creator_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_wish_thanks_email(creator_name, wish, responder_email):
    """Thank the accepted responder when the wish creator marks it resolved."""
    subject = T("wish_thanks_subject")
    plain = T("wish_thanks_plain").format(creator=creator_name, wish=wish.headline)
    html = _render_email(
        [
            _para(T("wish_thanks_intro").format(creator=creator_name)),
            _strong(wish.headline),
            _para(T("wish_thanks_outro")),
        ]
    )
    _send(responder_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_return_reminder_email(requester_name, thing_headline, end_date, owner_email):
    """Remind the owner that a booking ends tomorrow."""
    subject = T("reminder_subject")
    plain = T("reminder_plain").format(requester=requester_name, thing=thing_headline, end=end_date)
    body = T("reminder_body").format(requester=requester_name, thing=thing_headline, end=end_date)
    html = _render_email([_para(body)])
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_swap_request_email(
    requester, thing, offered_things, owner_email, accept_link, reject_link
):
    """Send swap request email to owner with offered thing headlines."""
    requester_name = requester.display_name
    offered_names = ", ".join(t.headline for t in offered_things)

    subject = T("swap_request_subject")
    plain = T("swap_request_plain").format(
        requester=requester_name,
        thing=thing.headline,
        offered=offered_names,
        accept=accept_link,
        reject=reject_link,
    )
    html = _render_email(
        [
            _para(T("swap_request_intro").format(requester=requester_name)),
            _strong(thing.headline),
            _para(T("swap_exchange_label")),
            _list(t.headline for t in offered_things),
            _links((accept_link, T("swap_confirm_cta")), (reject_link, T("swap_cancel_cta"))),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_swap_confirmation_email(requester, thing, offered_things, booking):
    """Send swap request confirmation to the requester."""
    offered_names = ", ".join(t.headline for t in offered_things)

    subject = T("swap_conf_subject")
    plain = T("swap_conf_plain").format(thing=thing.headline, offered=offered_names)
    html = _render_email(
        [
            _para(T("swap_conf_sent")),
            _para(T("swap_conf_requested_label")),
            _strong(thing.headline),
            _para(T("swap_conf_offered_label")),
            _list(t.headline for t in offered_things),
            _para(T("swap_conf_outro")),
        ]
    )
    _send(requester.email, subject, plain, html, CATEGORY_ACTIVITY)


# --- Category 3: News / broadcast ---------------------------------------------


def send_digest_email(collection_headline, collection_code, thing_headlines, emails):
    """Send a digest email listing new things added to a collection."""
    base_url = _frontend_base_url()
    collection_url = f"{base_url}/collections/{collection_code}"

    things_plain = "\n".join(f"  - {h}" for h in thing_headlines)

    subject = T("digest_subject").format(collection=collection_headline)
    plain = T("digest_plain").format(
        collection=collection_headline, things=things_plain, url=collection_url
    )
    html = _render_email(
        [
            _para(T("digest_intro").format(collection=collection_headline)),
            _list(thing_headlines),
            _links((collection_url, T("view_collection_cta"))),
        ]
    )

    recipients = _filter_recipients(emails, CATEGORY_NEWS)
    users = _lookup_users(recipients)
    for email in recipients:
        _send(email, subject, plain, html, CATEGORY_NEWS, user=users.get(email))


def send_stats_summary_email(recipient, subject, sections):
    """Email the first-party stats summary to the platform operator.

    ``sections`` is the structure the ``stats_summary`` command builds: a list of
    ``{"title": str, "rows": [(label, value), ...], "note"?: str}``. Sent as
    CATEGORY_MANDATORY — an internal ops report, not a user notification, so it
    ignores ``notify_*`` prefs and carries no footer. Values are escaped by the
    autoescaping layout (they're aggregate numbers, but the pipeline stays uniform).
    """
    blocks = []
    plain_lines = []
    for section in sections:
        blocks.append(_heading(section["title"]))
        plain_lines.append(section["title"])
        for label, value in section["rows"]:
            blocks.append(_field(label, str(value)))
            plain_lines.append(f"  {label}: {value}")
        if section.get("note"):
            blocks.append(_para(section["note"]))
            plain_lines.append(f"  ({section['note']})")
        plain_lines.append("")

    _send(
        recipient,
        subject,
        "\n".join(plain_lines),
        _render_email(blocks),
        CATEGORY_MANDATORY,
        include_viral=False,
    )


def send_newsletter_email(
    collection_headline, collection_code, new_thing_headlines, transfer_entries, emails
):
    """Send a weekly newsletter for share collections.

    Args:
        collection_headline: The collection name.
        collection_code: 6-char collection code, used to build the
            "View collection" link.
        new_thing_headlines: List of headlines of newly added things.
        transfer_entries: List of dicts with keys: date, thing, from_name, to_name.
        emails: List of recipient email addresses.
    """
    base_url = _frontend_base_url()
    collection_url = f"{base_url}/collections/{collection_code}"

    newsletter_intro = T("newsletter_intro").format(collection=collection_headline)
    blocks = [_para(newsletter_intro)]
    plain_blocks = []

    if new_thing_headlines:
        things_plain = "\n".join(f"  - {h}" for h in new_thing_headlines)
        plain_blocks.append(f"{T('newsletter_new_things')}:\n{things_plain}\n")
        blocks.append(_heading(T("newsletter_new_things")))
        blocks.append(_list(new_thing_headlines))

    if transfer_entries:
        transfers_plain = "\n".join(
            f"  - {t['date']} — {t['thing']}: {t['from_name']} → {t['to_name']}"
            for t in transfer_entries
        )
        plain_blocks.append(f"{T('newsletter_transfers')}:\n{transfers_plain}\n")
        blocks.append(_heading(T("newsletter_transfers")))
        blocks.append(
            _list(
                f"{t['date']} — {t['thing']}: {t['from_name']} → {t['to_name']}"
                for t in transfer_entries
            )
        )

    blocks.append(_links((collection_url, T("view_collection_cta"))))

    subject = T("newsletter_subject").format(collection=collection_headline)
    plain = (
        f"{newsletter_intro}\n\n"
        f"{''.join(b + chr(10) for b in plain_blocks)}"
        f"{T('view_collection_cta')}: {collection_url}"
    )
    html = _render_email(blocks)

    recipients = _filter_recipients(emails, CATEGORY_NEWS)
    users = _lookup_users(recipients)
    for email in recipients:
        _send(email, subject, plain, html, CATEGORY_NEWS, user=users.get(email))
