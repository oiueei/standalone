"""
Centralized email service for OIUEEI.

All email composition and sending is handled here to avoid
duplicating email logic across views.
"""

from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils.html import escape


def send_magic_link_email(email, magic_link):
    """Send magic link authentication email."""
    send_mail(
        subject="Hello, welcome to OIUEEI!",
        message=f"Hello! Click here to sign in: {magic_link}",
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>Hello! Click here to sign in:</p>
            <a href="{magic_link}">Sign in</a>
            </html>
            """,
    )


def send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link):
    """Send booking request email to owner with accept/reject links."""
    requester_name = requester.name or requester.email
    safe_requester_name = escape(requester_name)
    safe_headline = escape(thing.headline)

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        message = (
            f"{requester_name} has requested to hold '{thing.headline}' "
            f"from {booking.start_date} to {booking.end_date}. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
        html_extra = f"<p>Dates: {safe_start} - {safe_end}</p>"
        subject = "You have a pending hold request"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        message = (
            f"{requester_name} has requested {booking.quantity}x '{thing.headline}' "
            f"for {booking.delivery_date}. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
        html_extra = f"<p>Quantity: {safe_quantity}</p>" f"<p>Delivery date: {safe_delivery}</p>"
        subject = "You have a pending hold request"
    else:
        message = (
            f"{requester_name} has requested to hold '{thing.headline}'. "
            f"Confirm hold: {accept_link} | Cancel hold: {reject_link}"
        )
        html_extra = ""
        subject = "You have a pending hold request"

    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_requester_name}</strong> has requested:</p>
            <p><strong>{safe_headline}</strong></p>
            {html_extra}
            <p>
                <a href="{accept_link}">Confirm hold</a> |
                <a href="{reject_link}">Cancel hold</a>
            </p>
            </html>
            """,
    )


def send_booking_decision_email(booking, thing, accepted=True):
    """Send booking accept/reject notification email to requester."""
    if accepted:
        decision_word = "confirmed"
    else:
        decision_word = "cancelled"

    safe_decision_word = escape(decision_word)
    safe_headline = escape(thing.headline)

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        message = (
            f"Your hold request for '{thing.headline}' "
            f"from {booking.start_date} to {booking.end_date} has been {decision_word}."
        )
        html_extra = f"<p>Dates: {safe_start} - {safe_end}</p>"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        message = (
            f"Your order of {booking.quantity}x '{thing.headline}' "
            f"for {booking.delivery_date} has been {decision_word}."
        )
        html_extra = f"<p>Quantity: {safe_quantity}</p>" f"<p>Delivery date: {safe_delivery}</p>"
    else:
        message = f"Your hold request for '{thing.headline}' has been {decision_word}."
        html_extra = ""

    send_mail(
        subject="We have news",
        message=message,
        from_email=None,
        recipient_list=[booking.requester_email],
        html_message=f"""
            <html>
            <p>Your request has been <strong>{safe_decision_word}</strong>:</p>
            <p><strong>{safe_headline}</strong></p>
            {html_extra}
            </html>
            """,
    )


def send_collection_invite_email(
    inviter_name, collection_headline, email, accept_link, reject_link
):
    """Send collection invitation email with accept and reject links."""
    safe_inviter = escape(inviter_name)
    safe_headline = escape(collection_headline)

    send_mail(
        subject="You have an invitation to OIUEEI!",
        message=(
            f"You have been invited to view: {collection_headline}. "
            f"Accept invitation: {accept_link} | Decline invitation: {reject_link}"
        ),
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>{safe_inviter} has invited you to view:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>
                <a href="{accept_link}">Accept invitation</a> |
                <a href="{reject_link}">Decline invitation</a>
            </p>
            </html>
            """,
    )


def send_invite_rejected_email(invitee_name, collection_headline, owner_email):
    """Send notification to collection owner that an invite was declined."""
    safe_invitee = escape(invitee_name)
    safe_headline = escape(collection_headline)

    send_mail(
        subject="Your invitation was rejected",
        message=f"{invitee_name} has declined the invitation to '{collection_headline}'.",
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_invitee}</strong> has declined your invitation to:</p>
            <p><strong>{safe_headline}</strong></p>
            </html>
            """,
    )


def send_collection_revoke_email(owner_name, collection_headline, email):
    """Send collection access revoked notification email."""
    safe_owner = escape(owner_name)
    safe_headline = escape(collection_headline)

    send_mail(
        subject="Your access has been revoked",
        message=(f"{owner_name} has revoked your access to '{collection_headline}'."),
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>{safe_owner} has revoked your access to:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>You will no longer be able to view this collection.</p>
            </html>
            """,
    )


def send_booking_confirmation_email(requester, thing, booking):
    """Send booking confirmation email to the requester."""
    from django.conf import settings

    safe_headline = escape(thing.headline)
    owner_name = thing.owner.name or thing.owner.email
    safe_owner = escape(owner_name)

    base_url = settings.MAGIC_LINK_BASE_URL.rsplit("/", 1)[0]
    collection = thing.collections.first()
    if collection:
        thing_url = f"{base_url}/collections/{collection.code}/things/{thing.code}"
    else:
        thing_url = f"{base_url}/things/{thing.code}"
    safe_collection = escape(collection.headline) if collection else None

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        message = (
            f"You've put a hold on '{thing.headline}' from {booking.start_date} to {booking.end_date}. "
            f"We've let {owner_name} know — they'll get back to you soon. View thing: {thing_url}"
        )
        html_extra = f"<p>Dates: {safe_start} — {safe_end}</p>"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        message = (
            f"You've requested {booking.quantity}x '{thing.headline}' for {booking.delivery_date}. "
            f"We've let {owner_name} know — they'll get back to you soon. View thing: {thing_url}"
        )
        html_extra = f"<p>Quantity: {safe_quantity}</p><p>Delivery: {safe_delivery}</p>"
    else:
        message = (
            f"You've put a hold on '{thing.headline}'. "
            f"We've let {owner_name} know — they'll get back to you soon. View thing: {thing_url}"
        )
        html_extra = ""

    collection_line = (
        f"<p>Part of: <strong>{safe_collection}</strong></p>" if safe_collection else ""
    )

    send_mail(
        subject="Hold request sent",
        message=message,
        from_email=None,
        recipient_list=[requester.email],
        html_message=f"""
            <html>
            <p>You've put a hold on:</p>
            <p><strong>{safe_headline}</strong></p>
            {collection_line}
            {html_extra}
            <p>We've let <strong>{safe_owner}</strong> know — they'll get back to you soon.</p>
            <p><a href="{thing_url}">View thing</a></p>
            </html>
            """,
    )


def send_faq_question_email(questioner_name, thing, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    from django.conf import settings

    safe_questioner = escape(questioner_name)
    safe_headline = escape(thing.headline)
    safe_question = escape(question)

    # Build link to thing page
    base_url = settings.MAGIC_LINK_BASE_URL.rsplit("/", 1)[0]
    collection = thing.collections.first()
    if collection:
        thing_url = f"{base_url}/collections/{collection.code}/things/{thing.code}"
    else:
        thing_url = f"{base_url}/things/{thing.code}"

    send_mail(
        subject="There is a question to be answered",
        message=(
            f"{questioner_name} has asked about '{thing.headline}': {question} "
            f"View thing: {thing_url}"
        ),
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_questioner}</strong> has asked a question about:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Question: {safe_question}</p>
            <p><a href="{thing_url}">View and reply</a></p>
            </html>
            """,
    )


def send_faq_answer_email(owner_name, thing_headline, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)
    safe_answer = escape(answer)

    send_mail(
        subject="Your question has been answered",
        message=f"{owner_name} has replied: {answer}",
        from_email=None,
        recipient_list=[questioner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_owner}</strong> has replied to your question about:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Your question: {safe_question}</p>
            <p>Reply: {safe_answer}</p>
            </html>
            """,
    )


def send_faq_hide_email(owner_name, thing_headline, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)

    send_mail(
        subject="Your question has been hidden",
        message=f"{owner_name} has hidden your question: {question}",
        from_email=None,
        recipient_list=[questioner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_owner}</strong> has hidden your question about:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Question: {safe_question}</p>
            </html>
            """,
    )


def send_event_announcement_email(
    owner_name, thing_headline, event_date, collection_headline, emails
):
    """Send event announcement email to all collection invitees."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_collection = escape(collection_headline)
    date_str = event_date.strftime("%d %B %Y, %H:%M") if event_date else ""

    subject = f"New event: {thing_headline}"
    plain = f"{owner_name} has created a new event in {collection_headline}: " f"{thing_headline}."
    if date_str:
        plain += f" Date: {date_str}."

    html = f"""
        <html>
        <p><strong>{safe_owner}</strong> has created a new event in <strong>{safe_collection}</strong>:</p>
        <p><strong>{safe_headline}</strong></p>
        {"<p>Date: " + escape(date_str) + "</p>" if date_str else ""}
        </html>
        """

    for email in emails:
        send_mail(
            subject=subject,
            message=plain,
            from_email=None,
            recipient_list=[email],
            html_message=html,
        )


def send_broadcast_email(owner_name, owner_email, collection_headline, subject, message, emails):
    """Send a broadcast email from a collection owner to all invitees.

    Includes reply-to header so invitees can respond directly to the owner.
    """
    safe_owner = escape(owner_name)
    safe_collection = escape(collection_headline)
    safe_subject = escape(subject)
    safe_message = escape(message)

    full_subject = f"[{collection_headline}] {subject}"
    plain = (
        f"Message from {owner_name} ({collection_headline}):\n\n"
        f"{message}\n\n"
        f"Reply directly to this email to respond to {owner_name}."
    )

    html = f"""
        <html>
        <p><strong>{safe_owner}</strong> sent a message to <strong>{safe_collection}</strong>:</p>
        <p><strong>{safe_subject}</strong></p>
        <p>{safe_message}</p>
        <p><em>Reply directly to this email to respond to {safe_owner}.</em></p>
        </html>
        """

    for email in emails:
        msg = EmailMultiAlternatives(
            subject=full_subject,
            body=plain,
            from_email=None,
            to=[email],
            reply_to=[owner_email],
        )
        msg.attach_alternative(html, "text/html")
        msg.send()


def send_digest_email(collection_headline, thing_headlines, emails):
    """Send a digest email listing new things added to a collection."""
    safe_collection = escape(collection_headline)

    things_plain = "\n".join(f"  - {h}" for h in thing_headlines)
    things_html = "".join(f"<li>{escape(h)}</li>" for h in thing_headlines)

    subject = f"What's new in {collection_headline}"
    plain = (
        f"New things in {collection_headline}:\n\n"
        f"{things_plain}\n\n"
        f"Log in to OIUEEI to see more."
    )
    html = f"""
        <html>
        <p>New things in <strong>{safe_collection}</strong>:</p>
        <ul>{things_html}</ul>
        <p>Log in to OIUEEI to see more.</p>
        </html>
        """

    for email in emails:
        send_mail(
            subject=subject,
            message=plain,
            from_email=None,
            recipient_list=[email],
            html_message=html,
        )


def send_return_reminder_email(requester_name, thing_headline, end_date, owner_email):
    """Remind the owner that a booking ends tomorrow."""
    safe_requester = escape(requester_name)
    safe_headline = escape(thing_headline)
    safe_date = escape(str(end_date))

    send_mail(
        subject="Reminder: a hold ends tomorrow",
        message=(f"Reminder: {requester_name}'s hold on '{thing_headline}' " f"ends {end_date}."),
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p>Reminder: <strong>{safe_requester}</strong>'s hold on
            <strong>{safe_headline}</strong> ends <strong>{safe_date}</strong>.</p>
            </html>
            """,
    )


def send_delivery_reminder_email(requester_name, thing_headline, delivery_date, owner_email):
    """Remind the owner that a delivery is due tomorrow."""
    safe_requester = escape(requester_name)
    safe_headline = escape(thing_headline)
    safe_date = escape(str(delivery_date))

    send_mail(
        subject="Reminder: a delivery is due tomorrow",
        message=(
            f"Reminder: {requester_name}'s order of '{thing_headline}' "
            f"is due for delivery {delivery_date}."
        ),
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p>Reminder: <strong>{safe_requester}</strong>'s order of
            <strong>{safe_headline}</strong> is due for delivery
            <strong>{safe_date}</strong>.</p>
            </html>
            """,
    )


def send_event_reminder_email(owner_name, thing_headline, event_date, emails):
    """Remind attendees that an event is tomorrow."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    date_str = event_date.strftime("%d %B %Y, %H:%M") if event_date else ""

    subject = f"Reminder: {thing_headline} is tomorrow"
    plain = f"Reminder: {thing_headline} by {owner_name} is happening tomorrow."
    if date_str:
        plain += f" Date: {date_str}."

    html = f"""
        <html>
        <p>Reminder: <strong>{safe_headline}</strong> by
        <strong>{safe_owner}</strong> is happening tomorrow.</p>
        {"<p>Date: " + escape(date_str) + "</p>" if date_str else ""}
        </html>
        """

    for email in emails:
        send_mail(
            subject=subject,
            message=plain,
            from_email=None,
            recipient_list=[email],
            html_message=html,
        )


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

    send_mail(
        subject=f"Documents for {thing_headline}",
        message=(
            f"Here are the documents for '{thing_headline}':\n\n"
            f"{plain_links}\n\n"
            f"Log in to OIUEEI to see more."
        ),
        from_email=None,
        recipient_list=[requester_email],
        html_message=f"""
            <html>
            <p>Here are the documents for <strong>{safe_headline}</strong>:</p>
            <ul>{html_links}</ul>
            <p>Log in to OIUEEI to see more.</p>
            </html>
            """,
    )


def send_newsletter_email(collection_headline, new_thing_headlines, transfer_entries, emails):
    """Send a weekly newsletter for share collections.

    Args:
        collection_headline: The collection name.
        new_thing_headlines: List of headlines of newly added things.
        transfer_entries: List of dicts with keys: date, thing, from_name, to_name.
        emails: List of recipient email addresses.
    """
    safe_collection = escape(collection_headline)

    # Block 1: New things
    if new_thing_headlines:
        things_plain = "\n".join(f"  - {h}" for h in new_thing_headlines)
        things_html = "".join(f"<li>{escape(h)}</li>" for h in new_thing_headlines)
        block1_plain = f"New things:\n{things_plain}\n\n"
        block1_html = f"<h3>New things</h3><ul>{things_html}</ul>"
    else:
        block1_plain = ""
        block1_html = ""

    # Block 2: Ownership changes
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
    plain = f"Newsletter for {collection_headline}:\n\n{block1_plain}{block2_plain}"
    html = f"""
        <html>
        <p>Newsletter for <strong>{safe_collection}</strong>:</p>
        {block1_html}
        {block2_html}
        <p>Log in to OIUEEI to see more.</p>
        </html>
        """

    for email in emails:
        send_mail(
            subject=subject,
            message=plain,
            from_email=None,
            recipient_list=[email],
            html_message=html,
        )


def send_swap_request_email(
    requester, thing, offered_things, owner_email, accept_link, reject_link
):
    """Send swap request email to owner with offered thing headlines."""
    requester_name = requester.name or requester.email
    safe_requester_name = escape(requester_name)
    safe_headline = escape(thing.headline)
    offered_names = ", ".join(t.headline for t in offered_things)
    offered_html = "".join(f"<li>{escape(t.headline)}</li>" for t in offered_things)

    message = (
        f"{requester_name} wants to swap '{thing.headline}' "
        f"for: {offered_names}. "
        f"Confirm swap: {accept_link} | Cancel swap: {reject_link}"
    )

    send_mail(
        subject="You have a swap request",
        message=message,
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
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
            """,
    )


def send_swap_confirmation_email(requester, thing, offered_things, booking):
    """Send swap request confirmation to the requester."""
    safe_headline = escape(thing.headline)
    offered_names = ", ".join(t.headline for t in offered_things)
    offered_html = "".join(f"<li>{escape(t.headline)}</li>" for t in offered_things)

    message = (
        f"Your swap request for '{thing.headline}' "
        f"(offering: {offered_names}) has been sent. "
        f"The owner will get back to you soon."
    )

    send_mail(
        subject="Swap request sent",
        message=message,
        from_email=None,
        recipient_list=[requester.email],
        html_message=f"""
            <html>
            <p>Your swap request has been sent!</p>
            <p>You requested: <strong>{safe_headline}</strong></p>
            <p>You offered:</p>
            <ul>{offered_html}</ul>
            <p>The owner will get back to you soon.</p>
            </html>
            """,
    )
