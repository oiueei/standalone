"""English email texts — the reference catalogue (and universal fallback).

Values are ``str.format`` templates; keep every ``{placeholder}`` when
translating. ``*_plain`` keys are the plain-text bodies (may repeat the HTML
copy with quoting differences — they are faithful to the pre-extraction
wording, which the email content tests assert)."""

TEXTS = {
    # Shared
    "footer_manage": "Manage your email preferences",
    # Art. 14 GDPR: every email — mandatory ones included — links to the
    # legal page, since this is a disclosure duty and not a preference.
    "footer_legal": "Legal & privacy",
    # How a booking's dates read inside a sentence: a range, or one day said once
    # ("from the 13th to the 13th" was a loan for a single day, 2026-10-02).
    "when_range": "from {start} to {end}",
    "when_day": "on {start}",
    "dates_label": "Dates",
    # What a person is called when they never set a name, wherever the reader is
    # someone who is not entitled to their address. `User.display_name` falls
    # back to the email, and `name` is empty for everyone who joined by magic
    # link and never filled in their profile — so the fallback is the *default*
    # state of a new member, not an edge case. See `_member_name`.
    "a_member": "A member",
    # The same stand-in in the middle of a sentence or a list (`_member_name(inline=True)`).
    "a_member_inline": "a member",
    "view_collection_cta": "View collection",
    # Per-type action nouns for the booking emails — mirror the frontend's
    # thingCard.action / types vocabulary so a SELL request reads "purchase
    # request", a LEND request "loan request", etc.
    "action_noun_GIFT_THING": "gift",
    "action_noun_SELL_THING": "purchase",
    "action_noun_LEND_THING": "loan",
    "action_noun_RENT_THING": "rental",
    "action_noun_RESERVE_THING": "reservation",
    # Magic link
    "magic_subject": "Hello, welcome to OIUEEI!",
    "magic_subject_collection": "Hello, welcome to '{collection}' - OIUEEI!",
    # The greeting repeated at the top of the body — the inbox preview shows
    # only the subject, the body has to stand on its own (see send_magic_link_email).
    "magic_greeting": "Hello, welcome to OIUEEI!",
    "magic_greeting_collection": "Hello, welcome to '{collection}'!",
    "magic_plain": "Click the link to sign in: {link}",
    "magic_cta": "Sign in →",
    "cta_fallback": "If you'd rather, copy and paste this link into your browser:",
    # Shared by every CTA (one button or two) that has to spell its link out below it.
    "ctas_fallback": "If you'd rather, copy and paste these links into your browser:",
    # The one-line "what is this" under the OIUEEI parent title, for the one
    # email a reader may open with no idea what OIUEEI is.
    "generic_parent_pitch": (
        "Share what you have with the people around you: a stall to give away or sell, a "
        "library of things to lend or rent out, a shed to book by the day or by the hour. Then "
        "invite your people to ask for what they need."
    ),
    # What a kind of collection is, one sentence each. The same words as
    # `kinds.<K>.what` in the frontend's locale files (the kind chooser): a shared
    # link's card uses them for a collection with no description of its own.
    # `test_kind_what_parity.py` keeps the two copies equal.
    "kind_what_STALL": "Things to sell or give away: whoever takes one keeps it.",
    "kind_what_LIBRARY": "Things to lend or rent out: people take them home and bring them back.",
    "kind_what_SHED": "Machines and spaces used where they are, booked by the day or by the hour.",
    # Collection invite
    "invite_subject": "You have an invitation to '{collection}' - OIUEEI!",
    "invite_plain": (
        "You have been invited to join {collection}. "
        "Accept invitation: {accept} | Decline invitation: {reject}"
    ),
    "invite_intro": "{inviter} has invited you to this group.",
    "invite_recommended_by": "{proposer} suggested you for this group.",
    "invite_accept_cta": "Accept invitation",
    "invite_decline_cta": "Decline invitation",
    # Art. 14 GDPR: this address came from whoever invited you, not from you.
    "invite_source_note": (
        "You got this because someone invited you — that's where we got your "
        "address, and it's only used to send you this invitation. Decline it or "
        "do nothing, and that person can't invite you by email again for a year."
    ),
    # Collection access revoked
    "revoke_subject": "Your access has been revoked",
    "revoke_plain": "{owner} has revoked your access to '{collection}'.",
    "revoke_intro": "{owner} has revoked your access to this group.",
    "revoke_outro": "You will no longer be able to view this collection.",
    "revoke_things": "Your things in this group were deleted with your membership: {things}.",
    "thing_left_subject": "“{thing}” is no longer in {group}",
    "thing_left_intro": (
        "Whoever offered “{thing}” is no longer a member of {group}, "
        "and the thing has gone with them. "
        "Your request or reservation for it no longer stands."
    ),
    "thing_left_holding": "If you have it with you, return it to them as you agreed.",
    "thing_withdrawn_subject": "“{thing}” has been withdrawn from {group}",
    "thing_withdrawn_intro": (
        "“{thing}” has been withdrawn from {group}, and your request is cancelled."
    ),
    # Collection welcome document (sent once, the first time someone joins)
    "welcome_doc_subject": "Welcome to '{collection}'",
    "welcome_doc_plain": (
        "Welcome to '{collection}'. The group has a welcome and rules document — "
        "please have a read: {url}"
    ),
    "welcome_doc_intro": "Welcome! The group has a welcome and rules document:",
    "welcome_doc_link_label": "Open the document",
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
    # Inactivity warning (sent before an unused account is deleted)
    "inactivity_subject": "Your OIUEEI account has gone quiet",
    "inactivity_intro": (
        "You haven't signed in to OIUEEI for {months} months. We don't keep accounts "
        "nobody uses, so here is the warning that comes first."
    ),
    "inactivity_deletes": (
        "In {days} days your account goes, permanently: your collections, your things "
        "and their photos with it."
    ),
    "inactivity_keep": "Signing in once is enough to keep it. There is nothing else to do.",
    "inactivity_cta": "Sign in",
    "inactivity_outro": ("And if you would rather it went, you don't have to do anything at all."),
    "inactivity_plain": (
        "You haven't signed in to OIUEEI for {months} months, and we don't keep accounts "
        "nobody uses. In {days} days your account goes, permanently, with your "
        "collections, your things and their photos. Signing in once is enough to keep "
        "it: {link} — and if you would rather it went, you don't have to do anything."
    ),
    # Same warning, for an account that will NOT be deleted because a group
    # depends on it. It must not threaten something that will not happen.
    "inactivity_kept": (
        "Your account stays — there are people using a collection of yours, and we are "
        "not taking that away from them while you are gone. But nobody has looked "
        "after it in all that time, and it is yours to look after."
    ),
    "inactivity_kept_outro": (
        "If you would rather leave, you can delete your account yourself from your "
        "profile, whenever you like."
    ),
    "inactivity_kept_plain": (
        "You haven't signed in to OIUEEI for {months} months. Your account stays — "
        "there are people using a collection of yours and we are not taking that away "
        "from them while you are gone — but nobody has looked after it in all that "
        "time. You can pick it up here: {link} — or delete your account yourself from "
        "your profile, whenever you like."
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
        "{requester} has sent a {action} request for '{thing}' {when}. "
        "Confirm request: {accept} | Decline request: {reject}"
    ),
    "booking_request_plain": (
        "{requester} has sent a {action} request for '{thing}'. "
        "Confirm request: {accept} | Decline request: {reject}"
    ),
    "booking_request_intro": "{requester} has sent a {action} request:",
    # The requester's address travels with the request to whoever manages the thing:
    # shared by the request email and the reservation notice. There is no
    # sentence saying that "Reply" reaches them.
    "requester_email_label": "Email",
    "hold_confirm_cta": "Confirm request",
    "hold_cancel_cta": "Decline request",
    # Booking decision (to requester)
    "decision_subject_confirmed": "Your request is confirmed",
    "decision_subject_cancelled": "Your request didn't go through",
    "decision_confirmed": "confirmed",
    "decision_cancelled": "declined",
    "decision_plain_dated": (
        "Your {action} request for '{thing}' {when} has been {decision}. View thing: {url}"
    ),
    "decision_plain": "Your {action} request for '{thing}' has been {decision}. View thing: {url}",
    "decision_by_confirmed": "{who} has accepted your {action} request:",
    "decision_by_declined": "{who} has declined your {action} request:",
    "point_name_label": "Pickup point",
    "point_address_label": "Address",
    "point_hours_label": "Hours",
    "point_contact_label": "Contact",
    "decision_intro": "Your {action} request has been {decision}:",
    # Invite declined (to collection owner)
    "invite_rejected_subject": "Your invitation was rejected",
    "invite_rejected_plain": "{invitee} has declined the invitation to '{collection}'.",
    "invite_rejected_intro": "{invitee} has declined your invitation to this group.",
    # Booking confirmation (to requester)
    "confirmation_subject": "Your {action} request was sent",
    "confirmation_plain_dated": (
        "Your {action} request for '{thing}' {when} has been sent. {outro} View thing: {url}"
    ),
    "confirmation_plain": (
        "Your {action} request for '{thing}' has been sent. {outro} View thing: {url}"
    ),
    "confirmation_intro": "Your {action} request has been sent:",
    # Who was told: one person who runs the thing, or more than one (a team) — the
    # person's name is not in it any more.
    "confirmation_outro_one": (
        "We've let the person who runs it know — they'll get back to you soon."
    ),
    "confirmation_outro_other": (
        "We've let the people who run it know — they'll get back to you soon."
    ),
    # Where the requester will be written to: the address they sign in with,
    # which the managers now hold. Said, never printed — the email already arrives there.
    "contact_shared_request": (
        "Your email goes with the request: if needed, they'll write to you here, at the address "
        "you sign in to OIUEEI with."
    ),
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
    # FAQ answer (to the rest of the managing team — not the answerer, not the asker)
    "faq_answered_team_subject": "A question about '{thing}' has been answered",
    "faq_answered_team_plain": (
        "{answerer} has answered a question about '{thing}'. Reply: {answer} View thing: {url}"
    ),
    "faq_answered_team_intro": "{answerer} answered a question about:",
    # FAQ hidden (to questioner)
    "faq_hide_subject": "Your question has been hidden",
    "faq_hide_plain": "{owner} has hidden your question: {question}",
    "faq_hide_intro": "{owner} has hidden your question about:",
    # FAQ hidden (to the rest of the managing team — not the hider, not the asker)
    "faq_hidden_team_subject": "A question about '{thing}' was hidden",
    "faq_hidden_team_plain": "{hider} has hidden a question about '{thing}'. View thing: {url}",
    "faq_hidden_team_intro": "{hider} hid a question about:",
    # Listing reported (to owner, anonymous)
    "reported_subject": "Someone reported one of your things",
    "reported_plain": (
        "Someone reported your thing '{thing}'. "
        "We don't share who reported it. Please take a look: {url}"
    ),
    "reported_intro": "Someone reported one of your things:",
    "reported_outro": (
        "We don't share who reported it. Please take a look and make sure everything is in order."
    ),
    "reported_review_cta": "Review the thing",
    "thing_hidden_subject": "{founder} hid one of your things",
    "thing_hidden_plain": (
        "{founder} hid {thing} from {group}. It is still yours: you can show it again "
        "whenever you like. {url}"
    ),
    "thing_hidden_intro": "{founder} hid this thing from {group}:",
    "thing_hidden_outro": "It is still yours: you can show it again whenever you like.",
    "thing_hidden_cta": "Review the thing",
    # Broadcast (owner → invitees)
    "email_note_test_subject": "Your email note, as members will see it — {collection}",
    "email_note_test_intro": (
        "This is how your note will look in the emails people get after asking for "
        "something in {collection}. Only you received this one."
    ),
    "broadcast_subject": "Hey! {collection}",
    "broadcast_plain": "Message from {owner}:\n\n{message}\n\nOpen the group: {url}",
    "broadcast_intro": "{owner} sent a message to the group:",
    "broadcast_open_cta": "Open the group",
    # Return reminder (to owner). "Comes back" names what a loan does — a
    # "reservation" is only RESERVE_THING, which never comes through this email.
    "reminder_subject": "Reminder: {thing} comes back tomorrow",
    "reminder_plain": "Reminder: {requester} is due to return '{thing}' to you on {end}.",
    "reminder_body": "Reminder: {requester} is due to return {thing} to you on {end}.",
    "return_due_subject": "Tomorrow you take {thing} back",
    "return_due_plain": "A friendly nudge: you're due to return '{thing}' to {owner} on {end}.",
    "return_due_body": "A friendly nudge: you're due to return {thing} to {owner} on {end}.",
    # Pickup reminders (LEND/RENT, start_date = tomorrow) — the day before the handover
    "pickup_due_subject": "Tomorrow you pick up {thing}",
    "pickup_due_plain": "A friendly nudge: you're picking up '{thing}' from {owner} on {start}.",
    "pickup_due_body": "A friendly nudge: you're picking up {thing} from {owner} on {start}.",
    "pickup_reminder_subject": "Tomorrow you hand over {thing}",
    "pickup_reminder_plain": "Reminder: {requester} picks up '{thing}' on {start}.",
    "pickup_reminder_body": "Reminder: {requester} picks up {thing} on {start}.",
    # Manual nudge from /owner-bookings: the return date has already passed
    "return_overdue_subject": "Reminder: please return {thing}",
    "return_overdue_plain": (
        "{manager} is reminding you that '{thing}' was due back on {end}. "
        "If you've already returned it, you can ignore this email."
    ),
    "return_overdue_body": (
        "{manager} is reminding you that {thing} was due back on {end}. "
        "If you've already returned it, you can ignore this email."
    ),
    "view_thing_cta": "View the thing",
    "demo_note": "This group is a demo: its things and its people are examples.",
    # Reservations (RESERVE_THING) — auto-confirmed, so "confirmed", not "requested"
    "reservation_confirmed_subject": "Your reservation of '{thing}' is confirmed",
    "reservation_confirmed_plain": (
        "Your reservation of '{thing}' is confirmed {when}. View the thing: {url}"
    ),
    "reservation_confirmed_intro": "Your reservation is confirmed:",
    "contact_shared_reservation": "Your email goes with the booking.",
    "reservation_fee_label": "Fee",
    "reservation_where_label": "Where",
    "reservation_notice_subject": "{requester} reserved '{thing}'",
    "reservation_notice_plain": "{requester} reserved '{thing}' {when}.",
    "reservation_notice_intro": "{requester} has reserved:",
    "reservation_notice_phone": (
        "They left a contact phone number: you'll find it on the bookings page "
        "until the day after the booking."
    ),
    "reservation_note_label": "Their note",
    "reservation_cancelled_subject": "Reservation cancelled: '{thing}'",
    "reservation_cancelled_to_guest_plain": (
        "{other} has cancelled your reservation of '{thing}' ({when})."
    ),
    "reservation_cancelled_to_guest_intro": "{other} has cancelled your reservation of:",
    "reservation_cancelled_to_owner_plain": (
        "{other} has cancelled their reservation of '{thing}' ({when})."
    ),
    "reservation_cancelled_to_owner_intro": "{other} has cancelled their reservation of:",
    "reservation_cancel_confirmation_subject_self": "Your reservation of '{thing}' is cancelled",
    "reservation_cancel_confirmation_subject_other": "You cancelled a reservation of '{thing}'",
    "reservation_cancel_confirmation_intro_self": "Your reservation is cancelled:",
    "reservation_cancel_confirmation_intro_other": "You cancelled {member}'s reservation:",
    "reservation_cancel_confirmation_plain_self": (
        "Your reservation of '{thing}' ({when}) is cancelled."
    ),
    "reservation_cancel_confirmation_plain_other": (
        "You cancelled {member}'s reservation of '{thing}' ({when})."
    ),
    "reservation_reminder_subject": "Your reservation of '{thing}' starts tomorrow",
    "reservation_reminder_plain": (
        "A friendly nudge: your reservation of '{thing}' is {when}. View the thing: {url}"
    ),
    "reservation_reminder_intro": "Your reservation starts tomorrow:",
    # Digest
    "digest_subject": "What's new in {collection}",
    "digest_plain": "New things:\n\n{things}\n\n{members}View collection: {url}",
    "digest_new_members_one": "And 1 new person joined the group.",
    "digest_new_members_other": "And {count} new people joined the group.",
    "join_summary_subject_one": "Someone new in {group}",
    "join_summary_subject_other": "{count} new people in {group}",
    "join_summary_intro_one": "New in {group}: {names}.",
    "join_summary_intro_other": "New in {group}: {names}.",
    "join_summary_more": "and {count} more",
    "join_summary_cta": "See the members",
    "join_summary_and": "and",
    "digest_intro": "New things:",
    "proposal_subject": "{collection}: can we invite someone?",
    "proposal_plain": (
        "{proposer} would like to invite someone to {collection}:\n\n  {email}\n\n"
        "Nobody has been contacted yet — this only happens if you say yes.\n\n"
        "Invite them: {approve}\nNot this time: {reject}"
    ),
    "proposal_intro": "{proposer} would like to invite someone to {collection}.",
    "proposal_note": "They added: {note}",
    "proposal_nobody_told": (
        "Nobody has been contacted yet. The invitation is only sent if you say yes, and if you "
        "don't, the person suggested will never know they were."
    ),
    "proposal_approve_cta": "Invite them",
    "proposal_reject_cta": "Not this time",
    "proposal_declined_subject": "About your suggestion for {collection}",
    "proposal_declined_intro": (
        "Thanks for thinking of someone for {collection}. {owner} has "
        "decided not to send that invitation for now:"
    ),
    "proposal_declined_outro": (
        "This person hasn't been contacted and won't be. Nothing else "
        "changes — you're still part of the group."
    ),
    "proposal_declined_body": (
        "Thanks for thinking of someone for {collection}. {owner} has decided not to send that "
        "invitation for now, so {email} hasn't been contacted and won't be. Nothing else changes "
        "— you're still part of the group."
    ),
    "digest_mute_cta": "Stop the summaries from this group",
}

# Growth blurbs appended to outbound emails (above the preferences footer) to
# turn guests into creators. One is chosen at random per send. ``path`` is where
# the CTA leads, under the frontend's base URL: the form of the kind the line
# talks about, or the chooser (`/new`) for a line about no kind in particular (a
# line with no ``path`` leads there too). The same destinations in every language;
# ``cta`` is the link label only.
VIRAL_LINES = [
    {
        "text": (
            "Refreshing your wardrobe? Open a stall with the clothes you no longer wear and "
            "offer them to your friends."
        ),
        "cta": "Start here",
        "path": "/stall/new",
    },
    {
        "text": (
            "A drill you use twice a year? Open a library of things with your tools and lend "
            "them to your neighbours."
        ),
        "cta": "Open your library",
        "path": "/library/new",
    },
    {
        "text": (
            "Shelves full of books you've already read? Put them on a stall and give them a "
            "second life."
        ),
        "cta": "Easy as that",
        "path": "/stall/new",
    },
    {
        "text": ("Toys the kids have outgrown? Open a stall and pass them on to other families."),
        "cta": "Create yours",
        "path": "/stall/new",
    },
    {
        "text": ("Moving soon? Open a stall with what you're not taking and find it a new home."),
        "cta": "Start here",
        "path": "/stall/new",
    },
    {
        "text": (
            "A group of friends, your building, the PTA? Open a stall, a library of things or "
            "a shed together and share among everyone."
        ),
        "cta": "Create your group",
        "path": "/new",
    },
]
