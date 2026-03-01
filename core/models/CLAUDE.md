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
| `last_activity` | DateField | Auto | Date of last login/activity |
| `headline` | CharField(64) | No | Short bio/tagline |
| `thumbnail` | CharField(16) | No | Cloudinary image ID for avatar |
| `hero` | CharField(16) | No | Cloudinary image ID for banner |
| `theeeme` | ForeignKey(Theeeme) | No | Colour palette (default: HDS000 / B4s1C0) |
| `is_active` | BooleanField | Auto | Default True |
| `is_staff` | BooleanField | Auto | Default False |
| `is_superuser` | BooleanField | Auto | Default False |

### Business Rules

1. **Email is mandatory and unique** - A user must have an email address, and no two users can share the same email. This is enforced at the database level with `unique=True`.

2. **Optional profile fields** - The `headline`, `thumbnail`, and `hero` fields are optional and default to empty strings.

3. **Relationships via FK/M2M** - Owned collections are accessed via `user.owned_collections.all()` (Collection FK reverse). Invited collections via `user.invited_to_collections.all()` (Collection M2M reverse). Owned things via `user.owned_things.all()` (Thing FK reverse).

4. **Cannot create things for others' collections** - A user can only add their own things to their own collections. Enforced at the view level.

5. **Creation date is persisted** - The `created` field is automatically set to today's date when the user is created.

6. **Last activity is updated on login** - The `update_last_activity()` method is called on each successful authentication.

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

- Users have a FK to Theeeme with `on_delete=PROTECT` and `default="HDS000"`
- This prevents deleting a Theeeme that is in use
- Default Theeeme is "B4s1C0" (code: HDS000)

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
| `thumbnail` | CharField(16) | No | Cloudinary image ID for thumbnail |
| `hero` | CharField(16) | No | Cloudinary image ID for banner |
| `status` | CharField(8) | No | Status: ACTIVE (default) or INACTIVE |
| `things` | ManyToManyField(Thing) | No | Things in this collection |
| `invites` | ManyToManyField(User) | No | Users invited to view this collection |

### Business Rules

1. **ACTIVE by default** - A collection starts with `status="ACTIVE"`.

2. **Owner manages all fields** - Only the owner can update the collection's headline, description, images, and status. Enforced via `IsCollectionOwner` DRF permission.

3. **Only owner adds/removes things** - The `add_thing()` and `remove_thing()` methods modify the M2M relationship.

4. **Only owner invites/revokes** - The `add_invite()` and `remove_invite()` methods modify the M2M relationship.

5. **Visible only to owner and invites** - The `can_view()` method returns True only if the user is the owner or is in `invites`.

### Methods

- `add_thing(thing_code)` - Adds a thing to the collection via M2M
- `remove_thing(thing_code)` - Removes a thing from the collection via M2M
- `add_invite(user_code)` - Invites a user to view the collection via M2M
- `remove_invite(user_code)` - Revokes a user's invite via M2M
- `is_owner(user_code)` - Returns True if user is the owner (`self.owner_id == user_code`)
- `is_invited(user_code)` - Returns True if user is in invites (`self.invites.filter(code=user_code).exists()`)
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

The `Theeeme` model represents a colour palette for customising collections. Each theeeme has 6 colours.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `name` | CharField(16) | **Yes** | Name of the theeeme |
| `color_01` through `color_06` | CharField(6) | **Yes** | Hex colour codes (without #) |

### Business Rules

1. **Each user has a theeeme** - Users are personalised with a `theeeme` FK.
2. **Default theeeme is B4s1C0** (code: HDS000).
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
| `thing_type` | CharField(12) | No | Type of thing (default: GIFT_THING) |
| `requester_code` | ForeignKey(User) | **Yes** | User who made the request |
| `requester_email` | CharField(64) | **Yes** | Email of the requester |
| `owner_code` | ForeignKey(User) | **Yes** | Owner of the thing |
| `start_date` | DateField | No | Start date (for LEND/RENT/SHARE) |
| `end_date` | DateField | No | End date (for LEND/RENT/SHARE) |
| `delivery_date` | DateField | No | Delivery date (for ORDER_THING) |
| `quantity` | PositiveIntegerField | No | Quantity ordered (for ORDER_THING) |
| `status` | CharField(9) | No | Status: PENDING, ACCEPTED, REJECTED, CANCELLED, EXPIRED. Indexed (`db_index=True`) |

### Thing Type Categories

```python
DATE_BASED_TYPES = ["LEND_THING", "RENT_THING", "SHARE_THING"]  # Require dates
SINGLE_USE_TYPES = ["GIFT_THING", "SELL_THING"]  # Thing becomes INACTIVE after acceptance
REPEATABLE_TYPES = ["ORDER_THING"]  # Thing stays ACTIVE, can be ordered again
```

### Business Rules

1. **72h expiry** - PENDING bookings expire after `BOOKING_EXPIRY_HOURS` (default 72h).
2. **Date-based (LEND/RENT/SHARE)**: `start_date` and `end_date` required. No overlapping bookings. Thing stays ACTIVE.
3. **Single-use (GIFT/SELL)**: No dates. Thing status changes to TAKEN on request, INACTIVE on accept.
4. **Repeatable (ORDER)**: `delivery_date` and `quantity` required. Thing stays ACTIVE.
5. **Accept/reject/cancel via services** - `booking_service.accept_booking()`, `reject_booking()`, and `cancel_booking()` handle status changes.
6. **Requester can cancel** - Requesters can cancel their own PENDING bookings. For single-use things, cancellation restores status to ACTIVE.

### Methods

- `is_valid()` - Returns True if not expired and PENDING
- `is_date_based()` / `is_single_use()` / `is_repeatable()` - Category checks
- `accept()` / `reject()` / `cancel()` / `expire()` - Status transitions

### Class Methods

- `has_overlap(thing_code, start_date, end_date, exclude_booking_code)` - Check for date conflicts
- `get_blocked_periods(thing_code)` - Get all PENDING/ACCEPTED bookings
- `expire_old_pending()` - Batch expire stale PENDING bookings (used by `manage.py expire_bookings`)

---

## Thing

The `Thing` model represents an item in a collection.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `type` | CharField(16) | No | Type: GIFT_THING, SELL_THING, ORDER_THING, RENT_THING, LEND_THING, SHARE_THING |
| `owner` | ForeignKey(User) | **Yes** | Owner of the thing |
| `created` | DateTimeField | Auto | Timestamp when thing was created |
| `headline` | CharField(64) | **Yes** | Title of the thing |
| `description` | CharField(256) | No | Description of the thing |
| `thumbnail` | CharField(16) | No | Cloudinary image ID for thumbnail |
| `pictures` | JSONField | No | Array of Cloudinary image IDs |
| `status` | CharField(8) | No | Status: ACTIVE, TAKEN, INACTIVE |
| `fee` | DecimalField | No | Price/fee (for SELL/RENT types) |
| `deal` | ManyToManyField(User) | No | Users who have reserved |
| `available` | BooleanField | No | Visibility flag (default: True) |

### Visibility vs Reservation Status

| Field | Purpose | Values |
|-------|---------|--------|
| `available` | **Visibility control** | `True` = visible to owner + invites, `False` = visible only to owner |
| `status` | **Reservation state** | `ACTIVE` = can be reserved, `TAKEN` = pending confirmation, `INACTIVE` = no longer available |

These fields are **independent**.

### Methods

- `is_owner(user_code)` - Check if user is the owner (`self.owner_id == user_code`)
- `can_view(user_code)` - Check if user can view. Returns `False` if `self.available` is `False` (unless user is owner). Uses efficient query: `self.collections.filter(invites__code=user_code).exists()`
- `reserve(user_code)` - Add user to `deal` M2M and set `available=False`. Does NOT change `status` (status is managed by the booking service)
- `release(user_code)` - Remove user from `deal` M2M. Only restores `available=True` if no deals remain (`if not self.deal.exists()`)

### Reverse Relations

- `thing.collections` - Collections containing this thing (Collection.things M2M reverse)
- `thing.faq_set` - FAQs about this thing (FAQ.thing FK reverse)
- `thing.bookings` - Bookings for this thing (BookingPeriod.thing_code FK reverse)

For security considerations, view patterns, service layer, and utilities documentation, see [`core/views/CLAUDE.md`](../views/CLAUDE.md).
