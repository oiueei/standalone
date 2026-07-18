"""English email texts — the reference catalogue (and universal fallback).

Values are ``str.format`` templates; keep every ``{placeholder}`` when
translating. ``*_plain`` keys are the plain-text bodies (may repeat the HTML
copy with quoting differences — they are faithful to the pre-extraction
wording, which the email content tests assert)."""

TEXTS = {
    # Shared
    "footer_manage": "Manage your email preferences",
    "dates_label": "Dates",
    "view_collection_cta": "View collection",
    # Per-type action nouns for the booking emails — mirror the frontend's
    # thingCard.action / types vocabulary so a SELL request reads "purchase
    # request", a LEND request "loan request", etc. SWAP's request/confirmation
    # emails have their own dedicated templates, but the decision email
    # (send_booking_decision_email) is shared and interpolates {action} for
    # swaps too, so SWAP needs a noun as well. WISH never books.
    "action_noun_GIFT_THING": "gift",
    "action_noun_SELL_THING": "purchase",
    "action_noun_LEND_THING": "loan",
    "action_noun_RENT_THING": "rental",
    "action_noun_SHARE_THING": "transfer",
    "action_noun_SWAP_THING": "swap",
    # Magic link
    "magic_subject": "Hello, welcome to OIUEEI!",
    "magic_subject_collection": "Hello, welcome to '{collection}' - OIUEEI!",
    "magic_plain": "Hello! Click here to sign in: {link}",
    "magic_intro": "Hello! Click here to sign in:",
    "magic_cta": "Sign in",
    # Collection invite
    "invite_subject": "You have an invitation to '{collection}' - OIUEEI!",
    "invite_plain": (
        "You have been invited to view: {collection}. "
        "Accept invitation: {accept} | Decline invitation: {reject}"
    ),
    "invite_intro": "{inviter} has invited you to view:",
    "invite_accept_cta": "Accept invitation",
    "invite_decline_cta": "Decline invitation",
    # Collection access revoked
    "revoke_subject": "Your access has been revoked",
    "revoke_plain": "{owner} has revoked your access to '{collection}'.",
    "revoke_intro": "{owner} has revoked your access to:",
    "revoke_outro": "You will no longer be able to view this collection.",
    # Collection welcome document (sent once, the first time someone joins)
    "welcome_doc_subject": "Welcome to '{collection}'",
    "welcome_doc_plain": (
        "Welcome to '{collection}'. The group has a welcome and rules document — "
        "please have a read: {url}"
    ),
    "welcome_doc_intro": "Welcome! The group has a welcome and rules document:",
    "welcome_doc_outro": "Have a read before you get started.",
    # Account deletion confirmation (right to erasure)
    "account_delete_subject": "Delete your OIUEEI account?",
    "account_delete_plain": (
        "You asked to delete your OIUEEI account. If you confirm, it is immediate and "
        "irreversible: your account, your collections, your things and their photos, "
        "and your pending requests are permanently deleted. Questions you asked on "
        "other people's things and the history of things that passed through your "
        "hands stay, without your name. Confirm here (the link works for 24 hours): "
        "{link} — if you didn't request this, ignore this email and nothing will "
        "happen."
    ),
    "account_delete_intro": (
        "You asked to delete your OIUEEI account. This is the confirmation step — "
        "nothing has been deleted yet."
    ),
    "account_delete_deletes": (
        "If you confirm, it is immediate and irreversible: your account, your "
        "collections, your things and their photos, and your pending requests are "
        "permanently deleted."
    ),
    "account_delete_keeps": (
        "Questions you asked on other people's things and the history of things that "
        'passed through your hands stay, without your name — shown as "former '
        'member".'
    ),
    "account_delete_cta": "Confirm the deletion",
    "account_delete_outro": (
        "The link works for 24 hours and the page asks you to confirm once more. If "
        "you didn't request this, ignore this email — nothing will happen."
    ),
    # Contact form (support channel, to the operator)
    "contact_subject": "OIUEEI contact: {sender}",
    "collab_subject": "OIUEEI collaboration: {sender}",
    "contact_plain": (
        "Someone wrote through the contact form.\n\nName: {name}\nEmail: {email}\n\n{message}"
    ),
    "contact_intro": "Someone wrote through the contact form:",
    "contact_name_label": "Name",
    "contact_email_label": "Email",
    # Booking request (to owner)
    "booking_request_subject": "You have a pending {action} request",
    "booking_request_plain_dated": (
        "{requester} has sent a {action} request for '{thing}' from {start} to {end}. "
        "Confirm hold: {accept} | Cancel hold: {reject}"
    ),
    "booking_request_plain": (
        "{requester} has sent a {action} request for '{thing}'. "
        "Confirm hold: {accept} | Cancel hold: {reject}"
    ),
    "booking_request_intro": "{requester} has sent a {action} request:",
    "hold_confirm_cta": "Confirm hold",
    "hold_cancel_cta": "Cancel hold",
    # Booking decision (to requester)
    "decision_subject": "We have news",
    "decision_confirmed": "confirmed",
    "decision_cancelled": "cancelled",
    "decision_plain_dated": (
        "Your {action} request for '{thing}' from {start} to {end} has been {decision}."
    ),
    "decision_plain": "Your {action} request for '{thing}' has been {decision}.",
    "decision_intro": "Your {action} request has been {decision}:",
    # Booking auto-declined (someone else got it)
    "unavailable_subject": "Someone got there first",
    "unavailable_plain": (
        "'{thing}' went to someone else this time. "
        "No worries — things come and go around here, so keep an eye out!"
    ),
    "unavailable_intro": "{thing} went to someone else this time.",
    "unavailable_outro": "No worries — things come and go around here, so keep an eye out!",
    # Invite declined (to collection owner)
    "invite_rejected_subject": "Your invitation was rejected",
    "invite_rejected_plain": "{invitee} has declined the invitation to '{collection}'.",
    "invite_rejected_intro": "{invitee} has declined your invitation to:",
    # Booking confirmation (to requester)
    "confirmation_subject": "Your {action} request was sent",
    "confirmation_plain_dated": (
        "Your {action} request for '{thing}' from {start} to {end} has been sent. "
        "We've let {owner} know — they'll get back to you soon. "
        "View thing: {url}"
    ),
    "confirmation_plain": (
        "Your {action} request for '{thing}' has been sent. "
        "We've let {owner} know — they'll get back to you soon. View thing: {url}"
    ),
    "confirmation_intro": "Your {action} request has been sent:",
    "part_of_label": "Part of",
    "confirmation_outro": "We've let {owner} know — they'll get back to you soon.",
    # FAQ question (to owner)
    "faq_question_subject": "There is a question to be answered",
    "faq_question_plain": "{questioner} has asked about '{thing}': {question} View thing: {url}",
    "faq_question_intro": "{questioner} has asked a question about:",
    "question_label": "Question",
    "faq_view_reply_cta": "View and reply",
    # FAQ answer (to questioner)
    "faq_answer_subject": "Your question has been answered",
    "faq_answer_plain": "{owner} has replied: {answer}. See '{thing}': {url}",
    "faq_answer_intro": "{owner} has replied to your question about:",
    "your_question_label": "Your question",
    "reply_label": "Reply",
    # FAQ hidden (to questioner)
    "faq_hide_subject": "Your question has been hidden",
    "faq_hide_plain": "{owner} has hidden your question: {question}",
    "faq_hide_intro": "{owner} has hidden your question about:",
    # Listing reported (to owner, anonymous)
    "reported_subject": "Someone reported one of your listings",
    "reported_plain": (
        "Someone reported your listing '{thing}'. "
        "We don't share who reported it. Please take a look: {url}"
    ),
    "reported_intro": "Someone reported one of your listings:",
    "reported_outro": (
        "We don't share who reported it. Please take a look and make sure everything is in order."
    ),
    "reported_review_cta": "Review the listing",
    # Broadcast (owner → invitees)
    "broadcast_subject": "Hey! {collection}",
    "broadcast_plain": "Message from {owner} ({collection}):\n\n{message}\n\nI can help! {url}",
    "broadcast_intro": "{owner} sent a message to {collection}:",
    "broadcast_help_cta": "I can help!",
    # Wish posted (to group)
    "wish_posted_subject": "A neighbour is looking for something",
    "wish_posted_plain": "{creator} posted a new wish: '{wish}'. Can you help? View it: {url}",
    "wish_posted_intro": "{creator} posted a new wish:",
    "wish_posted_cta": "See if you can help",
    # Wish answered (to creator)
    "wish_response_subject": "Someone answered your wish",
    "wish_response_plain": "{responder} answered your wish '{wish}'. View the answer: {url}",
    "wish_response_intro": "{responder} answered your wish:",
    "wish_response_cta": "View the answer",
    # Wish resolved — thanks (to accepted responder)
    "wish_thanks_subject": "Thanks for your help",
    "wish_thanks_plain": (
        "{creator} marked the wish '{wish}' as resolved and wanted to thank you for your help."
    ),
    "wish_thanks_intro": "{creator} marked this wish as resolved:",
    "wish_thanks_outro": "Thanks for helping out!",
    # Return reminder (to owner)
    "reminder_subject": "Reminder: a hold ends tomorrow",
    "reminder_plain": "Reminder: {requester}'s hold on '{thing}' ends {end}.",
    "reminder_body": "Reminder: {requester}'s hold on {thing} ends {end}.",
    # Swap request (to owner)
    "swap_request_subject": "You have a swap request",
    "swap_request_plain": (
        "{requester} wants to swap '{thing}' for: {offered}. "
        "Confirm swap: {accept} | Cancel swap: {reject}"
    ),
    "swap_request_intro": "{requester} wants to swap:",
    "swap_exchange_label": "In exchange for:",
    "swap_confirm_cta": "Confirm swap",
    "swap_cancel_cta": "Cancel swap",
    # Swap confirmation (to requester)
    "swap_conf_subject": "Swap request sent",
    "swap_conf_plain": (
        "Your swap request for '{thing}' (offering: {offered}) has been sent. "
        "The owner will get back to you soon."
    ),
    "swap_conf_sent": "Your swap request has been sent!",
    "swap_conf_requested_label": "You requested:",
    "swap_conf_offered_label": "You offered:",
    "swap_conf_outro": "The owner will get back to you soon.",
    # Digest
    "digest_subject": "What's new in {collection}",
    "digest_plain": "New things in {collection}:\n\n{things}\n\nView collection: {url}",
    "digest_intro": "New things in {collection}:",
    # Newsletter
    "newsletter_subject": "Weekly newsletter: {collection}",
    "newsletter_intro": "Newsletter for {collection}:",
    "newsletter_new_things": "New things",
    "newsletter_transfers": "Ownership changes",
}

# Growth blurbs appended to outbound emails (above the preferences footer) to
# turn guests into creators. One is chosen at random per send. The CTA always
# points to {frontend_base}/collections/new; ``cta`` is the link label only.
VIRAL_LINES = [
    {
        "text": (
            "Refreshing your wardrobe? Make a collection with the clothes you no "
            "longer wear and offer them to your friends."
        ),
        "cta": "Start here",
    },
    {
        "text": (
            "A drill you use twice a year? Make a collection with your tools and "
            "lend them to your neighbours."
        ),
        "cta": "Create your collection",
    },
    {
        "text": (
            "Shelves full of books you've already read? Turn them into a "
            "collection and give them a second life."
        ),
        "cta": "Easy as that",
    },
    {
        "text": (
            "Toys the kids have outgrown? Make a collection and pass them on to other families."
        ),
        "cta": "Create yours",
    },
    {
        "text": (
            "Moving soon? Make a collection with what you're not taking and find it a new home."
        ),
        "cta": "Start here",
    },
    {
        "text": (
            "A group of friends, your building, the PTA? Create a community "
            "collection and share among everyone."
        ),
        "cta": "Create your group",
    },
]
