# OIUEEI Views Documentation

This document describes the behaviour, endpoints, permissions, and business logic for each view in the OIUEEI application.

---

## Auth Views (`core/views/auth.py`)

### RequestLinkView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/request-link/` |
| **Permission** | `AllowAny` |
| **Rate limit** | 5 requests/minute per IP |

Requests a magic link for passwordless authentication.

**Request body:**
```json
{ "email": "user@example.com" }
```

**Behaviour:**
1. Validates email via `RequestLinkSerializer`.
2. Looks up user by email (lowercased). Returns 200 with unified message regardless of whether email exists (anti-enumeration).
3. If user found: creates an RSVP with action `MAGIC_LINK` and sends magic link email via `send_magic_link_email()`.
4. Logs request to `security` logger with IP.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Always (unified message for anti-enumeration) |
| 429 | Rate limited |

---

### VerifyLinkView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/auth/verify/{rsvp_code}/` (also aliased at `GET /api/v1/rsvp/{rsvp_code}/`) |
| **Permission** | `AllowAny` |
| **Rate limit** | 10 requests/minute per IP |

Processes all RSVP-based actions. Routes to the appropriate handler based on `rsvp.action`:

| Action | Handler | Description |
|--------|---------|-------------|
| `MAGIC_LINK` | `_handle_magic_link` | Authenticates user, sets auth cookies |
| `COLLECTION_INVITE` | `_handle_collection_invite` | Adds user to collection invites M2M, sets auth cookies, deletes sibling `COLLECTION_REJECT` RSVP |
| `COLLECTION_REJECT` | `_handle_collection_reject` | Notifies collection owner of rejection, deletes sibling `COLLECTION_INVITE` RSVP, no JWT |
| `BOOKING_ACCEPT` | `_handle_booking_accept` | Accepts booking via `accept_booking()` service |
| `BOOKING_REJECT` | `_handle_booking_reject` | Rejects booking via `reject_booking()` service |

**Common behaviour:**
1. Looks up RSVP by code. Returns 401 if not found.
2. Checks `rsvp.is_valid()` (24h expiry). Deletes and returns 401 if expired.
3. Delegates to action handler.
4. RSVP is deleted after use (one-time use).

**Internal helpers:**
- `_authenticate_user(request, rsvp)` — Shared by `MAGIC_LINK` and `COLLECTION_INVITE` handlers. Validates user, calls `update_last_activity()`, generates JWT, calls `login()`. Returns `(user, refresh, user_data)` tuple or `Response` on failure. Auth tokens are set as HttpOnly cookies via `_set_auth_cookies()`.
- `_handle_booking_action(rsvp, accepted)` — Shared by `BOOKING_ACCEPT` and `BOOKING_REJECT` handlers. Looks up booking, validates via `is_valid()`, calls `accept_booking()`/`reject_booking()` service, sends decision email, deletes sibling RSVPs.

**MAGIC_LINK response (200):**
```json
{
  "action": "MAGIC_LINK",
  "user": { ... }
}
```
Auth tokens (`access_token`, `refresh_token`) are set as HttpOnly cookies via `_set_auth_cookies()`.

**COLLECTION_INVITE response (200):**
```json
{
  "action": "COLLECTION_INVITE",
  "user": { ... },
  "invited_collection": "<collection_code>"
}
```
Auth tokens are set as HttpOnly cookies via `_set_auth_cookies()`.

**COLLECTION_REJECT response (200):**
```json
{
  "action": "COLLECTION_REJECT",
  "message": "Invitation declined"
}
```

**BOOKING_ACCEPT response (200):**
```json
{
  "action": "BOOKING_ACCEPT",
  "message": "Booking accepted",
  "thing_headline": "...",
  "start_date": "...",
  "end_date": "..."
}
```

---

### PopInView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/pop-in/` |
| **Permission** | `AllowAny` |
| **Rate limit** | 5 requests/minute per IP |

Open-door onboarding. Allows anyone to join OIUEEI without a prior invitation.

**Request body:**
```json
{ "email": "user@example.com" }
```

**Behaviour:**
1. Validates email via `RequestLinkSerializer`.
2. `get_or_create` user by email.
3. Adds user to all `Collection` objects where `is_onboarding=True`.
4. Creates a `MAGIC_LINK` RSVP and sends a magic link email.
5. Logs request to `security` logger with IP and whether user is new.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Always (unified message) |
| 429 | Rate limited |

---

### MeView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/auth/me/` |
| **Permission** | `IsAuthenticated` |

Returns the current authenticated user's full profile via `UserSerializer`. Updates `last_activity` on each call.

---

### LogoutView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/logout/` |
| **Permission** | `IsAuthenticated` |

Logs out the current user. Reads the refresh token from the `refresh_token` HttpOnly cookie, blacklists it, and clears both `access_token` and `refresh_token` cookies.

### TokenRefreshView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/refresh/` |
| **Permission** | `AllowAny` |

Rotates auth tokens. Reads the `refresh_token` from the HttpOnly cookie, validates it, generates a new access/refresh token pair, and sets them as HttpOnly cookies on the response.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Tokens rotated successfully |
| 401 | Missing, invalid, or expired refresh token |

---

## User Views (`core/views/users.py`)

### can_view_user(viewer_user_code, target_user_code)

Helper function. Returns `True` if:
- Viewer is the target (own profile)
- Target is invited to any collection owned by viewer
- Viewer is invited to any collection owned by target

This provides IDOR protection — users can only see profiles of people connected via collections.

### UserDetailView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/users/{user_code}/` |
| **Permission** | `IsAuthenticated` + `can_view_user()` |

Returns user profile. Own profile returns full data (`UserSerializer`), other profiles return public data (`UserPublicSerializer`) plus a `shared_collections` array (collections where both users are connected as owner/invite) with `code` and `headline` for each.

| | |
|---|---|
| **Endpoint** | `PUT /api/v1/users/{user_code}/` |
| **Permission** | `IsAuthenticated` + own profile only |

Updates own profile via `UserUpdateSerializer` (partial update). Accepts optional `theeeme` field (Theeeme code). Returns 403 if attempting to update another user.

---

## Thing Views (`core/views/things.py`)

### ThingViewSet

| | |
|---|---|
| **Base** | `ModelViewSet` with `DefaultRouter` |
| **Lookup** | `code` |

| Action | Endpoint | Permission |
|--------|----------|------------|
| `list` | `GET /api/v1/things/` | `IsAuthenticated` |
| `create` | `POST /api/v1/things/` | `IsAuthenticated` |
| `retrieve` | `GET /api/v1/things/{code}/` | `IsAuthenticated` + `can_view()` |
| `update` | `PUT /api/v1/things/{code}/` | `IsAuthenticated` + `IsThingOwner` |
| `partial_update` | `PATCH /api/v1/things/{code}/` | `IsAuthenticated` + `IsThingOwner` |
| `destroy` | `DELETE /api/v1/things/{code}/` | `IsAuthenticated` + `IsThingOwner` |
| `activate` | `POST /api/v1/things/{code}/activate/` | `IsAuthenticated` + `IsThingOwner` |
| `hide` | `POST /api/v1/things/{code}/hide/` | `IsAuthenticated` + `IsThingOwner` |

**Serializers:**
- Create: `ThingCreateSerializer`
- Update: `ThingUpdateSerializer` (`status` is read-only to prevent direct manipulation, `type` is editable)
- Read: `ThingSerializer`

**Queryset:** Own things only (`Thing.objects.filter(owner=request.user)`), ordered by `-created`.

**Retrieve:** Uses `thing.can_view(user_code)` — owner, or invited to an ACTIVE collection containing the thing (INACTIVE things are only visible to their owner).

**Create behaviour:** Optionally accepts `collection_code` in request body. If provided, validates the collection exists and the user can add things — returns 400 on invalid or non-permitted collection. If valid, the thing is automatically added to it. WISH_THING and SHARE_THING are restricted to COMMUNITY collections — returns 400 if no collection or if the collection is PROPRIETARY. SWAP_THING requires a swap collection (`is_swap=True`) — returns 400 otherwise. Swap collections only accept SWAP_THING — returns 400 for any other type. EVENT_THING sends an announcement email to all collection invitees on creation.

**`activate` action:** Sets `status = 'ACTIVE'`. Returns 400 if thing is not INACTIVE.

**`hide` action:** Sets `status = 'INACTIVE'`. Thing owner or collection owner can hide. Returns 400 if thing is not ACTIVE (cannot hide a TAKEN thing — cancel the hold first). For SHARE_THING after the first transfer, only the collection owner can hide (returns 403 for the thing owner who is not the collection owner).

### InvitedThingsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/invited-things/` |
| **Permission** | `IsAuthenticated` |
| **Pagination** | `StandardResultsPagination` |

Lists things from collections where the current user is invited. Only returns ACTIVE or TAKEN things (excludes INACTIVE). Only returns things from ACTIVE collections. Uses `.distinct()` to avoid duplicates.

---

## Collection Views (`core/views/collections.py`)

### CollectionViewSet

| | |
|---|---|
| **Base** | `ModelViewSet` with `DefaultRouter` |
| **Lookup** | `code` |

| Action | Endpoint | Permission |
|--------|----------|------------|
| `list` | `GET /api/v1/collections/` | `IsAuthenticated` |
| `create` | `POST /api/v1/collections/` | `IsAuthenticated` |
| `retrieve` | `GET /api/v1/collections/{code}/` | `IsAuthenticated` + `can_view()` |
| `update` | `PUT /api/v1/collections/{code}/` | `IsAuthenticated` + `IsCollectionOwner` |
| `partial_update` | `PATCH /api/v1/collections/{code}/` | `IsAuthenticated` + `IsCollectionOwner` |
| `destroy` | `DELETE /api/v1/collections/{code}/` | `IsAuthenticated` + `IsCollectionOwner` |
| `add_thing` | `POST /api/v1/collections/{code}/add-thing/` | `IsAuthenticated` + `can_add_thing()` |
| `remove_thing` | `POST /api/v1/collections/{code}/remove-thing/` | `IsAuthenticated` + owner or thing owner (COMMUNITY) |

**Serializers:**
- Create: `CollectionCreateSerializer`
- Update: `CollectionUpdateSerializer`
- Add thing: `CollectionAddThingSerializer`
- Read: `CollectionSerializer`

**Queryset:** Own collections only, ordered by `-created`. List and retrieve actions use the module-level `_optimise_collection_queryset()` helper for `select_related`/`prefetch_related` optimisation (also reused by `InvitedCollectionsView`).

**Retrieve:** Uses `collection.can_view(user_code)` — owner, or invited user if collection is ACTIVE (INACTIVE collections are only visible to their owner). The `CollectionSerializer.things` field excludes INACTIVE things for non-owners.

**Add thing:** Uses `collection.can_add_thing(user_code)` — owner can always add; in COMMUNITY mode, invited users can add their own things. Validates thing exists, belongs to user, and is not already in collection.

**Remove thing:** Owner can remove any thing. In COMMUNITY mode, thing owners can remove their own things. Validates thing is in the collection, removes it from the M2M without deleting the thing itself.

### CollectionInviteView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/invite/` |
| **Permission** | `IsAuthenticated` + collection owner |
| **Rate limit** | 30 requests/hour per user |

Invites a user to a collection by email. Creates user if they don't exist (`get_or_create`). Returns 400 if the user is already invited (in M2M). Deletes any existing pending RSVPs for the same user+collection before creating new ones (resend-safe). Creates two RSVPs (`COLLECTION_INVITE` for accept and `COLLECTION_REJECT` for decline) and sends invitation email with both links.

**Request body:**
```json
{ "email": "invitee@example.com" }
```

| | |
|---|---|
| **Endpoint** | `DELETE /api/v1/collections/{collection_code}/invite/` |
| **Permission** | `IsAuthenticated` + collection owner |

Removes a user from the collection's invite list. If the invite is still pending (user has not accepted yet), deletes the pending RSVPs instead of removing from M2M, and no revocation email is sent. If the invite was accepted (user is in M2M), removes from M2M and sends revocation notification email.

**Request body:**
```json
{ "user_code": "ABC123" }
```

### InvitedCollectionsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/invited-collections/` |
| **Permission** | `IsAuthenticated` |

Lists ACTIVE collections where the current user is in the invites M2M. INACTIVE collections are excluded — they are only visible to their owner. Not paginated.

### MyPendingInvitationsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/my-invitations/` |
| **Permission** | `IsAuthenticated` |

Lists pending collection invitations (not yet accepted) for the current user. Returns `COLLECTION_INVITE` RSVPs for the user, joined with the collection and its owner. For each invitation returns: `accept_code`, `reject_code`, `collection_code`, `collection_headline`, `owner_name`. Used to display in-app invitation notifications on the HomePage.

### CollectionBroadcastView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/broadcast/` |
| **Permission** | `IsAuthenticated` + collection owner |
| **Rate limit** | 5 requests/day per user |

Sends a broadcast email from the collection owner to all invitees. Validates `subject` (SafeHeadlineField, max 64) and `message` (SafeTextField, max 256) via `CollectionBroadcastSerializer`. Returns 400 if the collection has no invitees. Emails include a `Reply-To` header set to the owner's email so invitees can respond directly.

**Request body:**
```json
{ "subject": "Meeting tonight", "message": "Bring snacks please" }
```

**Response (200):**
```json
{ "message": "Broadcast sent", "recipients": 5 }
```

---

## FAQ Views (`core/views/faq.py`)

### ThingFAQListView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/faq/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |
| **Pagination** | `StandardResultsPagination` |

Lists FAQs for a thing. Owner sees all FAQs (including hidden). Invited users see only visible FAQs.

**Response fields:** `code`, `thing`, `created`, `questioner` (user code), `questioner_name` (user display name), `question`, `answer`, `is_visible`.

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/faq/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner |
| **Rate limit** | 20 requests/hour per user |

Creates a new FAQ question. Owner cannot ask questions about their own thing (400). Sends notification email to thing owner with a "View and reply" link to the thing page.

**Request body:**
```json
{ "question": "Is this available in blue?" }
```

### FAQDetailView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/faq/{faq_code}/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Returns a single FAQ. Hidden FAQs are only visible to the thing owner and the questioner. Returns 404 for others.

### FAQAnswerView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/answer/` |
| **Permission** | `IsAuthenticated` + thing owner only |

Answers a FAQ. Sends notification email to questioner.

**Request body:**
```json
{ "answer": "Yes, it comes in blue." }
```

### FAQVisibilityView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/hide/` |
| **Permission** | `IsAuthenticated` + thing owner only |

Hides a FAQ. Sends notification email to questioner (includes thing headline only, no question text).

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/show/` |
| **Permission** | `IsAuthenticated` + thing owner only |

Shows a previously hidden FAQ.

---

## Upload Views (`core/views/upload.py`)

### CloudinarySignatureView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/upload/signature/` |
| **Permission** | `IsAuthenticated` |

Generates a short-lived Cloudinary signed upload signature so the frontend can upload images directly to Cloudinary without routing the binary data through Django.

**Request body:**
```json
{ "folder": "oiueei/things", "resource_type": "image" }
```

Allowed folder values: `oiueei/users`, `oiueei/things`, `oiueei/collections`, `oiueei/documents`. Any other value falls back to `oiueei/users`.

Allowed `resource_type` values: `image` (default), `raw` (for document uploads). Any other value falls back to `image`.

**Response:**
```json
{
    "signature": "abc123...",
    "timestamp": 1234567890,
    "api_key": "...",
    "cloud_name": "hixm8hed8",
    "folder": "oiueei/things",
    "resource_type": "image"
}
```

**Frontend upload flow:**
1. Call this endpoint to get a signature.
2. POST the file directly to `https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload` with the signature parameters. Use `image/upload` for images and `raw/upload` for documents.
3. Cloudinary returns a `public_id` (e.g. `oiueei/things/abc123`).
4. Save the `public_id` to the relevant Django model field (`thumbnail`, `hero`, or append to `pictures`).

---

## Theeeme Views (`core/views/theeemes.py`)

### TheeemeListView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/theeemes/` |
| **Permission** | `IsAuthenticated` |

Lists all available theeemes. Returns `code` and `name` for each theeeme via `TheeemeSerializer`.

---

## Booking Views (`core/views/booking.py`)

### ThingCalendarView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/calendar/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Returns blocked periods for a thing's calendar. Owner sees full details (`BookingPeriodOwnerCalendarSerializer`), guests see only dates and status (`BookingPeriodCalendarSerializer`). For ASSET_THING and APPOINTMENT_THING, all users who can view the thing see full details (owner calendar serializer) — this enables shared calendar visibility.

### MyBookingsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/my-bookings/` |
| **Permission** | `IsAuthenticated` |
| **Pagination** | `StandardResultsPagination` |

Lists all booking requests made by the current user, ordered by `-created`.

### OwnerBookingsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/owner-bookings/` |
| **Permission** | `IsAuthenticated` |
| **Pagination** | `StandardResultsPagination` |

Lists all booking requests for things owned by the current user, ordered by `-created`.

### BookingCancelView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/cancel/` |
| **Permission** | `IsAuthenticated` + booking requester |

Allows the requester to cancel their own pending booking. Validates `booking.requester_code == request.user`, checks `is_valid()`. Calls `cancel_booking()` service (restores Thing status to ACTIVE for single-use types), and deletes related RSVPs.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Cancelled |
| 400 | Booking expired or already processed |
| 403 | Not the requester |
| 404 | Booking not found |

### BookingActionView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/accept/` |
| **Permission** | `IsAuthenticated` + booking owner |

Accepts a pending booking. Validates `booking.owner_code == request.user`, checks `is_valid()`. Calls `accept_booking()` service, sends decision email via `send_booking_decision_email()`, and deletes related RSVPs (`BOOKING_ACCEPT`/`BOOKING_REJECT`) to invalidate old email links.

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/reject/` |
| **Permission** | `IsAuthenticated` + booking owner |

Rejects a pending booking. Same permission and validation as accept. Calls `reject_booking()` service, sends decision email, and deletes related RSVPs.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Action completed |
| 400 | Booking expired or already processed |
| 403 | Not the booking owner |
| 404 | Booking not found |

---

## Slots Views (`core/views/slots.py`)

### ThingSlotsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/slots/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Returns a weekly slot grid for APPOINTMENT_THING. Only available for things with `type == "APPOINTMENT_THING"` — returns 400 for other types.

**Query parameters:**
- `week_start` — Monday of target week (YYYY-MM-DD). Defaults to current week's Monday.

**Response (200):**
```json
{
  "week_start": "2026-04-20",
  "slot_duration": 30,
  "days": [
    {
      "date": "2026-04-20",
      "day_of_week": 1,
      "slots": [
        {"start_time": "09:00", "end_time": "09:30", "status": "available"},
        {"start_time": "09:30", "end_time": "10:00", "status": "booked", "requester_name": "Lele"}
      ]
    }
  ]
}
```

**Algorithm:**
1. Reads `availability_schedule` (JSONField) and `slot_duration` from the thing.
2. For each day Mon–Sun, checks if that ISO weekday appears in any schedule window.
3. Generates slot start times from window start to window end, stepping by `slot_duration`.
4. Fetches BookingPeriod records (PENDING + ACCEPTED) for the target week.
5. Marks each slot as `available`, `pending`, or `booked`. Booked/pending slots include `requester_name`.

---

## Reservation Views (`core/views/reservations.py`)

### ThingRequestView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/request/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner |
| **Rate limit** | 10 requests/hour per user |

Creates a reservation/booking request. Returns 400 for EVENT_THING and WISH_THING (these types bypass BookingPeriod). Routes based on thing type:

**Hourly (APPOINTMENT_THING, or ASSET_THING with booking_unit=HOUR):**
- Requires `start_date`, `start_time`, and `end_time`.
- Creates a same-day booking (`start_date == end_date`) with time range.
- Checks for time-range overlap via `BookingPeriod.has_overlap()` with time params. Returns 409 if conflict.
- Thing stays `ACTIVE`.

**Request body:**
```json
{ "start_date": "2025-06-01", "start_time": "09:00", "end_time": "12:00" }
```

**Date-based (LEND/RENT/SHARE/ASSET_THING with booking_unit=DAY):**
- Requires `start_date` and `end_date`.
- Checks for overlap via `BookingPeriod.has_overlap()`. Returns 409 if conflict.
- Thing stays `ACTIVE` (multiple bookings for different date ranges allowed).

**Request body:**
```json
{ "start_date": "2025-06-01", "end_date": "2025-06-15" }
```

**Order (ORDER_THING):**
- Requires `delivery_date` and `quantity`.
- Thing stays `ACTIVE` (multiple orders allowed).

**Request body:**
```json
{ "delivery_date": "2025-06-01", "quantity": 3 }
```

**Swap (SWAP_THING):**
- Requires `offered_thing_codes` (list of thing codes to offer in exchange).
- Each offered thing must: be SWAP_THING, be owned by the requester, be ACTIVE, be in the same swap collection.
- Creates `BookingPeriod` with no dates, links offered things via M2M.
- Thing stays `ACTIVE`. Sends swap-specific emails via `_send_swap_email()`.

**Request body:**
```json
{ "offered_thing_codes": ["THNG01", "THNG02"] }
```

**Standard (GIFT/SELL):**
- No extra fields required.
- Checks for existing pending request from same user. Returns 400 if duplicate.
- Thing status changes to `TAKEN` (blocks other requests).

**Common behaviour:**
1. Validates owner email in the parent `post()` method (shared across all type handlers).
2. Creates `BookingPeriod` with status `PENDING`.
3. Creates two RSVPs (`BOOKING_ACCEPT` and `BOOKING_REJECT`) for the owner's email action links via `_send_booking_email()` (or `_send_swap_email()` for SWAP_THING).
4. Sends booking request email to owner with accept/reject links, and a confirmation email to the requester ("Hold request sent" / "Swap request sent").

**INACTIVE collection enforcement:**
If all collections containing the thing are INACTIVE, the request is blocked with 400 "This collection is currently inactive".

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Request sent |
| 400 | Own thing / already pending / invalid data / collection inactive |
| 403 | Not authorised to view thing |
| 409 | Date overlap (date-based only) |

---

## Transfer Views (`core/views/transfers.py`)

### ThingTransferView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/transfers/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Returns the transfer history (Loan Chain) and aggregate stats for a thing.

**Response (200):**
```json
{
  "total_transfers": 3,
  "unique_homes": 4,
  "current_holder": "ABC123",
  "current_holder_name": "Lala",
  "original_owner": "ABC123",
  "original_owner_name": "Lala",
  "is_share_in_community": true,
  "transfers": [
    {
      "code": "XYZ789",
      "from_user": "ABC123",
      "to_user": "DEF456",
      "from_user_name": "Lala",
      "to_user_name": "Lele",
      "lent_date": "2026-04-01",
      "returned_date": "2026-04-10"
    }
  ]
}
```

**Behaviour:**
1. Looks up thing by `thing_code`. Returns 404 if not found.
2. Checks `thing.can_view(user_code)`. Returns 403 if not authorised.
3. Queries all transfers for the thing, ordered by `-lent_date`.
4. Computes `unique_homes` (distinct user codes across all `from_user` and `to_user` fields).
5. Computes `current_holder` from the most recent unreturned transfer's `to_user`.
6. Computes `original_owner` from the `from_user` of the oldest transfer (by `lent_date`). Null if no transfers.
7. Computes `is_share_in_community`: True when the thing is a `SHARE_THING` and belongs to at least one `COMMUNITY` collection.

## Stats Views (`core/views/stats.py`)

### ThingStatsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/stats/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Returns aggregated usage statistics for a thing, based on ACCEPTED bookings. Primarily designed for ASSET_THING but works for any thing type.

**Response (200):**
```json
{
  "total_bookings": 12,
  "unique_users": 4,
  "monthly_usage": [
    {
      "month": "2026-04",
      "user_code": "ABC123",
      "user_name": "Lala",
      "bookings": 3
    }
  ]
}
```

**Behaviour:**
1. Looks up thing by `thing_code`. Returns 404 if not found.
2. Checks `thing.can_view(user_code)`. Returns 403 if not authorised.
3. Aggregates ACCEPTED bookings using `TruncMonth` annotation, grouped by month and requester.
4. Returns total booking count, unique user count, and per-user-per-month breakdown.

---

## Event Views (`core/views/events.py`)

### EventAttendView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/attend/` |
| **Permission** | `IsAuthenticated` |

Toggles attendance for an EVENT_THING using the `deal` M2M field. Returns 400 for non-event things. Returns 403 for users who cannot view the thing. Owner cannot attend their own event.

**Response:**
```json
{ "attending": true, "attendee_count": 5 }
```

### EventAttendeesView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/attendees/` |
| **Permission** | `IsAuthenticated` |

Lists attendees for an EVENT_THING. Returns 400 for non-event things. Returns 403 for users who cannot view the thing.

**Response:**
```json
{ "attendee_count": 2, "attendees": [{ "code": "ABC123", "name": "User Name" }] }
```

## Wish Views (`core/views/wishes.py`)

### WishOfferHelpView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/offer-help/` |
| **Permission** | `IsAuthenticated` |

Toggles "I can help" for a WISH_THING using the `deal` M2M field. Returns 400 for non-wish things. Returns 403 for users who cannot view the thing. Owner cannot offer help on their own wish.

**Response:**
```json
{ "offering": true, "helper_count": 3 }
```

### WishHelpersView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/helpers/` |
| **Permission** | `IsAuthenticated` |

Lists helpers for a WISH_THING. Returns 400 for non-wish things. Returns 403 for users who cannot view the thing.

**Response:**
```json
{ "helper_count": 2, "helpers": [{ "code": "ABC123", "name": "User Name" }] }
```

---

### Management Command: `close_transfers`

Daily command (`python manage.py close_transfers`) that closes overdue transfers:
- Finds unreturned `ThingTransfer` records linked to `ACCEPTED` bookings whose `end_date < today`.
- Sets `returned_date = today` via bulk update.
- Outputs count of closed transfers.

### Management Command: `send_reminders`

Daily command (`python manage.py send_reminders`) that sends reminder emails:
- **Booking return reminders**: ACCEPTED bookings with `end_date = tomorrow` — notifies thing owner.
- **Delivery reminders**: ACCEPTED bookings with `delivery_date = tomorrow` — notifies thing owner.
- **Event reminders**: ACTIVE EVENT_THINGs with `event_date` tomorrow — notifies all attendees (via `deal` M2M).
- Outputs count of reminder emails sent.

### Management Command: `send_digests`

Daily command (`python manage.py send_digests`) that sends digest emails:
- **Weekly digests**: sent on Mondays for collections with `digest_frequency = "WEEKLY"`. Lists things added in the past 7 days.
- **Monthly digests**: sent on the 1st of each month for collections with `digest_frequency = "MONTHLY"`. Lists things added in the previous month.
- Skips collections with no new things or no invitees.
- Outputs count of digest emails sent.

---

## Custom Permissions (`core/permissions.py`)

| Permission | Logic |
|-----------|-------|
| `IsThingOwner` | `obj.owner_id == request.user.code` |
| `IsCollectionOwner` | `obj.owner_id == request.user.code` |

---

## Security

### Authentication & Authorisation

1. **Invite-only registration** — Users cannot self-register. They must be invited to a collection first.
2. **Magic link authentication** — Passwordless via email. RSVPs expire after 24 hours and are one-time use.
3. **JWT tokens** — HttpOnly cookie-based. Access tokens expire after 1 hour. Refresh tokens expire after 7 days. Tokens are rotated on refresh via `POST /api/v1/auth/refresh/`, old tokens blacklisted.
4. **IDOR protection** — `can_view_user()` ensures users can only view profiles of people connected via collections.
5. **Custom DRF permissions** — `IsThingOwner` and `IsCollectionOwner` in `core/permissions.py`.

### Input Validation

1. **Image IDs** — Only alphanumeric characters, underscores, and hyphens allowed.
2. **Headlines** — HTML tags rejected to prevent XSS.
3. **Quantities** — Order quantities capped at 99.
4. **Dates** — Start dates must be today or future. End dates must be >= start dates.
5. **Email HTML** — All user content escaped via `django.utils.html.escape()` in `email_service.py`.

### Rate Limiting

- `/auth/request-link/` — 5 requests per minute per IP
- `/auth/verify/{code}/` — 10 requests per minute per IP
- `/collections/{code}/invite/` POST — 30 requests per hour per user
- `/things/{code}/request/` POST — 10 requests per hour per user
- `/things/{code}/faq/` POST — 20 requests per hour per user
- `/collections/{code}/broadcast/` POST — 5 requests per day per user

### Secure Code Practices

1. **ID generation** — Uses `secrets.choice()` for cryptographically secure random IDs.
2. **SECRET_KEY** — Required from environment variable, not hardcoded.
3. **RSVP obfuscation** — Real codes never exposed in URLs.
4. **Security logging** — Auth events logged with IP addresses.
5. **Production hardening** — HSTS, secure cookies, SSL redirect, custom admin path, JSON-only renderer.

---

## Architecture Notes

### View Patterns

- All views use `get_object_or_404` for consistent 404 responses.
- `ThingViewSet` and `CollectionViewSet` use DRF `ModelViewSet` with `DefaultRouter`.
- `ThingUpdateSerializer` has `status` as read-only to prevent direct status manipulation. `type` is editable. Use `POST /api/v1/things/{code}/activate/` to set status ACTIVE (from INACTIVE), and `POST /api/v1/things/{code}/hide/` to set status INACTIVE (from ACTIVE only).
- `ThingSerializer` and `CollectionThingSummarySerializer` include `pending_booking` (first PENDING booking code, or null) and `pending_questions` (count of unanswered FAQs).
- Accept/reject actions can be performed via the unified RSVP endpoint (`VerifyLinkView`) for email links, or via authenticated `BookingActionView` endpoints for in-app use. Both paths reuse the same `accept_booking()`/`reject_booking()` service functions.
- All email links use RSVP codes as intermediaries to avoid exposing real object codes in URLs.
- Security events are logged to the `security` logger with IP addresses.

### Service Layer

Business logic is extracted into `core/services/`:
- `email_service.py` — All email HTML composition and sending (8 functions). Uses `django.utils.html.escape()`.
- `booking_service.py` — `accept_booking()`, `reject_booking()`, and `cancel_booking()` handle status transitions for Thing and BookingPeriod, wrapped in `transaction.atomic()`.

### Utilities

- `core/utils.py`: `generate_id()`, `get_client_ip()`, `cloudinary_url()` — `cloudinary_url(public_id)` now uses the Cloudinary Python SDK (`cloudinary.utils.cloudinary_url`) with `fetch_format=auto` and `quality=auto`, replacing the previous hardcoded URL template.
- `core/validators.py`: `ImageIdField`, `SafeHeadlineField`, `SafeTextField`, `validate_image_id()`, `validate_headline()`
- `core/pagination.py`: `StandardResultsPagination` (max 100 items)
