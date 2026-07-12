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
| **Endpoint** | `GET` / `POST /api/v1/auth/verify/{token}/` (also aliased at `/api/v1/rsvp/{token}/`) |
| **Permission** | `AllowAny`. **`authentication_classes = []`** — the ~134-bit URL token is the bearer credential, so no authenticator runs; this also keeps `POST` clear of DRF's `SessionAuthentication` CSRF gate (no handler reads `request.user`). |
| **Rate limit** | 10 requests/minute per IP (GET and POST keyed separately) |

The URL segment is the RSVP's high-entropy `token` (≈134 bits), not the 6-char PK — the PK can no longer resolve an RSVP.

**GET vs POST — `BOOKING_ACCEPT`/`BOOKING_REJECT` require a POST to commit.** These two decisions are irreversible and authenticate no one, so a bare GET must never fire them — an email link-scanner or a page prefetch/refresh could otherwise auto-decide a hold. For those actions **GET only previews** (`200 {"action", "requires_confirmation": true, "thing_headline"}` — no mutation, RSVP not consumed); the frontend `VerifyPage` then **auto-fires the committing POST from JS** on load (one click for the owner — opening the link — with no second on-page button). This keeps the anti-prefetch guarantee: a scanner/prefetch does a bare GET, runs no JS, and so never reaches the committing POST. The login/invite actions (`MAGIC_LINK`, `COLLECTION_INVITE`, `COLLECTION_REJECT`) still resolve on GET — a scanner that consumes one only forces a fresh link; it decides nothing on the user's behalf.

Routes to the appropriate handler based on `rsvp.action`:

| Action | Handler | Commit verb | Description |
|--------|---------|-------------|-------------|
| `MAGIC_LINK` | `_handle_magic_link` | GET | Authenticates user, sets auth cookies, and returns the `landing` contract below |
| `COLLECTION_INVITE` | `_handle_collection_invite` | GET | Adds user to collection invites M2M, sets auth cookies, deletes sibling `COLLECTION_REJECT` RSVP. Returns `landing: "collection"` + `collection` + `invited_collection` (or `landing: "home"` if the collection was deleted meanwhile) |
| `COLLECTION_REJECT` | `_handle_collection_reject` | GET | Notifies collection owner of rejection, deletes sibling `COLLECTION_INVITE` RSVP, no JWT |
| `BOOKING_ACCEPT` | `_handle_booking_accept` | **POST** | Accepts booking via `accept_booking()` service (GET previews only) |
| `BOOKING_REJECT` | `_handle_booking_reject` | **POST** | Rejects booking via `reject_booking()` service (GET previews only) |

**Post-login landing (`landing`).** The successful-login response carries where the SPA should send the user — `"collection"` (plus `collection`, the code), `"welcome"`, or `"home"`. It used to be decided in the browser from the `seenWelcome` localStorage key, but logout clears that key, so every re-login looked like a first visit and dropped returning users on `/welcome`. The rules, in order:

1. The RSVP carries a `target_code` — a share-token or public-collection pop-in — ⇒ **that collection** (they joined it precisely to get there). `invited_collection` is still returned alongside `collection`: it is what tells the SPA the landing came from an invitation (it shows the collection's welcome box).
2. Otherwise the link was born in the plain `/popin` (`RSVP.origin == POPIN`) ⇒ **`/welcome`** — a genuinely new visitor with nothing else to see.
3. Otherwise (`/login`, `origin == LOGIN` — and any legacy magic link with a blank `origin`) ⇒ their **single ACTIVE collection** (owned or invited) when they have exactly one, else **home**. `_solo_collection_code()` stops the query at two rows.

`RSVP.origin` is stamped `LOGIN` by `RequestLinkView` and `POPIN` by `PopInView`; it is blank on every other action. `seenWelcome` survives only as the suppressor for `CollectionPage`'s first-time welcome box — it no longer decides navigation.

**Common behaviour (`_resolve_rsvp` → `_dispatch`):**
1. Looks up RSVP by `token` (the high-entropy URL token, not the PK). Returns 401 if not found.
2. Checks `rsvp.is_valid()` (per-action expiry — magic 24h / booking 72h / invite ~30 days, see the RSVP model). Deletes and returns 401 if expired.
3. GET previews a confirm-required action (`_preview`, no mutation); otherwise (and always on POST) delegates to the action handler.
4. On commit, the RSVP is deleted after use (one-time use).

**Internal helpers:**
- `_authenticate_user(request, rsvp)` — Shared by `MAGIC_LINK` and `COLLECTION_INVITE` handlers. Validates user, calls `update_last_activity()`, mints a JWT. Returns `(user, refresh, user_data)` tuple or `Response` on failure. Auth tokens are set as HttpOnly cookies via `_set_auth_cookies()`. Auth is JWT-cookie-only — it deliberately does **not** open a Django session (no `login()`); the admin site has its own session, so a shadow session would be needless attack surface.
- `_handle_booking_action(rsvp, accepted)` — Shared by `BOOKING_ACCEPT` and `BOOKING_REJECT` handlers. Looks up booking, validates via `is_valid()`, calls `accept_booking()`/`reject_booking()` service, sends decision email, deletes sibling RSVPs.

**MAGIC_LINK response (200):**
```json
{
  "action": "MAGIC_LINK",
  "user": { ... },
  "invited_collection": "<collection_code>"
}
```
Auth tokens (`access_token`, `refresh_token`) are set as HttpOnly cookies via `_set_auth_cookies()`. `invited_collection` is present **only** when the RSVP carried a `target_code` — i.e. the magic link came from a pop-in / share-link join (private share token or PUBLIC login-to-act code). The SPA then drops the user straight onto that collection instead of `/welcome`. A plain `/login` magic link has no `target_code`, so the field is omitted.

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
{ "email": "user@example.com", "share_token": "<optional 22-char token>", "collection_code": "<optional PUBLIC collection code>" }
```

**Behaviour:**
1. Validates email via `RequestLinkSerializer`.
2. Reads optional `share_token` from the body.
3. `get_or_create` user by email.
4. If a valid `share_token` is provided **and** the matching `Collection` is `ACTIVE`, adds the user to that collection's `invites` M2M **and stamps it as the RSVP `target_code`** (so verifying the magic link lands them on the collection, not `/welcome`). Invalid, missing, or pointing-to-INACTIVE tokens are silently ignored (anti-enumeration: response shape is identical regardless).
5. Otherwise, if a `collection_code` is provided and names a **PUBLIC, ACTIVE** collection, adds the user to that collection's `invites` M2M **and stamps it as `target_code`** — the login-to-act auto-join: a visitor who tries to act on a public collection is added to it on submission, then logs in via the magic link and lands back on it, able to act. A code that is unknown, INACTIVE, or PRIVATE is silently ignored — a code can never be used to enter a private, invite-only collection.
6. If the user did not join via a token or a public code, falls back to adding them to all `is_onboarding=True` collections (no `target_code` → the magic link lands on `/welcome` / home).
7. Creates a `MAGIC_LINK` RSVP (carrying any `target_code` from steps 4–5) and sends a magic link email **whose subject names the joined collection** (`"Hello, welcome to '{headline}' - OIUEEI!"`) when the visitor came via a share token or a public code, so they know which collection they are joining. The plain onboarding fallback (and `/login`'s `RequestLinkView`) keep the generic `"Hello, welcome to OIUEEI!"` subject — `_send_magic_link` forwards the resolved headline only on the join paths.
8. Logs request to `security` logger with IP, whether the user is new, and whether they joined a specific collection.

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
| **Permission** | `AllowAny`, `authentication_classes = []` |

Logs out the current user. Reads the refresh token from the `refresh_token` HttpOnly cookie (scoped to `/api/v1/auth/` so it actually reaches this endpoint — `REFRESH_COOKIE_PATH`), blacklists it so it can't be reused to refresh, and clears both `access_token` and `refresh_token` cookies.

**Authenticates nothing, on purpose — logout must never fail.** It used to be `IsAuthenticated`, which broke it in the two cases that matter most: an **expired access token** 401'd the request, leaving the still-valid (up to 7 days) refresh token unblacklisted; and a cookie-authenticated POST **without an `X-CSRFToken` header** was rejected by `CookieJWTAuthentication.enforce_csrf` with a 403, leaving every cookie alive while the SPA navigated to `/login` anyway — so the session came back to life on the next page load (the reported "logout doesn't log out" bug; `LogoutPage` now also goes through `apiFetch`, which sends the header). With no authenticator the view simply reads the refresh cookie, blacklists it (best-effort — an invalid token is swallowed) and **always** returns 200 with the three cookie-deleting headers. The trade-off is a CSRF-forced logout: a cross-site POST can end a session, never act inside one.

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

## Inbox Views (`core/views/inbox.py`)

### InboxView

| | |
|---|---|
| **Endpoints** | `GET /api/v1/inbox/` and `DELETE /api/v1/inbox/{code}/` |
| **Permission** | `IsAuthenticated` |

GET lists the current user's in-app notifications (`code`, `type`, `payload`, `created`). DELETE dismisses (hard-deletes) one, scoped to the requesting user — a code belonging to someone else 404s. Both URL routes resolve to this one view; each handler takes an optional `code` and returns a clean **405** for the combination it doesn't serve (`GET /inbox/{code}/` and `DELETE /inbox/`) rather than a signature-mismatch 500.

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
| `retrieve` | `GET /api/v1/things/{code}/` | `AllowAny` + `can_view()` — anonymous-safe: visible when the thing sits in a PUBLIC, ACTIVE collection |
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

**Create behaviour:** Optionally accepts `collection_code` in request body. `perform_create` raises DRF exceptions directly (no `{"error": ...}` two-phase protocol): an unknown `collection_code` → **404 NotFound**; a collection the user can't add to → **403 PermissionDenied**; a type/tag rule violation → **400 ValidationError** (field-keyed: `{"type": [...]}` / `{"tags": [...]}`, like `perform_update`). If valid, the thing is automatically added to it. WISH_THING and SHARE_THING are restricted to COMMUNITY collections — 400 (`type`) if no collection or if the collection is PROPRIETARY. SWAP_THING requires a swap collection (`is_swap=True`) — 400 otherwise. Swap-only and share-only collections accept their forced offer type (SWAP_THING / SHARE_THING) **plus WISH_THING** — a wish coexists with the offer pool and is exempt from the forced allowlist there; any other type returns 400. **Per-collection allowlist** (`Collection.allowed_thing_types`): if non-empty, the thing's type must be in it — returns 400 otherwise. Empty list = no per-collection restriction. **Tags**: any `tags` on the thing must belong to the collection's `Collection.tags` vocabulary — returns 400 otherwise (tags require a collection; on update, `ThingUpdateSerializer.validate_tags` checks the union of the thing's collections' tags). Removing a tag from a collection (via `CollectionUpdateSerializer`) cascade-strips it from that collection's things. **Group notice**: for `WISH_THING`, the request body may include `notify_group` (boolean, default `true`); when on, creating the wish in a COMMUNITY collection emails every other group member via `send_wish_posted_email` and bulk-creates a `WISH_POSTED` in-app notification (payload: `wish_headline`, `creator_name`, `wish_code`, `collection_code`) for each.

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

### ThingBulkCreateView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/things/bulk/` |
| **Permission** | `IsAuthenticated` + `collection.can_add_thing()` |
| **Rate limit** | `10/h` per user |

CSV/ZIP bulk-add (F-9). Body is `{"rows": [{type, headline, description, fee, availability, location, condition, tags, thumbnail, is_endless}, ...]}` (max 100 rows), parsed and previewed client-side by `BulkAddCsv`. Each row is validated with `ThingBulkRowSerializer` (the project's Safe* fields + a `reject_spreadsheet_formula` CSV-injection guard on free-text fields, including each `tags` entry; `thumbnail` uses `ImageIdField`, path-traversal-safe) and `type_validity_error`; `tags` are additionally checked in the view against the target collection's `Collection.tags` vocabulary (mirrors the single-create subset check). If **any** row fails the request returns `400 {"errors": [{row, errors}]}` and **nothing** is created. On full success every row is created in one `transaction.atomic()` and the response is `201 {"created": N, "codes": [...]}`. **Photos** are importable via the client's ZIP path: `BulkAddCsv` unzips, uploads each image to Cloudinary, and sends the resulting public_id as `thumbnail` — the server only ever receives the validated id, never the binary. Gallery photos are still not bulk-importable.

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
| `retrieve` | `GET /api/v1/collections/{code}/` | `AllowAny` + `can_view()` — anonymous-safe: a PUBLIC, ACTIVE collection is readable without login |
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

### CollectionLeaveView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/leave/` |
| **Permission** | `IsAuthenticated` + must be an invited member (not the owner) |

Lets an invited member remove **themselves** from a collection (self-unlink) — the inverse of the owner-only `CollectionInviteView` DELETE. Returns 400 if the requester is the collection **owner** ("The owner can't leave their own collection." — owners delete instead) or is **not a member** ("You are not a member of this collection."). On success removes the user from the `invites` M2M, creates a `MEMBER_LEFT` in-app notification for the owner (payload: `collection_headline`, `member_name`, `collection_code`), and returns `200 {"message": "You have left the collection"}`. The frontend shows the "Leave the group" button (hero, `CollectionSerializer.is_member` gate) → `LeaveCollectionPage` confirm → back to Home.

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

Sends a broadcast email from the collection owner to all invitees. Validates `message` (SafeTextField, max 256) via `CollectionBroadcastSerializer`; the subject is auto-generated as `Hey! {collection_headline}` (the owner does not provide one). Returns 400 if the collection has no invitees. Emails carry a `Reply-To` header (the owner) and a link to the collection (labelled "I can help!"); the in-app `BROADCAST` notification carries `collection_code` so it can deep-link there too. The email send is dispatched off the request thread in production (`_send_broadcast` → daemon thread when `EMAIL_SEND_ASYNC`, mirroring `_send_bulk_invites`) so a large group's sequential SMTP can't exhaust the Heroku 30s window (H12); the in-app notifications are still written synchronously.

**Request body:**
```json
{ "message": "Bring snacks please" }
```

**Response (200):**
```json
{ "message": "Broadcast sent", "recipients": 5 }
```

### CollectionBulkInviteView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/invite/bulk/` |
| **Permission** | `IsAuthenticated` + collection owner |
| **Rate limit** | 5 requests/hour per user |

Invites many guests at once from a client-parsed CSV (`{"invites": [{"email": ..., "name": ...?}, ...]}`, capped at `MAX_ROWS=100`). Best-effort: valid, new addresses are invited (accept + reject RSVP pair created, invite email sent) and the rest are reported as skipped with a reason (`invalid`, `duplicate`, `already_member`, `already_invited`) — one bad row never fails the batch.

**Response (200):** `{ "invited": 2, "skipped": [{"email": "...", "reason": "..."}], "total": 3 }`

### CollectionStatsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/collections/{collection_code}/stats/` |
| **Permission** | `IsAuthenticated` + collection owner |

Owner-only usage statistics for a collection, returned as a `metric,value` CSV download: a snapshot (members, pending invitations, things total/active) plus a 90-day activity window, and an aggregate age-range/postal-code breakdown (member demographics stay COMMUNITY-only and per-member on the guests page — this endpoint is aggregate-only).

---

## FAQ Views (`core/views/faq.py`)

### ThingFAQListView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/faq/` |
| **Permission** | `AllowAny` (part of the public social layer — anyone who can view the thing may read its FAQs) |
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

Generates a short-lived Cloudinary signed upload signature so the frontend can upload images directly to Cloudinary without routing the binary data through Django. The signature binds every parameter, so a client cannot tamper with them: the **`public_id` is generated server-side** (preventing arbitrary ids / overwrites), `allowed_formats` restricts accepted formats (raster photo formats only — SVG excluded), and `resource_type` is always `image` (not client-trusted). Cloudinary's `max_file_size` is not enforced on the current plan, so the per-file size cap stays a client-side check.

**Document mode (the collection welcome PDF).** `{"kind": "document"}` narrows `allowed_formats` to **`pdf` alone** and adds a signed `max_file_size` of 5 MB (harmless while the plan ignores it, binding the day it doesn't — the real cap today is `PdfUpload`'s client-side check). Everything else is unchanged, including the server-generated `public_id` and `resource_type: image` — Cloudinary treats a PDF as a page-based image, so both kinds share the resource type. Any `kind` other than the literal `"document"` is an image upload, so an unknown value can only ever narrow to the existing defaults.

**Request body:**
```json
{ "folder": "oiueei/things" }
{ "folder": "oiueei/collections", "kind": "document" }
```

Allowed folder values: `oiueei/users`, `oiueei/things`, `oiueei/collections`. Any other value falls back to `oiueei/users`.

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
    "max_file_size": 5242880
}
```
(`max_file_size` is present in document mode only.)

**Frontend upload flow:**
1. Call this endpoint to get the signed parameters.
2. POST the file directly to `https://api.cloudinary.com/v1_1/{cloud_name}/image/upload`, sending the signed parameters back verbatim (`folder`, `public_id`, `allowed_formats`).
3. Cloudinary returns the final `public_id` (folder-prefixed) — store **that** returned value.
4. Save the `public_id` to the relevant Django model field (`thumbnail` cover, the `User.photo` profile photo, or append to a Thing's `gallery`).

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
| **Permission** | `AllowAny` + `get_viewable_thing()` (public read on a viewable thing) |

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

Creates a reservation/booking request. Returns 400 for WISH_THING (this type bypasses BookingPeriod). The view is **thin**: it runs the shared guards (auth, own-thing, availability, INACTIVE/paused collection, owner email) and validates the type-specific serializers, then dispatches to the `request_*` functions in `core.services.booking_service` (`request_share_booking`, `request_date_based_booking`, `request_standard_booking`, `request_swap_booking`) which own the locked create + status transition + email fan-out. A business-rule failure raises `BookingRequestError(message, status_code)`, which the view maps back to `{"error": message}` with the same status. Routes based on thing type:

**Share (SHARE_THING)** — `booking_service.request_share_booking()`:
- NOT date-based — no `start_date`/`end_date` fields.
- Permanent ownership transfer on acceptance; thing stays `ACTIVE`.
- Multiple pending requests from different users are allowed.
- Returns 400 if the requesting user already has a PENDING request for this thing.

**Date-based (LEND/RENT):**
- Requires `start_date` and `end_date`.
- **Rental rules (#7):** resolves the applicable collection (the `collection_code` in the body — the SPA passes the collection context — else the thing's first collection with rules) and calls `collection.rental_violation(start, end)`. Returns 400 if the span isn't an allowed fixed duration or the pickup/return day isn't an allowed weekday. Collections without rules impose no constraint (legacy free range). This is the server-side backstop; the frontend already limits the picker.
- Checks for conflict via `BookingPeriod.has_overlap()` (**strict** overlap — a booking's return day may be the next's pickup day; only a shared interior day conflicts). Returns 409 if conflict.
- Thing stays `ACTIVE` (multiple bookings for different date ranges allowed).

**Request body:**
```json
{ "start_date": "2025-06-01", "end_date": "2025-06-15" }
```

**Swap (SWAP_THING):**
- Requires `offered_thing_codes` (list of thing codes to offer in exchange).
- Each offered thing must: be SWAP_THING, be owned by the requester, be ACTIVE, be in the same swap collection.
- **Minimum-items gate** (`Collection.swap_minimum_items`): if `>0`, the requester must already have at least that many own SWAP_THINGs (status ACTIVE or TAKEN) in the same collection — otherwise returns 400 with the message "You need to upload at least N item(s) to this collection before you can propose a swap." Applies symmetrically to guests AND the collection owner (owners only request swaps on guests' things, but the rule treats them the same). Frontend mirrors the gate via `collection_swap_minimum_items` + `my_swap_count_in_collection` on the thing serializer.
- Creates `BookingPeriod` with no dates, links offered things via M2M.
- Thing stays `ACTIVE`. Sends swap-specific emails via `booking_service.send_swap_request_notifications()`.

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
3. Creates two RSVPs (`BOOKING_ACCEPT` and `BOOKING_REJECT`) for the owner's email action links via `booking_service.send_booking_request_notifications()` (or `send_swap_request_notifications()` for SWAP_THING).
4. Sends booking request email to owner with accept/reject links, and a confirmation email to the requester ("Hold request sent" / "Swap request sent").

**INACTIVE collection enforcement:**
If all collections containing the thing are INACTIVE, the request is blocked with 400 "This collection is currently inactive".

**Paused collection enforcement:**
If all active collections containing the thing have a non-empty `pause_message` (i.e. are paused), the request is blocked with 400 "This collection is currently paused". Collections that are paused remain visible but no new hold requests are accepted.

**Responses:**
| Status | Condition |
|--------|-----------|
| 201 | Request created (booking `PENDING`) |
| 400 | Own thing / already pending / invalid data / collection inactive |
| 403 | Not authorised to view thing |
| 409 | Date overlap (date-based only) |

---

## Transfer Views (`core/views/transfers.py`)

### ThingTransferView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/transfers/` |
| **Permission** | `AllowAny` + `get_viewable_thing()` (public read on a viewable thing) |

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

## Report Views (`core/views/report.py`)

### ThingReportView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/report/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner |
| **Rate limit** | 10 requests/hour per user |

A logged-in member flags a thing as inappropriate (content moderation, #12).

**Behaviour:**
1. Returns 400 if the requester is the thing owner ("You can't report your own listing").
2. Returns 403 if the requester can't view the thing (`deny_if_cannot_view`).
3. `get_or_create` a `Report` for `(thing, reporter)` with a `thing_headline` snapshot — **idempotent per member**, so re-reporting the same thing doesn't create a second row or re-notify.
4. On the **first** report only: emails the owner (`send_thing_reported_email`, Cat. 2) and creates a `THING_REPORTED` `InAppNotification` (payload `thing_headline`, `thing_code`). Both are **anonymous** — the reporter's identity is never included.
5. Always returns `200 {"message": "Thanks — we've let the owner know."}` (the reporter can't tell whether it was their first report).

The reporter is stored server-side only (`Report.reporter`) as a moderation trail; see the [`Report` model](../models/CLAUDE.md#report) and `ReportAdmin` for the platform-facing log.

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
- Outputs count of reminder emails sent.

### Management Command: `send_digests`

Daily command (`python manage.py send_digests`) that sends digest emails and newsletters:
- **Weekly digests**: sent on Mondays for collections with `digest_frequency = "WEEKLY"`. Lists things added in the past 7 days.
- **Monthly digests**: sent on the 1st of each month for collections with `digest_frequency = "MONTHLY"`. Lists things added in the previous month.
- **Weekly newsletters**: sent on Mondays for share collections with `newsletter_enabled = True`. Includes two blocks: (1) new things added in the past 7 days, (2) ownership changes (ThingTransfer records) in the past 7 days. Skips collections with no activity or no invitees.
- Skips collections with no new things or no invitees.
- Outputs count of digest emails sent.

### Management Command: `cleanup_orphan_images`

On-demand command (`python manage.py cleanup_orphan_images`) that deletes **orphaned Cloudinary images** (#9) — uploads whose form was never submitted, so no DB row ever referenced them (the complement to `core.services.cloudinary_cleanup`, which handles record *deletes*). Superuser-run (there is no in-app endpoint — the shell/Heroku access is the gate).

- **Dry-run by default.** It only lists what it would delete; pass `--commit` to actually delete. On Heroku, quote the inner command so the CLI doesn't eat the flag: `heroku run --app <app> "python manage.py cleanup_orphan_images --commit"`.
- **Cross-references every DB image field** — `Thing.thumbnail` + `Thing.gallery`, `User.photo`, `Collection.thumbnail` — so anything in use is kept.
- **Never touches `oiueei/seed/`** (the demo's shared image pool), even if unreferenced.
- **Age window:** only assets older than `--min-age-hours` (default 24, so an in-flight upload mid-form isn't mistaken for an orphan) and younger than `--max-age-days` (default 30, keeping it a recent sweep). Run regularly (e.g. weekly) so every orphan is caught within its window.
- Pages through `cloudinary.api.resources` (prefix `oiueei/`), deletes in batches of 100 via `cloudinary.api.delete_resources`, and prints a per-run summary (scanned / in use / seed / outside window / orphans / deleted).

### Management Command: `stats_summary`

First-party product stats (see the [`Event`](../models/CLAUDE.md#event) and [`DailyActivity`](../models/CLAUDE.md#dailyactivity) models). Computes metrics from three sources — current state (domain tables), accumulated history (`Event`), retention (`DailyActivity`) — and **always prints** them to stdout; it emails them to the operator (`oiueei@disroot.org`) once a week — on the `STATS_EMAIL_WEEKDAY` weekday (0=Monday … 6=Sunday, default Monday; weekday-gated inside the command, mirroring `send_digests`) — or on any day with `--email`. The email goes through `email_service.send_stats_summary_email` (CATEGORY_MANDATORY, escaped via the layout template).

- **Demo never mixes into real numbers**: the five seed users (imported from `seed_data/common.py`), `is_onboarding` collections, and pop-in users who only ever landed in onboarding collections are split into a separate "Demo funnel" section. `build_report()` returns a list of `{title, rows, note?}` sections reused by both the stdout renderer and the email.
- **Scheduler**: appended to the existing daily 05:00 UTC Heroku Scheduler job (`expire_bookings && cleanup_rsvps && close_transfers && send_reminders && send_digests && stats_summary`).

### Management Command: `backfill_events`

One-off, idempotent seed of the `Event` log from existing rows (users → `USER_JOINED` at `date_joined`, collections/things/bookings at their `created`; accepted bookings also get `HOLD_ACCEPTED`). Run **once**, the day tracking ships, before forward instrumentation accumulates. Kept out of migrations per repo convention. Re-running never double-counts (skips when an equal event already exists).

---

## Middleware (`core/middleware.py`)

- **`SecurityHeadersMiddleware`** — adds CSP + Permissions-Policy to every response (all environments).
- **`DailyActivityMiddleware`** — records the authenticated user's daily activity (see [`DailyActivity`](../models/CLAUDE.md#dailyactivity)). Registered **innermost** so it can read the DRF-authenticated `request.user` *after* the view (there is no Django session — auth is JWT-cookie via DRF authenticators, so `request.user` only resolves once a view/permission touches it). A DatabaseCache key gates it to one write per user per day; failures are swallowed so tracking can never 500 a good response. Anonymous / non-DRF requests are skipped.

---

## Custom Permissions (`core/permissions.py`)

| Permission | Logic |
|-----------|-------|
| `IsThingOwner` | `obj.owner_id == request.user.code` |
| `IsCollectionOwner` | `obj.owner_id == request.user.code` |

---

## Security

### Authentication & Authorisation

1. **Invite-only registration (owner-controlled), with a separate demo gate** — There is no open public self-registration on the main model. Accounts are created when a collection owner invites someone (`POST /collections/{code}/invite/`) or when a visitor uses an owner-enabled public share link (`POST /auth/pop-in/` with a `share_token`, from `/share/{token}`). `/login` (`POST /auth/request-link/`) only mails magic links to already-registered accounts and never creates users. The separate `/popin` endpoint (`POST /auth/pop-in/` with no token) is an intentional open demo/onboarding gate that creates an account for anyone and adds them to the `is_onboarding` demo collections.
2. **Magic link authentication** — Passwordless via email. RSVPs are one-time use and expire per action (magic links 24h; booking accept/reject 72h; collection invites ~30 days — `RSVP.expiry_hours_for`).
3. **JWT tokens** — HttpOnly cookie-based. Access tokens expire after 1 hour. Refresh tokens expire after 7 days. Tokens are rotated on refresh via `POST /api/v1/auth/refresh/`, old tokens blacklisted.
4. **CSRF (cookie auth)** — because the access token rides in a cookie, `CookieJWTAuthentication` runs DRF's CSRF check (`enforce_csrf`, mirroring `SessionAuthentication`) for **cookie-authenticated unsafe methods** — defence in depth behind the cookie's `SameSite=Lax`. Bearer-header auth is exempt (the header is never sent cross-site), so API clients and the Bearer-token test suite are unaffected. `MeView` GET sets the `csrftoken` cookie via `@ensure_csrf_cookie` (hit on every app load); the SPA reads it and sends it as `X-CSRFToken` on every unsafe request. The test client disables the check by default (`enforce_csrf_checks=False`), so only `test_csrf.py` (which opts in) exercises it.
5. **IDOR protection** — `can_view_user()` ensures users can only view profiles of people connected via collections.
6. **Custom DRF permissions** — `IsThingOwner` and `IsCollectionOwner` in `core/permissions.py`.
7. **Public collections (anonymous read)** — a collection with `visibility=PUBLIC` (and ACTIVE) is readable without authentication. The read endpoints `CollectionViewSet.retrieve`, `ThingViewSet.retrieve`, the FAQ list (GET on `ThingFAQListView`), `ThingTransferView` and `ThingCalendarView` are `AllowAny`, each gated by an **anonymous-safe** `can_view` (a `viewer_code(request)` helper passes the user's code, or `None` for a visitor, into the model guard — `None` matches PUBLIC collections only). Every *write/act* endpoint (reserve, ask a question, answer, add a thing, manage invites/visibility) still requires authentication plus membership/ownership, so an anonymous visitor may browse a public collection but must log in to act. INACTIVE things are excluded from the serialised `things` for any non-owner, and the collection *list* (`GET /collections/`) stays private (it returns only the caller's own collections).

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
- `/things/{code}/report/` POST — 10 requests per hour per user
- `/notifications/token/{t}/` — GET 20/min per IP, PATCH 10/min per IP
- `/things/` POST (single create) — 60 requests per hour per user (so the 10/h bulk cap can't be bypassed one-by-one into unbounded rows)
- `/collections/` POST (single create) — 30 requests per hour per user
- `/collections/{code}/add-thing/` POST — 60 requests per hour per user
- `/wish-responses/{code}/accept/` POST — 30 requests per hour per user
- `/collections/{code}/leave/` POST — 30 requests per hour per user

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
- Accept/reject actions can be performed via the unified RSVP endpoint (`VerifyLinkView`) for email links — **a POST commits, GET only previews** (booking decisions never fire from a bare GET) — or via authenticated `BookingActionView` endpoints for in-app use. Both paths reuse the same `accept_booking()`/`reject_booking()` service functions.
- All email links use RSVP codes as intermediaries to avoid exposing real object codes in URLs.
- Security events are logged to the `security` logger with IP addresses.

### Service Layer

Business logic is extracted into `core/services/`:
- `email_service.py` — All email HTML composition and sending (22 `send_*` functions). Uses `django.utils.html.escape()`.
- `booking_service.py` — `accept_booking()`, `reject_booking()`, and `cancel_booking()` handle status transitions for Thing and BookingPeriod, wrapped in `transaction.atomic()`. The reservation-**request** side lives here too: `request_share_booking()`, `request_date_based_booking()`, `request_standard_booking()`, and `request_swap_booking()` (plus `resolve_rental_collection()` and the `send_*_request_notifications()` email/notification helpers). They raise `BookingRequestError(message, status_code)` on a rule violation; `ThingRequestView` catches it and returns `{"error": message}`.

### Utilities

- `core/utils.py`: `generate_id()`, `get_client_ip()`, `cloudinary_url()` — `cloudinary_url(public_id)` now uses the Cloudinary Python SDK (`cloudinary.utils.cloudinary_url`) with `fetch_format=auto` and `quality=auto`, replacing the previous hardcoded URL template.
- `core/validators.py`: `ImageIdField`, `SafeHeadlineField`, `SafeTextField`, `validate_image_id()`, `validate_headline()`
- `core/pagination.py`: `StandardResultsPagination` (max 100 items)
