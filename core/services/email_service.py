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

import logging
import smtplib

from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives, send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.utils.html import escape

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
    from core.models import User

    return User.objects.filter(email=email).only("code", "notify_activity", "notify_news").first()


def _lookup_users(emails):
    """Bulk-resolve users for a recipient list — one query, not N.

    Returns ``{email: user}`` for the emails that match a User; addresses with no
    User (not-yet-registered invitees) are simply absent, so callers pass
    ``users.get(email)`` (None) and ``_send`` treats them as opted-in non-users
    without firing another lookup.
    """
    from core.models import User

    return {
        u.email: u
        for u in User.objects.filter(email__in=list(emails)).only(
            "code", "email", "notify_activity", "notify_news"
        )
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
    footer_plain = f"\n\n---\nManage your email preferences: {link}"
    footer_html = (
        '<hr style="border:none;border-top:1px solid #ddd;margin-top:24px;">'
        '<p style="color:#666;font-size:12px;">'
        f'Manage your email preferences: <a href="{escape(link)}">{escape(link)}</a>'
        "</p>"
    )
    return plain + footer_plain, html + footer_html


def _send(to_email, subject, plain, html, category, reply_to=None, user=_UNSET):
    """Send a single email through the category + footer pipeline.

    Returns True if the email was dispatched, False if the recipient opted out
    or the send failed. A failed send (SMTP error / timeout / socket error / bad
    header) is logged and swallowed — it never propagates, so it cannot 500 a
    user action whose DB work has already committed, nor abort a multi-recipient
    loop or a nightly cron.

    ``user`` lets a multi-recipient sender (broadcast/digest/newsletter) pass a
    batch-resolved User (or a known-absent None) so the preference + footer
    lookups don't fire a query per recipient. Single-recipient callers leave it
    as ``_UNSET`` and the lookup happens here, as before.
    """
    if not _should_send(to_email, category, user=user):
        return False
    plain, html = _with_footer(plain, html, to_email, category, user=user)
    try:
        if reply_to:
            msg = EmailMultiAlternatives(
                subject=subject, body=plain, from_email=None, to=[to_email], reply_to=reply_to
            )
            msg.attach_alternative(html, "text/html")
            msg.send()
        else:
            send_mail(
                subject=subject,
                message=plain,
                from_email=None,
                recipient_list=[to_email],
                html_message=html,
            )
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
    """Render the HTML body from a list of blocks through the autoescaping layout."""
    return render_to_string("email/layout.html", {"blocks": blocks})


def _booking_detail_blocks(booking):
    """Date/quantity detail blocks shared by the three booking emails."""
    if booking.start_date and booking.end_date:
        return [_field("Dates", f"{booking.start_date} - {booking.end_date}")]
    return []


def _thing_url(thing):
    """Build the frontend URL for a thing (collection-scoped when possible)."""
    base = _frontend_base_url()
    collection = thing.collections.first()
    if collection:
        return f"{base}/collections/{collection.code}/things/{thing.code}"
    return f"{base}/things/{thing.code}"


# --- Category 1: Mandatory -----------------------------------------------------


def send_magic_link_email(email, magic_link):
    """Send magic link authentication email."""
    subject = "Hello, welcome to OIUEEI!"
    plain = f"Hello! Click here to sign in: {magic_link}"
    html = _render_email(
        [
            _para("Hello! Click here to sign in:"),
            _links((magic_link, "Sign in")),
        ]
    )
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


def send_collection_invite_email(
    inviter_name, collection_headline, email, accept_link, reject_link
):
    """Send collection invitation email with accept and reject links."""
    subject = "You have an invitation to OIUEEI!"
    plain = (
        f"You have been invited to view: {collection_headline}. "
        f"Accept invitation: {accept_link} | Decline invitation: {reject_link}"
    )
    html = _render_email(
        [
            _para(f"{inviter_name} has invited you to view:"),
            _strong(collection_headline),
            _links((accept_link, "Accept invitation"), (reject_link, "Decline invitation")),
        ]
    )
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


def send_collection_revoke_email(owner_name, collection_headline, email):
    """Send collection access revoked notification email."""
    subject = "Your access has been revoked"
    plain = f"{owner_name} has revoked your access to '{collection_headline}'."
    html = _render_email(
        [
            _para(f"{owner_name} has revoked your access to:"),
            _strong(collection_headline),
            _para("You will no longer be able to view this collection."),
        ]
    )
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


# --- Category 2: Activity ------------------------------------------------------


def send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link):
    """Send booking request email to owner with accept/reject links."""
    requester_name = requester.display_name

    if booking.start_date and booking.end_date:
        plain = (
            f"{requester_name} has requested to hold '{thing.headline}' "
            f"from {booking.start_date} to {booking.end_date}. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
    else:
        plain = (
            f"{requester_name} has requested to hold '{thing.headline}'. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )

    subject = "You have a pending hold request"
    html = _render_email(
        [
            _para(f"{requester_name} has requested:"),
            _strong(thing.headline),
            *_booking_detail_blocks(booking),
            _links((accept_link, "Confirm hold"), (reject_link, "Cancel hold")),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_decision_email(booking, thing, accepted=True):
    """Send booking accept/reject notification email to requester."""
    decision_word = "confirmed" if accepted else "cancelled"

    if booking.start_date and booking.end_date:
        plain = (
            f"Your hold request for '{thing.headline}' "
            f"from {booking.start_date} to {booking.end_date} has been {decision_word}."
        )
    else:
        plain = f"Your hold request for '{thing.headline}' has been {decision_word}."

    subject = "We have news"
    html = _render_email(
        [
            _para(f"Your request has been {decision_word}:"),
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
    subject = "Someone got there first"
    plain = (
        f"'{thing.headline}' went to someone else this time. "
        "No worries — things come and go around here, so keep an eye out!"
    )
    html = _render_email(
        [
            _para(f"{thing.headline} went to someone else this time."),
            _para("No worries — things come and go around here, so keep an eye out!"),
        ]
    )
    _send(booking.requester_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_invite_rejected_email(invitee_name, collection_headline, owner_email):
    """Send notification to collection owner that an invite was declined."""
    subject = "Your invitation was rejected"
    plain = f"{invitee_name} has declined the invitation to '{collection_headline}'."
    html = _render_email(
        [
            _para(f"{invitee_name} has declined your invitation to:"),
            _strong(collection_headline),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_confirmation_email(requester, thing, booking):
    """Send booking confirmation email to the requester."""
    owner_name = thing.owner.display_name
    thing_url = _thing_url(thing)
    collection = thing.collections.first()

    if booking.start_date and booking.end_date:
        plain = (
            f"You've put a hold on '{thing.headline}' from "
            f"{booking.start_date} to {booking.end_date}. "
            f"We've let {owner_name} know — they'll get back to you soon. "
            f"View thing: {thing_url}"
        )
    else:
        plain = (
            f"You've put a hold on '{thing.headline}'. "
            f"We've let {owner_name} know — they'll get back to you soon. View thing: {thing_url}"
        )

    subject = "Hold request sent"
    html = _render_email(
        [
            _para("You've put a hold on:"),
            _strong(thing.headline),
            *([_field("Part of", collection.headline)] if collection else []),
            *_booking_detail_blocks(booking),
            _para(f"We've let {owner_name} know — they'll get back to you soon."),
            _links((thing_url, "View thing")),
        ]
    )
    _send(requester.email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_question_email(questioner_name, thing, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    thing_url = _thing_url(thing)

    subject = "There is a question to be answered"
    plain = (
        f"{questioner_name} has asked about '{thing.headline}': {question} View thing: {thing_url}"
    )
    html = _render_email(
        [
            _para(f"{questioner_name} has asked a question about:"),
            _strong(thing.headline),
            _field("Question", question),
            _links((thing_url, "View and reply")),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_answer_email(owner_name, thing_headline, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner."""
    subject = "Your question has been answered"
    plain = f"{owner_name} has replied: {answer}"
    html = _render_email(
        [
            _para(f"{owner_name} has replied to your question about:"),
            _strong(thing_headline),
            _field("Your question", question),
            _field("Reply", answer),
        ]
    )
    _send(questioner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_hide_email(owner_name, thing_headline, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    subject = "Your question has been hidden"
    plain = f"{owner_name} has hidden your question: {question}"
    html = _render_email(
        [
            _para(f"{owner_name} has hidden your question about:"),
            _strong(thing_headline),
            _field("Question", question),
        ]
    )
    _send(questioner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_thing_reported_email(thing, owner_email):
    """Notify a thing owner that someone reported their listing.

    The reporter's identity is deliberately never included — the owner learns
    only *that* it was reported and *which* listing, so they can go and check it.
    """
    thing_url = _thing_url(thing)

    subject = "Someone reported one of your listings"
    plain = (
        f"Someone reported your listing '{thing.headline}'. "
        f"We don't share who reported it. Please take a look: {thing_url}"
    )
    html = _render_email(
        [
            _para("Someone reported one of your listings:"),
            _strong(thing.headline),
            _para(
                "We don't share who reported it. Please take a look and make sure "
                "everything is in order."
            ),
            _links((thing_url, "Review the listing")),
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

    full_subject = f"Hey! {collection_headline}"
    plain = (
        f"Message from {owner_name} ({collection_headline}):\n\n"
        f"{message}\n\n"
        f"I can help! {collection_url}"
    )
    html = _render_email(
        [
            _para(f"{owner_name} sent a message to {collection_headline}:"),
            _para(message),
            _links((collection_url, "I can help!")),
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

    subject = "A neighbour is looking for something"
    plain = (
        f"{creator_name} posted a new wish: '{wish.headline}'. Can you help? View it: {wish_url}"
    )
    html = _render_email(
        [
            _para(f"{creator_name} posted a new wish:"),
            _strong(wish.headline),
            _links((wish_url, "See if you can help")),
        ]
    )
    for email in _filter_recipients(emails, CATEGORY_ACTIVITY):
        _send(email, subject, plain, html, CATEGORY_ACTIVITY)


def send_wish_response_email(responder_name, wish, creator_email):
    """Notify a wish creator that someone answered their pedido."""
    wish_url = _thing_url(wish)

    subject = "Someone answered your wish"
    plain = f"{responder_name} answered your wish '{wish.headline}'. View the answer: {wish_url}"
    html = _render_email(
        [
            _para(f"{responder_name} answered your wish:"),
            _strong(wish.headline),
            _links((wish_url, "View the answer")),
        ]
    )
    _send(creator_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_wish_thanks_email(creator_name, wish, responder_email):
    """Thank the accepted responder when the wish creator marks it resolved."""
    subject = "Thanks for your help"
    plain = (
        f"{creator_name} marked the wish '{wish.headline}' as resolved "
        f"and wanted to thank you for your help."
    )
    html = _render_email(
        [
            _para(f"{creator_name} marked this wish as resolved:"),
            _strong(wish.headline),
            _para("Thanks for helping out!"),
        ]
    )
    _send(responder_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_return_reminder_email(requester_name, thing_headline, end_date, owner_email):
    """Remind the owner that a booking ends tomorrow."""
    subject = "Reminder: a hold ends tomorrow"
    plain = f"Reminder: {requester_name}'s hold on '{thing_headline}' ends {end_date}."
    html = _render_email(
        [
            _para(f"Reminder: {requester_name}'s hold on {thing_headline} ends {end_date}."),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_swap_request_email(
    requester, thing, offered_things, owner_email, accept_link, reject_link
):
    """Send swap request email to owner with offered thing headlines."""
    requester_name = requester.display_name
    offered_names = ", ".join(t.headline for t in offered_things)

    subject = "You have a swap request"
    plain = (
        f"{requester_name} wants to swap '{thing.headline}' "
        f"for: {offered_names}. "
        f"Confirm swap: {accept_link} | Cancel swap: {reject_link}"
    )
    html = _render_email(
        [
            _para(f"{requester_name} wants to swap:"),
            _strong(thing.headline),
            _para("In exchange for:"),
            _list(t.headline for t in offered_things),
            _links((accept_link, "Confirm swap"), (reject_link, "Cancel swap")),
        ]
    )
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_swap_confirmation_email(requester, thing, offered_things, booking):
    """Send swap request confirmation to the requester."""
    offered_names = ", ".join(t.headline for t in offered_things)

    subject = "Swap request sent"
    plain = (
        f"Your swap request for '{thing.headline}' "
        f"(offering: {offered_names}) has been sent. "
        f"The owner will get back to you soon."
    )
    html = _render_email(
        [
            _para("Your swap request has been sent!"),
            _para("You requested:"),
            _strong(thing.headline),
            _para("You offered:"),
            _list(t.headline for t in offered_things),
            _para("The owner will get back to you soon."),
        ]
    )
    _send(requester.email, subject, plain, html, CATEGORY_ACTIVITY)


# --- Category 3: News / broadcast ---------------------------------------------


def send_digest_email(collection_headline, collection_code, thing_headlines, emails):
    """Send a digest email listing new things added to a collection."""
    base_url = _frontend_base_url()
    collection_url = f"{base_url}/collections/{collection_code}"

    things_plain = "\n".join(f"  - {h}" for h in thing_headlines)

    subject = f"What's new in {collection_headline}"
    plain = (
        f"New things in {collection_headline}:\n\n"
        f"{things_plain}\n\n"
        f"View collection: {collection_url}"
    )
    html = _render_email(
        [
            _para(f"New things in {collection_headline}:"),
            _list(thing_headlines),
            _links((collection_url, "View collection")),
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

    _send(recipient, subject, "\n".join(plain_lines), _render_email(blocks), CATEGORY_MANDATORY)


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

    blocks = [_para(f"Newsletter for {collection_headline}:")]
    plain_blocks = []

    if new_thing_headlines:
        things_plain = "\n".join(f"  - {h}" for h in new_thing_headlines)
        plain_blocks.append(f"New things:\n{things_plain}\n")
        blocks.append(_heading("New things"))
        blocks.append(_list(new_thing_headlines))

    if transfer_entries:
        transfers_plain = "\n".join(
            f"  - {t['date']} — {t['thing']}: {t['from_name']} → {t['to_name']}"
            for t in transfer_entries
        )
        plain_blocks.append(f"Ownership changes:\n{transfers_plain}\n")
        blocks.append(_heading("Ownership changes"))
        blocks.append(
            _list(
                f"{t['date']} — {t['thing']}: {t['from_name']} → {t['to_name']}"
                for t in transfer_entries
            )
        )

    blocks.append(_links((collection_url, "View collection")))

    subject = f"Weekly newsletter: {collection_headline}"
    plain = (
        f"Newsletter for {collection_headline}:\n\n"
        f"{''.join(b + chr(10) for b in plain_blocks)}"
        f"View collection: {collection_url}"
    )
    html = _render_email(blocks)

    recipients = _filter_recipients(emails, CATEGORY_NEWS)
    users = _lookup_users(recipients)
    for email in recipients:
        _send(email, subject, plain, html, CATEGORY_NEWS, user=users.get(email))
