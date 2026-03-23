# Serializers Documentation

All serializers live in `core/serializers/` and are re-exported via `__init__.py` for flat imports (`from core.serializers import ThingSerializer`).

---

## Patterns

### Naming Convention

Each domain module follows a consistent set of serializer roles:

| Suffix | Purpose | Example |
|--------|---------|---------|
| `Serializer` | Full read representation | `ThingSerializer`, `CollectionSerializer` |
| `CreateSerializer` | Validated input for creation | `ThingCreateSerializer` |
| `UpdateSerializer` | Validated input for partial updates | `ThingUpdateSerializer` |
| (action name) | Single-purpose input | `CollectionInviteSerializer`, `FAQAnswerSerializer` |

### Security Fields (`core/validators.py` and `core/serializers/thing.py`)

All user-facing text inputs use custom validator fields to prevent XSS:

| Field | Validates | Used for |
|-------|-----------|----------|
| `SafeHeadlineField` | Rejects HTML tags (regex) | Headlines, FAQ questions, location |
| `SafeTextField` | Rejects HTML tags (regex) | Descriptions, FAQ answers |
| `ImageIdField` | Alphanumeric + `_-` only | Cloudinary image IDs (prevents path traversal) |
| `ImageIdListField` | List of validated image IDs | Thing `pictures` field (defined in `core/serializers/thing.py`) |

### Cloudinary Image URLs

Read serializers expose `thumbnail_url` / `hero_url` / `pictures_urls` as `SerializerMethodField`s that call `core.utils.cloudinary_url()` to convert stored image IDs into full Cloudinary URLs. The raw IDs are also exposed (e.g. `thumbnail`, `hero`) for edit forms.

### Prefetch-Aware Computed Fields

Several `SerializerMethodField`s check for prefetched attributes before falling back to queries:

- `ThingSerializer.get_pending_booking` — checks `obj._pending_bookings` (set by view-level `Prefetch`)
- `ThingSerializer.get_faqs` / `get_pending_questions` — uses `obj.faq_set.all()` (prefetched)
- `CollectionThingSummarySerializer.get_pending_booking` / `get_pending_questions` — same pattern

This avoids N+1 queries when serialising lists of things.

### Foreign Key Exposure

Foreign keys are exposed as 6-character alphanumeric codes, not database IDs:

- `owner = CharField(source="owner_id")` — exposes the FK value directly
- `SlugRelatedField(slug_field="code")` — used for `theeeme` and `deal` (M2M)

---

## Modules

### `auth.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `RequestLinkSerializer` | `email` | Plain `Serializer` (no model). Validates email for magic link requests. |

### `user.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `UserSerializer` | code, email, name, created, last_activity, own_collections, invited_collections, things, headline, thumbnail/url, hero/url, theeeme | Full profile for authenticated user. Collections and things returned as code lists. |
| `UserPublicSerializer` | code, name, headline, thumbnail/url, hero/url | Limited public profile. No email, no collections. |
| `UserUpdateSerializer` | name, headline, thumbnail, hero, theeeme | PUT/PATCH input. Uses `SafeHeadlineField` and `ImageIdField`. |

### `thing.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `ThingSerializer` | code, type, owner, owner_name, created, headline, description, thumbnail/url, pictures/urls, status, faqs, fee, availability, location, condition, deal, available, pending_booking, pending_questions, collection_code, collection_headline | Full read representation. `owner_name` returns owner's name (falls back to email). `pending_booking` returns first PENDING booking code. `collection_code/headline` from first associated collection. |
| `ThingCreateSerializer` | type, headline, description, thumbnail, pictures, fee, availability, location, condition | Uses `SafeHeadlineField`, `SafeTextField`, `ImageIdField`, `ImageIdListField`. `location` uses `SafeHeadlineField(max_length=32)`. |
| `ThingUpdateSerializer` | type, headline, description, thumbnail, pictures, status (read-only), fee, availability, location, condition, available | Same validation fields. `status` is read-only (changed by booking flow, not direct edit). |

### `collection.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `CollectionSerializer` | code, owner, created, headline, description, thumbnail/url, hero/url, status, things, invites, pending_invites | `things` filters by `available=True` for non-owners. `pending_invites` queries RSVP table. |
| `CollectionThingSummarySerializer` | code, type, owner, headline, description, status, fee, availability, location, condition, available, thumbnail_url, pending_booking, pending_questions, created | Lightweight thing representation nested inside `CollectionSerializer`. |
| `CollectionInviteSummarySerializer` | code, email, name | Lightweight user representation for invite lists. |
| `CollectionCreateSerializer` | headline, description, thumbnail, hero | Input for collection creation. |
| `CollectionUpdateSerializer` | headline, description, thumbnail, hero, status | Input for collection updates. |
| `CollectionInviteSerializer` | email | Input for inviting a user. |
| `CollectionAddThingSerializer` | thing_code | Input for adding a thing to a collection. |
| `CollectionRemoveThingSerializer` | thing_code | Input for removing a thing from a collection. |
| `CollectionRemoveInviteSerializer` | user_code | Input for removing a user from invites. |

### `booking.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `BookingPeriodSerializer` | code, created, thing_code, thing_headline, thing_type, requester_code, requester_name, requester_email, owner_code, start_date, end_date, delivery_date, quantity, status | Full booking for owner view. Uses `source` to traverse FK relations. |
| `BookingPeriodCalendarSerializer` | start_date, end_date, status | Minimal calendar view for guests (no requester info). |
| `BookingPeriodOwnerCalendarSerializer` | code, requester_code, requester_name, start_date, end_date, delivery_date, quantity, status | Owner calendar view with requester details. `requester_name` falls back to email. |
| `ThingRequestWithDatesSerializer` | start_date, end_date | Plain `Serializer` for LEND/RENT/SHARE requests. Validates start >= today, end >= start. |
| `ThingOrderSerializer` | delivery_date, quantity (1-99) | Plain `Serializer` for ORDER requests. Validates delivery >= today. |
| `MyBookingSerializer` | code, created, thing_code, thing_headline, thing_type, owner_code, owner_name, start_date, end_date, delivery_date, quantity, status | Requester's own booking view. `owner_name` falls back to email. |

### `faq.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `FAQSerializer` | code, thing, created, questioner, questioner_name, question, answer, is_visible | Full FAQ read representation. |
| `FAQCreateSerializer` | question | Plain `Serializer`. Uses `SafeHeadlineField` (max 64 chars). |
| `FAQAnswerSerializer` | answer | Plain `Serializer`. Uses `SafeTextField` (max 256 chars). |

### `theeeme.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `TheeemeSerializer` | code, name | Read-only `ModelSerializer` for theme listing. |
