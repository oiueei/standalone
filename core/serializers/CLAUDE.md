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
- `ThingSerializer` / `CollectionThingSummarySerializer` `get_available_today` / `get_next_available` — delegate to `Thing.availability_window()`, which reads `obj._blocked_periods` (PENDING+ACCEPTED `Prefetch` set by `ThingViewSet`/`InvitedThingsView` and by `_optimise_collection_queryset` for collection cards) before falling back to a query, and memoises the result so both fields cost one computation
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
| `UserSerializer` | code, email, name, created, last_activity, own_collections, invited_collections, things, headline, about, photo, photo_url, koro, theeeme, theeeme_colors, notify_activity, notify_news, age_range, postal_code, in_community | Full profile for authenticated user. Collections and things returned as code lists. `koro` is the user's chosen Koros wave type. `about` is the raw Markdown bio; `photo` is the raw Cloudinary public_id (for the edit form) and `photo_url` the built Cloudinary URL (for display). `theeeme_colors` returns a dict with `color_01`–`color_06` HDS token names (or null if no theeeme). `notify_activity`/`notify_news` control Cat. 2 / Cat. 3 email delivery (see `core/services/CLAUDE.md`). `age_range`/`postal_code` are the optional COMMUNITY demographics; `in_community` is a computed bool (the user owns or belongs to ≥1 COMMUNITY collection) that gates whether the profile editor shows those two fields. |
| `UserPublicSerializer` | code, name, headline, about, photo_url, created | Limited public profile. No email, no collections, and **no raw `photo`** (only the display `photo_url`). `about` is the Markdown bio (rendered safely on the frontend). `created` allows "Member since" display. |
| `UserUpdateSerializer` | name, headline, about, photo, koro, theeeme, notify_activity, notify_news, age_range, postal_code | PUT/PATCH input. Uses `SafeHeadlineField` (name/headline) and `SafeTextField` for `about` (rejects raw HTML, permits Markdown, max 2000). `photo` uses `ImageIdField` (Cloudinary public_id, path-traversal safe). `koro` accepts: basic, beat, calm, pulse, vibration, wave. `notify_activity` / `notify_news` are the global Cat. 2 / Cat. 3 opt-out toggles. `age_range` (a `ChoiceField` over the four brackets) and `postal_code` (`SafeHeadlineField`, max 10) are the optional COMMUNITY demographics. |
| `NotificationPrefsSerializer` | notify_activity, notify_news | Lives in `core/views/notifications.py`. Used by `NotificationsByTokenView` for unauthenticated token-based preference editing. |

### `thing.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `DocumentSerializer` | public_id, filename, content_type | Plain `Serializer` for validating document entries. `public_id` validated via `validate_image_id`. `content_type` whitelisted to PDF, Word, Excel, Markdown. |
| `ThingSerializer` | code, type, owner, owner_name, created, headline, description, thumbnail/url, gallery, gallery_urls, tags, collection_tags, status, faqs, fee, availability, location, condition, documents, document_urls, available_today, next_available, deal, pending_booking, my_pending_booking, pending_questions, collection_code, collection_headline, collection_owner, collection_swap_minimum_items, my_swap_count_in_collection, transfer_count, response_count, my_response, is_endless | Full read representation. `owner_name` returns the owner's name only — never the email fallback, since it's shown to co-members in the community grid (L2). `gallery` is the raw ordered list of Cloudinary public_ids (additional photos beyond the cover `thumbnail`); `gallery_urls` is the matching list of built Cloudinary URLs. `available_today` (bool) and `next_available` (date) are the live availability for date-based types (LEND/RENT), computed from the booking calendar via the prefetch-aware `Thing.availability_window()` — both null for non-date types. `pending_booking` returns first PENDING booking code (owner use). `my_pending_booking` returns the requesting user's own PENDING booking code (or null) — used by guests to distinguish "Not available" vs "Waiting for confirmation". `collection_code/headline/owner` from first associated collection. `collection_owner` is the owner code of the first associated collection — used by the frontend to decide whether to show the "Delete" button for SHARE_THING after transfer. `collection_swap_minimum_items` mirrors the first associated collection's `swap_minimum_items` (0 when not a swap collection). `my_swap_count_in_collection` is the requester's count of own ACTIVE/TAKEN SWAP_THINGs in that collection — together they let the frontend gate the "Propose swap" button without an extra request. `response_count` is the number of answers to a wish (WISH_THING only, null otherwise) and `my_response` is the requesting user's own answer (`{code, kind, status}`) or null — both prefetch-aware via the `responses` Prefetch. `documents` is the raw JSONField (with Cloudinary public_ids), serialised to the **owner only** (null for other viewers — it backs the owner's edit form; exposing public_ids would let a viewer rebuild an eternal URL for legacy public documents). `document_urls` returns `[{filename, url}]` where `url` is the gated `DocumentDownloadView` endpoint, never a raw Cloudinary URL — documents are private and the endpoint mints a short-lived signed URL per request (M2). `tags` are the thing's owner-defined tags; `collection_tags` is the union of its collections' tag vocabularies (feeds the edit-form tag picker). |
| `ThingCreateSerializer` | type, headline, description, thumbnail, gallery, tags, fee, availability, location, condition, documents, is_endless | Uses `SafeHeadlineField`, `SafeTextField`, `ImageIdField`. `location` uses `SafeHeadlineField(max_length=32)`. `documents` is a `ListField(max_length=5)` validated via `DocumentSerializer`. `gallery` is a `ListField(child=ImageIdField(), max_length=8)` — each entry validated as a Cloudinary public_id; `thumbnail` stays the cover, `gallery` is purely additive. `is_endless` is an optional BooleanField (default False), meaningful only for GIFT_THING and SELL_THING. |
| `ThingUpdateSerializer` | type, headline, description, thumbnail, gallery, tags, status (read-only), fee, availability, location, condition, documents, is_endless | Same validation fields. `status` is read-only (changed by booking flow or dedicated activate/hide endpoints). `documents` and `gallery` same as create (add/reorder/delete = PATCH the full ordered list). `tags` is a `ListField` (max 12); `validate_tags` enforces the tags are a subset of the thing's collections' `tags`. On create the subset check runs in `ThingViewSet.perform_create` against the target collection. `is_endless` same as create. |

### `collection.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `CollectionSerializer` | code, owner, owner_name, created, headline, description, status, mode, digest_frequency, is_swap, is_share, newsletter_enabled, is_minimalist, swap_minimum_items, allowed_thing_types, tags, thumbnail, thumbnail_url, pause_message, is_paused, things, invites, pending_invites | `things` excludes INACTIVE things for non-owners. **`invites` (co-member emails) and `pending_invites` are owner-only (L2):** the owner gets `invites` as `code`+`email`+`name` (plus each member's `age_range`+`postal_code` when the collection is COMMUNITY — owner-only demographics, never public) and the full `pending_invites`; non-owners get `invites` as `code`+`name` (no email — preserves the member count for the card) and an empty `pending_invites`. `pending_invites` queries the RSVP table. `is_swap` indicates swap-only collection. `is_share` indicates share-only collection (mutually exclusive with `is_swap`). `newsletter_enabled` enables weekly activity newsletter (requires `is_share`). `is_minimalist` enables photo-album mode (mutually exclusive with `is_swap`, compatible with `is_share`). `allowed_thing_types` is a per-collection allowlist of Thing types — empty list means no restriction. `pause_message` is the owner's custom message shown to guests during a pause; empty = not paused. `is_paused` is a read-only computed boolean (`bool(pause_message)`). **`share_token` is deliberately excluded** — it is a public bearer credential and would grant access to anyone who can read it. The token is only returned by `POST /api/v1/collections/{code}/share-link/`. **`visibility`** (PUBLIC/PRIVATE) is exposed read-side so the frontend can show the open/closed state and badge — it is not sensitive (it gates *whether* anyone may read, not *what* a reader sees). |
| `CollectionThingSummarySerializer` | code, type, owner, owner_name, headline, description, status, fee, availability, available_today, next_available, location, condition, thumbnail_url, gallery_urls, tags, pending_booking, my_pending_booking, pending_questions, transfer_count, response_count, my_response, collection_swap_minimum_items, my_swap_count_in_collection, deal, created | Lightweight thing representation nested inside `CollectionSerializer`. `tags` are the thing's owner-defined tags (rendered as HDS Tags on the card). `gallery_urls` lets the collection-grid card (`ThingLinkbox`) show the same "Image pagination" carousel when a thing has more than one photo. `available_today`/`next_available` are the same live availability as on `ThingSerializer` (date-based types only, null otherwise) so the collection-page cards (`ThingLinkbox`) show it too — prefetch-aware via the `_blocked_periods` Prefetch added in `_optimise_collection_queryset`. `owner_name` returns the thing owner's name only (never the email — it's shown to co-members, L2) — used by the frontend to show attribution in COMMUNITY collections. `my_pending_booking` same as in `ThingSerializer`. `response_count` is the number of answers to a wish (WISH_THING only, null otherwise) and `my_response` is the requesting user's own answer (`{code, kind, status}`) or null — both prefetch-aware via the `responses` Prefetch. `collection_swap_minimum_items` and `my_swap_count_in_collection` mirror the parent collection's swap-minimum rule and the requester's own count — `CollectionSerializer.get_things()` computes the count once per collection and passes it via context, so it costs 1 query regardless of how many things the collection contains. Request context is forwarded from `CollectionSerializer.get_things()`. |
| `CollectionCreateSerializer` | headline, description, mode, digest_frequency, is_swap, is_share, newsletter_enabled, is_minimalist, swap_minimum_items, allowed_thing_types, tags, thumbnail | Input for collection creation. `tags` is the owner-defined tag vocabulary (`ListField` of `SafeHeadlineField`, max 12, ≤32 chars each, no HTML; `validate_tags` trims + dedupes case-insensitively). `is_swap` and `is_share` are mutually exclusive and require COMMUNITY mode. `newsletter_enabled` requires `is_share`. `is_minimalist` is mutually exclusive with `is_swap`. `swap_minimum_items > 0` requires `is_swap=True`. `allowed_thing_types` is validated by `_validate_allowed_thing_types`: empty list is always accepted (UI enforces "pick at least one"). When non-empty: rejected if `is_swap` or `is_share` is on (the flag already forces the type — combining is redundant); in PROPRIETARY mode the list must be a subset of `(GIFT, SELL, ORDER, RENT, LEND)`, or exactly `["GIFT_THING"]` when `is_minimalist=True`; in COMMUNITY mode (without `is_swap`/`is_share`) the list must be a subset of the 7 community-valid types (everything except SWAP), or `["GIFT_THING", "SHARE_THING"]` (or a subset) when `is_minimalist=True`. **`visibility`** is optional: when omitted it defaults by mode (COMMUNITY→PUBLIC, PROPRIETARY→PRIVATE); an explicit value overrides (e.g. a proprietary owner may open theirs to PUBLIC). |
| `CollectionUpdateSerializer` | headline, description, status, mode, digest_frequency, is_swap, is_share, newsletter_enabled, is_minimalist, swap_minimum_items, allowed_thing_types, tags, thumbnail, pause_message | Input for collection updates. Same validation as create. **Cascade-strip:** `update()` drops any tag removed from `tags` from every thing in the collection that still had it (tags are cosmetic — no orphan-block, unlike `allowed_thing_types`). `pause_message` accepts an empty string (resume) or a non-empty message (pause). When narrowing `allowed_thing_types`, an orphan check runs: any existing thing whose type would no longer fit causes a 400 listing the offending types. **`visibility`** (PUBLIC/PRIVATE) is togglable here, so an owner can open a collection to anonymous readers or close it back to invite-only. |
| `CollectionInviteSerializer` | email | Input for inviting a user. |
| `CollectionAddThingSerializer` | thing_code | Input for adding a thing to a collection. |
| `CollectionRemoveThingSerializer` | thing_code | Input for removing a thing from a collection. |
| `CollectionRemoveInviteSerializer` | user_code | Input for removing a user from invites. |
| `CollectionBroadcastSerializer` | subject, message | Input for broadcasting to invitees. Uses `SafeHeadlineField` (max 64) and `SafeTextField` (max 256). |

### `booking.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `BookingPeriodSerializer` | code, created, thing_code, thing_headline, thing_type, requester_code, requester_name, requester_email, owner_code, start_date, end_date, delivery_date, quantity, status, offered_thing_codes, offered_thing_headlines | Full booking for owner view. Uses `source` to traverse FK relations. `offered_thing_codes`/`offered_thing_headlines` return lists for SWAP_THING bookings, null otherwise. |
| `BookingPeriodCalendarSerializer` | start_date, end_date, status | Minimal calendar view for guests (no requester info). |
| `BookingPeriodOwnerCalendarSerializer` | code, created, requester_code, requester_name, start_date, end_date, delivery_date, quantity, status, offered_thing_codes, offered_thing_headlines | Owner calendar view with requester details. `requester_name` falls back to email. `created` is the booking request date. `offered_thing_codes`/`offered_thing_headlines` return lists for SWAP_THING bookings, null otherwise. |
| `ThingRequestWithDatesSerializer` | start_date, end_date | Plain `Serializer` for LEND/RENT requests. Validates start >= today, end >= start. |
| `ThingOrderSerializer` | delivery_date, quantity (1-99) | Plain `Serializer` for ORDER requests. Validates delivery >= today. |
| `MyBookingSerializer` | code, created, thing_code, thing_headline, thing_type, owner_code, owner_name, start_date, end_date, delivery_date, quantity, status | Requester's own booking view. `owner_name` falls back to email. |

### `faq.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `FAQSerializer` | code, thing, created, questioner, questioner_name, question, answer, is_visible | Full FAQ read representation. |
| `FAQCreateSerializer` | question | Plain `Serializer`. Uses `SafeHeadlineField` (max 64 chars). |
| `FAQAnswerSerializer` | answer | Plain `Serializer`. Uses `SafeTextField` (max 256 chars). |

### `wish.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `WishResponseSerializer` | code, wish, responder, responder_name, created, kind, thing, thing_headline, thing_type, thing_thumbnail_url, message, url, fee, status | Full read representation of an answer to a wish. `thing*` fields are populated only for `HAVE_THIS` answers (the offered listing). All fields read-only. |
| `WishResponseCreateSerializer` | kind, thing_code, message, url, fee | Plain `Serializer`. `validate()` enforces: `HAVE_THIS` requires `thing_code`; `KNOW_WHERE`/`CAN_MAKE` require a non-blank `message`. `message` uses `SafeTextField` (max 256); `url` is a `URLField`. The view additionally checks the offered listing is owned by the responder. |

### `theeeme.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `TheeemeSerializer` | code, name, color_01–color_06 | Read-only `ModelSerializer` for theme listing. Includes all six HDS colour token names so the frontend can render colour swatches. |

### `transfer.py`

| Serializer | Fields | Notes |
|------------|--------|-------|
| `ThingTransferSerializer` | code, from_user, to_user, from_user_name, to_user_name, lent_date, returned_date | Individual transfer record. `from_user_name`/`to_user_name` are the bare name (empty if unset — never the email, since the journey is shown community-wide, L2). |
| `ThingTransferStatsSerializer` | total_transfers, unique_homes, current_holder, current_holder_name, original_owner, original_owner_name, is_share_in_community, transfers | Aggregated stats plus full transfer list. `transfers` is a nested list of `ThingTransferSerializer`. `current_holder` is the user code of the most recent unreturned transfer's `to_user`, or null. `original_owner` is the `from_user` of the oldest transfer (null if no transfers). `is_share_in_community` is True when the thing is a SHARE_THING in a COMMUNITY collection. |

Note: `ThingSerializer` and `CollectionThingSummarySerializer` both include a `transfer_count` computed field that returns the number of transfers for each thing (uses prefetched `_transfer_count` annotation when available, falls back to queryset count).
