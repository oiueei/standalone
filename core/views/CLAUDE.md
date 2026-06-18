# OIUEEI Views Documentation

This document describes the behaviour, endpoints, permissions, and business logic for each view in the OIUEEI application.

---

## Auth Views (`core/views/auth.py`)

### RequestLinkView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/request-link/` |
| **Permission** | `AllowAny` |
| **Rate limit** | 5 requests/minute per IP **and** 5 requests/hour per account (the requested email, lowercased — `email_ratelimit_key`) so one mailbox can't be flooded from rotating IPs. |

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
| **Endpoint** | `GET /api/v1/auth/verify/{token}/` (also aliased at `GET /api/v1/rsvp/{token}/`) |
| **Permission** | `AllowAny` |
| **Rate limit** | 10 requests/minute per IP |

The URL segment is the RSVP's high-entropy `token` (≈134 bits), not the 6-char PK — the PK can no longer resolve an RSVP.

Processes all RSVP-based actions. Routes to the appropriate handler based on `rsvp.action`:

| Action | Handler | Description |
|--------|---------|-------------|
| `MAGIC_LINK` | `_handle_magic_link` | Authenticates user, sets auth cookies |
| `COLLECTION_INVITE` | `_handle_collection_invite` | Adds user to collection invites M2M, sets auth cookies, deletes sibling `COLLECTION_REJECT` RSVP |
| `COLLECTION_REJECT` | `_handle_collection_reject` | Notifies collection owner of rejection, deletes sibling `COLLECTION_INVITE` RSVP, no JWT |
| `BOOKING_ACCEPT` | `_handle_booking_accept` | Accepts booking via `accept_booking()` service |
| `BOOKING_REJECT` | `_handle_booking_reject` | Rejects booking via `reject_booking()` service |

**Common behaviour:**
1. Looks up RSVP by `token` (the high-entropy URL token, not the PK). Returns 401 if not found.
2. Checks `rsvp.is_valid()` (24h expiry). Deletes and returns 401 if expired.
3. Delegates to action handler.
4. RSVP is deleted after use (one-time use).

**Internal helpers:**
- `_authenticate_user(request, rsvp)` — Shared by `MAGIC_LINK` and `COLLECTION_INVITE` handlers. Validates user, calls `update_last_activity()`, mints a JWT. Returns `(user, refresh, user_data)` tuple or `Response` on failure. Auth tokens are set as HttpOnly cookies via `_set_auth_cookies()`. Auth is JWT-cookie-only — it deliberately does **not** open a Django session (no `login()`); the admin site has its own session, so a shadow session would be needless attack surface.
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
{ "email": "user@example.com", "share_token": "<optional 22-char token>" }
```

**Behaviour:**
1. Validates email via `RequestLinkSerializer`.
2. Reads optional `share_token` from the body.
3. `get_or_create` user by email.
4. If a valid `share_token` is provided **and** the matching `Collection` is `ACTIVE`, adds the user to that collection's `invites` M2M. Invalid, missing, or pointing-to-INACTIVE tokens are silently ignored (anti-enumeration: response shape is identical regardless).
5. If the user did not join via `share_token`, falls back to adding them to all `is_onboarding=True` collections.
6. Creates a `MAGIC_LINK` RSVP and sends a magic link email.
7. Logs request to `security` logger with IP, whether user is new, and whether they joined via share token.

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

Logs out the current user. Reads the refresh token from the `refresh_token` HttpOnly cookie (scoped to `/api/v1/auth/` so it actually reaches this endpoint — `REFRESH_COOKIE_PATH`), blacklists it so it can't be reused to refresh, and clears both `access_token` and `refresh_token` cookies.

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

Updates own profile via `UserUpdateSerializer` (partial update). Accepts optional `name`, `headline`, `about` (Markdown bio, max 2000, HTML rejected), `photo` (Cloudinary public_id), `koro`, `theeeme` (Theeeme code), `notify_activity`, and `notify_news`. Returns the full `UserSerializer` (including `photo_url`). Returns 403 if attempting to update another user.

---

## Notification Preference Views (`core/views/notifications.py`)

### NotificationsByTokenView

| | |
|---|---|
| **Endpoints** | `GET /api/v1/notifications/token/{token}/` and `PATCH /api/v1/notifications/token/{token}/` |
| **Permission** | `AllowAny` |
| **Rate limits** | GET: 20/min per IP. PATCH: 10/min per IP. |

Unauthenticated endpoint scoped to editing `notify_activity` / `notify_news` on a specific user. The token is a `TimestampSigner` signature over the user's code (salt `notifications-prefs`, ~1-year TTL — no stored column), produced by `core.services.email_service.make_notifications_token()` and resolved by `verify_notifications_token()`; every Cat. 2 / Cat. 3 email footer contains a link of the form `/me/notifications/{token}`.

**Behaviour:**
- Resolves the token via `verify_notifications_token()`. Returns 401 `{ "detail": "Invalid or expired link" }` if invalid.
- On GET: returns `{ notify_activity, notify_news }` for the signed user.
- On PATCH: accepts partial `{ notify_activity?, notify_news? }` via `NotificationPrefsSerializer` and persists the change.
- Token has blast radius limited to these two booleans — it cannot be used to read or modify anything else.

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
| `destroy` | `DELETE /api/v1/things/{code}/` | `IsAuthenticated` + `_can_delete()` |
| `activate` | `POST /api/v1/things/{code}/activate/` | `IsAuthenticated` + `IsThingOwner` |
| `hide` | `POST /api/v1/things/{code}/hide/` | `IsAuthenticated` + `IsThingOwner` |

**Serializers:**
- Create: `ThingCreateSerializer`
- Update: `ThingUpdateSerializer` (`status` is read-only to prevent direct manipulation, `type` is editable)
- Read: `ThingSerializer`

**Queryset:** Own things only (`Thing.objects.filter(owner=request.user)`), ordered by `-created`.

**Retrieve:** Uses `thing.can_view(user_code)` — owner, or invited to an ACTIVE collection containing the thing (INACTIVE things are only visible to their owner).

**Create behaviour:** Optionally accepts `collection_code` in request body. If provided, validates the collection exists and the user can add things — returns 400 on invalid or non-permitted collection. If valid, the thing is automatically added to it. WISH_THING and SHARE_THING are restricted to COMMUNITY collections — returns 400 if no collection or if the collection is PROPRIETARY. SWAP_THING requires a swap collection (`is_swap=True`) — returns 400 otherwise. Swap collections only accept SWAP_THING — returns 400 for any other type. Minimalist collections (`is_minimalist=True`) only accept GIFT_THING, SHARE_THING, and SWAP_THING — returns 400 for other types — and require a thumbnail (photo) — returns 400 if missing. **Per-collection allowlist** (`Collection.allowed_thing_types`): if non-empty, the thing's type must be in it — returns 400 otherwise. Empty list = no per-collection restriction. **Tags**: any `tags` on the thing must belong to the collection's `Collection.tags` vocabulary — returns 400 otherwise (tags require a collection; on update, `ThingUpdateSerializer.validate_tags` checks the union of the thing's collections' tags). Removing a tag from a collection (via `CollectionUpdateSerializer`) cascade-strips it from that collection's things. **Group notice**: for `WISH_THING`, the request body may include `notify_group` (boolean, default `true`); when on, creating the wish in a COMMUNITY collection emails every other group member via `send_wish_posted_email` and bulk-creates a `WISH_POSTED` in-app notification (payload: `wish_headline`, `creator_name`, `wish_code`, `collection_code`) for each.

**`activate` action:** Sets `status = 'ACTIVE'`. Returns 400 if thing is not INACTIVE.

**`hide` action:** Sets `status = 'INACTIVE'`. Only the current thing owner (`thing.owner`) can hide — returns 403 for everyone else. Returns 400 if thing is not ACTIVE (cannot hide a TAKEN thing — cancel the hold first).

**`destroy` action (`_can_delete()`):** Permanent deletion (the thing and all related data). Two cases grant permission: (1) the user owns any collection containing the thing (collection owner can always delete); (2) the user is the current thing owner AND no `ThingTransfer` records exist (thing has never changed hands). Returns 403 otherwise. Frontend shows the Delete button for the collection owner regardless of thing status; for the thing owner, Delete is only shown when `transfer_count === 0` (for SHARE_THING) — otherwise the button is hidden.

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

### CollectionShareLinkView

| | |
|---|---|
| **Endpoints** | `POST` and `DELETE /api/v1/collections/{collection_code}/share-link/` |
| **Permission** | `IsAuthenticated` + collection owner |
| **Rate limit** | POST: 30 requests/hour per user. DELETE: unrestricted. |

Owner-only management of the public share token. The token is a 22-character URL-safe bearer credential (`secrets.token_urlsafe(16)`); anyone with the resulting `/share/{token}` link can join the collection by completing the pop-in flow. The token is intentionally excluded from `CollectionSerializer` and any other read endpoint — it must never leak.

**`POST` behaviour:**
- Generates a new token if none exists. Returns the existing token unchanged on subsequent calls (idempotent).
- Pass `{"rotate": true}` to force a fresh token (invalidates any previously shared link).
- Returns `{share_url, share_token}`. `share_url` is built from `settings.SHARE_LINK_BASE_URL` (default `http://localhost:3000/share`).

**`DELETE` behaviour:**
- Sets `share_token` back to `null`. The shared link becomes invalid for everyone immediately.
- Returns `{"message": "Share link revoked"}`.

**Frontend integration:** `ShareCollectionMenu` (HDS Select with `IconEnvelope` / `IconShare` / `IconWhatsapp`) calls `POST` lazily the first time the owner triggers any share action. The URL is cached for the rest of the session to avoid extra round-trips.

### CollectionBroadcastView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/broadcast/` |
| **Permission** | `IsAuthenticated` + collection owner |
| **Rate limit** | 5 requests/day per user |

Sends a broadcast email from the collection owner to all invitees. Validates `message` (SafeTextField, max 256) via `CollectionBroadcastSerializer`; the subject is auto-generated as `Hey! {collection_headline}` (the owner does not provide one). Returns 400 if the collection has no invitees. Emails carry a `Reply-To` header (the owner) and a link to the collection (labelled "I can help!"); the in-app `BROADCAST` notification carries `collection_code` so it can deep-link there too.

**Request body:**
```json
{ "message": "Bring snacks please" }
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

Generates a short-lived Cloudinary signed upload signature so the frontend can upload files directly to Cloudinary without routing the binary data through Django. The signature binds every parameter, so a client cannot tamper with them: the **`public_id` is generated server-side** (preventing arbitrary ids / overwrites), `allowed_formats` restricts accepted formats (raster photo formats for image folders — SVG excluded; PDF/Office/Markdown for the documents folder), `resource_type` is derived from the folder (not client-trusted), and documents upload as **`type=authenticated`** (private — see `DocumentDownloadView`). Cloudinary's `max_file_size` is not enforced on the current plan, so the per-file size cap stays a client-side check.

**Request body:**
```json
{ "folder": "oiueei/things" }
```

Allowed folder values: `oiueei/users`, `oiueei/things`, `oiueei/collections`, `oiueei/documents`. Any other value falls back to `oiueei/users`. `resource_type` is derived from the folder (`raw` for `oiueei/documents`, otherwise `image`) — it is no longer taken from the client.

**Response:**
```json
{
    "signature": "abc123...",
    "timestamp": 1234567890,
    "api_key": "...",
    "cloud_name": "...",
    "folder": "oiueei/things",
    "public_id": "<server-generated>",
    "allowed_formats": "jpg,jpeg,png,...",
    "resource_type": "image",
    "type": "authenticated"
}
```
(`type` is returned for the documents folder only.)

**Frontend upload flow:**
1. Call this endpoint to get the signed parameters.
2. POST the file directly to `https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload`, sending the signed parameters back verbatim (`folder`, `public_id`, `allowed_formats`, and — for documents — `type`).
3. Cloudinary returns the final `public_id` (folder-prefixed, with the file extension for raw documents) — store **that** returned value.
4. Save the `public_id` to the relevant Django model field (`thumbnail` cover, the `User.photo` profile photo, append to a Thing's `gallery`, or a Thing `documents` entry).

### DocumentDownloadView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/documents/{index}/download/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Documents are uploaded privately (`type=authenticated`), so their plain Cloudinary URL 404s — this gated endpoint is the only way to obtain a working URL. It checks the caller can view the thing, then 302-redirects to a short-lived (5 min) signed `private_download_url` minted by `core.utils.signed_document_url()`. `ThingSerializer.document_urls` points here (never at a raw Cloudinary URL), and the raw `documents` array (carrying public_ids) is serialised to the owner only.

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

Returns blocked periods for a thing's calendar. Owner sees full details (`BookingPeriodOwnerCalendarSerializer`), guests see only dates and status (`BookingPeriodCalendarSerializer`).

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

## Reservation Views (`core/views/reservations.py`)

### ThingRequestView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/request/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner |
| **Rate limit** | 10 requests/hour per user |

Creates a reservation/booking request. Returns 400 for WISH_THING (this type bypasses BookingPeriod). Routes based on thing type:

**Share (SHARE_THING)** — handled by `_handle_share_request()`:
- NOT date-based — no `start_date`/`end_date` fields.
- Permanent ownership transfer on acceptance; thing stays `ACTIVE`.
- Multiple pending requests from different users are allowed.
- Returns 400 if the requesting user already has a PENDING request for this thing.

**Date-based (LEND/RENT):**
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
- **Minimum-items gate** (`Collection.swap_minimum_items`): if `>0`, the requester must already have at least that many own SWAP_THINGs (status ACTIVE or TAKEN) in the same collection — otherwise returns 400 with the message "You need to upload at least N item(s) to this collection before you can propose a swap." Applies symmetrically to guests AND the collection owner (owners only request swaps on guests' things, but the rule treats them the same). Frontend mirrors the gate via `collection_swap_minimum_items` + `my_swap_count_in_collection` on the thing serializer.
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

**Paused collection enforcement:**
If all active collections containing the thing have a non-empty `pause_message` (i.e. are paused), the request is blocked with 400 "This collection is currently paused". Collections that are paused remain visible but no new hold requests are accepted.

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

---

## Wish Views (`core/views/wishes.py`)

A wish is a `Thing` of type `WISH_THING` (reusing `ThingViewSet` for create/edit/hide). These views add the structured-answer layer on top: members answer with `WishResponse` objects ("Tengo esto" / "Sé dónde" / "Puedo hacértelo") instead of a reservation, and the creator accepts one and resolves the wish. All return 400 if the target `Thing` is not a `WISH_THING`.

### ThingWishResponseView

| | |
|---|---|
| **Endpoints** | `GET` and `POST /api/v1/things/{thing_code}/responses/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |
| **Rate limit** | POST: 20 requests/hour per user |
| **Pagination** | `StandardResultsPagination` |

`GET` lists answers — the wish creator sees every answer; any other member sees only their own. `POST` answers the wish via `WishResponseCreateSerializer`: `kind=HAVE_THIS` requires `thing_code` (a real listing **owned by the responder** — 400 otherwise); `KNOW_WHERE`/`CAN_MAKE` require `message` (plus optional `url` / `fee`). The owner cannot answer their own wish (400). On success, emails the creator via `send_wish_response_email()` and creates a `WISH_RESPONSE` `InAppNotification`.

### WishResponseAcceptView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/wish-responses/{code}/accept/` |
| **Permission** | `IsAuthenticated` + wish creator only |

Marks one `WishResponse` `ACCEPTED` (others stay `PENDING`) — this is the "reserve" applied to the answer, not the wish, so two members can't both think they won. Creates a `WISH_ACCEPTED` `InAppNotification` for the responder. Returns 403 for anyone but the wish creator.

### WishResolveView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/resolve/` |
| **Permission** | `IsAuthenticated` + wish creator only |

Sets the wish `Thing.status` to `INACTIVE` (so it leaves the active board — the repo's soft-delete pattern), and emails the accepted responder a thank-you via `send_wish_thanks_email()`. Returns 400 if the wish is already resolved (not `ACTIVE`), 403 for non-creators. Reopen with the standard `POST /things/{code}/activate/`.

> The previous "I can help" toggle (`offer-help` / `helpers` endpoints on the `deal` M2M) was replaced by this structured-answer flow.

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
- Outputs count of reminder emails sent.

### Management Command: `send_digests`

Daily command (`python manage.py send_digests`) that sends digest emails and newsletters:
- **Weekly digests**: sent on Mondays for collections with `digest_frequency = "WEEKLY"`. Lists things added in the past 7 days.
- **Monthly digests**: sent on the 1st of each month for collections with `digest_frequency = "MONTHLY"`. Lists things added in the previous month.
- **Weekly newsletters**: sent on Mondays for share collections with `newsletter_enabled = True`. Includes two blocks: (1) new things added in the past 7 days, (2) ownership changes (ThingTransfer records) in the past 7 days. Skips collections with no activity or no invitees.
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

- `/auth/request-link/` — 5 requests per minute per IP **and** 5 per hour per account (email)
- `/auth/pop-in/` — 5 requests per minute per IP **and** 5 per hour per account (email)
- `/auth/verify/{token}/` — 10 requests per minute per IP
- `/collections/{code}/invite/` POST — 30 requests per hour per user
- `/things/{code}/request/` POST — 10 requests per hour per user
- `/things/{code}/faq/` POST — 20 requests per hour per user
- `/collections/{code}/broadcast/` POST — 5 requests per day per user
- `/collections/{code}/share-link/` POST — 30 requests per hour per user
- `/notifications/token/{t}/` — GET 20/min per IP, PATCH 10/min per IP

### Secure Code Practices

1. **ID generation** — Uses `secrets.choice()` for cryptographically secure random IDs.
2. **SECRET_KEY** — Required from environment variable, not hardcoded.
3. **RSVP obfuscation + high-entropy links** — Email/magic links carry the RSVP's 26-char (~134-bit) `token` via `generate_token()`, never the 6-char PK or real object codes, so they resist both enumeration and brute force.
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
