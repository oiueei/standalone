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
| `compute_availability(blocked_periods, today=None, horizon_days=90, allowed_weekdays=None, durations=None)` | iterable of PENDING/ACCEPTED bookings (objects with `start_date`/`end_date`), plus the governing collection's rental rules | **Pure, side-effect-free.** Returns `(available_today: bool, next_available: date|None)` for a date-based thing. Walks forward from `today` (default `timezone.localdate()`), treating each booking `[s, e]` as blocking pickup on `[s, e)` — the return day `e` is free for the next pickup (matching `BookingPeriod.has_overlap()`'s strict overlap / back-to-back handovers) — and returns the first day a pickup could start, or `(False, None)` when no day within `horizon_days` qualifies. Null-dated rows are skipped. **`allowed_weekdays` (0=Mon…6=Sun) + `durations` (days) are the rental rules (#7)**: a day counts only if its weekday is allowed, it is free for pickup, and — when the collection fixes the lengths — at least one length both lands its return day on an allowed weekday and fits without a strict overlap. This mirrors `frontend/src/utils/rental.js::isPickupDisabled` exactly, so the card and the date picker can't contradict each other (the bug: a Wednesdays-only collection with next Wednesday booked reported "available today" on a Monday). Either rule may be passed alone; with neither the walk is byte-identical to the unrestricted one. Consumed by `Thing.availability_window()` → the `available_today`/`next_available` serializer fields. |

##### Reservation requests

These own the **create** side (formerly the `ThingRequestView._handle_*` methods). Each performs the locked create + status transition, then fans out the request emails + in-app notification + `HOLD_REQUESTED` event via the shared `send_*_request_notifications()` helpers. Rule violations raise `BookingRequestError(message, status_code)`; `ThingRequestView` catches it and returns `{"error": message}` with that status (default 400; 409 for a date overlap). Serializer validation stays in the view.

| Function | Input | Behaviour |
|----------|-------|-----------|
| `request_share_booking(thing, requester, owner_email)` | SHARE_THING | Rejects a duplicate PENDING request (400), else creates a dateless booking (thing stays ACTIVE). Returns the booking. |
| `request_date_based_booking(thing, requester, owner_email, start_date, end_date, rental_collection=None)` | LEND/RENT | Enforces `rental_collection.rental_violation()` (400) and `BookingPeriod.has_overlap()` (409), then creates the dated booking. Returns the booking. |
| `request_standard_booking(thing, requester, owner_email)` | GIFT/SELL | Re-checks availability + duplicate under the lock; creates the booking and flips a non-endless thing to `TAKEN`. Returns the booking. |
| `request_swap_booking(thing, requester, owner_email, offered_codes)` | SWAP_THING | Validates the swap collection, the `swap_minimum_items` gate, and every offered thing (SWAP type, owned, ACTIVE, same collection); creates the booking + M2M links. Returns `(booking, offered_things)`. |
| `resolve_rental_collection(thing, collection_code=None)` | LEND/RENT | Picks the collection whose rental rules apply (the passed `collection_code`, else the thing's first collection with rules, else `None`). |
| `send_booking_request_notifications(...)` / `send_swap_request_notifications(...)` | — | RSVP accept/reject pair → owner request email + requester confirmation + owner in-app notification + `HOLD_REQUESTED` event. |

#### Patterns

- **Atomic transactions**: Every function wraps its work in `transaction.atomic()` to ensure `BookingPeriod` and `Thing` are updated together or not at all.
- **Row-level locking**: Uses `Thing.objects.select_for_update()` to prevent race conditions when two concurrent requests try to modify the same thing's status.
- **Single-use type check**: Only GIFT and SELL things (`SINGLE_USE_TYPES` from `core.models.booking`) change thing status on accept/reject/cancel. Date-based types (LEND, RENT) and SHARE_THING leave thing status unchanged because multiple bookings can coexist.
- **`is_endless` guard**: For GIFT/SELL things where `thing.is_endless=True`, all status changes (TAKEN on request, INACTIVE on accept, ACTIVE on reject/cancel) and ThingTransfer creation are skipped. The thing remains ACTIVE at all times and accumulates multiple simultaneous PENDING bookings from different users. `expire_old_pending()` also excludes endless things from the TAKEN→ACTIVE restore.
- **SHARE_THING ownership transfer**: On acceptance, `thing.owner` is changed to the requester. The thing stays `ACTIVE` so the new owner can continue sharing it. This enables a chain of ownership transfers within a community collection.
- **SWAP_THING bilateral transfer**: On acceptance, the requested thing transfers to the requester, and all offered things transfer to the original owner. All things stay `ACTIVE`. `ThingTransfer` records are created for every thing involved (requested + offered).
- **Thin view, service raises**: the reservation-request business logic lives entirely in the `request_*` functions. `ThingRequestView` only does HTTP-layer work — shared guards, serializer parsing, response shaping — and translates `BookingRequestError` into the `{"error": ...}` response. Callers outside DRF (management commands, future flows) can request bookings without touching the view.

---

### `email_service.py` — Centralised Email Sending

All outbound emails are composed and sent from this module. Views call these functions rather than constructing emails inline.

#### Categories and notification preferences

Every email belongs to one of three categories. Each function routes through the internal `_send()` helper, which checks the recipient's preferences (looked up by email on the `User` model) before dispatching.

| Category | Constant | User flag | Scope |
|----------|----------|-----------|-------|
| **Cat. 1 — Mandatory** | `CATEGORY_MANDATORY` | (ignored — always sent) | `send_magic_link_email`, `send_collection_invite_email`, `send_collection_welcome_doc_email`, `send_collection_revoke_email` |
| **Cat. 2 — Activity** | `CATEGORY_ACTIVITY` | `User.notify_activity` | `send_booking_request_email`, `send_booking_decision_email`, `send_booking_confirmation_email`, `send_invite_rejected_email`, `send_faq_question_email`, `send_faq_answer_email`, `send_faq_hide_email`, `send_thing_reported_email`, `send_return_reminder_email`, `send_broadcast_email`, `send_swap_request_email`, `send_swap_confirmation_email`, `send_wish_posted_email`, `send_wish_response_email`, `send_wish_thanks_email` |
| **Cat. 3 — News** | `CATEGORY_NEWS` | `User.notify_news` | `send_digest_email`, `send_newsletter_email` |

- **Lookup fallback**: if no `User` matches the recipient email (e.g. a not-yet-registered invitee), `_should_send` returns `True` — all emails reach non-users by default.
- **Multi-recipient**: functions that take `emails=[...]` (digest, newsletter, broadcast) use `_filter_recipients()` for a bulk query that drops opted-out addresses before iterating.
- **Footer**: Cat. 2 and Cat. 3 emails get an auto-appended footer with a link to `/me/notifications/{token}` (see below). Cat. 1 has no footer — nothing to manage.
- **Viral CTA**: every send except `send_stats_summary_email` (which passes `include_viral=False` — an operator report, not growth copy) prepends one random growth blurb from the per-language `VIRAL_LINES` catalogue (`email_texts/{lang}.py`, read via `viral_lines()`) above the footer — the CTA is always the plain `{frontend_base}/collections/new` link, never tracking-wrapped (DESIGN §9). It is suppressed for recipients who already own ≥1 collection (the `_owns_collection` flag is folded into the existing `_lookup_user`/`_lookup_users` query via an `Exists` annotation — no extra round-trip), and for an empty list. So the bottom order is always: body → viral line (when shown) → preferences footer (when present). **`send_magic_link_email` carries it too since S2** (CA decided: the magic link is the one email every user gets, so suppressing growth copy there starved the loop) — this makes `_send()` do one extra `User` lookup for magic-link sends it used to skip, but both its callers only ever reach it after the recipient is already resolved (`RequestLinkView` for a confirmed-registered address, `PopInView` after `get_or_create`), so the lookup adds no new registered/unregistered timing signal (L10 stays about language resolution, not this gate — see below).

#### Email language — the hierarchy (`EMAIL_LANGUAGE` + `Collection.language` + `User.language`)

Which language an email speaks is decided per **recipient**, by three levels, weakest to strongest:

1. **Deployment default** — `EMAIL_LANGUAGE` (env var, default `en`; the standalone repo stays English, www.oiueei.com sets `es`).
2. **The collection's language** — `Collection.language`, the owner's choice for their group.
3. **The recipient's own preference** — `User.language`, which always wins.

Blank means "inherit", so a level only speaks when it was actually set — existing rows keep the old per-deployment behaviour with no data migration. `resolve_email_language(user=None, collection=None)` implements it; `_recipient(email, collection=None)` resolves the recipient's `User` **once** and returns `(user, lang)`, handing the user to `_send()` so the preference check, footer link and viral gate don't re-query it.

Senders **shadow the module-level `T` with a language-bound one** (`T = _texts(lang)`), so every `T("key")` in the body speaks the recipient's language without threading the argument through each call. `_send(..., lang=)` follows it for the footer and viral line, so the whole message is in one language.

Senders bind **`L = _local(lang)`** next to `T` and pass every **owner-written** value through it — a collection headline, a thing headline, a wish headline (O6: any of them may carry one text per language as inline JSON). So the resolution happens exactly where the recipient's language is already known, and a Catalan member reads "…a 'Les coses de mama'…" while their Spanish neighbour reads "…a 'Las cosas de mamá'…" from the same row. A plain headline — nearly all of them — comes back untouched. The one operator-facing sender, `send_stats_summary_email`, carries aggregate numbers, not owner content.

- **Collection-scoped emails pass their collection**: invite (+ bulk), invite-rejected, revoke, welcome-doc, broadcast, digest, newsletter, wish-posted, and the pop-in/join magic link.
- **Thing-scoped 1:1 emails pass only the recipient** (bookings, FAQs, swaps, reminders, reports): there is no group to speak for, so it's their preference or the deployment default — never a guessed collection.
- **Bulk sends compose per language**: `_send_per_language(emails, category, compose, collection=...)` drops opt-outs, bulk-resolves the users in one query, and calls `compose(lang)` once per *distinct* language among the recipients — so one digest to a bilingual group leaves in two languages while a 50-member single-language group still composes once.
- **The magic link is the exception**: its caller (`core/views/auth.py::_send_magic_link`) resolves the language and passes it in, because that sender must not look the recipient up — `request-link` only sends for a registered address, so a DB round trip would make "registered" responses measurably slower and become an email-enumeration timing oracle (L10).
- **`PopInView` accepts an optional `language`** in the body and stores it on **newly created** users only, so a joiner's very first magic link already speaks their UI language; an existing user's saved preference is never overwritten by the browser they arrived from.

Every user-facing string lives in a per-language catalogue — `email_texts/en.py` (the reference + universal fallback), `es.py`, `ca.py` — as flat `TEXTS` dicts of `str.format` templates, mirroring the `seed_data/{lang}.py` pattern. `T(key, lang=None)` falls back to English for an unknown language or a missing key; without `lang` it reads `settings.EMAIL_LANGUAGE` on every call (so `override_settings` works in tests). `test_email_language.py` pins the en default, the es/ca deployments, the fallback, and en↔{es,ca} catalogue/placeholder/viral-line parity (the email analogue of `i18nParity.test.js`); `test_email_hierarchy.py` pins the resolution matrix and the per-recipient bulk sends. To add a language: copy `en.py` → `{lang}.py`, translate only the values (keep keys + `{placeholders}`), and add the code to `Language` in `core/models/language.py` so owners and users can pick it. The operator-facing `send_stats_summary_email` carries data built by the command and is not part of the catalogue.

#### Signed tokens for unauthenticated preference editing

- `make_notifications_token(user_code)` — returns a `TimestampSigner`-signed string (salt `notifications-prefs`, TTL 1 year) scoped to notification preferences editing.
- `verify_notifications_token(token)` — returns the user_code on success, `None` on failure.
- Used by `NotificationsByTokenView` at `GET/PATCH /api/v1/notifications/token/<token>/` so recipients can toggle preferences via the email footer without logging in.



#### Functions

| Function | Trigger | Recipient |
|----------|---------|-----------|
| `send_magic_link_email(email, magic_link, collection_headline=None)` | User requests login / pop-in / share-link join | The user (subject names the joined collection when `collection_headline` is passed; generic welcome subject otherwise) |
| `send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link)` | Guest submits a hold request | Thing owner |
| `send_booking_confirmation_email(requester, thing, booking)` | Guest submits a hold request | Requester (confirmation of what was requested) |
| `send_booking_decision_email(booking, thing, accepted)` | Owner accepts or rejects a booking | Requester |
| `send_collection_invite_email(inviter_name, collection_headline, email, accept_link, reject_link)` | Owner invites a user to a collection | Invitee |
| `send_invite_rejected_email(invitee_name, collection_headline, owner_email)` | Invitee declines a collection invitation | Collection owner |
| `send_collection_welcome_doc_email(collection_headline, doc_url, email)` | A user becomes a member of a collection **for the first time** (any join path — invite, share-token pop-in, public-collection join, onboarding) and the owner has set a welcome PDF | The new member. The PDF travels as a **link** (Cloudinary), never an attachment. Membership lifecycle ⇒ Cat. 1: a member who never sees the rules can't follow them |
| `send_collection_revoke_email(owner_name, collection_headline, email)` | Owner removes a user from a collection | Revoked user |
| `send_faq_question_email(questioner_name, thing, question, owner_email)` | Guest asks a question on a thing | Thing owner |
| `send_faq_answer_email(owner_name, thing, question, answer, questioner_email)` | Owner answers a FAQ | Questioner (the email links the thing — label is the thing headline, via `_thing_url`) |
| `send_faq_hide_email(owner_name, thing_headline, question, questioner_email)` | Owner hides a FAQ | Questioner |
| `send_thing_reported_email(thing, owner_email)` | A member reports a thing | Thing owner (**anonymous** — the reporter is never named; body links to the listing so they can review it) |
| `send_broadcast_email(owner_name, owner_email, collection_headline, collection_code, message, emails)` | Owner sends broadcast to collection | All collection invitees (individually, Reply-To owner + a link to the collection). Subject auto-generated as `Hey! {collection}`. |
| `send_digest_email(collection_headline, collection_code, thing_headlines, emails)` | Daily command (weekly/monthly) | All collection invitees (individually) |
| `send_newsletter_email(collection_headline, collection_code, new_thing_headlines, transfer_entries, emails)` | Daily command (Mondays, share collections with `newsletter_enabled`) | All collection invitees (individually). Two blocks: new things (bulleted) and ownership changes (date — thing: from → to). |
| `send_return_reminder_email(requester_name, thing_headline, end_date, owner_email)` | Daily command (end_date = tomorrow) | Thing owner |
| `send_swap_request_email(requester, thing, offered_things, owner_email, accept_link, reject_link)` | Guest proposes a swap | Thing owner (lists offered thing headlines, accept/reject links) |
| `send_swap_confirmation_email(requester, thing, offered_things, booking)` | Guest proposes a swap | Requester (confirmation of swap proposal) |
| `send_wish_posted_email(creator_name, wish, emails)` | Member posts a wish with "Avisar al grupo" on | Every group member (individually; activity opt-out applies) |
| `send_wish_response_email(responder_name, wish, creator_email)` | Member answers a wish | Wish creator |
| `send_wish_thanks_email(creator_name, wish, responder_email)` | Wish creator marks it resolved | Accepted responder |
| `send_stats_summary_email(recipient, subject, sections)` | `stats_summary` command (weekly, `STATS_EMAIL_WEEKDAY` — default Monday — / `--email`) | The operator. Internal ops report — **CATEGORY_MANDATORY** (ignores `notify_*`, no footer). `sections` is the `[{title, rows, note?}]` structure the command builds; rendered to escaped HTML via the layout blocks |

#### Patterns

- **XSS prevention**: All user-provided content is escaped with `django.utils.html.escape()` before being inserted into HTML email bodies. Plain text versions use raw values (safe in plain text context).
- **Dual format**: Every email is an `EmailMultiAlternatives` with a plain-text body plus an HTML alternative (`attach_alternative(html, "text/html")`) for clients that support it.
- **Inline logo (CID, no remote fetch)**: `_send()` attaches `frontend/public/oiueei-logo.png` as an inline `MIMEImage` (`Content-ID: <oiueei-logo>`, `Content-Disposition: inline`), read once via `_logo_bytes()` (`functools.lru_cache`). `layout.html` renders `<img src="cid:oiueei-logo" ...>` above the body blocks — `_render_email()` only emits the tag when `_logo_bytes()` found the file, so a missing asset degrades to "no logo" (never a broken image, never a failed send). A remotely-hosted logo would be a de-facto open beacon (DESIGN.md §9), so the PNG travels inside the email instead. When the logo is present, `_send()` sets `mixed_subtype = "related"` before attaching it, so the image is a CID reference inside `multipart/related[multipart/alternative[plain, html], image]` rather than a `multipart/mixed` sibling — Apple Mail otherwise renders the 30px inline logo *and* a full-size copy with a paperclip (S1).
- **Action links**: Booking and invitation emails include accept/reject links (RSVP-based URLs generated by the calling view). FAQ question emails include a direct link to the thing page.
- **`from_email=None`**: Uses Django's `DEFAULT_FROM_EMAIL` setting.
- **Booking email variants**: `send_booking_request_email` and `send_booking_decision_email` adapt their content based on booking type — date-based (start/end) or simple (no extra fields).
- **Per-type action nouns**: the three generic booking emails (request/confirmation/decision) interpolate `{action}` from `_action_noun(thing)` (`T(f"action_noun_{thing.type}")`) so the wording mirrors the frontend's per-type vocabulary — a SELL request reads "purchase request" / "solicitud de compra", a LEND request "loan request" / "solicitud de préstamo", etc. Six nouns live in each catalogue (`action_noun_{GIFT,SELL,LEND,RENT,SHARE,SWAP}_THING`); SWAP's request/confirmation emails have their own dedicated templates, but the **decision** email is shared (`finalize_booking_decision` runs for every booking type), so SWAP needs a noun too — a missing key is a `KeyError` mid-decision, after the ownership transfer already committed (guarded by `test_every_bookable_type_has_an_action_noun`). WISH never books. **Catalan caveat**: in `ca.py` the noun values carry the preposition (`"de compra"`, `"d'intercanvi"`) and the templates read `sol·licitud {action}` — Catalan elides "de" before a vowel, so the en/es template shape (`de {action}`) can't work there. The owner confirm/cancel button verbs (`hold_confirm_cta`/`hold_cancel_cta`) stay generic by design.
- **Reply-To header**: `send_broadcast_email()` uses `EmailMultiAlternatives` with `reply_to` so invitees can respond directly to the collection owner (routed through `_send(..., reply_to=[owner_email])`). The visible body links to the collection (`/collections/{code}`) — the object that originated the message — rather than promising an email reply.
- **Digest emails**: `send_digest_email()` lists new thing headlines in both plain text (bulleted) and HTML (`<ul>/<li>`) formats.
- **Direct collection links**: `send_digest_email()` and `send_newsletter_email()` link straight to `{frontend_base}/collections/{code}`. Per DESIGN.md §9 we do not track email engagement — links are never wrapped in a redirect or tracking pixel.
- **Preference pipeline**: every send goes through `_send()` → `_should_send()` + `_with_viral_line()` + `_with_footer()`. Never build an `EmailMultiAlternatives` directly from outside this module — the preference check, viral CTA, footer and logo attachment would all be bypassed.

---

### `cloudinary_cleanup.py` — Delete Cloudinary Assets on Delete

Frees the Cloudinary images a record owns when the record itself is deleted, so removing a thing / collection / user doesn't leave orphaned assets piling up (storage cost + clutter).

#### How it's wired

- **`post_delete` signal handlers** on `Thing`, `Collection` and `User` (registered in `core.apps.CoreConfig.ready`). Django fires `post_delete` for cascade-deleted rows too, so this single hook covers every path: a direct thing/collection delete, the collection view's orphan-thing sweep (`CollectionViewSet.perform_destroy`), and a user-account FK cascade (which removes their collections and things).
- **Runs on `transaction.on_commit`** — a delete that rolls back keeps its images. The destroy **never raises** (`_destroy` swallows + logs): an orphaned asset is a smaller problem than a delete that blows up.

#### What gets destroyed per model

| Model | Assets |
|-------|--------|
| `Thing` | `thumbnail` and every `gallery` id |
| `Collection` | `thumbnail`, `welcome_doc` (the welcome PDF — also `resource_type=image`, so the default destroy kwargs are right) |
| `User` | `photo` |

#### Suspension (the demo-seed guard)

`suspended()` is a context manager that disables the cleanup for deletes inside the block. **`seed_demo._reset()` wraps its deletes in it**: the demo reuses a fixed pool of shared Cloudinary public ids, so wiping them on `--reset` would destroy the very images the immediate re-seed points back at. Any other bulk delete that must not touch Cloudinary can reuse the same guard.
