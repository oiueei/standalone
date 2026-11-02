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
| `name` | CharField(32) | No | **Public name** — presented in the profile editor as "Nombre público" with a helper making its reach explicit ("your name, a nickname, anything you like — it's how everyone will see you"). One field, chosen pseudonymity: each user decides how identifying their public name is (early-adopter hardening, 2026-07-18). Never auto-filled from anywhere |
| `created` | DateField | Auto | Date the user was created |
| `last_activity` | DateField | No | Date of last login/activity. Null until the user's first verify — `update_last_activity()` populates it. |
| `headline` | CharField(64) | No | Short bio/tagline |
| `about` | CharField(2000) | No | Free-form Markdown profile content (contact info, social links, extra info). Optional; any user may set it. Rendered with the frontend `MarkdownText` component; written through `SafeTextField` (rejects raw HTML, allows Markdown). |
| `photo` | CharField(255) | No | Storage key for the optional profile photo. Exposed read-side as `photo_url`. When present, the `/:code` profile hero becomes a two-column split on desktop — text beside the photo, separated by a vertical Koros divider (rotated 90°, filled with theeeme `color_03`) — stacking vertically on mobile. |
| `notify_activity` | BooleanField | No | Opt-out toggle for Cat. 2 (activity) emails — bookings, FAQs, reminders, broadcasts. Default: `True` |
| `notify_news` | BooleanField | No | Opt-out toggle for Cat. 3 (news) emails — the per-collection digest. Default: `True` (it was `False`, and the digest consequently reached almost nobody). Defensible under DESIGN §6 only because of `Collection.digest_muted`: the way out of one group's summaries costs none of the transactional email. Remove that control and this default must go back to `False`. |
| `age_range` | CharField(8) | No | Optional **birth-year generation** (`PRE_1946` / `BOOMER` 1946–1964 / `GEN_X` 1965–1980 / `GEN_Y` 1981–1996 / `GEN_Z` 1997–2012 / `GEN_A` 2013–2024 / `GEN_B` 2025–2039 — switched from age brackets in migration 0115: 51_60→GEN_X and 31_40→GEN_Y mapped faithfully, the rest reset to unanswered, mirroring 0114's policy). Asked of every user in the profile editor. Per member it's shared only with the owner of a COMMUNITY collection (guests page); in aggregate it appears in any collection owner's stats CSV. Never public. Default empty. |
| `postal_code` | CharField(10) | No | Optional postal/area code. Same scope as `age_range`: asked of everyone, per-member owner-only in COMMUNITY, aggregate in any owner's stats CSV, never public. Default empty. |
| `language` | CharField(2) | No | The language OIUEEI writes to this user in (`es`/`ca`/`en`) — **the strongest level of the email language hierarchy**, beating both the collection's language and the deployment default. Blank (default) = inherit. Saved **only** from the language `Select` in `EditProfilePage` (which also switches the UI) — a deliberate choice. `JoinView` used to also stamp it on newly-created users from whichever UI language the join page happened to be in; that accidental value then permanently outranked the joined collection's own language for every future email to that member, with no way back short of a profile edit. A brand-new joiner's `language` now stays blank, so the collection's own language governs until they set a preference themselves. The frontend's `useCollectionLanguage` (`frontend/CLAUDE.md`) mirrors the same hierarchy for UI chrome, reading this field via `GET /auth/me/`. |
| `is_active` | BooleanField | Auto | Default True |
| `is_staff` | BooleanField | Auto | Default False |
| `is_superuser` | BooleanField | Auto | Default False |

### Business Rules

1. **Email is mandatory and unique** - A user must have an email address, and no two users can share the same email. This is enforced at the database level with `unique=True`.

2. **Optional profile fields** - The `headline`, `about`, and `photo` fields are optional and default to empty strings.

3. **Relationships via FK/M2M** - Owned collections are accessed via `user.owned_collections.all()` (Collection FK reverse). Invited collections via `user.invited_to_collections.all()` (Collection M2M reverse). Owned things via `user.owned_things.all()` (Thing FK reverse).

4. **Cannot create things for others' collections** - A user can only add their own things to their own collections. Enforced at the view level.

5. **Creation date is persisted** - The `created` field is automatically set to today's date when the user is created.

6. **Last activity is updated on login** - The `update_last_activity()` method is called on each successful authentication **and on every `GET /auth/me/`**, so an account in daily use through the SPA never looks dormant to the retention sweep. Newly-created users have `last_activity = None` until that first call; subsequent calls bump the date to today, and a call on a day already recorded writes nothing.

7. **Email notification preferences** - `notify_activity` and `notify_news` (**both default on**) are consulted by `core/services/email_service.py` before sending. News is additionally narrowed per group by `Collection.digest_muted`, which is what keeps an on-by-default news flag from being a pre-ticked opt-in (DESIGN §6). Magic links and invitations (Cat. 1) are mandatory and always sent regardless of these flags.

8. **Right to erasure** - Any user can delete their own account (`POST /api/v1/auth/delete-account/` → emailed 24h confirmation link → explicit POST commit). The deletion is one `user.delete()` inside a transaction (`core/services/account_service.py`): collections, things, bookings, RSVPs, notifications and daily activity cascade; FAQ questions and ThingTransfer hops on *other people's* things survive with the user FK nulled; stored files are deleted by the `post_delete` handlers.

### Methods

- `update_last_activity()` - Sets `last_activity` to today and clears any standing `inactivity_notified` warning. **A no-op when neither would change**: the column holds a date, and `MeView` calls this on every `GET /auth/me/` — which the SPA asks three or four times per page load — so an unconditional save was that many `UPDATE`s writing the value already there.
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

- **A user has no palette.** `User.theeeme` and `User.koro` moved to the collection (migration `0165`) and their columns (`users.user_theeeme`, `users.koro`) were dropped one release later (`0166`, the pattern of `0152`/`0153`: the previous release's dynos named them in every User query while the release phase ran).
- A collection has a FK to Theeeme with `on_delete=PROTECT` and `default=random_theeeme` (`core/models/theeeme.py`: a new collection gets a random theeeme, not a fixed one). `random_theeeme` reads the **live** Theeeme table (not a hardcoded list) and falls back to `DEFAULT_THEEEME_CODE` (BUU331) if it is empty, so deleting a theeeme can never assign a dangling FK.
- This prevents deleting a Theeeme that is in use by a collection

---

## Collection

The `Collection` model represents a list of things (gifts, sales, orders) owned by a user. Collections can be shared with other users via invites.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `owner` | ForeignKey(User) | **Yes** | Owner of the collection |
| `created` | DateTimeField | Auto | Timestamp when collection was created |
| `headline` | CharField(256) | **Yes** | Title of the collection. **64 characters per language, 256 stored**: an owner may write one text per language as inline JSON (`{"es": "Las cosas de mamá", "ca": "Les coses de mama"}`) and each reader sees theirs — see the multilingual-content note below. |
| `description` | TextField | No | Description of the collection — long-form Markdown. **2000 per language**, serializer-enforced (`LocalizedTextField`); the column is a `TextField` so there is nothing to overflow. |
| `status` | CharField(8) | No | Status: ACTIVE (default) or INACTIVE |
| `kind` | CharField(8) | No | What the collection is for, **fixed when it is created and never changed**: `STALL` (gift or sell — the default), `LIBRARY` (lend or rent out) or `SHED` (book by the day or the hour; always PROPRIETARY). `KIND_THING_TYPES` (module level in `core/models/collection.py`) is the one map of the verbs each holds, and `kind_for_thing_type(verb)` its inverse; `derive_thing_type(kind, fee)` is the verb a thing in such a collection takes (a price makes the paid one, none the free one, a shed always RESERVE). Added in 0157, whose data step reads each existing collection's verbs (the list and its things): one family gives that kind, none a stall, a mix the family with most things — the things of the other family keep their verb — and rewrites `allowed_thing_types` to the kind's own. Its address in the app is `path()`, `/{kind}/{code}`. |
| `mode` | CharField(12) | No | Mode: PROPRIETARY (default), COMMUNITY or **NETWORK**. A NETWORK is a library only (`kind == LIBRARY`; the serializers refuse it on a stall or a shed) and is **fixed at creation in both directions**: a library is born one or never becomes one. Several dinamizadores (the founder and the co-curators) each run their own things, loans and pickup point (`NetworkPoint`); `allowed_thing_types` is both of the library's verbs, as in PROPRIETARY. A deployment's `CREATOR_POLICY` gates the mode like the other two |
| `visibility` | CharField(7) | No | Visibility: PUBLIC or PRIVATE. A PUBLIC collection is readable by anyone — including anonymous visitors — at its address `/{kind}/{code}`; PRIVATE keeps the invite-only behaviour (403 without membership). New collections are born **PRIVATE in both modes** (`CollectionCreateSerializer`, when the request sends no `visibility`); making one PUBLIC is the owner's explicit choice — the switch in the form, or `visibility` in the request — in either mode (whoever contributes to a group is not shown whether it is public, so a Community group that was born public was readable by anyone without its members knowing). Collections that already existed were **not** migrated: making today's public Community groups private would break every public link their curators have already handed out, and each curator decides that from Edit. The DB-level default is PRIVATE as well. |
| `digest_frequency` | CharField(7) | No | Digest email frequency: NONE, WEEKLY, or **MONTHLY (the default; it used to be WEEKLY, and NONE before that)**. Both ends of the digest moved together: an on-by-default frequency here is what makes `User.notify_news` defaulting on mean anything. **Existing collections keep what they have** — an `AlterField` default rewrites no rows, and starting to mail someone else's members on their behalf isn't ours to decide (contrast migration 0127, which subscribes existing *recipients*, who can unsubscribe themselves). Shown in **both** the Create and Edit forms now: a default that sends email has to be visible to the person it sends for. |
| `theeeme` | ForeignKey(Theeeme) | No | The colour palette this group's pages are painted with (`to_field="code"`, `PROTECT`, related name `collections`). Default: a random existing Theeeme (`random_theeeme`). Chosen by a curator among the twelve rows of `theeemes`; **the app's own palette (`Braaanding`) is not one of them and cannot be picked**. Added in `0165`, which gave each existing collection its founder's palette. |
| `koro` | CharField(9) | No | The Koros wave type of the group's pages: basic, beat, calm, pulse, vibration, wave (default: basic). Also from its founder's, in `0165`. |
| `language` | CharField(2) | No | The language this group's outbound email is written in (`es`/`ca`/`en`). Blank (default) = inherit the deployment default (`EMAIL_LANGUAGE`); a member's own `User.language` still wins over it. Set by the owner in the Create/Edit collection form. See `core/services/CLAUDE.md` → the email language hierarchy. **Also drives the frontend's generic UI chrome** on every collection/thing page (`useCollectionLanguage`, `frontend/CLAUDE.md`) for a visitor with no deliberate language of their own — the same hierarchy, applied client-side — unless the owner also wrote that page's text in the visitor's own language, which then wins. `ThingSerializer.get_collection_language` exposes it to the thing-only pages that never fetch the collection object directly. |
| `allow_member_proposals` | BooleanField | No | Whether members may recommend guests (`InvitationProposal`). The owner still decides on every one — this is whether they are willing to be **asked**, which a group with a waiting list, a subscription or an admission process may not be. Default `False` (it was `True`): a new collection asks its owner nothing until the owner turns it on — being asked is something the person who runs a group chooses, not something every group is handed. Collections that existed before kept the value they had (migration 0155 changes only the default for new rows, no data). |
| `is_onboarding` | BooleanField | No | Marks a collection as the landing place for a deployment's **open door**. Nothing in the standalone reads it any more — the open door left with the demo (v0.12.0) — but `seed_demo` still sets it and a deployment that mounts its own door from `DEPLOYMENT_URLCONFS` joins new accounts to every collection carrying it (default: False) |
| `rental_durations` | JSONField (list) | No | Rental rules (#7): allowed rental lengths in **days** for LEND/RENT things in this collection (weeks are normalised to days, e.g. `[1, 3, 7, 14]`). The renter picks exactly one; the return date is derived (N days → `end = start + N`, so a one-week rental picked up on a Wednesday returns the NEXT Wednesday — this keeps a single allowed weekday satisfiable for week-multiple lengths). Default `[]` = no fixed durations (free date range). Sorted + deduped by the serializer. |
| `rental_weekdays` | JSONField (list) | No | Rental rules (#7): allowed weekdays (Python `weekday()`, 0=Mon…6=Sun) for **both** pickup (start) and return (end) of LEND/RENT bookings. Default `[]` = any day. Sorted + deduped by the serializer. **Reused for RESERVE_THING** as "days reservations are allowed" — every day of a reservation's span must fall on one. |
| `reservation_max_days` | PositiveSmallIntegerField | No | **Sheds only** (`kind == SHED`, the reservations collection). The longest a member may book the space for in one reservation, 1–7 (serializer-enforced). Default `1`. Inert on every other collection. |
| `reservation_horizon_days` | PositiveSmallIntegerField | No | **Reservations collections only.** How far ahead a member may book, 1–365 (serializer-enforced). Default `90` (the LEND/RENT horizon it replaces for this type). Also caps how far `Thing.availability_window` walks for a RESERVE thing. The owner sets it because lead time is a fact about the space. |
| `reservation_max_active_per_member` | PositiveSmallIntegerField | No | **Reservations collections only.** How many of a member's own reservations *in this collection* may be `ACCEPTED` and not yet finished at once, 1–50 (serializer-enforced). Default `10`. A courtesy cap against one member sitting on the whole calendar — see `active_reservation_count` — not a security invariant: two simultaneous requests on two different things by the same member could both pass the check before either lands. Inert on every other collection. |
| `reservation_unit` | CharField(4) | No | **Reservations collections only.** `DAY` (default) or `HOUR` — never both. `DAY` is the original shape: a reservation occupies one or more whole days (`reservation_max_days`, `rental_weekdays` reused as "days open"). `HOUR` books a single day in slots within that day's `opening_hours`, bounded by `reservation_min_minutes`/`reservation_max_minutes` — see `Collection.reservation_hour_violation`. |
| `opening_hours` | JSONField (dict) | No | **`HOUR`-unit reservations collections only.** Per-weekday opening windows, keyed by Django's string form of `weekday()` (`"0"`–`"6"`, Mon–Sun), each a list of non-overlapping `["HH:MM", "HH:MM"]` pairs — e.g. `{"0": [["10:00","14:00"],["16:00","20:00"]], "6": []}`. An empty list (or an absent key) means closed that day, **replacing** `rental_weekdays` as "which days are open" under `HOUR` — the two would otherwise be able to disagree. Default `{}` (every day closed until the owner sets hours). Validated + sorted by `core.serializers.collection._validate_opening_hours`; read by `Collection.day_opening_blocks`. |
| ~~`reservation_max_hours`~~ | — (column only) | — | **Out of the model since 0152.** Replaced in 0150 by `reservation_min_minutes`/`reservation_max_minutes` below (an early adopter wanted reservations shorter than an hour, which a whole-hours field can't express), dormant after that. 0152 removes it from Django's state only and gives the still-NOT-NULL **column a database default of 3** (`db_default`), so the release that stops declaring it can't break the previous release's dynos (which still SELECT and INSERT it) while Heroku's release phase runs, and the new code's inserts still satisfy the constraint. **A later release drops the column** — a plain `DROP COLUMN`, safe once no running code names it. |
| `reservation_min_minutes` | PositiveSmallIntegerField | No | **`HOUR`-unit reservations collections only.** The shortest a single reservation may run, in minutes, 1–720 (serializer-enforced, cross-checked against the maximum — see below). Default `60`, matching the fixed floor every `HOUR`-unit collection lived under before this field existed, so no existing collection's behaviour changes until an owner lowers it. **Also the step every duration/start-time choice on the request page is offered in** (`frontend/CLAUDE.md`) — a minimum of 15 offers 15/30/45/… up to the maximum, and start times fall every 15 minutes too; a short minimum the picker still only offered on the hour would be a minimum in name only. Inert under `DAY`. |
| `reservation_max_minutes` | PositiveSmallIntegerField | No | **`HOUR`-unit reservations collections only.** The longest a single reservation may run, in minutes, 1–720 (serializer-enforced). Default `180` (matches `reservation_max_hours`'s old default of 3 hours). **Applies to the full-day span too, with no exception**: a venue whose day adds up to more minutes than this cap simply never offers "the whole day" as a bookable span; the owner raises the cap if they want it offered. See `Collection.reservation_hour_violation`. The Create/Update serializers reject `reservation_min_minutes > reservation_max_minutes` (falling back to the stored value on an update that only touches one side of the pair). Inert under `DAY` (`reservation_max_days` governs there). |
| `closed_dates` | JSONField (list) | No | Holidays / one-off closures — ISO date strings (`"2026-12-25"`), sorted + deduped, past ones dropped on save (the owner re-enters each year). The serializer parses the owner's comma-separated **DD/MM/YYYY** line (`_parse_closed_dates`, cap 60). **No LEND/RENT pickup or return on one; a RESERVE booking can't span one.** Default `[]`. |
| `deposit_policy` | CharField(1024) | No | How deposits work in this group, in the owner's own words ("50 €, back when the drill comes home in one piece"). **256 per language, 1024 stored** — same trick as `description`, `LocalizedTextField` in the serializer. **Writing a policy is the on/off switch**: there is deliberately no boolean beside it, since a second door can disagree with the first (`digest_muted` uses the same shape). A bare amount is the beginning of an argument — the condition for getting it back is the actual rule, and it belongs to the group rather than to each thing. |
| `request_info` | CharField(2048) | No | A short note for anyone reaching the request page — **LEND/RENT/RESERVE alike, not RESERVE_THING only, but never GIFT/SELL**: those complete straight from the card and never visit that page, so a note written here is invisible to them ("bring ID", "reservations must be confirmed 24h ahead"). **512 per language, 2048 stored** (256 was too short for this one) — same trick as `deposit_policy`/`description`, `LocalizedTextField` in the serializer with an explicit `storage_max_length=2048` (wider than `LOCALIZED_TEXT_STORAGE`'s default 1024). Rendered as Markdown on the frontend's `RequestThingPage`, below the title (`ThingSerializer.get_collection_request_info` resolves it through `_viewable_collection`). Default `""`. |
| `email_note` | CharField(2048) | No | The owner's note in the **emails a requester receives about their request** — "request received" and its **acceptance** for every verb, plus RESERVE's auto-confirmation (which is both in one) — inserted after the link to the listing and before the legal footer. Never a **refusal** (no next steps for the note's prose to describe), and never the owner/curator notifications (their own note read back would be noise). **512 per language, 2048 stored** — the same shape and arithmetic as `request_info`, `LocalizedTextField` in the serializer. A small Markdown subset (bold, italics, lists, http(s) links) plus emojis is rendered into the HTML part by `email_service._note_blocks`; the plain-text part carries the raw Markdown. Resolved per recipient like every owner text, through the language that email already speaks. Default `""`. |
| `allowed_thing_types` | JSONField (list) | No | The verbs this collection takes — **always within `KIND_THING_TYPES[kind]` and never empty** (before kinds it was a free allowlist, `[]` meaning no restriction; 0157 rewrote every row). PROPRIETARY always holds both of the kind's verbs (its curators put the things in and set each price); COMMUNITY holds both when members may set a price (a stall's GIFT+SELL, a library's LEND+RENT) and **only the free one** (`[GIFT_THING]` / `[LEND_THING]`) when they may not — the one switch a community group has. A shed is always `["RESERVE_THING"]` and PROPRIETARY. `core/views/things.py::ThingViewSet.create` still rejects a verb outside the list (`type_validity_error`, which answers "This group doesn't take prices." for a paid verb in a free-only group). `normalize_allowed_thing_types(kind, mode, list)` in the collection serializer is what writes it; the Update serializer also runs an orphan check — dropping the paid verb while things of it exist returns 400 naming the types. |
| `tags` | JSONField (list) | No | Owner-defined tag vocabulary for the collection — an ordered list of free-text labels (max 12, ≤32 chars **per language**, no HTML; a label may itself be a localized `{lang: text}` map, capped at 160 stored; trimmed + deduped case-insensitively — on the **raw** string, so a map is one label like any other). Things in the collection may be tagged with a subset (`Thing.tags`). Removing a tag here cascade-strips it from the collection's things. Default `[]`. |
| `home_page` | URLField(128) | No | The group's own website, if it has one. The collection hero's back link goes there (worded "Home") instead of to the app's home. `URLField` so Django's `URLValidator` rejects anything but http(s)/ftp(s); the serializer also caps it at 128 (CI runs Postgres, which enforces the column). The frontend still runs it through `sanitizeUrl` before rendering the link. Set in the Create/Edit collection forms. Default `""`. |
| `thumbnail` | CharField(255) | No | Storage key for the collection thumbnail (default: empty string). |
| `welcome_doc` | CharField(255) | No | Storage key of the owner's optional **welcome & rules PDF** (default: empty string). Emailed as a **link, never an attachment** (Cat. 1, `send_collection_welcome_doc_email`) the first time a user becomes a member — every join path funnels through `core/views/auth.py::_join_collection`, which decides "first time" *before* the idempotent M2M add, so a login-to-act re-join never resends. PDF only, uploaded to the `oiueei/documents` folder (`kind: "document"` on the upload ticket — the server forces this folder), **5 MB enforced server-side**: the cap used to be a client-side check only, because `max_file_size` was not a signable Cloudinary parameter, and it is now signed into the presigned URL where a client cannot skip it. `core.utils.doc_asset_url` builds the delivery URL — no longer a `.pdf`-suffixed one: Cloudinary filed a PDF under `resource_type=image` and needed the extension to serve it as a document, whereas the object store serves the `Content-Type` signed at upload. `asset_cleanup` deletes it with the record, and `cleanup_orphan_images` must keep cross-referencing it or its sweep would delete a live document. |
| `pause_message` | CharField(256) | No | Owner's message to guests explaining why the collection is paused (default: empty string). Non-empty = paused. |
| `share_token` | CharField(22) | No | URL-safe public share token (`secrets.token_urlsafe(16)` → 22 chars). Nullable, unique. Generated on demand the first time the owner opens the share menu. Anyone with the token can join the collection via `POST /api/v1/auth/join/` with `share_token`. **Bearer credential — must never appear in any read serializer.** |
| `things_alarm_sent` | BooleanField | No | Mass-upload guard: the thing-count alarm has already emailed the superusers for this collection. Fire-once, so a crossing is reported one time and not on every subsequent add. Inert unless `COLLECTION_THINGS_ALARM` is set. |
| `join_summary_sent_on` | DateField | No | Null | The last day `send_join_summaries` has already told the curators about. NULL = never looked at (the first summary names only yesterday); every pass dates the groups it had nothing to tell. Claimed with a conditional UPDATE before sending, so a second run does nothing and a skipped day is picked up (at most 7 days back). |
| `invites_alarm_sent` | BooleanField | No | The same fire-once flag for the **member**-count alarm (`COLLECTION_INVITES_ALARM`). The two counters are independent: dumping stock and harvesting a mailing list are different abuses. |
| `capacity_unblocked` | BooleanField | No | Superuser override: lifts **both** hard ceilings (`COLLECTION_THINGS_BLOCK` / `COLLECTION_INVITES_BLOCK`) for this collection. One flag because the unblock follows one manual review of the account, the owner and the collection. Ticked in the Django admin — there is no API for it. |
| `things` | ManyToManyField(Thing) | No | Things in this collection. **A thing lives in exactly one collection**: the app creates it in the one it is for and never moves it, and `core/services/single_collection.py` (an `m2m_changed` `pre_add` receiver) raises `ValidationError` for a second membership from either side (`collection.things.add`, `thing.collections.add`). Code that reasons about several collections of a thing (`resolve_request_collection`, `_viewable_collection`) is still there; its tests build that case through the through table (`core.tests.factories.also_in`) |
| `invites` | ManyToManyField(User) | No | Users invited to view this collection |
| `digest_muted` | ManyToManyField(User) | No | Members who have silenced **this** collection's digest. A row means "don't send"; its absence means subscribed, so the on-by-default costs no data and a new member is written nothing. Consulted for `CATEGORY_NEWS` only — a muted group still sends its Cat. 2 activity mail. Reverse: `user.muted_digest_collections`. Table `collection_digest_muted`. |
| `co_owners` | ManyToManyField(User) | No | The admin tier, in **either mode** (2026-09, co-curators in PROPRIETARY), promoted from the collection's own `invites` — never a separate door in (`co_owners ⊆ invites` is enforced at the promote endpoint, not by the schema), and **capped at `Collection.MAX_CO_OWNERS` (10)** by the same endpoint — the abuse bound on a stolen curator credential, not the design intent of owner + 1–2 (a network, where each dinamizador is a co-curator, is what raised it from 5); re-promoting an existing co-curator is idempotent and never hits it, and a collection that somehow holds more than the cap is not broken, it just cannot grow. A co-curator gets the founder's collection-level powers (edit, invite/revoke, broadcast, share link, stats/export, decide member proposals, promote/demote another co-curator) but is deliberately **not** a CASCADE root: deleting a co-curator's account never takes the collection with it, only the founding `owner` does — see `is_curator`. Reverse: `user.co_owned_collections`. Table `collection_co_owners`. |

**In a stall the rental and reservation fields are not used** (`rental_durations`, `rental_weekdays`, `closed_dates`, `reservation_*`, `opening_hours`): the form neither shows nor sends them. A stall that the kind migration took from a collection that also lent things may still hold values from before; nothing reads them.

### Business Rules

1. **ACTIVE by default** - A collection starts with `status="ACTIVE"`.

2. **Owner or co-owner manages all fields** - The owner or a co-owner can update the collection's headline, description, images, and status. Enforced via `IsCollectionCurator` DRF permission. Only the owner may delete the collection (`IsCollectionOwner`, deliberately not curator-widened).

3. **Adding things** - Any **curator** (owner or co-curator) can add — a PROPRIETARY collection's catalogue is run by its curators collectively (2026-09). Beyond that, in COMMUNITY mode any invited member can add their own things. Enforced via `can_add_thing(user_code)`. **In a NETWORK only the dinamizadores add** (`can_add_thing` is `is_curator`; a member who is not one does not), each their own things.

4. **Removing / managing things** - The owner or a co-owner can always delete any thing. In a **PROPRIETARY** collection a curator also *manages* every thing in it — edit / hide / activate / delete, via `Thing.can_manage` + `IsThingManager` — because every one was added by a curator for the group. **COMMUNITY is unchanged**: a member owns what they contribute, and a curator's reach there stops short of editing a member's thing. A thing owner can delete their own. **In a NETWORK every entity runs its own and nobody else's**: `Thing.can_manage` is the thing's owner alone and `managers()` is `[owner]`, so a co-curator edits, hides, activates and decides only what they own (and the founder, who is a dinamizador too, only theirs); the owner of a thing who is a dinamizador of the network deletes it whenever, lent or not (`ThingViewSet._can_delete`), and the founder deletes any, as the owner of the collection does in every mode. The founder has besides the **rescue** (`Collection.can_rescue`, a method of its own and not a widening of `can_manage`): reject a pending request on any thing of the network and hide any thing — never accept, never edit, never touch an accepted loan, and not a recipient of the day-to-day mail. A dinamizador who is demoted, removed or leaves takes their things and their pickup point with them, and cannot while someone holds one of those things.

5. **Owner or co-owner invites/revokes** - Enforced at the view level (`CollectionInviteView` + `require_collection_curator`), which also owns the invitation email/RSVP flow. Revoking a member also strips their `co_owners` row, if any (`co_owners ⊆ invites`). **Any curator may promote or demote a co-curator, in either mode** (2026-09) — only deleting the collection stays owner-only. The founding `owner` is an FK, not an `invites` row, so the promote/demote endpoint structurally cannot demote them. **No door adds the founder to `invites`** (`_join_collection` and `deliver_invitation` treat the owner as already inside; the bulk and recommendation endpoints count their address as already a member) **and none removes them** (`CollectionInviteView.delete` 400 `owner_cannot_be_removed`, `end_membership` raises). The model-level `add_invite()`/`remove_invite()` helpers are test-only and perform no checks (see Methods).

6. **Visible to owner, invites, and anyone when PUBLIC** - `can_view(user_code)` returns True for the owner, for an invited member, or for **anyone** (including an anonymous visitor, `user_code=None`) when `visibility=PUBLIC` and the collection is ACTIVE. INACTIVE collections remain owner-only regardless of visibility.

7. **Public share link is owner-managed** — `share_token` is generated lazily by `POST /api/v1/collections/{code}/share-link/` and revoked by `DELETE` on the same endpoint. The token grants invitee status to anyone who completes the join flow with it; revoke + rotate invalidate previously shared links immediately. The token is excluded from `CollectionSerializer` so it cannot leak via any read endpoint.

8. **Owner content can be multilingual** — on **Thing and Collection**, `headline`, `description` and each `tags` label may hold one text per language as inline JSON: `{"es": "Las cosas de mamá", "ca": "Les coses de mama"}`. There is no per-field schema behind it — the map lives in the existing CharField, and `core.utils.parse_localized` is what makes it a map. It is deliberately **strict**: a value qualifies only when it is a JSON object whose keys are all languages OIUEEI speaks (≥1) and whose values are all non-empty strings. Everything else — prose, a JSON list, an unknown key — renders **verbatim**, which is what keeps the trick invisible to owners who never use it. `resolve_localized(value, lang)` picks the reader's text (`lang` → `es` → the first language written, so nobody ever faces raw JSON); the frontend mirrors both in `src/utils/localized.js`, and the emails resolve through the language already picked for that recipient. Validation is **per language** (`LocalizedHeadlineField` / `LocalizedTextField`): each text gets the visible limit and the same HTML / unsafe-scheme rejection a plain value would — three languages don't buy three times the length. Known rough edges (accepted): the Django admin and the stats CSV show the raw map.

### Methods

- `add_thing(thing_code)` / `remove_thing(thing_code)` / `add_invite(user_code)` / `remove_invite(user_code)` - **Test-only fixture helpers** that mutate the M2Ms directly: no permission or type checks, no Event logging, no emails/RSVPs, and unknown codes are silent no-ops. Production code must go through the views (`ThingViewSet`, `CollectionViewSet`, `CollectionInviteView`), which enforce all of that.
- `is_paused` — Property. Returns `bool(self.pause_message)`. True when the collection has a non-empty `pause_message`.
- `is_owner(user_code)` - Returns True if user is the owner (`self.owner_id == user_code`)
- `is_invited(user_code)` - Returns True if user is in invites (`self.invites.filter(code=user_code).exists()`)
- **`is_curator(user_code)`** — `is_owner(user_code) or any(u.code == user_code for u in self.co_owners.all())`. The single primitive every co-owner permission gate builds on, the way `is_owner` already was for owner-only ones — strictly wider than `is_owner`, never wider than `is_invited` (a co-owner is always also in `invites`). Iterates the prefetched `co_owners` (`.all()`, not `.filter(...).exists()`) — `_optimise_collection_queryset` prefetches it alongside `invites`, and a `.filter()` call would bypass that cache and reopen the N+1 it exists to close.
- **`promote_co_owner(member)`** (2026-09-29) — makes `member` a co-curator unless the set already holds `MAX_CO_OWNERS`, and returns a **`Collection.Promotion`**: `ADDED`, `ALREADY` (they were one — re-promoting is idempotent and never meets the ceiling, since it grows nothing) or `FULL`. **The membership test, the `count()` and the add are one atomic step on a locked row**: `transaction.atomic()` + `Collection.objects.select_for_update().get(pk=self.pk)`, both reads taken *under* the lock, so promotions that run together serialise — the second waits for the first's commit and counts the full set. Before, the endpoint did `count()` then `add()` unlocked and N concurrent promotions all read the same count and all added; the ceiling is the bound on a stolen curator credential, so it has to hold under concurrency. The lock is on the collection rather than a constraint because the rule is about the size of a set. Does **not** check `co_owners ⊆ invites` — `CollectionCoOwnerView` does, before calling. `test_models.py::TestPromoteCoOwner` pins the three answers; the race is `test_booking_row_locks.py::TestTheCoCuratorCeilingIsAtomic`, PostgreSQL only.
- `is_community()` - Returns True if `mode == "COMMUNITY"`
- `is_network()` - Returns True if `mode == "NETWORK"`
- `can_rescue(user_code)` - The founder's rescue of a network (see rule 4): `is_network() and is_owner(user_code)`. Thing-level twin: `Thing.can_rescue`, true when any collection the thing sits in lets the user rescue.
- `owner_member_rows(members=None)` - Every member as **their owner** sees them: `code`, `name`, `email`, plus `age_range` and `postal_code` **only in a COMMUNITY group**. The single definition of that privacy gate, used by both surfaces that answer the question — `CollectionSerializer.get_invites` (the guests page) and `export_service._collection_members` (the collection export). It was two near-identical loops in two files that agreed only because somebody kept them agreeing, and the direction they drift in is the dangerous one: an export is a file, so a gate the API applies and the export forgets is a leak that leaves the building. It builds a row and nothing else — **who may ask is the caller's job** (`_requester_is_owner`, `require_collection_curator`). Pass `members` to reuse a prefetched or ordered queryset.
- `is_public()` - Returns True if `visibility == "PUBLIC"`
- `has_rental_rules()` - Returns True if the collection constrains LEND/RENT dates (`rental_durations`, `rental_weekdays` **or `closed_dates`** set)
- `closed_date_set()` - `closed_dates` (ISO strings) as a `set` of `date` objects; a bad string is skipped defensively.
- **The three rule checks below return a `core.utils.Refusal`, not a bare string**: still a `str` — the same English sentence, so every comparison, log line and existing test reads it unchanged — carrying a machine `code` and the `params` its wording interpolates (`reservation_beyond_horizon` with `{days}`, `rental_length_not_allowed` with `{allowed}`, …). `BookingRequestError` picks both up on its own, the request endpoint answers `{error, code, params}`, and the SPA says the refusal in the member's language (`requestErrors.<code>`); `core` has no gettext catalogue. A new refusal needs a code and a string in all three locales — `core/tests/unit/test_refusal_codes.py` reads the codes out of the source and fails otherwise.
- `rental_violation(start_date, end_date)` - Returns an error string if a LEND/RENT booking `[start, end]` breaks the rules (span not an allowed duration, pickup/return not on an allowed weekday, **or pickup/return on a `closed_dates` day** — only the handoff days matter, an interior closure stops nothing), else `None`. Used by `booking_service.request_date_based_booking` as the server-side backstop.
- `is_reservations_collection()` - `kind == SHED`: the reservations collection **is** the shed. (It was derived from `allowed_thing_types == ["RESERVE_THING"]` before kinds; a stall whose list says so is not one.)
- `path()` - The app's route of the collection, `/{kind}/{code}` — what the emails link to and the 301 from `/collections/{code}` goes to.
- `reservation_violation(start_date, duration_days, today=None)` - The RESERVE_THING backstop, parallel to `rental_violation`: an error string if `duration_days` is outside `1..reservation_max_days`, the **pickup day** is past `today + reservation_horizon_days` (the pickup day, not the exclusive `end_date` — that is what the picker's `maxDate` and `Thing.availability_window` both cap, so judging `end_date` rejected the picker's own last day), or any day of `[start, start+duration)` falls outside `rental_weekdays` (when set) **or on a `closed_dates` day**, else `None`. `today` defaults to `timezone.localdate()`. The **single** backstop `booking_service.request_reservation` relies on (it does no horizon check of its own).
- `active_reservation_count(requester_code, today=None)` - How many of `requester_code`'s RESERVE bookings **in this collection** are `ACCEPTED` and not yet finished (`end_date` after `today`, default `timezone.localdate()`). The backstop for `reservation_max_active_per_member`, checked by `booking_service.request_reservation` inside the same locked block that runs `has_overlap` — but unlike that check it is a courtesy limit, not a locked invariant (see the field's own note above).
- `is_hourly_reservations()` - `reservation_unit == HOUR`. Meaningless (and unchecked) unless the collection is already a reservations collection — callers guard with `is_reservations_collection()` first.
- `day_opening_blocks(day)` - The `HOUR`-unit opening blocks for one date, as a sorted list of `(time, time)` pairs (e.g. `[(10:00, 14:00), (16:00, 20:00)]`). Empty when the collection is closed that weekday — no entry, an empty list, or every pair malformed (skipped defensively, mirroring `closed_date_set`).
- `reservation_hour_violation(start_date, start_time, end_time, today=None)` - The `HOUR`-unit twin of `reservation_violation`: an error string if `[start_time, end_time)` on `start_date` breaks the collection's hourly rules, else `None`. A valid span is either **entirely inside one opening block**, or **exactly the full day** (first block's open to last block's close, any gap included). Duration is checked in minutes against `reservation_min_minutes`/`reservation_max_minutes` — the maximum is a hard cap with **no exception for the full-day form** — a day (or a single-block day) adding up to more minutes than the cap just can't be booked as "the whole day"; the owner raises the cap instead. Anything else (a span crossing a gap without covering the whole day, one landing off a block boundary) is refused rather than clipped. Horizon and `closed_dates` checks mirror `reservation_violation` exactly, in minutes instead of days. **The minimum is also the step** (2026-09-18): times must be whole minutes, and inside a block a reservation must start on the grid running every `reservation_min_minutes` from that block's opening and last a multiple of it — exactly the starts and durations `RequestThingPage` offers, so a request made straight to the API can no longer leave slivers no member can book (the full-day form, defined by the blocks rather than the step, is exempt). **A slot that has already begun today is refused** too ("That time has already begun."), by the deployment's own clock — `TIME_ZONE`, from `DJANGO_TIME_ZONE`, the zone `opening_hours` is read in; a start in the current minute has not begun. Only checked when `today` is the real one (an optional `now` makes it testable). The **single** backstop `booking_service.request_reservation`'s `HOUR` branch relies on.
- **`capacity_ceiling(counter="things")`** — the ceiling in force for that counter, or `0` when there is none (unset threshold, or `capacity_unblocked`). Callers use it as a cheap gate: with no ceiling to judge them, working out how many rows a request would actually add is wasted effort, so the guard costs not one query on a deployment that sets no thresholds.
- **`capacity_violation(counter="things", adding=1)`** — mass-upload ceiling. Returns an error string (like `rental_violation`) if adding `adding` rows to that counter would cross `COLLECTION_THINGS_BLOCK` / `COLLECTION_INVITES_BLOCK`, else `None`. 0/unset = no ceiling (the standalone default); `capacity_unblocked` lifts it. Checked **before** the add and against the **whole batch**, so a bulk import or bulk invite cannot step over the line 100 rows at a time. **`adding` must be what would genuinely land**: a caller counting rows the request will drop anyway — above all an invitee who is *already a member*, and so already inside the count the ceiling is measured against — would refuse a request that adds nobody. The views therefore count newcomers, not CSV lines.
- **`note_capacity(counter="things")`** — the silent tripwire. Emails the superusers **once** per collection when that counter crosses its `*_ALARM` threshold, and tells the owner nothing: a legitimate bulk import must not be interrupted, and someone probing the endpoint must not learn where the line sits. Called **after** a successful add so the count is real; send failures are swallowed, since the ceiling is what stops abuse and the alarm is only the early warning. "Once" holds **under concurrency**: the flag is claimed with a conditional `UPDATE … WHERE flag=False`, so two requests crossing the line together both read `False` but only one gets a matched row back and sends.
- `can_add_thing(user_code)` - Returns True if user is a **curator** (owner or co-curator, any mode), OR if the collection is COMMUNITY and the user is invited
- `can_view(user_code, invited_to=None)` - Returns True if user is owner, OR the collection is PUBLIC and ACTIVE (anonymous-safe — `user_code=None` is accepted), OR the user is invited. INACTIVE collections are owner-only. **`invited_to`** is for a caller judging many collections for one user (`booking_service._readable_collections`): the codes of the collections the user is already known to be invited to, fetched in one query for the whole list, so the last rule reads a set instead of firing an `is_invited` per collection. The rules stay in this method; `None` asks the database. Pinned against the default for every visibility × status × relationship by `test_a_known_membership_set_never_changes_the_answer`.

### Validations

| Field | Validation | Level | Error |
|-------|------------|-------|-------|
| `headline` | Required | Serializer | 400 Bad Request |
| `things` | Thing must exist | View (get_object_or_404) | 404 Not Found |
| `things` | Thing must belong to owner | View | 403 Forbidden |
| `owner` | From authenticated user | View | Always valid |

---

## NetworkPoint

The pickup point of one dinamizador of a **NETWORK** (`core/models/network_point.py`, table `network_points`): the entity they answer for (a cooperative, a neighbourhood association, a shop, a union), not their home. Public with the collection, address included. One row per `(collection, user)` (`one_point_per_curator`); the founder is a dinamizador too. It is optional: with none, a dinamizador lends under the collection's rules, and each condition left empty falls back to the collection's, field by field.

| Field | Type | Description |
|-------|------|-------------|
| `collection` / `user` | FK, CASCADE | The network and the dinamizador. Deleted with either, and by `membership_service` when the dinamizador is demoted or removed (their things go in the same step) |
| `entity_name` | CharField(64) | A proper name, plain text, not localized |
| `address` | CharField(64) | Same width as `Thing.location`, which it replaces in a network |
| `hours_note` | CharField(128) | Free text ("martes y jueves de 18 a 20") |
| `contact` | CharField(64) | Web or phone of the entity; shown as typed, escaped, never made a link |
| `weekdays` | JSONField (list) | One set for pickup **and** return, like `Collection.rental_weekdays` (0=Mon…6=Sun). Empty = the collection's |
| `closed_dates` | JSONField (list) | The entity's own closures, ISO strings cleaned like `Collection.closed_dates` |
| `deposit_policy` / `request_info` / `email_note` | CharField(1024 / 2048 / 2048) | The collection's fields with the collection's widths and serializers (visible limit per language 256 / 512 / 512) |

`display_name` is `entity_name` or, when empty, the dinamizador's bare `name`: the one name the card, the request page, the emails, the broadcast and the future filter use, resolved once on the server.

`Collection.point_for(user_code)` finds a dinamizador's point (`None` outside a network; one read per collection instance). `Collection.rental_rules_for(owner_code)` is the single answer to "which LEND/RENT rules govern a thing of this owner": the point's weekdays when it set any (else the collection's), the **union** of both closures, the collection's lengths. `rental_violation`, `Thing.availability_window` and the thing payload's `rental_weekdays` / `closed_dates` all read it, and `core/tests/integration/test_network_effective_rules.py` pins that the payload and the refusal agree on every day. `Collection.effective_text(field, owner_code)` is the same for the three conditions (the point's own, else the collection's). Horizon and per-member limit are the collection's only. `deposit_policy` has no reader on a member's side today; its effective value is there for when it has one.

---

## Theeeme

The `Theeeme` model represents a colour palette a collection can be painted with. Each theeeme has a name and 6 colours.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `name` | CharField(16) | No | Display name of the theeeme (default: `""`) |
| `color_01` through `color_06` | CharField(32) | **Yes** | HDS colour token names (e.g. "bus", "coat-of-arms-medium-light") |

### Business Rules

1. **Each collection has a theeeme** - A group's pages are painted with the palette its curators chose (`Collection.theeeme`); the viewer's own choice does not exist.
2. **Default theeeme is a random one of those that exist** for a new collection; Bussi (code: `BUU331`) is the fallback if the table is empty.
3. **Protected deletion** - Theeemes cannot be deleted if any collection references them (`on_delete=PROTECT`).
4. **The twelve are the selector.** `TheeemeListView` serves exactly these rows; the app's own palette is the `Braaanding` table below, never a row here.

---

## Braaanding

The app's own palette (`core/models/braaanding.py`, table `braaanding`): what paints everything that is **not** a collection's page — Home, the account pages, the front door, the legal text, the 404 — and every email. It is a table of its own, with **one row** (primary key `OIUEEI`), and deliberately **not** a row of `theeemes`: that table is the selector the collections choose from and the pool a new collection's palette is drawn from at random, so a palette stored there could reach both. No curator can pick it.

| Field | Type | Description |
|-------|------|-------------|
| `code` | CharField(6) | Primary key, always `OIUEEI` |
| `color_01` … `color_06` | CharField(7) | **Hexadecimal** `#RRGGBB` (validated), not HDS token names. The roles are the `Theeeme`'s: 01 primary button, secondary border and links, 02 page and wave, 03 hero, 04 body text, 05 hero text and table headers, 06 primary button text |
| `koro` | CharField(9) | A `KORO_CHOICES` wave type |

Migration `0164` creates the table and seeds the row (`#191919 #F4E5DD #D77452 #191919 #191919 #FAFAFA`, koro `basic`). After that an operator edits it in the Django admin (`BraaandingAdmin`: no add, no delete) and no code changes.

**The admin refuses a palette that fails the contrast the twelve collection palettes meet.** `paletteContrast.test.js` proves those twelve against the HDS colour table, but it cannot see values that live in a database, so the guard goes where they are changed: `Braaanding.clean()` runs `core.services.palette_contrast.contrast_failures`, which asks 4.5:1 for body text on the page (04/02), the primary button's label on its fill (06/01), the hero's text on the hero (05/03), `color_04` on white (the secondary button's text and the content links' fallback) and the front door's warning (`brick-dark`) on the page. The keyboard ring is not checked: it is two bands, black and white, and one of the two reaches 3:1 on any surface. A malformed hex is rejected by the field before any contrast is measured.

**`braaanding()`** returns the palette as `{"color_01": "#…", …, "koro": "basic"}`, remembered **in the process's own memory** for 60 seconds and dropped on every save or delete of the row. It is not in the shared cache (a table) because every page the server hands out reads the palette, and the pages that promise to ask the database nothing would otherwise spend a query on it; the price is that another worker keeps the old colours for up to a minute after an edit in the admin. The suite forgets it before every test (`conftest.py`). With no row the seeded defaults answer, so a page and an email still paint.

---

## FAQ

The `FAQ` model represents a question and answer about a thing. Invited users can ask questions, and only the thing owner can answer or hide them.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `thing` | ForeignKey(Thing) | **Yes** | The thing this FAQ is about |
| `created` | DateTimeField | Auto | Timestamp when FAQ was created |
| `questioner` | ForeignKey(User) | No | User who asked the question. **SET_NULL + `null=True`**: deleting the questioner's account keeps the question (knowledge about the thing) but sheds the attribution (right to erasure) — serialised as `questioner=null`, `questioner_name=""` |
| `question` | CharField(64) | **Yes** | The question text |
| `answer` | CharField(256) | No | The answer text (empty until answered) |
| `is_visible` | BooleanField | No | Whether FAQ is visible (default: True) |

### Business Rules

1. **FK to Thing** - Each FAQ references a thing via ForeignKey.
2. **FK to User** - Questioner tracked via ForeignKey (`SET_NULL` — the Q&A outlives a deleted account, anonymised).
3. **Only invited users can ask** - Must be invited to the collection containing the thing.
4. **A manager cannot ask questions** - the thing owner, or a curator of a PROPRIETARY collection it sits in (`Thing.can_manage`) — they answer, they don't ask. Returns 400 Bad Request.
5. **Only a manager can answer** - The thing owner, or a curator of a PROPRIETARY collection it sits in (`Thing.can_manage`, 2026-09 — a PROPRIETARY space's curators run its FAQs together). 403 for everyone else. In COMMUNITY, still the thing owner alone — a member owns what they contribute.
6. **Default visible** - New FAQs have `is_visible=True`.
7. **Only a manager can change visibility** - Via `/faq/{code}/hide/` or `/faq/{code}/show/` (`Thing.can_manage`); a manager and the questioner also see hidden FAQs.
8. **Email notifications** - A new question notifies **every manager** of the thing (`Thing.managers` — the owner, and a PROPRIETARY collection's curators), so co-curators answer questions shoulder to shoulder with the founder; in COMMUNITY that set is just the thing owner. The questioner is notified on answer/hide, by whoever acted.

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
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID. Used for DB joins/target lookups, **not** in URLs. |
| `token` | CharField(26) | Auto | Unique high-entropy URL token (~134 bits): 26 lowercase alphanumerics via `generate_token()`. Backs every email action link (`action_link()` and the magic link) so links can't be brute-forced the way the 6-char PK (~31 bits) could. |
| `created` | DateTimeField | Auto | Timestamp when RSVP was created |
| `user_code` | ForeignKey(User) | **Yes** | User this RSVP is for. For a booking accept/reject it is the **manager the link was minted to** (owner or co-curator), and it is who signs the decision — see `VerifyLinkView._handle_booking_action` |
| `user_email` | CharField(64) | **Yes** | Email address of the recipient |
| `action` | CharField(20) | No | Action type (default: MAGIC_LINK). Indexed (`db_index=True`) |
| `target_code` | CharField(6) | No | Target object code (booking, collection, etc.). Indexed (`db_index=True`) |
| `context` | JSONField | No | Additional context data for the action (`default=dict`). A join through `/auth/join/` stamps `{"join_source": "SHARE"|"PUBLIC"}` here (the membership is made when the magic link is pressed, not when the address is typed — `VerifyLinkView._join_when_pressed` reads this to decide, and to log the `MEMBER_JOINED` event's `source`), plus `"share_token"` (the token the link was sent with, compared at the click with the collection's current one) for a share link, plus `"thing_code"` when the visitor clicked "Reserve" on one specific thing, so `VerifyLinkView` can land them back on it; `deliver_invitation` uses `{"via": "recommendation"}` to keep an approved recommendation apart from a plain invite in the Event log; a `MAGIC_LINK` of `origin=LOGIN` stores `{"next": "/some/path"}` when the person asked for the link from a page their session had run out on (`RequestLinkView`, only after `core.utils.safe_next_path`; `VerifyLinkView` validates it again and lands them there — `landing: "path"`). Server-side rather than in browser storage because the link is often opened in another browser |

### Action Types

| Action | Description |
|--------|-------------|
| `MAGIC_LINK` | Passwordless authentication (default) |
| `COLLECTION_INVITE` | Accept invitation to view a collection |
| `COLLECTION_REJECT` | Decline invitation to a collection |
| `BOOKING_ACCEPT` | Accept a booking (all thing types) |
| `BOOKING_REJECT` | Reject a booking (all thing types) |
| `ACCOUNT_DELETE` | Right-to-erasure confirmation link (24h expiry, default). GET previews; only an explicit POST commits — and the frontend never auto-commits it (unlike bookings, the person must press the on-page confirm button) |

### Business Rules

1. **One-time use** - RSVPs are deleted after being used.
2. **Per-action expiry** - Link lifetime depends on the action (`RSVP.expiry_hours_for`, the single source of truth for both `is_valid()` and the `cleanup_rsvps` command): magic links `MAGIC_LINK_EXPIRY_HOURS` (24h), booking accept/reject `BOOKING_EXPIRY_HOURS` (72h — the full PENDING window they act on), collection invite/reject `COLLECTION_INVITE_EXPIRY_HOURS` (720h / ~30 days — a pending invitation has no natural deadline). All overridable via settings.
3. **RSVP tokens obfuscate URLs** - Email links use the high-entropy `token` (≈134 bits) — never the 6-char PK or real object codes — so they resist both enumeration and brute force.
4. **RSVP for ALL email communications** - Every email that requires user action uses an RSVP.
5. **Sibling RSVP cleanup** - Collection invite/reject RSVPs are created in pairs. Using either one deletes both to invalidate the other link.

### Methods

- `is_valid()` - Returns True if not expired, using the per-action lifetime from `expiry_hours_for`
- `expiry_hours_for(action)` - Classmethod: hours an RSVP of the given action stays valid (24h magic / 72h booking / 720h invite). Used by both `is_valid()` and `cleanup_rsvps`
- `create_for_booking(action, booking, recipient)` / `create_booking_pair(booking, recipient)` - Factories for booking RSVPs, minted to `recipient` (a `User`: `user_code=recipient`, `user_email=recipient.email`) — one pair per manager of the thing, not one per booking

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
| `deposit_amount` | DecimalField | No | **Snapshot** of `Thing.deposit` at the moment the reservation was made, copied beside `thing_type` for the same reason: an owner editing the listing in June must not rewrite what a March loan said. One snapshot covers the whole handover — every `ThingTransfer` is created with its booking attached, so a journey reaches the agreed amount through `transfer.booking` and there is no second copy to drift. **Nothing renders it yet**: it is the record, and the column has to exist from the first reservation that carries a deposit or the history starts with a hole. |
| `project_note` | CharField(512) | No | **RESERVE_THING only** — the requester's optional few lines about what the space is for ("Explica'ns breument el teu projecte"). Shown to the owner in the reservation-notice email and on their bookings page; blank for every other type and when the requester left it empty. |
| `requester_code` | ForeignKey(User) | **Yes** | User who made the request |
| `requester_email` | CharField(64) | **Yes** | Email of the requester |
| `owner_code` | ForeignKey(User) | **Yes** | Owner of the thing |
| `start_date` | DateField | No | Start date (LEND/RENT/RESERVE — `request_standard_booking` leaves GIFT/SELL bookings dateless) |
| `end_date` | DateField | No | End date (LEND/RENT/RESERVE, same as `start_date`) |
| `start_time` | TimeField | No | **`HOUR`-unit RESERVE_THING only.** `NULL` means "whole day" — true of every LEND/RENT/DAY-unit-RESERVE booking, always, and read that way by `has_overlap` (a whole-day row blocks any hour of that date). A `HOUR`-unit reservation still carries `end_date = start_date + 1` (it never spans midnight); this narrows that one day to a slot within it. |
| `end_time` | TimeField | No | **`HOUR`-unit RESERVE_THING only.** Same `NULL`-means-whole-day rule as `start_time`. |
| `return_reminded_at` | DateTimeField | No | When a manager last pressed "remind them to return it" (`POST /bookings/{code}/remind-return/`). `null` = never. The action is capped at one a day per booking, so this timestamp is what answers "was it already today?" — claimed with a conditional `UPDATE` in the view. LEND/RENT only in practice; every other row stays `null`. |
| `status` | CharField(9) | No | Status: PENDING, ACCEPTED, REJECTED, CANCELLED, EXPIRED. Indexed (`db_index=True`). **RESERVE bookings are born `ACCEPTED`** (auto-confirmed) and never touch the PENDING flow. |

### Thing Type Categories

```python
DATE_BASED_TYPES = ["LEND_THING", "RENT_THING", "RESERVE_THING"]  # Require dates
SINGLE_USE_TYPES = ["GIFT_THING", "SELL_THING"]  # Thing becomes INACTIVE after acceptance
ON_SITE_TYPES = ["RESERVE_THING"]  # Auto-confirmed, no ThingTransfer (nothing changes hands)
RETURNABLE_TYPES = ["LEND_THING", "RENT_THING"]  # Derived: DATE_BASED minus ON_SITE — carried away, so a return is due
```

The kinds of collection group these the same way (`KIND_THING_TYPES` in
`core/models/collection.py`): `STALL` = `SINGLE_USE_TYPES`, `LIBRARY` =
`RETURNABLE_TYPES`, `SHED` = `ON_SITE_TYPES`. A collection holds one kind, and the
verb of a thing in it follows its price (`derive_thing_type`).

**RESERVE_THING** is date-based (it gets the strict-overlap conflict check and
the live availability window) but its create/cancel flow lives in
`booking_service.request_reservation` / `cancel_reservation`: the booking is
created straight to `ACCEPTED`, no RSVP accept/reject pair is minted, no
`ThingTransfer` is written, and both parties are emailed at once. The
accept/reject/`finalize_booking_decision` machinery is never reached for it.
Either the requester **or any curator** of the reservations collection (owner or
co-curator, `Thing.can_manage`, 2026-09) may cancel one that hasn't started yet
(`BookingCancelView` branches on `thing_type`); everyone who didn't cancel is
notified.

### Business Rules

1. **72h expiry** - PENDING bookings expire after `BOOKING_EXPIRY_HOURS` (default 72h).
2. **Date-based (LEND/RENT)**: `start_date` and `end_date` required. No **strictly** overlapping bookings — a booking's return day may be the next booking's pickup day (back-to-back handovers); only a shared *interior* day conflicts. Thing stays ACTIVE.
3. **Single-use (GIFT/SELL)**: No dates. Thing status changes to TAKEN on request, INACTIVE on accept. When `is_endless=True`: multiple simultaneous PENDING bookings allowed, status never TAKEN, thing stays ACTIVE after accept, no ThingTransfer created.
4. **Accept/reject/cancel via services** - `booking_service.accept_booking()`, `reject_booking()`, and `cancel_booking()` handle status changes.
5. **Requester can cancel** - Requesters can cancel their own PENDING bookings. For single-use things, cancellation restores status to ACTIVE. **For a RESERVE reservation, a curator of its collection may also cancel** (2026-09), and the accept/reject decision on a LEND/RENT/GIFT/SELL hold is a curator's too (`BookingActionView`), not only the founder's.

### Methods

- `is_valid()` - Returns True if not expired and PENDING
- `is_date_based()` / `is_single_use()` - Category checks
- **`can_be_return_reminded(today=None)`** - Whether "remind them to return it" may be offered for this booking: ACCEPTED, LEND/RENT, `end_date` strictly before today (**not** on the return day itself — the day-before email covers it — but from the next day), **and no later ACCEPTED booking of the same thing has started** (`start_date` after this one's and not after today): a thing already handed to the next borrower has by definition come back, and "later" is what matters — an earlier loan, returned months ago, must not veto the overdue one. So the action sits on the last loan of each thing, not on every old loan of a busy one. Read by `BookingRemindReturnView` and by `BookingPeriodSerializer.can_remind_return`; the once-a-day cap is not part of it (`return_reminded_at` answers that). When the row comes from `OwnerBookingsView` it carries a `lent_again` annotation that answers the last question without a query; anywhere else the method asks.
- `accept()` / `reject()` / `cancel()` / `expire()` - Status transitions

### Class Methods

- `has_overlap(thing_code, start_date, end_date, exclude_booking_code, *, start_time=None, end_time=None)` - Check for date conflicts using **strict overlap** (`start < e AND s < end`): touching at a boundary (a return day equal to the next pickup day) is allowed; only a shared interior day is a conflict. **`start_time`/`end_time` (keyword-only)** narrow a same-day clash to a time check, for an `HOUR`-unit RESERVE_THING: once the date filter finds bookings sharing that day, the request conflicts only with a row that is itself whole-day (`start_time` `NULL`) or whose own time range strictly overlaps by the identical boundary-touching-is-fine rule. Passing neither keyword is the exact whole-day check every other caller (LEND/RENT, `DAY`-unit RESERVE) still uses.
- `blocking_filter()` - The `Q` every calendar reader uses: PENDING/ACCEPTED, and undated (a GIFT/SELL hold) or `end_date` no earlier than yesterday. Every reader only ever used what is still ahead (the SPA already dropped the rest), so loading the whole history made each read of a thing — anonymous reads of a PUBLIC one included — carry it, and the hourly availability walk scan it once per horizon day. One day of grace for a browser whose today is the server's yesterday
- `get_blocked_periods(thing_code)` - The PENDING/ACCEPTED bookings still shaping the calendar (`blocking_filter`)
- `expire_old_pending()` - Batch expire stale PENDING bookings (used by `manage.py expire_bookings`). For single-use types (GIFT/SELL), also restores the Thing to `ACTIVE` within the same transaction — prevents things getting permanently stuck in `TAKEN` after booking expiry.

---

## Thing

The `Thing` model represents an item in a collection.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `type` | CharField(16) | No | **Put by the server, not chosen**: in a collection it is `derive_thing_type(collection.kind, fee)` — a stall gives or sells, a library lends or rents out, a shed books — and an edit that sets or clears the price moves it (a thing a mixed collection kept from the other family at the 0157 migration keeps its verb). A thing with no collection keeps the pre-kind rules. Type: GIFT_THING, SELL_THING, RENT_THING, LEND_THING, **RESERVE_THING** (an on-site reservation — booked to be used on the owner's premises, never carried away; see BookingPeriod's Thing Type Categories and `Collection.is_reservations_collection`). Column is 16 (longest value is 13) for headroom. |
| `owner` | ForeignKey(User) | **Yes** | Owner of the thing |
| `created` | DateTimeField | Auto | Timestamp when thing was created |
| `headline` | CharField(256) | **Yes** | Title of the thing. **64 per language, 256 stored** — may be an inline `{lang: text}` map (see the multilingual-content note under Collection). |
| `description` | TextField | No | Description of the thing — long-form Markdown (a space, a machine, a piece of history can need a page). **2000 per language**, serializer-enforced; `TextField`, no column cap. |
| `thumbnail` | CharField(255) | No | Storage key for the cover thumbnail |
| `gallery` | JSONField (list) | No | Additional photos beyond the cover `thumbnail`: an ordered list of storage keys. Max 8 (enforced in the serializer). Exposed read-side as `gallery_urls`. Things only (not Collections). Default `[]`. The frontend renders cover + gallery as an "Image pagination" carousel on `ThingPage` **and** inside the collection-grid cards (`ThingLinkbox`) when there is more than one photo. |
| `tags` | JSONField (list) | No | Owner-defined tags assigned to this thing — a subset of its collection's `Collection.tags` vocabulary (validated on create/update). Max 12. Rendered as HDS `Tag`s on the card and detail. Default `[]`. |
| `status` | CharField(8) | No | Status: ACTIVE, TAKEN, INACTIVE |
| `fee` | DecimalField | No | Price/fee. **Required** for SELL/RENT, **optional** for RESERVE (a space may cost something, or nothing). No type rule at all — a price on a gift is merely odd, not a broken promise (contrast `deposit`). |
| `deposit` | DecimalField | No | What the owner asks to be left as security, **LEND/RENT only** (nothing to give back on a gift, a sale or a reservation — the serializers enforce the type rule, since the JSON API and the CSV import are two more doors into the column). **Information, nothing else**: OIUEEI never holds it, never moves it, and has no "returned"/"kept" state — a number shown next to the price, settled between the two people. The model comment says so at length on purpose: the risk here was never technical, it is somebody a year from now asking whether OIUEEI could hold the money, which is a different product and has to be a decision taken on purpose. |
| `availability` | CharField(12) | No | Availability: IMMEDIATE, NEXT_WEEK, END_OF_MONTH, NEXT_MONTH. Offered by the thing form for GIFT/SELL/LEND only (`DETAIL_TYPES` in `frontend/src/constants/things.js`); the column and the serializers accept it on any type. |
| `location` | CharField(64) | No | Free-text location. Widened 32→64 so a RESERVE space can carry a full address ("Planta 1, sala 2, Ateneu del Poblenou"). Form gate: GIFT/SELL/LEND **and RESERVE** (`DETAIL_TYPES`); not enforced server-side. |
| `condition` | CharField(12) | No | Condition: NEW, GOOD, FAIR, USED, WELL_USED, ALMOST_JUNK. Same GIFT/SELL/LEND form gate as `availability` — not enforced server-side. |
| `is_endless` | BooleanField | No | GIFT_THING and SELL_THING only. When True: multiple simultaneous PENDING bookings from different users are allowed, thing status never changes to TAKEN, no ThingTransfer is created on acceptance, thing remains ACTIVE forever (until owner hides or deletes it). Default: False. |
| `deal` | ManyToManyField(User) | No | Users who have reserved |

### Status

| Value | Visibility | Reservation |
|-------|-----------|-------------|
| `ACTIVE` | Visible to owner + invited users | Available for new requests |
| `TAKEN` | Visible to owner + invited users | Pending confirmation, no new requests |
| `INACTIVE` | Visible to owner only | Not available for reservation |

### Methods

- `is_owner(user_code)` - Check if user is the owner (`self.owner_id == user_code`)
- **`can_manage(user_code)`** — the thing owner, **or a curator of a PROPRIETARY collection this thing sits in** (`c.mode == PROPRIETARY and c.is_curator(...)` over `collections.all()`). The thing-level twin of `Collection.is_curator`: in a PROPRIETARY group every thing was added by a curator for the group, so its curators run the whole catalogue — edit / hide / activate / delete any thing, answer any FAQ, decide any booking. COMMUNITY is excluded by the `mode` check. Iterates `.all()` (and `is_curator` iterates `co_owners.all()`) so a view that prefetched `collections__co_owners` pays no extra query. Backs `IsThingManager` and the `can_manage` serializer field. **In a NETWORK it is the thing owner alone** (an entity runs its own things; the founder's reach is the rescue, `can_rescue`).
- **`managers()`** — the *set* `can_manage` answers a boolean for: `[self.owner]` plus the curators (owner + co-curators) of every PROPRIETARY collection the thing is in, deduped by code. Used to fan a notice out to the whole team that runs the thing — the FAQ-question notice and the reservation notices. In a NETWORK it is `[owner]`: the founder is deliberately not a recipient of an entity's day-to-day mail.
- `can_view(user_code)` - Check if user can view. Returns `False` if status is `INACTIVE` (unless user is owner). Otherwise True when the thing sits in an ACTIVE collection that the user is invited to, owns, **or that is PUBLIC** (anonymous-safe — `user_code=None` matches PUBLIC collections only; the membership/ownership terms are dropped for anonymous callers so a `NULL` code can't spuriously match an invitee-less collection).
- `reserve(user_code)` / `release(user_code)` - **Test-only fixture helpers** that add/remove a user on the `deal` M2M directly: no status transitions, no locking, no emails, and unknown codes are silent no-ops. The real reservation flow lives in `core/services/booking_service.py`; production code must not call these.
- `availability_window(horizon_days=90, collection=None)` - For date-based types (LEND/RENT/**RESERVE**) only, returns `{"available_today": bool, "next_available": date|None}` computed from the booking calendar; returns `None` for all other types (the doc used to say LEND/RENT only — RESERVE has had its own branch since `reservation_max_active_per_member` shipped). Prefetch-aware (reuses `self._blocked_periods` when set, else queries `BookingPeriod.get_blocked_periods`) and memoised on the instance. **LEND/RENT applies the governing collection's rental rules (#7)** via `booking_service.compute_availability` — its `rental_weekdays`/`rental_durations` decide which days a pickup could actually start on, so the indicator agrees with the date picker; `collection` names that collection when the caller already knows it (the collection grid passes the collection being rendered, since it doesn't prefetch each thing's `collections`), otherwise it is resolved via `booking_service.resolve_rental_collection` — a thing in two rule-setting collections uses the first one, the same approximation a booking request makes. **RESERVE_THING** resolves its reservations collection instead (`resolve_reservations_collection`) and picks the walk by `reservation_unit`: `DAY` still calls `compute_availability` (weekdays reused as "open days", the collection's own horizon); `HOUR` calls `compute_hourly_availability` (a free gap of at least the collection's own `reservation_min_minutes` in that day's `opening_hours` — fixed 2026-09-18: it compared every gap against a hardcoded 60 until then, unchanged since before `reservation_min_minutes` existed, so a sub-hour minimum collection under-reported its own availability). Backs the `available_today` / `next_available` serializer fields.

### Reverse Relations

- `thing.collections` - Collections containing this thing (Collection.things M2M reverse) — at most one, see `Collection.things`
- `thing.faq_set` - FAQs about this thing (FAQ.thing FK reverse)
- `thing.bookings` - Bookings for this thing (BookingPeriod.thing_code FK reverse)
- `thing.transfers` - Transfer history for this thing (ThingTransfer.thing FK reverse)

---

## ThingTransfer

The `ThingTransfer` model tracks the physical journey of a thing between users (the "Loan Chain"). Each record represents one handoff — from one user to another — with optional link to the booking that triggered it.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `thing` | ForeignKey(Thing) | **Yes** | The thing being transferred |
| `from_user` | ForeignKey(User) | No | User lending/giving the thing. **SET_NULL + `null=True`** — a deleted account keeps its hops in other people's things' journeys but sheds the name (right to erasure; the journey of the deleted user's *own* things still cascades away with the things) |
| `to_user` | ForeignKey(User) | No | User receiving the thing. Same SET_NULL erasure behaviour |
| `booking` | ForeignKey(BookingPeriod) | No | The booking that triggered this transfer (null for manual transfers) |
| `lent_date` | DateField | **Yes** | Date the thing was handed over |
| `returned_date` | DateField | No | Date the thing was returned (null = still with `to_user`) |
| `auto_closed` | BooleanField | No | The return date was **inferred**, not confirmed: `close_transfers` wrote it because the booking's `end_date` passed, and nobody said the thing came back. The journey timeline reads it and renders "Due back on {date}" instead of "Returned on {date}". Default `False`, i.e. a genuine handover. The journey is the product's most human surface ("this item has travelled to 4 homes") and it must not narrate a handover it never witnessed |
| `created` | DateTimeField | Auto | Record creation timestamp |

### Business Rules

1. **Created on booking acceptance** — When `accept_booking()` is called in the booking service, a `ThingTransfer` is automatically created with `from_user` = owner, `to_user` = requester, and `lent_date` = booking's `start_date` (or today for types without dates).
2. **Closed by management command, and marked as a guess** — The `close_transfers` daily command sets `returned_date = today` **and `auto_closed = True`** for transfers linked to ACCEPTED bookings whose `end_date` has passed. Nobody confirms the return; the due date passing is the whole of what is known, so the UI says "due back on" rather than claiming a handover. A transfer already closed with a real date is skipped and keeps `auto_closed = False`.
3. **Booking FK uses SET_NULL** — If a booking is deleted, the transfer record survives (the physical handoff happened regardless). The two user FKs follow the same logic for account deletion: the hop stays, the name goes (`unique_homes` counts the nulls as at most one former home; the serializer returns `""` names and the frontend renders "former member").
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

`InAppNotification.team_booking_notices(queryset=None)` selects the request/reservation notices that are for whoever **manages** a request (`BOOKING_REQUESTED`, `BOOKING_DECIDED`, `RESERVATION_MADE`, and a manager's copies of `RESERVATION_CANCELLED`) — never a copy for the person who asked or held the reservation; the rule and its reason are in its docstring and in `core/views/CLAUDE.md` (Inbox Views).

`InAppNotification.ACTION_NOTICE_TYPES` lists the types that ask their reader to do something; `InAppNotification.informative_notices(queryset=None)` is every other notice that is not in the team group above — the ones the inbox folds into one card and `DELETE /inbox/?group=info` dismisses. `core/tests/unit/test_notice_budget.py` makes each `Type` be decided as asking, team-group or informing, so a new type cannot ship unclassified.

The `InAppNotification` model stores in-app inbox notifications. Every user-action email that targets another party also creates an `InAppNotification` for that party. Rendered by the shared `InboxNotifications` component as dismissible HDS `Notification` banners — on `HomePage` (all of them) and, filtered by `collection_code`, on a collection's own page for the owner **and any invited member** — each viewer sees only their own rows regardless, so this reaches a COMMUNITY member whose own contributed thing got a booking request, not only the collection owner.

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
| `BROADCAST` | Owner sends a broadcast to collection | Each invitee | `owner_name`, `collection_headline`, `message`, `collection_code` |
| `COLLECTION_DELETED` | Owner deletes a collection | Each invitee | `collection_headline`, `owner_name` |
| `COLLECTION_REVOKED` | Owner removes a guest from collection | Removed user | `collection_headline`, `owner_name` |
| `BOOKING_ACCEPTED` | A manager accepts a hold request | Requester | `thing_headline`, `owner_name` (**whoever decided** — the acting curator, not necessarily the thing's owner, since 2026-09-29), `booking_code`, `thing_code`, `collection_code`; plus `start_date`/`end_date` for a dated (LEND/RENT) decision, since 2026-09-29 — the inbox shows them |
| `BOOKING_REJECTED` | A manager rejects a hold request | Requester | `thing_headline`, `owner_name` (whoever decided), `booking_code`, `thing_code`, `collection_code`; plus `start_date`/`end_date` for a dated decision |
| `BOOKING_REQUESTED` | User requests a hold | **Everyone who runs the thing** — every manager (`Thing.managers`: the owner plus a PROPRIETARY collection's curators), **never the requester** (a co-curator who asks is not warned of their own request); the same payload in every copy | `thing_headline`, `requester_name`, `booking_code`, `thing_code`, `collection_code`; plus `start_date`/`end_date` for a dated (LEND/RENT) request, since 2026-09-29 — the inbox shows them |
| `BOOKING_DECIDED` | A manager accepts or rejects a hold (`finalize_booking_decision`, 2026-09-29) | **The rest of the team that runs the thing** — every manager (`Thing.managers`) **except the requester** (their copy is the `BOOKING_ACCEPTED`/`BOOKING_REJECTED` above) **and except whoever decided** (since 2026-10-02: a card saying "You confirmed…" told the reader what they had just pressed; a team of one leaves no record at all) | `thing_headline`, `requester_name` (the **display name** — name, else email — exactly as `BOOKING_REQUESTED` names them: both go only to managers, who already see the address, and a bare name here made one person "a member" in one card and an email in the next, 2026-10-02), `decider_name` (bare name), `accepted` (bool), `booking_code`, `thing_code`, `collection_code`; plus `start_date`/`end_date` for a dated decision. (Rows written before 2026-10-02 may also carry `by_you: true` — the decider's own copy; the inbox still reads them, nothing writes new ones.) A trail for the team, not news — the inbox renders it `info` and reuses the accepted/rejected labels. Carries the same `booking_code` its `BOOKING_REQUESTED` had, under a different type, so `_clear_request_notifications` leaves it standing |
| `FAQ_QUESTION` | User asks a FAQ question | **Every manager** of the thing (`Thing.managers` — the owner, plus a PROPRIETARY collection's curators), minus the asker. Just the owner in COMMUNITY | `thing_headline`, `questioner_name` |
| `FAQ_ANSWERED` | Owner answers a FAQ | Questioner | `thing_headline`, `owner_name` |
| `FAQ_HIDDEN` | Owner hides a FAQ | Questioner | `thing_headline`, `owner_name` |
| `INVITE_REJECTED` | Invitee declines a collection invite | Collection owner | `collection_headline`, `invitee_name` |
| `MEMBER_LEFT` | A member leaves a collection (self-unlink), or a **co-curator** removes one (`CollectionInviteView` DELETE); their things in it are deleted with them. The founder removing someone writes none | Collection owner (only) | `collection_headline`, `member_name` (the bare `name`), `member_email` (only when the member has no name: the founder already reads it in the members list), `collection_code`, `things_deleted` (how many of their things went; absent in rows written before it existed, read as 0), and — only when a co-curator removed them — `removed_by_name` (the co-curator's bare `name`, never the address; the inbox words the notice as "X removed Y from …" and a nameless one reads "A member") |
| `MEMBER_JOINED` | Someone becomes a member of a group, through any door (`_join_collection`, only on a new membership) | **Each curator** (founder + co-curators) except the one joining | `collection_code`, `collection_headline`, `member_name` (the bare `name`), plus `member_email` only when that name is empty (a member who joined by a public link has given just an address; the inbox names them by it, since the team reads it in the members list anyway and nobody else gets this notice). Informative, so it folds into «N updates»; `drop_team_notices_of` leaves it alone (it asks nothing) |
| `THING_REPORTED` | A member reports a thing | Thing owner | `thing_headline`, `thing_code` (no reporter identity — anonymous to the owner) |
| `INVITE_PROPOSED` | A member recommends a guest (`invitation_service.create_proposal`) | **Each curator** (founder + co-curators, never the one recommending), one copy apiece | `collection_headline`, `collection_code`, `proposal_code`, `proposer_name`, `email`, `note`. Every copy goes when anyone decides (`clear_proposal_traces`, matched by `proposal_code`); a copy written before the key existed never matches and stays until dismissed |
| `INVITE_PROPOSAL_APPROVED` | The owner approves that recommendation | The proposer | `collection_headline`, `collection_code`, `email`, `approved: True` |
| `INVITE_PROPOSAL_DECLINED` | The owner declines it | The proposer | `collection_headline`, `collection_code`, `owner_name`, `email` |
| `PROMOTED_CO_OWNER` | The owner promotes a member to co-owner (`CollectionCoOwnerView.post`, first promotion only) | The promoted member | `collection_headline`, `collection_code`, `network: true` only in a NETWORK (the card words a narrower reach) |
| `DEMOTED_CO_OWNER` | The owner demotes a co-owner back to a plain member (`CollectionCoOwnerView.delete`) | The demoted member | `collection_headline`, `collection_code`, and in a NETWORK `things_deleted` (how many of their things went with the role) |
| `THING_HIDDEN` | The founder of a network hides another dinamizador's thing (the rescue; `ThingViewSet.hide`) | The thing's owner (and an email) | `thing_headline`, `founder_name`, `thing_code`, `collection_code`. Not written when the one hiding manages the thing |
| `RESERVATION_MADE` | A member auto-confirms an on-site reservation (RESERVE_THING) | **Every curator** of the reservations collection (owner + co-curators), deduped, minus the requester if they are one — a notice, not a question | `thing_headline`, `requester_name`, `start_date`, `end_date`, `start_time`, `end_time` (both `null` for a `DAY`-unit reservation), `booking_code`, `thing_code`, `collection_code` |
| `RESERVATION_CANCELLED` | Requester or any curator cancels a not-yet-started reservation | Everyone bar whoever cancelled: the member (if a curator cancelled) **and every other curator** — plus, since 2026-09-29, whoever cancelled, whose own `by_you` copy reads in the first person | `thing_headline`, `other_name` (always whoever actually cancelled), `start_date`, `end_date`, `start_time`, `end_time` (both `null` for a `DAY`-unit reservation), `thing_code`, `cancelled_by_owner` (true only on the member's copy); the canceller's own copy adds `by_you: true` and `member_name` (the requester's bare name) when the reservation was somebody else's |

**The three above used to go unrendered.** `InboxNotifications` had no `case` for any of them, so all three fell through to the `BROADCAST` default and drew a card reading `" — {headline}"` with an empty body — worst of all the decline, whose payload carries `owner_name` and so rendered as a blank message *from the owner*. Approval also used to reuse `INVITE_PROPOSED` with `approved: True`, one type addressing two audiences with opposite meanings; it now has its own type, and the inbox still reads the legacy flag so rows written before the split render correctly. Any new `Type` added here owes a matching `case` in `notificationLabel`/`notificationBody` — the `default` branch is broadcast copy, not a safe fallback.

The booking payloads carry **`thing_code` + `collection_code`** for the same reason (the banner links the thing, where a hold is actually answered) and so a collection's page can filter its own; `BOOKING_REQUESTED` additionally carries **`booking_code`**, which is what lets the decision clear it (see below). `collection_code` is `""` when the thing sits in no active collection — a thing can live in several, so it records the one the request was made through (`booking_service.resolve_request_collection`).

### Business Rules

1. **One notification per action** — created atomically alongside the corresponding email. **A PROPRIETARY collection's team is the exception (2026-09): one per manager.** `BOOKING_REQUESTED`, `RESERVATION_MADE`, `RESERVATION_CANCELLED`, `FAQ_QUESTION` and `BOOKING_DECIDED` fan out to every manager of the thing (`Thing.managers`) so the people who run a space all hear it — deduped, and never to whoever performed the action (`BOOKING_DECIDED` included: since 2026-10-02 whoever decided gets none — it used to include them, flagged `by_you`).
2. **Dismissal via DELETE** — `DELETE /api/v1/inbox/{code}/` removes the record (one-time dismiss).
3. **A settled request clears its own notification** — `BOOKING_REQUESTED` asks the team to decide; accept, reject and requester-cancel all answer that question, and `booking_service._clear_request_notifications()` deletes **every copy** (matched by `payload__booking_code`, not scoped to a user — the co-curators' copies go whoever settled it) so no inbox asks twice. Rows written before the key existed don't match and stay until dismissed by hand.
4. **Ordered newest-first** — Default ordering is `-created`.
5. **Cascades on user delete** — `on_delete=CASCADE` on the `user` FK.

### Reverse Relations

- `user.inbox_notifications` — All in-app notifications for a user (InAppNotification.user FK reverse)

---


---

## Report

A `Report` is a logged-in member's flag on a `Thing` (content moderation, #12). It is the platform's moderation log — **not** shown to the reported owner, who only receives an anonymous `THING_REPORTED` notification.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `thing` | ForeignKey(Thing) | No | The reported thing. `SET_NULL` + `null=True`, reverse `reports` — the log row survives the thing being deleted |
| `thing_headline` | CharField(256) | No | Snapshot of the thing's headline at report time, so the log stays readable after the thing is gone. Tracks `Thing.headline`'s width — a localized headline is longer than the 64 an owner sees, and a narrower snapshot would make reporting the thing fail outright on PostgreSQL |
| `reporter` | ForeignKey(User) | No | Who reported it. `SET_NULL` + `null=True`, reverse `reports_made`. **Server-side only — never exposed to the owner or any read endpoint** |
| `created` | DateTimeField | Auto | Timestamp (`db_index=True`) — lets the platform count reports over a period |

### Business Rules

1. **Authenticated only** — reporting requires login (`ThingReportView` is `IsAuthenticated`). There are no anonymous reports; the reporter is recorded purely as a moderation trail.
2. **Anonymous to the owner** — the owner learns only *that* a listing was reported (and which one, via the `THING_REPORTED` notification + email), never by whom. `reporter` is excluded from every read path.
3. **One report per member+thing** — `UniqueConstraint(thing, reporter)` (`unique_report_per_reporter_thing`); the view uses `get_or_create`, so re-reporting is idempotent and doesn't re-notify/spam the owner.
4. **Can't report your own listing** — the view returns 400 for the thing owner.
5. **Must be viewable** — the reporter must pass `thing.can_view()` (403 otherwise).
6. **Moderation log** — surfaced in Django admin (`ReportAdmin`, read-only) with `created` filtering. Ordered newest-first; table `reports`.

### Reverse Relations

- `thing.reports` — reports filed against a thing (`Report.thing` FK reverse)
- `user.reports_made` — reports a user has filed (`Report.reporter` FK reverse)

---

## Event

An `Event` is one row in an **append-only, first-party analytics log**. The domain tables can't answer historical questions on their own: Collections and Things are **hard-deleted**, `Collection.invites` has no join timestamp, and there is no session concept. `Event` records the handful of actions we care about so accumulated counts and funnels survive those deletes. Read only by whatever reporting the deployment runs over it — never exposed to any read endpoint (DESIGN §9).

**The one exception: your own rows, in your own data export.** `GET /api/v1/auth/export/` carries the `Event` rows whose `actor_code` is the requester's, and nobody else's. DESIGN §9 protects this log as an *aggregate product surface* — no endpoint that lets anyone read how other people behave — while GDPR arts. 15/20 still cover one person's own rows, which are observed data about them. Narrowly scoped and worth writing down here rather than leaving as an apparent contradiction between the rule and the export.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `kind` | CharField(18) | **Yes** | One of the `Kind` choices (see below) |
| `actor_code` | CharField(6) | No | **Snapshot** of the acting user's code (not an FK). Default `""` |
| `collection_code` | CharField(6) | No | **Snapshot** of the relevant collection's code. Default `""` |
| `thing_code` | CharField(6) | No | **Snapshot** of the relevant thing's code. Default `""` |
| `thing_type` | CharField(17) | No | **Snapshot** of the thing's type (for THING_/HOLD_ events). Default `""` |
| `source` | CharField(14) | No | **`MEMBER_JOINED` only** — which of OIUEEI's six doors the member came through: `INVITE`, `RECOMMENDATION`, `SHARE`, `PUBLIC`, `ONBOARDING`. Blank on every other kind, and on rows written before the field existed (a report over this column needs an explicit "unrecorded" bucket rather than folding them into a door they may not belong to). Added because every acquisition path was counted as the same undifferentiated join, so "which of these is worth keeping?" — the question that decides whether a door earns its place — had no answer in the data. An approved recommendation is delivered as an ordinary invitation on purpose (one code path, so neither can rot), so `deliver_invitation` marks its accept RSVP `context={"via": "recommendation"}` and `_join_collection` reads that back; it is the only thing keeping the two apart |
| `created` | DateTimeField | Auto | `default=timezone.now` (**not** `auto_now_add`, so `backfill_events` can stamp historical timestamps) |

### Kinds

`USER_JOINED`, `COLLECTION_CREATED`, `COLLECTION_DELETED`, `THING_ADDED`, `THING_REMOVED`, `MEMBER_JOINED` (carrying a `source`, see above), `MEMBER_LEFT`, `FAQ_ASKED`, `HOLD_REQUESTED`, `HOLD_ACCEPTED`. Guest→creator conversion is **derived** (first `MEMBER_JOINED` vs first `COLLECTION_CREATED` per actor), not a stored kind.

### Business Rules

1. **Snapshots, not FKs** — every reference is a plain code string so the row survives the referenced object being hard-deleted. That's the whole point of the log.
2. **Written alongside the existing side-effects** — instrumentation is a one-liner (`Event.log(...)`) placed next to the notification/email each action already fires, in `core/views/` and `core/services/`. **Deletions are the exception**: `COLLECTION_DELETED`, `THING_REMOVED` (one per thing deleted with its collection) and one `MEMBER_LEFT` per membership of a deleted account are written by `post_delete` / `pre_delete` receivers in `core/services/deletion_events.py`, inside the delete's own transaction, so the admin, an account erasure, the retention purge and a `QuerySet.delete()` log exactly like the API. The actor is the `deleting_as(user)` block the views and `delete_account` wrap their delete in, and blank outside one; `deletion_events_suppressed()` (the demo's `--reset`) records nothing. A view never calls `Event.log` for a delete. `HOLD_ACCEPTED` and `HOLD_REQUESTED` are both anchored to the **requester** so a guest's request→accept funnel and the success rate are plain counts by kind.
3. **`THING_REMOVED` = hard delete only** — `THING_REMOVED` is logged only when a thing is deleted, keeping `THING_ADDED`/`THING_REMOVED` symmetric (net = live things).
4. **Backfill is a command, not a migration** — `backfill_events` seeds history from existing users/collections/things/bookings at their original timestamps; idempotent (skips when an equal event already exists).

### Methods

- `Event.log(kind, *, actor=None, collection=None, thing=None, thing_type=None, created=None, source="")` — the instrumentation one-liner. Accepts model instances **or** raw code strings (use strings when the object is about to be / has just been deleted). `thing_type` defaults to `thing.type` when a Thing instance is passed. Meta: `db_table="events"`, ordered `-created`, index on `(kind, created)`.

---

## DailyActivity

A `DailyActivity` is one `(user, date)` row per user per day they were active — the smallest first-party record that answers returns/retention, since the app keeps no session concept.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `user` | ForeignKey(User) | **Yes** | The active user (`on_delete=CASCADE`, reverse `daily_activity`) |
| `date` | DateField | **Yes** | The day of activity (local date) |

### Business Rules

1. **At most one row per user per day** — `UniqueConstraint(user, date)` (`unique_daily_activity_per_day`). Written by `core.middleware.DailyActivityMiddleware` **after** the view resolves the DRF-authenticated user, gated by a DatabaseCache key (`da:{user}:{date}`, ~24h TTL) so it costs one DB write per user per day, not per request.
2. **Best-effort** — the middleware swallows any write error: activity bookkeeping must never turn a good response into a 500.
3. **Retention questions** — this is the table that answers WAU/MAU per role, returners (active ≥2 days), and "guests who never came back after their first visit", for whatever reporting the deployment runs. Index on `date` for the range scans.

### Reverse Relations

- `user.daily_activity` — a user's activity days (`DailyActivity.user` FK reverse)

---

## DeviceDay

A `DeviceDay` is a daily count, per kind of device, of signed-in people and of collection/thing saves. It answers one question — how much of the use, above all how many saves, comes from a phone — and holds nobody to do it.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key, 6-character alphanumeric ID |
| `date` | DateField | **Yes** | The day (local date) |
| `device` | CharField(8) | **Yes** | `MOBILE` or `OTHER` (a tablet is `OTHER`: an iPad presents itself as a desktop Safari, so a third group would not be reliable) |
| `metric` | CharField(16) | **Yes** | `PEOPLE` (signed-in people per day and device) or `FORM_SAVES` (every successful create/edit of a collection or a thing) |
| `count` | PositiveIntegerField | Auto | Default 0; raised in the database with `F("count") + 1`, never read-add-save |

### Business Rules

1. **No user, no `User-Agent`** — there is no column that could hold either, so the table is not personal data. It is left out of `purge_expired_data`, the data export and account erasure, and has **no retention period**.
2. **One row per `(date, device, metric)`** — `UniqueConstraint` (`unique_device_day_metric`), index on `date`.
3. **Written by `DailyActivityMiddleware`**, after the view, from headers the request already carries (`core.device.device_class`: `Sec-CH-UA-Mobile` when sent, else a `Mobi` in the `User-Agent`; no header at all counts nothing). `PEOPLE` is gated by a cache key `dd:{user}:{date}:{device}` of its own, so it does not depend on the `da:` gate of `DailyActivity` — one person on a phone and a laptop the same day counts once in each. `FORM_SAVES` counts `POST` to `collection-list`/`thing-list` and `PATCH`/`PUT` to `collection-detail`/`thing-detail` that answer 200/201, without deduplicating.
4. **Best-effort** — a failure is swallowed and never turns a good response into a 500, nor loses the `DailyActivity` row.
5. **Read** with `python manage.py device_share [--weeks N] [--csv]`; its admin is read-only.

---

## InvitationProposal

A member asking the owner to invite somebody. Members could not bring anyone in
at all before this: every new person cost an owner action, so a group grew only
as fast as one person worked at it. But the owner is not a bottleneck to route
around — the group may be closed, or run on rules of admission the product knows
nothing about — so **the member proposes and the owner decides**.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key |
| `collection` | ForeignKey(Collection) | **Yes** | CASCADE, reverse `invitation_proposals` |
| `proposer` | ForeignKey(User) | **Yes** | The member. CASCADE — a departed account's pending suggestions go with it, so an owner never answers a request from somebody who no longer exists |
| `email` | CharField(64) | **Yes** | The proposed address. **No `User` row is created for it and no email is sent to it while the proposal is pending** |
| `note` | CharField(256) | No | The proposer's word to the owner ("my downstairs neighbour", "he's paid the subs"). What makes the approval a decision rather than a guess. **Owner-only — never travels to the person it describes** |
| `status` | CharField(8) | No | PENDING (default) / APPROVED / REJECTED, indexed |
| `created` / `resolved` | DateTimeField | Auto / No | |

### Business Rules

1. **Nobody is contacted before the owner says yes.** If the answer is no, the person suggested never learns they were suggested — no account, no email. Pinned by `test_invitation_proposals.py`.
2. **One live proposal per address per collection** (`unique_pending_proposal_per_email`, a partial constraint on PENDING) — the owner must not be asked the same question twice, nor able to approve it twice.
3. **Expiry mirrors an invitation** (~30 days, `COLLECTION_INVITE_EXPIRY_HOURS`) and lapses silently: nobody was told it existed.
4. **Approval reuses the ordinary invitation path** (`invitation_service.deliver_invitation`), so an approved proposal is indistinguishable from an owner's own invite — and is charged to the **owner's** `INVITE_EMAILS_PER_DAY`, since it leaves their group under their sending domain. The invitation email names the proposer (bare `name`, never the email fallback — this message goes to a third party).
5. **Rejection tells the proposer, with no reason** — silence would leave them waiting and asking again; a reason would put words in the owner's mouth about rules that are not the product's business.
6. **Two owner routes, one decision**: `POST /api/v1/proposals/{code}/{approve|reject}/` in-app, or the email links (RSVP `PROPOSAL_APPROVE`/`PROPOSAL_REJECT`, **POST-only** so a link scanner cannot invite a stranger). Either consumes both links, and both apply the same approval guard (`invitation_service.proposal_approval_blocked`) — the emailed link is not a way past the owner's daily invitation quota or the collection's member ceiling.
7. **`Collection.allow_member_proposals` gates the whole thing** — off means the owner is not asked at all (403).

---

## InvitationRecord

That an address was invited by email to a founder's group, and what became of it. It makes the invitation email's promise true — whoever invited you cannot do it again by email for a year, whether you declined or did nothing — and it is what `invitation_acceptance()` measures.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | CharField(6) | Auto | Primary key |
| `founder` | ForeignKey(User) | **Yes** | The owner of the collection the invitation was for. CASCADE, reverse `invitation_records_as_founder` |
| `inviter` | ForeignKey(User) | **Yes** | The account the daily quota was spent on (a co-curator who invited, or the founder — also for an approved recommendation). CASCADE, reverse `invitation_records_as_inviter` |
| `address_hash` | CharField(64) | **Yes** | `address_hash(email)` in `core/models/invitation_record.py`: `salted_hmac("core.invitation_record", email.lower(), algorithm="sha256")`. **Never the address**: the row outlives the invited person's `User` (the 60-day purge of unanswered guests). Rotating `SECRET_KEY` makes every record forget its address, and with it the blocks; accepted |
| `state` | CharField(8) | No | `SENT` (default), `ACCEPTED`, `DECLINED` |
| `sent_at` / `resolved_at` | DateTimeField | Auto / No | When it went out (reset by a new invitation after an `ACCEPTED`), and when it was answered |

`UniqueConstraint(founder, address_hash)`; index on `(inviter, sent_at)`.

### Business Rules

1. **Blocked** when a row with the address's hash is `SENT` or `DECLINED` and its `founder` is the collection's owner **or** its `inviter` is whoever invites now (`invitation_service.invitation_blocked`). Not answering counts from the first send. `ACCEPTED` blocks nothing.
2. **Written** by `deliver_invitation` and the bulk invite when an invitation goes out (`SENT`, and an `ACCEPTED` row goes back to `SENT`); moved to `ACCEPTED` by `_join_collection` on a genuine join through any door and to `DECLINED` by the decline link.
3. **Only the outgoing email is blocked.** Joining by the share link or a public collection never reads it.
4. **Kept `INVITE_RECORD_MONTHS` (12)** from `sent_at`, a constant that `purge_expired_data` enforces. Migration 0170 seeds a `SENT` row for every invitation pending at the time.

---

## CalendarExportMark (leaving the schema)

The model and its table are gone: migration `0159_forget_calendar_export_marks` took the model out of the state and emptied the table, and `0162_drop_calendar_export_marks` dropped it a release later.

Why it existed: `calendar_export_service` used to watermark every reservation it had delivered so a curator's calendar **CSV** download only ever carried what was new. The CSV format was the bug — Google Calendar's CSV importer reads dates in the *importing account's* locale, so `10/01/2026` (meant as 1 October) landed as 10 January for a day/month account. The export became **iCalendar (.ics)**, whose per-booking UID (`{booking.code}@oiueei`) makes a re-import idempotent on the calendar app's own side, which retired the watermark: `build_calendar_export` ships every upcoming reservation on every download. Pinned in `core/tests/unit/test_migration_forget_calendar_export_marks.py` (the real migration through `MigrationExecutor`: the model leaves the state, the table stays and is empty, the step reverses, and deleting a collection and a booking still works).
