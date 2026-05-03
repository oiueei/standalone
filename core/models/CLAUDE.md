# OIUEEI Models Documentation

This document describes the behaviour and business rules for each model in the OIUEEI application. It serves as a reference for Claude and other collaborators to understand the intended use cases.

---

## User

The `User` model represents a person who can own collections, be invited to others' collections, and create things.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `email` | CharField(64) | **Yes** | Unique email address for authentication |
| `name` | CharField(32) | No | Display name |
| `created` | DateField | Auto | Date the user was created |
| `last_activity` | DateField | No | Date of last login/activity. Null until the user's first verify — `update_last_activity()` populates it. |
| `headline` | CharField(64) | No | Short bio/tagline |
| `koro` | CharField(9) | No | Koros wave type: basic, beat, calm, pulse, vibration, wave (default: basic) |
| `theeeme` | ForeignKey(Theeeme) | No | Colour palette (default: BUU331) |
| `notify_activity` | BooleanField | No | Opt-out toggle for Cat. 2 (activity) emails — bookings, FAQs, reminders, event announcements, broadcasts. Default: `True` |
| `notify_news` | BooleanField | No | Opt-out toggle for Cat. 3 (news) emails — digests and newsletters. Default: `True` |
| `is_active` | BooleanField | Auto | Default True |
| `is_staff` | BooleanField | Auto | Default False |
| `is_superuser` | BooleanField | Auto | Default False |

### Business Rules

1. **Email is mandatory and unique** - A user must have an email address, and no two users can share the same email. This is enforced at the database level with `unique=True`.

2. **Optional profile fields** - The `headline` and `thumbnail` fields are optional and default to empty strings.

3. **Relationships via FK/M2M** - Owned collections are accessed via `user.owned_collections.all()` (Collection FK reverse). Invited collections via `user.invited_to_collections.all()` (Collection M2M reverse). Owned things via `user.owned_things.all()` (Thing FK reverse).

4. **Cannot create things for others' collections** - A user can only add their own things to their own collections. Enforced at the view level.

5. **Creation date is persisted** - The `created` field is automatically set to today's date when the user is created.

6. **Last activity is updated on login** - The `update_last_activity()` method is called on each successful authentication. Newly-created users have `last_activity = None` until that first call; subsequent calls bump the date to today.

7. **Email notification preferences** - `notify_activity` and `notify_news` are consulted by `core/services/email_service.py` before sending. Magic links and invitations (Cat. 1) are mandatory and always sent regardless of these flags.

### Methods

- `update_last_activity()` - Updates `last_activity` to today's date
- `has_perm(perm, obj)` - Returns True only for superusers
- `has_module_perms(app_label)` - Returns True only for superusers

### Authentication

Users authenticate via magic link (passwordless). The `UserManager` handles user creation:
- `create_user(email)` - Creates a regular user, validates email is provided
- `create_superuser(email)` - Creates a superuser with `is_staff=True` and `is_superuser=True`

### Reverse Relations

- `user.owned_collections` - Collections where user is owner (Collection.owner FK)
- `user.invited_to_collections` - Collections where user is invited (Collection.invites M2M)
- `user.owned_things` - Things owned by user (Thing.owner FK)
- `user.deals` - Things where user has a deal (Thing.deal M2M)
- `user.asked_faqs` - FAQs asked by user (FAQ.questioner FK)
- `user.rsvps` - RSVPs for user (RSVP.user_code FK)
- `user.booking_requests` - Bookings requested by user (BookingPeriod.requester_code FK)
- `user.booking_owned` - Bookings for user's things (BookingPeriod.owner_code FK)

### Theeeme Relationship

- Users have a FK to Theeeme with `on_delete=PROTECT` and `default="BUU331"`
- This prevents deleting a Theeeme that is in use
- Default Theeeme is "Bussi" (code: BUU331)

---

## Collection

The `Collection` model represents a list of things (gifts, sales, orders) owned by a user. Collections can be shared with other users via invites.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `owner` | ForeignKey(User) | **Yes** | Owner of the collection |
| `created` | DateTimeField | Auto | Timestamp when collection was created |
| `headline` | CharField(64) | **Yes** | Title of the collection |
| `description` | CharField(256) | No | Description of the collection |
| `status` | CharField(8) | No | Status: ACTIVE (default) or INACTIVE |
| `mode` | CharField(12) | No | Mode: PROPRIETARY (default) or COMMUNITY |
| `digest_frequency` | CharField(7) | No | Digest email frequency: NONE (default), WEEKLY, or MONTHLY |
| `is_onboarding` | BooleanField | No | If True, new users joining via `/popin` are added to this collection (default: False) |
| `is_swap` | BooleanField | No | If True, only SWAP_THING items allowed; enables item swapping (default: False). Only meaningful for COMMUNITY collections. |
| `is_share` | BooleanField | No | If True, only SHARE_THING items allowed (default: False). Mutually exclusive with `is_swap`. Only meaningful for COMMUNITY collections. |
| `newsletter_enabled` | BooleanField | No | If True, sends weekly activity newsletter on Mondays (default: False). Requires `is_share=True`. |
| `is_minimalist` | BooleanField | No | If True, enables photo-album mode: only GIFT/SHARE/SWAP things allowed, thumbnail required (default: False). Mutually exclusive with `is_swap`. Compatible with `is_share`. |
| `swap_minimum_items` | PositiveIntegerField | No | Number of own SWAP_THINGs (status ACTIVE or TAKEN) a user must already have in this collection before they can propose a swap. Default `0` (no requirement). Only meaningful when `is_swap=True` — the serializer rejects `>0` for non-swap collections. Enforced in `core/views/reservations.py::_handle_swap_request`. The frontend reads `collection_swap_minimum_items` and `my_swap_count_in_collection` (both exposed on `ThingSerializer` and `CollectionThingSummarySerializer`) to disable the "Propose swap" button and surface an inline `Notification` before the user submits. The check applies to **every** requester, including the collection owner — owners propose swaps on guests' things and the rule is symmetric. |
| `thumbnail` | CharField(255) | No | Cloudinary image ID for the collection thumbnail (default: empty string). |
| `pause_message` | CharField(256) | No | Owner's message to guests explaining why the collection is paused (default: empty string). Non-empty = paused. |
| `share_token` | CharField(22) | No | URL-safe public share token (`secrets.token_urlsafe(16)` → 22 chars). Nullable, unique. Generated on demand the first time the owner opens the share menu. Anyone with the token can join the collection via `POST /api/v1/auth/pop-in/` with `share_token`. **Bearer credential — must never appear in any read serializer.** |
| `things` | ManyToManyField(Thing) | No | Things in this collection |
| `invites` | ManyToManyField(User) | No | Users invited to view this collection |

### Business Rules

1. **ACTIVE by default** - A collection starts with `status="ACTIVE"`.

2. **Owner manages all fields** - Only the owner can update the collection's headline, description, images, and status. Enforced via `IsCollectionOwner` DRF permission.

3. **Adding things** - In PROPRIETARY mode, only the owner can add things. In COMMUNITY mode, any invited user can add their own things. Enforced via `can_add_thing(user_code)`.

4. **Removing things** - The owner can always remove any thing. In COMMUNITY mode, thing owners can remove their own things.

5. **Only owner invites/revokes** - The `add_invite()` and `remove_invite()` methods modify the M2M relationship.

6. **Visible only to owner and invites** - The `can_view()` method returns True only if the user is the owner or is in `invites`.

7. **Public share link is owner-managed** — `share_token` is generated lazily by `POST /api/v1/collections/{code}/share-link/` and revoked by `DELETE` on the same endpoint. The token grants invitee status to anyone who completes the pop-in flow with it; revoke + rotate invalidate previously shared links immediately. The token is excluded from `CollectionSerializer` so it cannot leak via any read endpoint.

### Methods

- `add_thing(thing_code)` - Adds a thing to the collection via M2M
- `remove_thing(thing_code)` - Removes a thing from the collection via M2M
- `add_invite(user_code)` - Invites a user to view the collection via M2M
- `remove_invite(user_code)` - Revokes a user's invite via M2M
- `is_paused` — Property. Returns `bool(self.pause_message)`. True when the collection has a non-empty `pause_message`.
- `is_owner(user_code)` - Returns True if user is the owner (`self.owner_id == user_code`)
- `is_invited(user_code)` - Returns True if user is in invites (`self.invites.filter(code=user_code).exists()`)
- `is_community()` - Returns True if `mode == "COMMUNITY"`
- `can_add_thing(user_code)` - Returns True if user is owner, OR if collection is COMMUNITY and user is invited
- `can_view(user_code)` - Returns True if user is owner OR invited

### Validations

| Field | Validation | Level | Error |
|-------|------------|-------|-------|
| `headline` | Required | Serializer | 400 Bad Request |
| `things` | Thing must exist | View (get_object_or_404) | 404 Not Found |
| `things` | Thing must belong to owner | View | 403 Forbidden |
| `owner` | From authenticated user | View | Always valid |

---

## Theeeme

The `Theeeme` model represents a colour palette for customising collections. Each theeeme has a name and 6 colours.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `name` | CharField(16) | No | Display name of the theeeme (default: `""`) |
| `color_01` through `color_06` | CharField(32) | **Yes** | HDS colour token names (e.g. "bus", "coat-of-arms-medium-light") |

### Business Rules

1. **Each user has a theeeme** - Users are personalised with a `theeeme` FK.
2. **Default theeeme is Bussi** (code: Bussi).
3. **Protected deletion** - Theeemes cannot be deleted if any user references them (`on_delete=PROTECT`).

---

## FAQ

The `FAQ` model represents a question and answer about a thing. Invited users can ask questions, and only the thing owner can answer or hide them.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `thing` | ForeignKey(Thing) | **Yes** | The thing this FAQ is about |
| `created` | DateTimeField | Auto | Timestamp when FAQ was created |
| `questioner` | ForeignKey(User) | **Yes** | User who asked the question |
| `question` | CharField(64) | **Yes** | The question text |
| `answer` | CharField(256) | No | The answer text (empty until answered) |
| `is_visible` | BooleanField | No | Whether FAQ is visible (default: True) |

### Business Rules

1. **FK to Thing** - Each FAQ references a thing via ForeignKey.
2. **FK to User** - Questioner tracked via ForeignKey.
3. **Only invited users can ask** - Must be invited to the collection containing the thing.
4. **Owner cannot ask questions** - Returns 400 Bad Request.
5. **Only owner can answer** - Returns 403 Forbidden for others.
6. **Default visible** - New FAQs have `is_visible=True`.
7. **Only owner can change visibility** - Via `/faq/{code}/hide/` or `/faq/{code}/show/`.
8. **Email notifications** - Owner notified on new question. Questioner notified on answer/hide.

### Methods

- `has_answer()` - Returns True if `answer` is not empty
- `set_answer(answer_text)` - Sets the answer and saves

### Visibility Rules

- **Owner** sees all FAQs (visible and hidden)
- **Invited users** see only visible FAQs (`is_visible=True`)
- **Questioner** can see their own hidden FAQ

---

## RSVP

The `RSVP` model is the central intermediary for all email-based actions. It serves two primary purposes:
1. **Magic link authentication** - Passwordless login via email
2. **Action intermediary** - All email links use RSVP codes to avoid exposing real codes in URLs

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `created` | DateTimeField | Auto | Timestamp when RSVP was created |
| `user_code` | ForeignKey(User) | **Yes** | User this RSVP is for |
| `user_email` | CharField(64) | **Yes** | Email address of the recipient |
| `action` | CharField(20) | No | Action type (default: MAGIC_LINK). Indexed (`db_index=True`) |
| `target_code` | CharField(6) | No | Target object code (booking, collection, etc.). Indexed (`db_index=True`) |
| `context` | JSONField | No | Additional context data for the action (`default=dict`) |

### Action Types

| Action | Description |
|--------|-------------|
| `MAGIC_LINK` | Passwordless authentication (default) |
| `COLLECTION_INVITE` | Accept invitation to view a collection |
| `COLLECTION_REJECT` | Decline invitation to a collection |
| `BOOKING_ACCEPT` | Accept a booking (all thing types) |
| `BOOKING_REJECT` | Reject a booking (all thing types) |

### Business Rules

1. **One-time use** - RSVPs are deleted after being used.
2. **24h expiry** - RSVPs expire after `MAGIC_LINK_EXPIRY_HOURS` (default 24 hours).
3. **RSVP codes obfuscate URLs** - Email links use `code` instead of exposing real codes.
4. **RSVP for ALL email communications** - Every email that requires user action uses an RSVP.
5. **Sibling RSVP cleanup** - Collection invite/reject RSVPs are created in pairs. Using either one deletes both to invalidate the other link.

### Methods

- `is_valid()` - Returns True if not expired (within 24h of creation)
- `create_for_booking(action, booking, owner_email)` - Factory method for booking RSVPs

---

## BookingPeriod

The `BookingPeriod` model is the unified reservation/booking model for all thing types.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `created` | DateTimeField | Auto | Timestamp when booking was created |
| `thing_code` | ForeignKey(Thing) | **Yes** | The thing being booked |
| `thing_type` | CharField(17) | No | Type of thing (default: GIFT_THING) |
| `requester_code` | ForeignKey(User) | **Yes** | User who made the request |
| `requester_email` | CharField(64) | **Yes** | Email of the requester |
| `owner_code` | ForeignKey(User) | **Yes** | Owner of the thing |
| `start_date` | DateField | No | Start date (for LEND/RENT/SHARE/ASSET) |
| `end_date` | DateField | No | End date (for LEND/RENT/SHARE/ASSET) |
| `start_time` | TimeField | No | Start time (for ASSET_THING hourly and APPOINTMENT_THING bookings) |
| `end_time` | TimeField | No | End time (for ASSET_THING hourly and APPOINTMENT_THING bookings) |
| `delivery_date` | DateField | No | Delivery date (for ORDER_THING) |
| `quantity` | PositiveIntegerField | No | Quantity ordered (for ORDER_THING) |
| `status` | CharField(9) | No | Status: PENDING, ACCEPTED, REJECTED, CANCELLED, EXPIRED. Indexed (`db_index=True`) |
| `offered_things` | ManyToManyField(Thing) | No | Things offered by the requester in exchange (SWAP_THING only). Related name: `swap_offers`. |

### Thing Type Categories

```python
DATE_BASED_TYPES = ["LEND_THING", "RENT_THING", "ASSET_THING", "APPOINTMENT_THING"]  # Require dates
SINGLE_USE_TYPES = ["GIFT_THING", "SELL_THING"]  # Thing becomes INACTIVE after acceptance
REPEATABLE_TYPES = ["ORDER_THING"]  # Thing stays ACTIVE, can be ordered again
```

### Business Rules

1. **72h expiry** - PENDING bookings expire after `BOOKING_EXPIRY_HOURS` (default 72h).
2. **Date-based (LEND/RENT/ASSET/APPOINTMENT)**: `start_date` and `end_date` required. No overlapping bookings. Thing stays ACTIVE. ASSET_THING with `booking_unit=HOUR` and APPOINTMENT_THING also require `start_time`/`end_time` and use same-day booking with time-range overlap detection.
3. **Share (SHARE_THING)**: NOT date-based. No dates required — permanent ownership transfer on acceptance. Multiple pending requests allowed from different users.
4. **Single-use (GIFT/SELL)**: No dates. Thing status changes to TAKEN on request, INACTIVE on accept. When `is_endless=True`: multiple simultaneous PENDING bookings allowed, status never TAKEN, thing stays ACTIVE after accept, no ThingTransfer created.
5. **Repeatable (ORDER)**: `delivery_date` and `quantity` required. Thing stays ACTIVE.
6. **Swap (SWAP_THING)**: No dates. Requester offers own things via `offered_things` M2M. On acceptance, requested thing transfers to requester and all offered things transfer to original owner. All things stay ACTIVE. ThingTransfer records created for each thing involved.
7. **Accept/reject/cancel via services** - `booking_service.accept_booking()`, `reject_booking()`, and `cancel_booking()` handle status changes.
8. **Requester can cancel** - Requesters can cancel their own PENDING bookings. For single-use things, cancellation restores status to ACTIVE.

### Methods

- `is_valid()` - Returns True if not expired and PENDING
- `is_date_based()` / `is_single_use()` / `is_repeatable()` - Category checks
- `accept()` / `reject()` / `cancel()` / `expire()` - Status transitions

### Class Methods

- `has_overlap(thing_code, start_date, end_date, exclude_booking_code, start_time=None, end_time=None)` - Check for date (and optionally time) conflicts. When `start_time`/`end_time` are provided, additionally filters by time-range overlap on bookings that have non-null time fields.
- `get_blocked_periods(thing_code)` - Get all PENDING/ACCEPTED bookings
- `expire_old_pending()` - Batch expire stale PENDING bookings (used by `manage.py expire_bookings`). For single-use types (GIFT/SELL), also restores the Thing to `ACTIVE` within the same transaction — prevents things getting permanently stuck in `TAKEN` after booking expiry.

---

## Thing

The `Thing` model represents an item in a collection.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `type` | CharField(17) | No | Type: GIFT_THING, SELL_THING, ORDER_THING, RENT_THING, LEND_THING, SHARE_THING, EVENT_THING, WISH_THING, ASSET_THING, SWAP_THING, APPOINTMENT_THING |
| `owner` | ForeignKey(User) | **Yes** | Owner of the thing |
| `created` | DateTimeField | Auto | Timestamp when thing was created |
| `headline` | CharField(64) | **Yes** | Title of the thing |
| `description` | CharField(256) | No | Description of the thing |
| `thumbnail` | CharField(255) | No | Cloudinary image ID for thumbnail |
| `status` | CharField(8) | No | Status: ACTIVE, TAKEN, INACTIVE |
| `fee` | DecimalField | No | Price/fee (for SELL/RENT types) |
| `availability` | CharField(12) | No | Availability: IMMEDIATE, NEXT_WEEK, END_OF_MONTH, NEXT_MONTH. Only for GIFT/SELL/LEND/SHARE types. |
| `location` | CharField(32) | No | Free-text location. Only for GIFT/SELL/LEND/SHARE types. |
| `condition` | CharField(12) | No | Condition: NEW, GOOD, FAIR, USED, WELL_USED, ALMOST_JUNK. Only for GIFT/SELL/LEND/SHARE types. |
| `event_date` | DateTimeField | No | Date/time for EVENT_THING (null for other types) |
| `booking_unit` | CharField(4) | No | Booking granularity for ASSET_THING: DAY or HOUR (default: empty) |
| `slot_duration` | PositiveIntegerField | No | Slot duration in minutes for APPOINTMENT_THING: 15, 30, or 60 |
| `availability_schedule` | JSONField | No | Weekly availability windows for APPOINTMENT_THING. Format: `[{"days": [1,2,3,4,5], "start_time": "09:00", "end_time": "12:00"}]`. Days are ISO weekday numbers (1=Monday, 7=Sunday). |
| `documents` | JSONField | No | Attached documents: `[{"public_id": "...", "filename": "...", "content_type": "..."}]`. Max 5. Allowed types: PDF, Word, Excel, Markdown. Max 1 MB each (enforced client-side). Stored in Cloudinary raw uploads. Download links sent via email on booking acceptance. |
| `is_endless` | BooleanField | No | GIFT_THING and SELL_THING only. When True: multiple simultaneous PENDING bookings from different users are allowed, thing status never changes to TAKEN, no ThingTransfer is created on acceptance, thing remains ACTIVE forever (until owner hides or deletes it). Default: False. |
| `deal` | ManyToManyField(User) | No | Users who have reserved. For EVENT_THING: attendees. For WISH_THING: helpers |

### Status

| Value | Visibility | Reservation |
|-------|-----------|-------------|
| `ACTIVE` | Visible to owner + invited users | Available for new requests |
| `TAKEN` | Visible to owner + invited users | Pending confirmation, no new requests |
| `INACTIVE` | Visible to owner only | Not available for reservation |

### Methods

- `is_owner(user_code)` - Check if user is the owner (`self.owner_id == user_code`)
- `can_view(user_code)` - Check if user can view. Returns `False` if status is `INACTIVE` (unless user is owner) or if the collection is INACTIVE. Uses query: `self.collections.filter(invites__code=user_code, status='ACTIVE').exists()`
- `reserve(user_code)` - Add user to `deal` M2M. Does NOT change `status` (status is managed by the booking service)
- `release(user_code)` - Remove user from `deal` M2M.

### Reverse Relations

- `thing.collections` - Collections containing this thing (Collection.things M2M reverse)
- `thing.faq_set` - FAQs about this thing (FAQ.thing FK reverse)
- `thing.bookings` - Bookings for this thing (BookingPeriod.thing_code FK reverse)
- `thing.transfers` - Transfer history for this thing (ThingTransfer.thing FK reverse)
- `thing.swap_offers` - Swap bookings where this thing was offered (BookingPeriod.offered_things M2M reverse)

---

## ThingTransfer

The `ThingTransfer` model tracks the physical journey of a thing between users (the "Loan Chain"). Each record represents one handoff — from one user to another — with optional link to the booking that triggered it.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `thing` | ForeignKey(Thing) | **Yes** | The thing being transferred |
| `from_user` | ForeignKey(User) | **Yes** | User lending/giving the thing |
| `to_user` | ForeignKey(User) | **Yes** | User receiving the thing |
| `booking` | ForeignKey(BookingPeriod) | No | The booking that triggered this transfer (null for manual transfers) |
| `lent_date` | DateField | **Yes** | Date the thing was handed over |
| `returned_date` | DateField | No | Date the thing was returned (null = still with `to_user`) |
| `created` | DateTimeField | Auto | Record creation timestamp |

### Business Rules

1. **Created on booking acceptance** — When `accept_booking()` is called in the booking service, a `ThingTransfer` is automatically created with `from_user` = owner, `to_user` = requester, and `lent_date` = booking's `start_date` (or today for types without dates).
2. **Closed by management command** — The `close_transfers` daily command sets `returned_date = today` for transfers linked to ACCEPTED bookings whose `end_date` has passed.
3. **Booking FK uses SET_NULL** — If a booking is deleted, the transfer record survives (the physical handoff happened regardless).
4. **Ordering** — Default ordering is `-lent_date` (most recent first).

### Key Methods

- `__str__` — Returns `"{thing} {from_user}→{to_user} (active|returned)"`.

### Reverse Relations

- `booking.transfer` — Transfer created from a booking (ThingTransfer.booking FK reverse, related_name `transfer`)
- `user.transfers_out` — Transfers where user is the lender (ThingTransfer.from_user FK reverse)
- `user.transfers_in` — Transfers where user is the borrower (ThingTransfer.to_user FK reverse)

For security considerations, view patterns, service layer, and utilities documentation, see [`core/views/CLAUDE.md`](../views/CLAUDE.md).

---

## InAppNotification

The `InAppNotification` model stores in-app inbox notifications. Every user-action email that targets another party also creates an `InAppNotification` for that party. Displayed on `HomePage` as dismissible HDS `Notification` banners.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `user` | ForeignKey(User) | **Yes** | Recipient of the notification |
| `type` | CharField(32) | **Yes** | Notification type constant (see below) |
| `payload` | JSONField | Auto | Type-specific data (default: `{}`) |
| `created` | DateTimeField | Auto | Timestamp when notification was created |

### Notification Types

| Type | Created when | Recipient | Payload fields |
|------|-------------|-----------|----------------|
| `BROADCAST` | Owner sends a broadcast to collection | Each invitee | `owner_name`, `collection_headline`, `subject`, `message` |
| `COLLECTION_DELETED` | Owner deletes a collection | Each invitee | `collection_headline`, `owner_name` |
| `COLLECTION_REVOKED` | Owner removes a guest from collection | Removed user | `collection_headline`, `owner_name` |
| `BOOKING_ACCEPTED` | Owner accepts a hold request | Requester | `thing_headline`, `owner_name` |
| `BOOKING_REJECTED` | Owner rejects a hold request | Requester | `thing_headline`, `owner_name` |
| `BOOKING_REQUESTED` | User requests a hold (non-swap) | Thing owner | `thing_headline`, `requester_name` |
| `SWAP_REQUESTED` | User proposes a swap | Thing owner | `thing_headline`, `requester_name` |
| `FAQ_QUESTION` | User asks a FAQ question | Thing owner | `thing_headline`, `questioner_name` |
| `FAQ_ANSWERED` | Owner answers a FAQ | Questioner | `thing_headline`, `owner_name` |
| `FAQ_HIDDEN` | Owner hides a FAQ | Questioner | `thing_headline`, `owner_name` |
| `INVITE_REJECTED` | Invitee declines a collection invite | Collection owner | `collection_headline`, `invitee_name` |
| `EVENT_ATTEND` | User toggles event attendance | Event owner | `thing_headline`, `attendee_name`, `attending` (bool) |

### Business Rules

1. **One notification per action** — Created atomically alongside the corresponding email.
2. **Dismissal via DELETE** — `DELETE /api/v1/inbox/{code}/` removes the record (one-time dismiss).
3. **Ordered newest-first** — Default ordering is `-created`.
4. **Cascades on user delete** — `on_delete=CASCADE` on the `user` FK.

### Reverse Relations

- `user.inbox_notifications` — All in-app notifications for a user (InAppNotification.user FK reverse)
