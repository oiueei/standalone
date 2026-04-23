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
| `ImageIdField` | Alphanumeric + `_-./` only, no leading/trailing/double slashes | Cloudinary public_ids including folder paths (e.g. `oiueei/things/abc123`) |

### Cloudinary Image URLs

Read serializers expose `thumbnail_url` as a `SerializerMethodField` that calls `core.utils.cloudinary_url()` to convert stored image IDs into full Cloudinary URLs. The raw ID is also exposed (e.g. `thumbnail`) for edit forms.

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
| `UserSerializer` | code, email, name, created, last_activity, own_collections, invited_collections, things, headline, koro, theeeme, theeeme_colors, notify_activity, notify_news | Full profile for authenticated user. Collections and things returned as code lists. `koro` is the user's chosen Koros wave type. `theeeme_colors` returns a dict with `color_01`–`color_06` HDS token names (or null if no theeeme). `notify_activity`/`notify_news` control Cat. 2 / Cat. 3 email delivery (see `core/services/CLAUDE.md`). |
| `UserPublicSerializer` | code, name, headline, created | Limited public profile. No email, no collections. `created` allows "Member since" display. |
| `UserUpdateSerializer` | name, headline, koro, theeeme, notify_activity, notify_news | PUT/PATCH input. Uses `SafeHeadlineField`. `koro` accepts: basic, beat, calm, pulse, vibration, wave. `notify_activity` / `notify_news` are the global Cat. 2 / Cat. 3 opt-out toggles. |
| `NotificationPrefsSerializer` | notify_activity, notify_news | Lives in `core/views/notifications.py`. Used by `NotificationsByTokenView` for unauthenticated token-based preference editing. |

### `thing.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `DocumentSerializer` | public_id, filename, content_type | Plain `Serializer` for validating document entries. `public_id` validated via `validate_image_id`. `content_type` whitelisted to PDF, Word, Excel, Markdown. |
| `ThingSerializer` | code, type, owner, owner_name, created, headline, description, thumbnail/url, status, faqs, fee, availability, location, condition, event_date, booking_unit, slot_duration, availability_schedule, documents, document_urls, deal, pending_booking, my_pending_booking, pending_questions, collection_code, collection_headline, collection_owner, transfer_count, attendee_count, helper_count, is_endless | Full read representation. `owner_name` returns owner's name (falls back to email). `pending_booking` returns first PENDING booking code (owner use). `my_pending_booking` returns the requesting user's own PENDING booking code (or null) — used by guests to distinguish "Reserved" vs "Waiting for confirmation". `collection_code/headline/owner` from first associated collection. `collection_owner` is the owner code of the first associated collection — used by the frontend to decide whether to show the "Hide" button for SHARE_THING after transfer. `attendee_count` returns deal count for EVENT_THING, null otherwise. `helper_count` returns deal count for WISH_THING, null otherwise. `booking_unit` is DAY or HOUR for ASSET_THING. `slot_duration` is 15/30/60 for APPOINTMENT_THING. `availability_schedule` is the JSONField schedule for APPOINTMENT_THING. `documents` is the raw JSONField. `document_urls` returns `[{filename, url}]` via Cloudinary raw URLs. |
| `ThingCreateSerializer` | type, headline, description, thumbnail, fee, availability, location, condition, event_date, booking_unit, slot_duration, availability_schedule, documents, is_endless | Uses `SafeHeadlineField`, `SafeTextField`, `ImageIdField`. `location` uses `SafeHeadlineField(max_length=32)`. `documents` is a `ListField(max_length=5)` validated via `DocumentSerializer`. `is_endless` is an optional BooleanField (default False), meaningful only for GIFT_THING and SELL_THING. |
| `ThingUpdateSerializer` | type, headline, description, thumbnail, status (read-only), fee, availability, location, condition, event_date, booking_unit, slot_duration, availability_schedule, documents, is_endless | Same validation fields. `status` is read-only (changed by booking flow or dedicated activate/hide endpoints). `documents` same as create. `is_endless` same as create. |

### `collection.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `CollectionSerializer` | code, owner, owner_name, created, headline, description, status, mode, digest_frequency, is_swap, is_share, newsletter_enabled, is_minimalist, thumbnail, thumbnail_url, things, invites, pending_invites | `things` excludes INACTIVE things for non-owners. `pending_invites` queries RSVP table. `is_swap` indicates swap-only collection. `is_share` indicates share-only collection (mutually exclusive with `is_swap`). `newsletter_enabled` enables weekly activity newsletter (requires `is_share`). `is_minimalist` enables photo-album mode (mutually exclusive with `is_swap`, compatible with `is_share`). |
| `CollectionThingSummarySerializer` | code, type, owner, headline, description, status, fee, availability, location, condition, event_date, booking_unit, slot_duration, thumbnail_url, pending_booking, my_pending_booking, pending_questions, transfer_count, attendee_count, helper_count, deal, created | Lightweight thing representation nested inside `CollectionSerializer`. `my_pending_booking` same as in `ThingSerializer`. `attendee_count` returns deal count for EVENT_THING, null otherwise. `helper_count` returns deal count for WISH_THING, null otherwise. `booking_unit` is DAY or HOUR for ASSET_THING. `slot_duration` is 15/30/60 for APPOINTMENT_THING. Request context is forwarded from `CollectionSerializer.get_things()`. |
| `CollectionInviteSummarySerializer` | code, email, name | Lightweight user representation for invite lists. |
| `CollectionCreateSerializer` | headline, description, mode, digest_frequency, is_swap, is_share, newsletter_enabled, is_minimalist, thumbnail | Input for collection creation. `is_swap` and `is_share` are mutually exclusive and require COMMUNITY mode. `newsletter_enabled` requires `is_share`. `is_minimalist` is mutually exclusive with `is_swap`. |
| `CollectionUpdateSerializer` | headline, description, status, mode, digest_frequency, is_swap, is_share, newsletter_enabled, is_minimalist, thumbnail | Input for collection updates. Same validation as create. |
| `CollectionInviteSerializer` | email | Input for inviting a user. |
| `CollectionAddThingSerializer` | thing_code | Input for adding a thing to a collection. |
| `CollectionRemoveThingSerializer` | thing_code | Input for removing a thing from a collection. |
| `CollectionRemoveInviteSerializer` | user_code | Input for removing a user from invites. |
| `CollectionBroadcastSerializer` | subject, message | Input for broadcasting to invitees. Uses `SafeHeadlineField` (max 64) and `SafeTextField` (max 256). |

### `booking.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `BookingPeriodSerializer` | code, created, thing_code, thing_headline, thing_type, requester_code, requester_name, requester_email, owner_code, start_date, end_date, start_time, end_time, delivery_date, quantity, status, offered_thing_codes, offered_thing_headlines | Full booking for owner view. Uses `source` to traverse FK relations. `start_time`/`end_time` for hourly ASSET_THING bookings. `offered_thing_codes`/`offered_thing_headlines` return lists for SWAP_THING bookings, null otherwise. |
| `BookingPeriodCalendarSerializer` | start_date, end_date, start_time, end_time, status | Minimal calendar view for guests (no requester info). Includes time fields for hourly bookings. |
| `BookingPeriodOwnerCalendarSerializer` | code, created, requester_code, requester_name, start_date, end_date, start_time, end_time, delivery_date, quantity, status, offered_thing_codes, offered_thing_headlines | Owner calendar view with requester details. `requester_name` falls back to email. `created` is the booking request date. Includes time fields for hourly bookings. `offered_thing_codes`/`offered_thing_headlines` return lists for SWAP_THING bookings, null otherwise. |
| `ThingRequestWithDatesSerializer` | start_date, end_date | Plain `Serializer` for LEND/RENT/ASSET(DAY) requests. Validates start >= today, end >= start. |
| `ThingRequestWithTimesSerializer` | start_date, start_time, end_time | Plain `Serializer` for ASSET(HOUR) requests. Validates start_date >= today, end_time > start_time. |
| `ThingOrderSerializer` | delivery_date, quantity (1-99) | Plain `Serializer` for ORDER requests. Validates delivery >= today. |
| `MyBookingSerializer` | code, created, thing_code, thing_headline, thing_type, owner_code, owner_name, start_date, end_date, start_time, end_time, delivery_date, quantity, status | Requester's own booking view. `owner_name` falls back to email. Includes time fields for hourly bookings. |

### `faq.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `FAQSerializer` | code, thing, created, questioner, questioner_name, question, answer, is_visible | Full FAQ read representation. |
| `FAQCreateSerializer` | question | Plain `Serializer`. Uses `SafeHeadlineField` (max 64 chars). |
| `FAQAnswerSerializer` | answer | Plain `Serializer`. Uses `SafeTextField` (max 256 chars). |

### `theeeme.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `TheeemeSerializer` | code, name, color_01–color_06 | Read-only `ModelSerializer` for theme listing. Includes all six HDS colour token names so the frontend can render colour swatches. |

### `transfer.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `ThingTransferSerializer` | code, from_user, to_user, from_user_name, to_user_name, lent_date, returned_date | Individual transfer record. `from_user_name`/`to_user_name` fall back to email if name is blank. |
| `ThingTransferStatsSerializer` | total_transfers, unique_homes, current_holder, current_holder_name, original_owner, original_owner_name, is_share_in_community, transfers | Aggregated stats plus full transfer list. `transfers` is a nested list of `ThingTransferSerializer`. `current_holder` is the user code of the most recent unreturned transfer's `to_user`, or null. `original_owner` is the `from_user` of the oldest transfer (null if no transfers). `is_share_in_community` is True when the thing is a SHARE_THING in a COMMUNITY collection. |

Note: `ThingSerializer` and `CollectionThingSummarySerializer` both include a `transfer_count` computed field that returns the number of transfers for each thing (uses prefetched `_transfer_count` annotation when available, falls back to queryset count).
