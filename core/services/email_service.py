"""
Centralized email service for OIUEEI.

All email composition and sending is handled here to avoid
duplicating email logic across views.

Each email belongs to one of three categories (see `_should_send`):
- CATEGORY_MANDATORY: magic links, invitations, revocations — always sent.
- CATEGORY_ACTIVITY: user↔user events (bookings, FAQs, reminders)
  — opt-out via User.notify_activity.
- CATEGORY_NEWS: broadcast/digest/newsletter — opt-out via User.notify_news.

Cat. 2 and Cat. 3 emails include a footer with a tokenised link to /me/notifications
that lets recipients change preferences without logging in.
"""

import logging
import smtplib

from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives, send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
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


def _lookup_user(email):
    from core.models import User

    return User.objects.filter(email=email).only("code", "notify_activity", "notify_news").first()


def _should_send(email, category):
    """True unless the recipient has opted out of this category."""
    if category == CATEGORY_MANDATORY:
        return True
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


def _notifications_link(email):
    user = _lookup_user(email)
    base = _frontend_base_url()
    if user:
        return f"{base}/me/notifications/{make_notifications_token(user)}"
    return f"{base}/me/notifications"


def _with_footer(plain, html, email, category):
    """Append the 'manage your emails' footer for Cat. 2 / Cat. 3 emails."""
    if category == CATEGORY_MANDATORY:
        return plain, html
    link = _notifications_link(email)
    footer_plain = f"\n\n---\nManage your email preferences: {link}"
    footer_html = (
        '<hr style="border:none;border-top:1px solid #ddd;margin-top:24px;">'
        '<p style="color:#666;font-size:12px;">'
        f'Manage your email preferences: <a href="{escape(link)}">{escape(link)}</a>'
        "</p>"
    )
    return plain + footer_plain, html + footer_html


def _send(to_email, subject, plain, html, category, reply_to=None):
    """Send a single email through the category + footer pipeline.

    Returns True if the email was dispatched, False if the recipient opted out
    or the send failed. A failed send (SMTP error / timeout / socket error / bad
    header) is logged and swallowed — it never propagates, so it cannot 500 a
    user action whose DB work has already committed, nor abort a multi-recipient
    loop or a nightly cron.
    """
    if not _should_send(to_email, category):
        return False
    plain, html = _with_footer(plain, html, to_email, category)
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
        logger.error(
            "Email send failed (to=%s, subject=%r): %s", redact_email(to_email), subject, exc
        )
        return False
    return True


# --- Category 1: Mandatory -----------------------------------------------------


def send_magic_link_email(email, magic_link):
    """Send magic link authentication email."""
    subject = "Hello, welcome to OIUEEI!"
    plain = f"Hello! Click here to sign in: {magic_link}"
    html = f"""
        <html>
        <p>Hello! Click here to sign in:</p>
        <a href="{magic_link}">Sign in</a>
        </html>
        """
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


def send_collection_invite_email(
    inviter_name, collection_headline, email, accept_link, reject_link
):
    """Send collection invitation email with accept and reject links."""
    safe_inviter = escape(inviter_name)
    safe_headline = escape(collection_headline)

    subject = "You have an invitation to OIUEEI!"
    plain = (
        f"You have been invited to view: {collection_headline}. "
        f"Accept invitation: {accept_link} | Decline invitation: {reject_link}"
    )
    html = f"""
        <html>
        <p>{safe_inviter} has invited you to view:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>
            <a href="{accept_link}">Accept invitation</a> |
            <a href="{reject_link}">Decline invitation</a>
        </p>
        </html>
        """
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


def send_collection_revoke_email(owner_name, collection_headline, email):
    """Send collection access revoked notification email."""
    safe_owner = escape(owner_name)
    safe_headline = escape(collection_headline)

    subject = "Your access has been revoked"
    plain = f"{owner_name} has revoked your access to '{collection_headline}'."
    html = f"""
        <html>
        <p>{safe_owner} has revoked your access to:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>You will no longer be able to view this collection.</p>
        </html>
        """
    _send(email, subject, plain, html, CATEGORY_MANDATORY)


# --- Category 2: Activity ------------------------------------------------------


def send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link):
    """Send booking request email to owner with accept/reject links."""
    requester_name = requester.display_name
    safe_requester_name = escape(requester_name)
    safe_headline = escape(thing.headline)

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        plain = (
            f"{requester_name} has requested to hold '{thing.headline}' "
            f"from {booking.start_date} to {booking.end_date}. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
        html_extra = f"<p>Dates: {safe_start} - {safe_end}</p>"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        plain = (
            f"{requester_name} has requested {booking.quantity}x '{thing.headline}' "
            f"for {booking.delivery_date}. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
        html_extra = f"<p>Quantity: {safe_quantity}</p><p>Delivery date: {safe_delivery}</p>"
    else:
        plain = (
            f"{requester_name} has requested to hold '{thing.headline}'. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
        html_extra = ""

    subject = "You have a pending hold request"
    html = f"""
        <html>
        <p><strong>{safe_requester_name}</strong> has requested:</p>
        <p><strong>{safe_headline}</strong></p>
        {html_extra}
        <p>
            <a href="{accept_link}">Confirm hold</a> |
            <a href="{reject_link}">Cancel hold</a>
        </p>
        </html>
        """
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_decision_email(booking, thing, accepted=True):
    """Send booking accept/reject notification email to requester."""
    decision_word = "confirmed" if accepted else "cancelled"
    safe_decision_word = escape(decision_word)
    safe_headline = escape(thing.headline)

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        plain = (
            f"Your hold request for '{thing.headline}' "
            f"from {booking.start_date} to {booking.end_date} has been {decision_word}."
        )
        html_extra = f"<p>Dates: {safe_start} - {safe_end}</p>"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        plain = (
            f"Your order of {booking.quantity}x '{thing.headline}' "
            f"for {booking.delivery_date} has been {decision_word}."
        )
        html_extra = f"<p>Quantity: {safe_quantity}</p><p>Delivery date: {safe_delivery}</p>"
    else:
        plain = f"Your hold request for '{thing.headline}' has been {decision_word}."
        html_extra = ""

    subject = "We have news"
    html = f"""
        <html>
        <p>Your request has been <strong>{safe_decision_word}</strong>:</p>
        <p><strong>{safe_headline}</strong></p>
        {html_extra}
        </html>
        """
    _send(booking.requester_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_unavailable_email(booking, thing):
    """Tell a requester their pending request can no longer be fulfilled.

    Sent when the owner gave or swapped the thing to someone else, so this
    requester's PENDING booking was auto-declined. Warm, non-blaming tone.
    """
    safe_headline = escape(thing.headline)

    subject = "Someone got there first"
    plain = (
        f"'{thing.headline}' went to someone else this time. "
        "No worries — things come and go around here, so keep an eye out!"
    )
    html = f"""
        <html>
        <p><strong>{safe_headline}</strong> went to someone else this time.</p>
        <p>No worries — things come and go around here, so keep an eye out!</p>
        </html>
        """
    _send(booking.requester_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_invite_rejected_email(invitee_name, collection_headline, owner_email):
    """Send notification to collection owner that an invite was declined."""
    safe_invitee = escape(invitee_name)
    safe_headline = escape(collection_headline)

    subject = "Your invitation was rejected"
    plain = f"{invitee_name} has declined the invitation to '{collection_headline}'."
    html = f"""
        <html>
        <p><strong>{safe_invitee}</strong> has declined your invitation to:</p>
        <p><strong>{safe_headline}</strong></p>
        </html>
        """
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_booking_confirmation_email(requester, thing, booking):
    """Send booking confirmation email to the requester."""
    safe_headline = escape(thing.headline)
    owner_name = thing.owner.display_name
    safe_owner = escape(owner_name)

    base_url = _frontend_base_url()
    collection = thing.collections.first()
    if collection:
        thing_url = f"{base_url}/collections/{collection.code}/things/{thing.code}"
    else:
        thing_url = f"{base_url}/things/{thing.code}"
    safe_collection = escape(collection.headline) if collection else None

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        plain = (
            f"You've put a hold on '{thing.headline}' from "
            f"{booking.start_date} to {booking.end_date}. "
            f"We've let {owner_name} know — they'll get back to you soon. "
            f"View thing: {thing_url}"
        )
        html_extra = f"<p>Dates: {safe_start} — {safe_end}</p>"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        plain = (
            f"You've requested {booking.quantity}x '{thing.headline}' for {booking.delivery_date}. "
            f"We've let {owner_name} know — they'll get back to you soon. View thing: {thing_url}"
        )
        html_extra = f"<p>Quantity: {safe_quantity}</p><p>Delivery: {safe_delivery}</p>"
    else:
        plain = (
            f"You've put a hold on '{thing.headline}'. "
            f"We've let {owner_name} know — they'll get back to you soon. View thing: {thing_url}"
        )
        html_extra = ""

    collection_line = (
        f"<p>Part of: <strong>{safe_collection}</strong></p>" if safe_collection else ""
    )

    subject = "Hold request sent"
    html = f"""
        <html>
        <p>You've put a hold on:</p>
        <p><strong>{safe_headline}</strong></p>
        {collection_line}
        {html_extra}
        <p>We've let <strong>{safe_owner}</strong> know — they'll get back to you soon.</p>
        <p><a href="{thing_url}">View thing</a></p>
        </html>
        """
    _send(requester.email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_question_email(questioner_name, thing, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    safe_questioner = escape(questioner_name)
    safe_headline = escape(thing.headline)
    safe_question = escape(question)

    base_url = _frontend_base_url()
    collection = thing.collections.first()
    if collection:
        thing_url = f"{base_url}/collections/{collection.code}/things/{thing.code}"
    else:
        thing_url = f"{base_url}/things/{thing.code}"

    subject = "There is a question to be answered"
    plain = (
        f"{questioner_name} has asked about '{thing.headline}': {question} "
        f"View thing: {thing_url}"
    )
    html = f"""
        <html>
        <p><strong>{safe_questioner}</strong> has asked a question about:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>Question: {safe_question}</p>
        <p><a href="{thing_url}">View and reply</a></p>
        </html>
        """
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_answer_email(owner_name, thing_headline, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)
    safe_answer = escape(answer)

    subject = "Your question has been answered"
    plain = f"{owner_name} has replied: {answer}"
    html = f"""
        <html>
        <p><strong>{safe_owner}</strong> has replied to your question about:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>Your question: {safe_question}</p>
        <p>Reply: {safe_answer}</p>
        </html>
        """
    _send(questioner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_faq_hide_email(owner_name, thing_headline, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)

    subject = "Your question has been hidden"
    plain = f"{owner_name} has hidden your question: {question}"
    html = f"""
        <html>
        <p><strong>{safe_owner}</strong> has hidden your question about:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>Question: {safe_question}</p>
        </html>
        """
    _send(questioner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_broadcast_email(
    owner_name, owner_email, collection_headline, collection_code, message, emails
):
    """Send a broadcast email from a collection owner to all invitees.

    The subject is auto-generated as "Hey! {collection}" (the owner only writes
    the message). Carries a reply-to header (the owner) and a link to the
    collection — the object that originated the message — so recipients can open
    it in-app.
    """
    safe_owner = escape(owner_name)
    safe_collection = escape(collection_headline)
    safe_message = escape(message)
    collection_url = f"{_frontend_base_url()}/collections/{collection_code}"

    full_subject = f"Hey! {collection_headline}"
    plain = (
        f"Message from {owner_name} ({collection_headline}):\n\n"
        f"{message}\n\n"
        f"I can help! {collection_url}"
    )
    html = f"""
        <html>
        <p><strong>{safe_owner}</strong> sent a message to <strong>{safe_collection}</strong>:</p>
        <p>{safe_message}</p>
        <p><a href="{collection_url}">I can help!</a></p>
        </html>
        """

    for email in _filter_recipients(emails, CATEGORY_ACTIVITY):
        _send(email, full_subject, plain, html, CATEGORY_ACTIVITY, reply_to=[owner_email])


def _thing_url(thing):
    """Build the frontend URL for a thing (collection-scoped when possible)."""
    base = _frontend_base_url()
    collection = thing.collections.first()
    if collection:
        return f"{base}/collections/{collection.code}/things/{thing.code}"
    return f"{base}/things/{thing.code}"


def send_wish_posted_email(creator_name, wish, emails):
    """Notify a community that a member posted a new wish (pedido).

    ``emails`` is the list of group members. Respects each recipient's
    activity opt-out via ``_filter_recipients``.
    """
    safe_creator = escape(creator_name)
    safe_headline = escape(wish.headline)
    wish_url = _thing_url(wish)

    subject = "A neighbour is looking for something"
    plain = (
        f"{creator_name} posted a new wish: '{wish.headline}'. "
        f"Can you help? View it: {wish_url}"
    )
    html = f"""
        <html>
        <p><strong>{safe_creator}</strong> posted a new wish:</p>
        <p><strong>{safe_headline}</strong></p>
        <p><a href="{wish_url}">See if you can help</a></p>
        </html>
        """
    for email in _filter_recipients(emails, CATEGORY_ACTIVITY):
        _send(email, subject, plain, html, CATEGORY_ACTIVITY)


def send_wish_response_email(responder_name, wish, creator_email):
    """Notify a wish creator that someone answered their pedido."""
    safe_responder = escape(responder_name)
    safe_headline = escape(wish.headline)
    wish_url = _thing_url(wish)

    subject = "Someone answered your wish"
    plain = (
        f"{responder_name} answered your wish '{wish.headline}'. " f"View the answer: {wish_url}"
    )
    html = f"""
        <html>
        <p><strong>{safe_responder}</strong> answered your wish:</p>
        <p><strong>{safe_headline}</strong></p>
        <p><a href="{wish_url}">View the answer</a></p>
        </html>
        """
    _send(creator_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_wish_thanks_email(creator_name, wish, responder_email):
    """Thank the accepted responder when the wish creator marks it resolved."""
    safe_creator = escape(creator_name)
    safe_headline = escape(wish.headline)

    subject = "Thanks for your help"
    plain = (
        f"{creator_name} marked the wish '{wish.headline}' as resolved "
        f"and wanted to thank you for your help."
    )
    html = f"""
        <html>
        <p><strong>{safe_creator}</strong> marked this wish as resolved:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>Thanks for helping out!</p>
        </html>
        """
    _send(responder_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_return_reminder_email(requester_name, thing_headline, end_date, owner_email):
    """Remind the owner that a booking ends tomorrow."""
    safe_requester = escape(requester_name)
    safe_headline = escape(thing_headline)
    safe_date = escape(str(end_date))

    subject = "Reminder: a hold ends tomorrow"
    plain = f"Reminder: {requester_name}'s hold on '{thing_headline}' ends {end_date}."
    html = f"""
        <html>
        <p>Reminder: <strong>{safe_requester}</strong>'s hold on
        <strong>{safe_headline}</strong> ends <strong>{safe_date}</strong>.</p>
        </html>
        """
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_delivery_reminder_email(requester_name, thing_headline, delivery_date, owner_email):
    """Remind the owner that a delivery is due tomorrow."""
    safe_requester = escape(requester_name)
    safe_headline = escape(thing_headline)
    safe_date = escape(str(delivery_date))

    subject = "Reminder: a delivery is due tomorrow"
    plain = (
        f"Reminder: {requester_name}'s order of '{thing_headline}' "
        f"is due for delivery {delivery_date}."
    )
    html = f"""
        <html>
        <p>Reminder: <strong>{safe_requester}</strong>'s order of
        <strong>{safe_headline}</strong> is due for delivery
        <strong>{safe_date}</strong>.</p>
        </html>
        """
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_documents_email(requester_email, thing_headline, documents):
    """Send document download links to the requester after booking acceptance."""
    import cloudinary.utils

    safe_headline = escape(thing_headline)

    doc_links = []
    for doc in documents:
        url, _ = cloudinary.utils.cloudinary_url(doc["public_id"], resource_type="raw")
        doc_links.append({"filename": doc["filename"], "url": url})

    plain_links = "\n".join(f"  - {d['filename']}: {d['url']}" for d in doc_links)
    html_links = "".join(
        f'<li><a href="{d["url"]}">{escape(d["filename"])}</a></li>' for d in doc_links
    )

    subject = f"Documents for {thing_headline}"
    plain = (
        f"Here are the documents for '{thing_headline}':\n\n"
        f"{plain_links}\n\n"
        f"Log in to OIUEEI to see more."
    )
    html = f"""
        <html>
        <p>Here are the documents for <strong>{safe_headline}</strong>:</p>
        <ul>{html_links}</ul>
        <p>Log in to OIUEEI to see more.</p>
        </html>
        """
    _send(requester_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_swap_request_email(
    requester, thing, offered_things, owner_email, accept_link, reject_link
):
    """Send swap request email to owner with offered thing headlines."""
    requester_name = requester.display_name
    safe_requester_name = escape(requester_name)
    safe_headline = escape(thing.headline)
    offered_names = ", ".join(t.headline for t in offered_things)
    offered_html = "".join(f"<li>{escape(t.headline)}</li>" for t in offered_things)

    subject = "You have a swap request"
    plain = (
        f"{requester_name} wants to swap '{thing.headline}' "
        f"for: {offered_names}. "
        f"Confirm swap: {accept_link} | Cancel swap: {reject_link}"
    )
    html = f"""
        <html>
        <p><strong>{safe_requester_name}</strong> wants to swap:</p>
        <p><strong>{safe_headline}</strong></p>
        <p>In exchange for:</p>
        <ul>{offered_html}</ul>
        <p>
            <a href="{accept_link}">Confirm swap</a> |
            <a href="{reject_link}">Cancel swap</a>
        </p>
        </html>
        """
    _send(owner_email, subject, plain, html, CATEGORY_ACTIVITY)


def send_swap_confirmation_email(requester, thing, offered_things, booking):
    """Send swap request confirmation to the requester."""
    safe_headline = escape(thing.headline)
    offered_names = ", ".join(t.headline for t in offered_things)
    offered_html = "".join(f"<li>{escape(t.headline)}</li>" for t in offered_things)

    subject = "Swap request sent"
    plain = (
        f"Your swap request for '{thing.headline}' "
        f"(offering: {offered_names}) has been sent. "
        f"The owner will get back to you soon."
    )
    html = f"""
        <html>
        <p>Your swap request has been sent!</p>
        <p>You requested: <strong>{safe_headline}</strong></p>
        <p>You offered:</p>
        <ul>{offered_html}</ul>
        <p>The owner will get back to you soon.</p>
        </html>
        """
    _send(requester.email, subject, plain, html, CATEGORY_ACTIVITY)


# --- Category 3: News / broadcast ---------------------------------------------


def send_digest_email(collection_headline, collection_code, thing_headlines, emails):
    """Send a digest email listing new things added to a collection."""
    safe_collection = escape(collection_headline)
    base_url = _frontend_base_url()
    collection_url = f"{base_url}/collections/{collection_code}"

    things_plain = "\n".join(f"  - {h}" for h in thing_headlines)
    things_html = "".join(f"<li>{escape(h)}</li>" for h in thing_headlines)

    subject = f"What's new in {collection_headline}"
    plain = (
        f"New things in {collection_headline}:\n\n"
        f"{things_plain}\n\n"
        f"View collection: {collection_url}"
    )
    html = f"""
        <html>
        <p>New things in <strong>{safe_collection}</strong>:</p>
        <ul>{things_html}</ul>
        <p><a href="{collection_url}">View collection</a></p>
        </html>
        """

    for email in _filter_recipients(emails, CATEGORY_NEWS):
        _send(email, subject, plain, html, CATEGORY_NEWS)


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
    safe_collection = escape(collection_headline)
    base_url = _frontend_base_url()
    collection_url = f"{base_url}/collections/{collection_code}"

    if new_thing_headlines:
        things_plain = "\n".join(f"  - {h}" for h in new_thing_headlines)
        things_html = "".join(f"<li>{escape(h)}</li>" for h in new_thing_headlines)
        block1_plain = f"New things:\n{things_plain}\n\n"
        block1_html = f"<h3>New things</h3><ul>{things_html}</ul>"
    else:
        block1_plain = ""
        block1_html = ""

    if transfer_entries:
        transfers_plain = "\n".join(
            f"  - {t['date']} — {t['thing']}: {t['from_name']} → {t['to_name']}"
            for t in transfer_entries
        )
        transfers_html = "".join(
            f"<li>{escape(str(t['date']))} — {escape(t['thing'])}: "
            f"{escape(t['from_name'])} → {escape(t['to_name'])}</li>"
            for t in transfer_entries
        )
        block2_plain = f"Ownership changes:\n{transfers_plain}\n\n"
        block2_html = f"<h3>Ownership changes</h3><ul>{transfers_html}</ul>"
    else:
        block2_plain = ""
        block2_html = ""

    subject = f"Weekly newsletter: {collection_headline}"
    plain = (
        f"Newsletter for {collection_headline}:\n\n"
        f"{block1_plain}{block2_plain}"
        f"View collection: {collection_url}"
    )
    html = f"""
        <html>
        <p>Newsletter for <strong>{safe_collection}</strong>:</p>
        {block1_html}
        {block2_html}
        <p><a href="{collection_url}">View collection</a></p>
        </html>
        """

    for email in _filter_recipients(emails, CATEGORY_NEWS):
        _send(email, subject, plain, html, CATEGORY_NEWS)
