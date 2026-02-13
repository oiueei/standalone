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
2. Looks up user by email (lowercased). Returns 404 if not found (invite-only system).
3. Creates an RSVP with action `MAGIC_LINK`.
4. Sends magic link email via `send_magic_link_email()`.
5. Logs request to `security` logger with IP.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Magic link sent |
| 404 | Email not found |
| 429 | Rate limited |

---

### VerifyLinkView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/auth/verify/{rsvp_code}/` |
| **Permission** | `AllowAny` |
| **Rate limit** | 10 requests/minute per IP |

Processes all RSVP-based actions. Routes to the appropriate handler based on `rsvp.action`:

| Action | Handler | Description |
|--------|---------|-------------|
| `MAGIC_LINK` | `_handle_magic_link` | Authenticates user, returns JWT |
| `COLLECTION_INVITE` | `_handle_collection_invite` | Adds user to collection invites M2M, returns JWT, deletes sibling `COLLECTION_REJECT` RSVP |
| `COLLECTION_REJECT` | `_handle_collection_reject` | Notifies collection owner of rejection, deletes sibling `COLLECTION_INVITE` RSVP, no JWT |
| `BOOKING_ACCEPT` | `_handle_booking_accept` | Accepts booking via `accept_booking()` service |
| `BOOKING_REJECT` | `_handle_booking_reject` | Rejects booking via `reject_booking()` service |

**Common behaviour:**
1. Looks up RSVP by code. Returns 401 if not found.
2. Checks `rsvp.is_valid()` (24h expiry). Deletes and returns 401 if expired.
3. Delegates to action handler.
4. RSVP is deleted after use (one-time use).

**MAGIC_LINK response (200):**
```json
{
  "action": "MAGIC_LINK",
  "token": "<access_token>",
  "refresh": "<refresh_token>",
  "user": { ... }
}
```

**COLLECTION_INVITE response (200):**
```json
{
  "action": "COLLECTION_INVITE",
  "token": "<access_token>",
  "refresh": "<refresh_token>",
  "user": { ... },
  "invited_collection": "<collection_code>"
}
```

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

Logs out the current user. Optionally blacklists the provided refresh token.

**Request body (optional):**
```json
{ "refresh": "<refresh_token>" }
```

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

Returns user profile. Own profile returns full data (`UserSerializer`), other profiles return public data (`UserPublicSerializer`).

| | |
|---|---|
| **Endpoint** | `PUT /api/v1/users/{user_code}/` |
| **Permission** | `IsAuthenticated` + own profile only |

Updates own profile via `UserUpdateSerializer` (partial update). Returns 403 if attempting to update another user.

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

**Serializers:**
- Create: `ThingCreateSerializer`
- Update: `ThingUpdateSerializer` (`status` is read-only to prevent direct manipulation, `type` is editable)
- Read: `ThingSerializer`

**Queryset:** Own things only (`Thing.objects.filter(owner=request.user)`), ordered by `-created`.

**Retrieve:** Uses `thing.can_view(user_code)` — owner or invited to a collection containing the thing.

**Create behaviour:** Optionally accepts `collection_code` in request body. If provided and user owns the collection, the thing is automatically added to it.

### InvitedThingsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/invited-things/` |
| **Permission** | `IsAuthenticated` |
| **Pagination** | `StandardResultsPagination` |

Lists things from collections where the current user is invited. Only returns things with `available=True`. Uses `.distinct()` to avoid duplicates.

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
| `add_thing` | `POST /api/v1/collections/{code}/add-thing/` | `IsAuthenticated` + `IsCollectionOwner` |

**Serializers:**
- Create: `CollectionCreateSerializer`
- Update: `CollectionUpdateSerializer`
- Add thing: `CollectionAddThingSerializer`
- Read: `CollectionSerializer`

**Queryset:** Own collections only, ordered by `-created`.

**Retrieve:** Uses `collection.can_view(user_code)` — owner or in invites M2M.

**Create:** If no `theeeme` provided, defaults to `JMPA01` (BAR_CEL_ONA).

**Add thing:** Validates thing exists, belongs to user, and is not already in collection.

### CollectionInviteView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/invite/` |
| **Permission** | `IsAuthenticated` + collection owner |

Invites a user to a collection by email. Creates user if they don't exist (`get_or_create`). Returns 400 if the user is already invited. Creates two RSVPs (`COLLECTION_INVITE` for accept and `COLLECTION_REJECT` for decline) and sends invitation email with both links.

**Request body:**
```json
{ "email": "invitee@example.com" }
```

| | |
|---|---|
| **Endpoint** | `DELETE /api/v1/collections/{collection_code}/invite/` |
| **Permission** | `IsAuthenticated` + collection owner |

Removes a user from the collection's invite list. Sends revocation notification email.

**Request body:**
```json
{ "user_code": "ABC123" }
```

### InvitedCollectionsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/invited-collections/` |
| **Permission** | `IsAuthenticated` |

Lists collections where the current user is in the invites M2M. Not paginated.

---

## FAQ Views (`core/views/faq.py`)

### ThingFAQListView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/faq/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |
| **Pagination** | `StandardResultsPagination` |

Lists FAQs for a thing. Owner sees all FAQs (including hidden). Invited users see only visible FAQs.

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/faq/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner |

Creates a new FAQ question. Owner cannot ask questions about their own thing (400). Sends notification email to thing owner.

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

Hides a FAQ. Sends notification email to questioner.

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/show/` |
| **Permission** | `IsAuthenticated` + thing owner only |

Shows a previously hidden FAQ.

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

Creates a reservation/booking request. Routes based on thing type:

**Date-based (LEND/RENT/SHARE):**
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

**Standard (GIFT/SELL):**
- No extra fields required.
- Checks for existing pending request from same user. Returns 400 if duplicate.
- Thing status changes to `TAKEN` (blocks other requests).

**Common behaviour:**
1. Creates `BookingPeriod` with status `PENDING`.
2. Creates two RSVPs (`BOOKING_ACCEPT` and `BOOKING_REJECT`) for the owner's email action links.
3. Sends booking request email to owner with accept/reject links.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Request sent |
| 400 | Own thing / already pending / invalid data |
| 403 | Not authorised to view thing |
| 409 | Date overlap (date-based only) |

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
3. **JWT tokens** — Access tokens expire after 1 hour. Refresh tokens expire after 7 days. Tokens are rotated on refresh, old tokens blacklisted.
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
- `ThingUpdateSerializer` has `status` as read-only to prevent direct status manipulation. `type` is editable.
- `ThingSerializer` and `CollectionThingSummarySerializer` include `pending_booking` (first PENDING booking code, or null).
- Accept/reject actions can be performed via the unified RSVP endpoint (`VerifyLinkView`) for email links, or via authenticated `BookingActionView` endpoints for in-app use. Both paths reuse the same `accept_booking()`/`reject_booking()` service functions.
- All email links use RSVP codes as intermediaries to avoid exposing real object codes in URLs.
- Security events are logged to the `security` logger with IP addresses.

### Service Layer

Business logic is extracted into `core/services/`:
- `email_service.py` — All email HTML composition and sending (8 functions). Uses `django.utils.html.escape()`.
- `booking_service.py` — `accept_booking()` and `reject_booking()` handle status transitions for Thing and BookingPeriod, wrapped in `transaction.atomic()`.

### Utilities

- `core/utils.py`: `generate_id()`, `get_client_ip()`, `cloudinary_url()`
- `core/validators.py`: `ImageIdField`, `SafeHeadlineField`, `validate_image_id()`
- `core/pagination.py`: `StandardResultsPagination` (max 100 items)
