# Services Documentation

Business logic and side effects extracted from views into `core/services/`. Keeps views thin and logic reusable.

---

## Modules

### `booking_service.py` — Booking Business Logic

Handles state transitions for `BookingPeriod` and `Thing` models as an atomic unit.

#### Functions

| Function | Input | Behaviour |
|----------|-------|-----------|
| `cancel_booking(booking)` | `BookingPeriod` instance | Calls `booking.cancel()`. For single-use types (GIFT, SELL), restores thing to `ACTIVE`. Returns thing. |
| `accept_booking(booking)` | `BookingPeriod` instance | Calls `booking.accept()`. For single-use types, sets thing to `INACTIVE` and adds requester to `deal` M2M. For `SHARE_THING`, transfers ownership to the requester (`thing.owner = booking.requester_code`); thing stays `ACTIVE`. For `SWAP_THING`, transfers requested thing to requester and all offered things (`booking.offered_things`) to original owner; all things stay `ACTIVE`; creates `ThingTransfer` records for each thing involved. Creates a `ThingTransfer` record (from owner to requester, lent_date = start_date or today). Returns thing. |
| `reject_booking(booking)` | `BookingPeriod` instance | Calls `booking.reject()`. For single-use types, restores thing to `ACTIVE`. Returns thing. |

#### Patterns

- **Atomic transactions**: Every function wraps its work in `transaction.atomic()` to ensure `BookingPeriod` and `Thing` are updated together or not at all.
- **Row-level locking**: Uses `Thing.objects.select_for_update()` to prevent race conditions when two concurrent requests try to modify the same thing's status.
- **Single-use type check**: Only GIFT and SELL things (`SINGLE_USE_TYPES` from `core.models.booking`) change thing status on accept/reject/cancel. Date-based types (LEND, RENT, SHARE, ASSET) and repeatable types (ORDER) leave thing status unchanged because multiple bookings can coexist.
- **SHARE_THING ownership transfer**: On acceptance, `thing.owner` is changed to the requester. The thing stays `ACTIVE` so the new owner can continue sharing it. This enables a chain of ownership transfers within a community collection.
- **SWAP_THING bilateral transfer**: On acceptance, the requested thing transfers to the requester, and all offered things transfer to the original owner. All things stay `ACTIVE`. `ThingTransfer` records are created for every thing involved (requested + offered).
- **Document delivery on acceptance**: After any booking acceptance, if the thing has `documents`, `send_documents_email()` is called to send download links to the requester.

---

### `email_service.py` — Centralised Email Sending

All outbound emails are composed and sent from this module. Views call these functions rather than constructing emails inline.

#### Functions

| Function | Trigger | Recipient |
|----------|---------|-----------|
| `send_magic_link_email(email, magic_link)` | User requests login | The user |
| `send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link)` | Guest submits a hold request | Thing owner |
| `send_booking_confirmation_email(requester, thing, booking)` | Guest submits a hold request | Requester (confirmation of what was requested) |
| `send_booking_decision_email(booking, thing, accepted)` | Owner accepts or rejects a booking | Requester |
| `send_collection_invite_email(inviter_name, collection_headline, email, accept_link, reject_link)` | Owner invites a user to a collection | Invitee |
| `send_invite_rejected_email(invitee_name, collection_headline, owner_email)` | Invitee declines a collection invitation | Collection owner |
| `send_collection_revoke_email(owner_name, collection_headline, email)` | Owner removes a user from a collection | Revoked user |
| `send_faq_question_email(questioner_name, thing, question, owner_email)` | Guest asks a question on a thing | Thing owner |
| `send_faq_answer_email(owner_name, thing_headline, question, answer, questioner_email)` | Owner answers a FAQ | Questioner |
| `send_faq_hide_email(owner_name, thing_headline, question, questioner_email)` | Owner hides a FAQ | Questioner |
| `send_event_announcement_email(owner_name, thing_headline, event_date, collection_headline, emails)` | EVENT_THING created in a collection | All collection invitees (individually) |
| `send_broadcast_email(owner_name, owner_email, collection_headline, subject, message, emails)` | Owner sends broadcast to collection | All collection invitees (individually, with Reply-To owner) |
| `send_digest_email(collection_headline, thing_headlines, emails)` | Daily command (weekly/monthly) | All collection invitees (individually) |
| `send_newsletter_email(collection_headline, new_thing_headlines, transfer_entries, emails)` | Daily command (Mondays, share collections with `newsletter_enabled`) | All collection invitees (individually). Two blocks: new things (bulleted) and ownership changes (date — thing: from → to). |
| `send_return_reminder_email(requester_name, thing_headline, end_date, owner_email)` | Daily command (end_date = tomorrow) | Thing owner |
| `send_delivery_reminder_email(requester_name, thing_headline, delivery_date, owner_email)` | Daily command (delivery_date = tomorrow) | Thing owner |
| `send_event_reminder_email(owner_name, thing_headline, event_date, emails)` | Daily command (event_date = tomorrow) | All attendees (individually) |
| `send_documents_email(requester_email, thing_headline, documents)` | Booking accepted for thing with documents | Requester (download links to Cloudinary raw URLs) |
| `send_swap_request_email(requester, thing, offered_things, owner_email, accept_link, reject_link)` | Guest proposes a swap | Thing owner (lists offered thing headlines, accept/reject links) |
| `send_swap_confirmation_email(requester, thing, offered_things, booking)` | Guest proposes a swap | Requester (confirmation of swap proposal) |

#### Patterns

- **XSS prevention**: All user-provided content is escaped with `django.utils.html.escape()` before being inserted into HTML email bodies. Plain text versions use raw values (safe in plain text context).
- **Dual format**: Every email includes both a `message` (plain text) and `html_message` for clients that support HTML.
- **Action links**: Booking and invitation emails include accept/reject links (RSVP-based URLs generated by the calling view). FAQ question emails include a direct link to the thing page.
- **`from_email=None`**: Uses Django's `DEFAULT_FROM_EMAIL` setting.
- **Booking email variants**: `send_booking_request_email` and `send_booking_decision_email` adapt their content based on booking type — date-based (start/end), order (delivery + quantity), or simple (no extra fields).
- **Reply-To header**: `send_broadcast_email()` uses `EmailMultiAlternatives` with `reply_to` so invitees can respond directly to the collection owner.
- **Digest emails**: `send_digest_email()` lists new thing headlines in both plain text (bulleted) and HTML (`<ul>/<li>`) formats.
