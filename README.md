## What is OIUEEI?

An open source web application (EUPL-1.2 — strong copyleft, and its reciprocity reaches running a modified copy as a network service; every line of the product public and auditable; self-hosting in production is allowed) for people to share their belongings with friends and others around. Users open a stall (to give away or sell), a library of things (to lend or rent out) or a shed (to book by the day or by the hour) and share it with friends, who can then ask for things or ask questions.

No ads, no tracking of any kind, no third-party code running in your browser — and no cookie banner, because there is nothing to consent to. Each of those claims comes with a way to check it: **[→ Privacy](#privacy)**.

## Authorship & Development

OIUEEI is designed and led by Carlos Alberto, a designer, and co-written with [Claude Code](https://claude.ai/code), Anthropic's command-line coding assistant. UI and UX design decisions, product scope, tone and voice, and the choice to build on HDS are Carlos Alberto's; Claude carries a large share of the Django, DRF, and React implementation under direction. Every commit involves Claude, is reviewed before it ships, and names the tool and the model that wrote it in an `AI-assistant:` trailer — the contribution history is fully transparent. Commits up to 2026-09-22 carry a `Co-Authored-By:` trailer for this instead; that history is kept as it was rather than rewritten, and the trailer changed because a model cannot hold copyright and should not be recorded as an author.

## Try it (and tell me what breaks)

OIUEEI is in **alpha**: nothing is finished, nothing is at 100%, and you'll find rough edges. That's exactly why your hands on it would help.

**To see a populated OIUEEI in about a minute**, run it locally and sign in as one of the seeded people — no signup, no email server:

```bash
python manage.py seed_demo          # Lala, Lele, Lili, Lolo, Lulu and their collections
python manage.py runserver          # then, in frontend/: npm run dev
```

Open `http://localhost:3000/login`, enter **`lala@your-domain.test`**, and the magic link is **printed in the terminal running Django** (development uses the console email backend). Click it and you are in, with collections, things and every sharing mode already populated.

What I'm looking for is honest feedback from people willing to poke at it: things that confuse you, flows that break, words that don't make sense, design decisions you'd push back on. If something annoys you, that's signal.

**[→ Tell me what you found](https://github.com/oiueei/standalone/issues)** (open an issue)

## Tech Stack

- **Backend**: Django 5.x + Django REST Framework
- **Frontend**: React (same repo, work in progress)
- **Auth**: Magic link authentication (passwordless for users, password enabled for admin access)
- **Database**: SQLite (dev), PostgreSQL (prod via `dj-database-url`)
- **Deployment**: Heroku (Procfile + `.python-version` included)
- **Static files**: WhiteNoise
- **PWA**: installable web app manifest + icons ("Add to Home Screen"); no service worker yet
- **Scheduled tasks**: one daily Heroku Scheduler job chains `expire_bookings`, `cleanup_rsvps`, `close_transfers`, `send_reminders`, `send_join_summaries`, `send_digests` and `purge_expired_data --commit` (see [HEROKU.md](HEROKU.md))
- **Retention**: `purge_expired_data` enforces a period per category of data (`RETENTION_*` settings; 0 = keep indefinitely). Dry-run by default

## UI & Design System

OIUEEI's user interface is built on top of the [Helsinki Design System (HDS)](https://hds.hel.fi/), an open-source design system created by the City of Helsinki. OIUEEI consumes HDS at multiple levels:

- **React components** — via [`hds-react`](https://github.com/City-of-Helsinki/helsinki-design-system/tree/master/packages/react)
- **Design tokens** — colours, spacing, typography, and breakpoints from [`hds-design-tokens`](https://github.com/City-of-Helsinki/helsinki-design-system/tree/master/packages/design-tokens)
- **Core styles** — base CSS from [`hds-core`](https://github.com/City-of-Helsinki/helsinki-design-system/tree/master/packages/core)

### What I customise

HDS is designed for City of Helsinki services, so I adapt it to fit OIUEEI's context:

| Layer | HDS baseline | OIUEEI adaptation |
|---|---|---|
| Brand colours | Helsinki blue/black palette | Custom palette reflecting OIUEEI identity |
| Typography | HDS type scale | Same scale, different primary typeface (Curiosa) |
| Components | Used as-is where possible | Extended or wrapped when sharing-specific UX is needed |
| Layout & spacing | HDS grid and spacing tokens | Followed as-is |
| Icons | HDS icon set | Supplemented with domain-specific icons |

Our goal is to **stay as close to upstream HDS as possible** to benefit from accessibility audits, updates, and community contributions, while making only the changes strictly necessary for our use case.

### Why HDS?

- **Accessibility built-in** — All HDS components are WCAG 2.1 AA audited.
- **Open source (MIT)** — Fully compatible with OIUEEI's licence (EUPL-1.2).
- **Production-proven** — Used across hundreds of City of Helsinki digital services.
- **React-native support** — Aligns with our tech stack (React + Vite).

## Project Structure

```
config/
  settings/
    base.py           # Shared settings (CREATOR_POLICY / DEPLOYMENT_URLCONFS defaults)
    development.py    # Dev overrides (SQLite, DEBUG=True)
    production.py     # Prod overrides (PostgreSQL, security headers)
  urls.py             # Root URL config (admin at /oiueei-admin/; mounts DEPLOYMENT_URLCONFS before the SPA catch-all)
  wsgi.py             # WSGI entry point (defaults to production)
core/
  models/             # User, Collection, Thing, FAQ, Theeeme, Braaanding, RSVP, BookingPeriod, Transfer, Notification, Report, Event / DailyActivity / DeviceDay (first-party analytics)
  views/              # Auth, collections, things, bookings, FAQ, users
  serializers/        # DRF serializers per model
  services/           # Business logic layer
    email_service.py      # All email composition and sending (categorised opt-out pipeline)
    booking_service.py    # Accept/reject booking logic (transaction.atomic)
    creator_policy.py     # CREATOR_POLICY extension point — who may create what (OpenCreatorPolicy: no gate, the standalone default)
    export_service.py     # GDPR data export (per user and per collection)
    storage.py            # S3-compatible object storage (direct-upload tickets)
  checks.py           # System checks (CREATOR_POLICY importable + instantiable, etc.)
  permissions.py      # Custom DRF permissions (IsThingOwner, IsThingManager, IsCollectionOwner, IsCollectionCurator)
  validators.py       # Input validation (image IDs, headlines, localized-text caps)
  utils.py            # ID generation, client IP, asset URLs, localized-text parsing, coded refusals (Refusal)
  pagination.py       # StandardResultsPagination (max 100)
  management/
    commands/
      expire_bookings.py       # Batch expire stale PENDING bookings
      cleanup_rsvps.py         # Delete expired RSVPs (24h+)
      close_transfers.py       # Close overdue loan transfers
      send_reminders.py        # Daily booking/delivery reminders
      send_join_summaries.py   # Daily email to each group's curators: who joined since the last summary
      send_digests.py          # Weekly/monthly digest emails
      device_share.py          # Weekly share of mobile among people and form saves (reads DeviceDay)
      send_test_emails.py      # One sample of every email, sent to one address you choose
      purge_expired_data.py    # Retention sweep (GDPR art. 5.1.e) — dry-run unless --commit
      cleanup_orphan_images.py # Delete stored images no row references
      set_bucket_cors.py       # Write the object store's CORS rules (uploads fail without them)
      add_totp_device.py       # Bootstrap / replace the admin 2FA device
      backfill_events.py       # One-off: seed the Event log from existing rows
      seed_demo.py             # Populate demo data (idempotent; --lang=en|es|ca)
      seed_data/
        common.py         # structure + localized tag constants (non-translatable)
        en.py             # English demo content
        es.py             # Spanish demo content
        ca.py             # Catalan demo content
  tests/
    unit/             # Model, serializer, validator, security tests
    integration/      # View and booking integration tests
    scenarios/        # End-to-end user flow tests
```

## Data Models

| Model | Purpose |
|-------|---------|
| **User** | Custom user with `code` as PK (6-char alphanumeric). Magic link auth, no passwords. `notify_activity` and `notify_news` (both default on) control Cat. 2 / Cat. 3 email delivery (magic links and invitations are always sent). News is narrowed per group by `Collection.digest_muted`, so silencing one noisy collection never costs you the transactional mail — which is what keeps an on-by-default news flag off the DESIGN §6 dark-pattern list. Optional profile extras: `about` (free Markdown bio); `photo` (profile photo, stored as an object key and exposed as `photo_url`); `age_range` (birth-year generation) and `postal_code`, the optional demographics — shared per-member only with the owner of a COMMUNITY collection the user is in, and otherwise only in aggregate; and `language`, the language this user's own email is written in (`""` = inherit — the collection's language, else the deployment default). All four default to `""` |
| **Collection** | Lists of things owned by a user, each **one kind, fixed when it is created**: a **stall** (`STALL`: to give away or sell), a **library** (`LIBRARY`: to lend or rent out) or a **shed** (`SHED`: to book by the day or by the hour — always PROPRIETARY, the one that takes `RESERVE_THING`). A collection lives at `/stall/{code}`, `/library/{code}` or `/shed/{code}`; the address from before kinds, `/collections/{code}`, answers with a 301 to it (the query string and the rest of the path kept). `allowed_thing_types` is the verbs *within* the kind (never empty): both of its verbs, or — in a COMMUNITY stall or library whose members may not set a price — only the free one. Shared via M2M `invites`. FK to `Theeeme`. `allow_member_proposals` (default **off** for new collections since 2026-10-02; existing ones kept theirs) decides whether members may recommend new guests — a curator still approves every one, and nothing reaches the proposed person before that. Mode: PROPRIETARY (its curators add things), COMMUNITY (invited members can add their own too) or, for a library only, NETWORK (several entities, each lending its own things from a pickup point of its own: the dinamizadores — founder and co-curators — add and decide only what is theirs, and the founder can reject a pending request or hide a thing as a rescue) — mode decides WHO may add a thing, never which types, and a library's NETWORK mode is fixed when it is created. A curator may promote members to **co-curator** (`co_owners`, a subset of `invites`, capped at `MAX_CO_OWNERS` = 10 by the promote endpoint) in either mode — the founder's reach (edit, invite/revoke, broadcast, share link, stats/export, decide member proposals, and — in a PROPRIETARY collection — run the whole catalogue, FAQs and bookings: `Thing.can_manage`) without becoming the CASCADE-delete root. Any curator promotes or demotes another; **only the owner deletes the collection**, and the founder (an FK, not an `invites` row) can never be demoted. `share_token` is a 22-char URL-safe bearer credential generated on demand for the public `/share/{token}` link — never exposed in any read serializer. `tags` is an owner-defined free-text tag vocabulary (max 12) that the collection's things can be tagged with; removing a tag here cascade-strips it from those things. `headline`/`description`/each `tags` label may hold one text per language as inline `{lang: text}` JSON (each reader resolves their own); `description` is long-form Markdown (2000 characters per language). `closed_dates` is an owner-listed set of holiday/closure days on which no LEND/RENT pickup or return can fall and a reservation cannot span; `home_page` is an optional URL for the group. A **shed** (the reservations collection: `kind` is `SHED`, `allowed_thing_types` is `["RESERVE_THING"]`, always PROPRIETARY) additionally sets `reservation_horizon_days` (1–365, default 90: how far ahead its space can be booked) and `reservation_max_active_per_member` (1–50, default 10: how many active reservations one member may hold in the collection), and is booked in one **unit**, chosen per collection — `reservation_unit` is `DAY` (the default) or `HOUR`, and the two never mix inside a collection (LEND and RENT are always by the day). Under `DAY`, `reservation_max_days` (1–7, default 1) is the longest a reservation may run, and `rental_weekdays` are the days it is open. Under `HOUR`, a reservation is one slot within a single day: `opening_hours` is a JSON object keyed by weekday (`"0"` Monday … `"6"` Sunday) holding up to 4 `["HH:MM","HH:MM"]` blocks per day (`{}`, the default, means closed every day; it replaces `rental_weekdays` as the open days), `reservation_min_minutes` (1–720, default 60) is the shortest reservation and also the slot size (starts fall on that step from each block's opening, and a duration is a multiple of it), and `reservation_max_minutes` (1–720, default 180) is the longest, with no exception for a "whole day" span; the minimum may not exceed the maximum. Fields of the unit not in use are ignored. |
| **Thing** | Items in collections. Types: GIFT_THING, SELL_THING, RENT_THING, LEND_THING, RESERVE_THING (an on-site reservation — booked to use on the owner's premises, auto-confirmed, no deposit, lives only in a shed). **A thing's verb is not chosen: the server puts it from its collection's kind and its price** — a stall gives (no price) or sells (a price), a library lends or rents out, a shed books — and an edit that sets or clears the price moves it. `status` controls both visibility and reservation state (ACTIVE/TAKEN/INACTIVE). `gallery` JSONField holds up to 8 additional photos (exposed as `gallery_urls`), shown as an image carousel. For date-based types (LEND/RENT/RESERVE), `available_today`/`next_available` expose live availability computed from the booking calendar. `tags` holds owner-defined labels chosen from the collection's `tags` vocabulary, shown as HDS Tags on the card and detail |
| **FAQ** | Questions/answers about things. FK to Thing and User (questioner) |
| **Theeeme** | The twelve colour palettes (6 HDS colour token names each) a curator chooses among for a collection (`Collection.theeeme`, with its `koro`) |
| **Braaanding** | The app's own palette, one row of six hexadecimal colours and a koro, edited in the Django admin: what paints everything that is not a collection's page, and every email. Not a row of `theeemes`, so it can never be picked (see `SELF_HOSTING.md` § 6) |
| **RSVP** | One-time-use tokens (24h expiry) for auth and email actions. FK to User |
| **BookingPeriod** | Unified booking model for all thing types (72h PENDING expiry). FKs to Thing, User (requester), User (owner). LEND/RENT/RESERVE carry dates; GIFT/SELL don't. `start_time`/`end_time` (`TimeField`, nullable) narrow a booking to a slot within one day: `NULL` means whole days, which is every LEND/RENT and every `DAY`-unit reservation; an `HOUR`-unit reservation stores `end_date = start_date + 1` and never crosses midnight. There is no `DateTimeField`: times are wall-clock, read in `DJANGO_TIME_ZONE`. **RESERVE_THING bookings are auto-confirmed** — created straight to ACCEPTED with no accept/reject step, no `ThingTransfer`, both parties emailed at once — and either the requester **or any curator** of the shed (owner or co-curator) may cancel one that hasn't started. `project_note` (RESERVE only) carries the requester's optional note about what the space is for. |
| **Event** | Append-only first-party analytics log. Text **snapshots** (`actor_code`/`collection_code`/`thing_code`), not FKs, so rows outlive hard-deleted objects. `kind` covers the tracked actions (user joined, collection/thing added/removed, member joined/left, FAQ asked, hold requested/accepted). Written by one-line instrumentation next to the notification/email each action already fires — except deletions, which are logged by model receivers so every way a row can go (API, admin, account erasure, retention purge) leaves its event; read only by whatever reporting the deployment runs over it. Never exposed to users |
| **DailyActivity** | One `(user, date)` row per user per active day, written by `DailyActivityMiddleware` (cache-gated to ≤1 DB write per user per day). Powers WAU/MAU and retention. Records less than the web-server logs already hold and never leaves our DB |
| **DeviceDay** | A daily count, per kind of device (`MOBILE` / `OTHER`; a tablet is `OTHER`), of signed-in people and of collection/thing saves — `(date, device, metric, count)`, written by `DailyActivityMiddleware`. No user, no User-Agent; kept without a period because it holds nobody. Read with `device_share` |

## Key Relationships

All relationships use proper Django ForeignKey and ManyToManyField:

- `Collection.owner` -> FK to User
- `Collection.things` -> M2M to Thing (via `collection_things` table)
- `Collection.invites` -> M2M to User (via `collection_invites` table)
- `Collection.co_owners` -> M2M to User (via `collection_co_owners` table) — the co-curator tier in either mode, always a subset of `invites`
- `Collection.theeeme` -> FK to Theeeme (PROTECT)
- `Thing.owner` -> FK to User
- `Thing.deal` -> M2M to User (via `thing_deals` table)
- `FAQ.thing` -> FK to Thing
- `FAQ.questioner` -> FK to User
- `BookingPeriod.thing_code` -> FK to Thing
- `BookingPeriod.requester_code` -> FK to User
- `BookingPeriod.owner_code` -> FK to User
- `RSVP.user_code` -> FK to User

## API Endpoints

### Auth & RSVP Actions
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/auth/request-link/` | Request magic link (rate limited: 5/min); optional `next`: a same-site path the magic link returns to (a bad one is dropped, the response never changes) |
| POST | `/api/v1/auth/join/` | Ask to join a collection you were pointed at — by `share_token` (an owner's `/share/{token}` link) or by the `collection_code` of a PUBLIC one — and get a magic link. **Nothing is joined until the link is pressed** (an address typed may be somebody else's), and then only if the invitation is still in force. **Creates nothing without a valid target**, and answers identically either way (rate limited: 5/min per IP, 5/h per email) |
| GET / POST | `/api/v1/auth/verify/{rsvp_code}/` | Verify magic link / process an RSVP action (rate limited: 10/min). Booking accept/reject only **preview** on GET and require a **POST** to commit, so an email link-scanner or prefetch can't auto-decide a hold; login/invite actions resolve on GET |
| GET / POST | `/api/v1/rsvp/{rsvp_code}/` | Alias for verify endpoint |
| POST | `/api/v1/auth/refresh/` | Rotate access/refresh tokens via HttpOnly cookies |
| GET | `/api/v1/auth/me/` | Get authenticated user, plus a **`capabilities`** block — `{collection_modes, collection_kinds, thing_types, request_url, co_owners_enabled}` (`collection_kinds` is derived from `thing_types`: a kind is open when one of its verbs is offered), what this deployment lets them create (see [SELF_HOSTING.md](SELF_HOSTING.md)). It is the same `CreatorPolicy` answer the create endpoints refuse with, so a client cannot offer what the API would reject; upstream it lists everything, `co_owners_enabled` is `true`, and `request_url` is `null` |
| POST | `/api/v1/auth/logout/` | Log out (clears auth cookies) |
| POST | `/api/v1/auth/delete-account/` | Request account deletion (rate limited: 3/h): emails a 24h single-use confirmation link; the deletion itself commits via a POST on the verify endpoint (GET only previews) |
| GET | `/api/v1/auth/export/` | Download a copy of your own data as one JSON file (rate limited: 10/day). Attachment, `private, no-store`; carries no share tokens, no RSVP tokens and no third-party data beyond what you already see |

### Users
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/users/{user_code}/` | View profile (requires collection connection) |
| PUT | `/api/v1/users/{user_code}/` | Update own profile (name, headline, `about` Markdown bio, `photo`, `notify_activity`, `notify_news`, `age_range`, `postal_code`, `language`) |
| GET | `/api/v1/notifications/token/{token}/` | Read `notify_activity`/`notify_news` via signed token (no login required; linked from every Cat. 2/3 email footer) |
| PATCH | `/api/v1/notifications/token/{token}/` | Update `notify_activity`/`notify_news` via signed token |
| POST | `/api/v1/digest/mute/{token}/` | One-click unsubscribe from **one** collection's digest, via the signed link in that digest's footer (no login). POST-only so an email link-scanner can't unsubscribe anyone |

### Collections (ModelViewSet + Router)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/collections/` | List own collections (owned or co-owned) |
| POST | `/api/v1/collections/` | Create collection. Names its `kind` (`STALL`/`LIBRARY`/`SHED`); without one it is deduced from `allowed_thing_types`, and an empty or mixed list is a 400. The verb list is checked against the kind and normalised (PROPRIETARY takes both verbs; COMMUNITY may drop the paid one, never the free one). The kind cannot be changed afterwards |
| GET | `/api/v1/collections/{code}/` | View collection (owner, co-owner, or invited) |
| PUT | `/api/v1/collections/{code}/` | Update collection (owner or co-owner) |
| DELETE | `/api/v1/collections/{code}/` | Delete collection (owner only — never a co-owner) |
| POST | `/api/v1/collections/{code}/invite/` | Invite user (owner or co-owner). One invitation per person: an address already invited, and not accepted, by this founder or this inviter is refused with 400 `invite_already_asked` (they can join with the share link) |
| DELETE | `/api/v1/collections/{code}/invite/` | Remove invitee (owner or co-owner). Also strips co-owner status if the removed user had it, and deletes that member's things in the group (`things_deleted` in the answer) |
| POST | `/api/v1/collections/{code}/co-owners/` | Promote an existing member to co-curator — any curator in PROPRIETARY and COMMUNITY, only the founder in a NETWORK (rate limited: 30/h). Refused if this deployment's `CREATOR_POLICY` withholds `co_owners_enabled`, or when the collection already holds its ceiling of co-curators (`Collection.MAX_CO_OWNERS`, 10 — the abuse bound, not the design intent of 1–2; re-promoting an existing co-curator stays idempotent and never hits it) |
| DELETE | `/api/v1/collections/{code}/co-owners/` | Demote a co-curator back to a plain member — any curator (in a NETWORK only the founder, and their things go with the role; refused while one is in someone's hands). Not gated by the deployment policy. The founding owner is an FK, not an `invites` row, so this endpoint cannot demote them |
| GET / PUT | `/api/v1/collections/{code}/point/` | A NETWORK's dinamizador reads and edits **their own** pickup point (entity name, address, hours, contact, their days and closures, and the conditions of their loans: deposit policy, request note, email note). The points travel, public, with the collection (`points`). 404 outside a network, 403 for a plain member (rate limited: 30/h on PUT) |
| POST | `/api/v1/collections/{code}/share-link/` | Generate or rotate the public share token (owner or co-owner). Returns `share_url` and `share_token`. Pass `{"rotate": true}` to force a fresh token. Rate limited: 30/h. |
| DELETE | `/api/v1/collections/{code}/share-link/` | Revoke the public share token (owner or co-owner) |
| GET | `/api/v1/share/{token}/preview/` | **Public.** The `headline` and `description` (only) of the collection a `/share/{token}` link opens, so the join page can name it. Generic 404 for an unknown, revoked or inactive token. Rate limited: 30/min per IP |
| POST | `/api/v1/share/{token}/join/` | Accept a `/share/{token}` invitation **with the session you already have** — the signed-in twin of `POST /auth/join/`'s share-token door, which asks for an email and answers with a magic link no live session needs. The token is the credential: generic 404 for an unknown, revoked or inactive one (the same answer as the preview, so it reveals nothing new), `200 {"collection", "joined"}` otherwise (`joined: false` for the owner or a member: idempotent), 429 past the `COLLECTION_JOINS_PER_DAY` ceiling. Never returns the token. Rate limited: 30/h per user |
| GET | `/api/v1/invited-collections/` | List collections where invited |
| GET | `/api/v1/my-invitations/` | List my pending collection invitations |
| POST | `/api/v1/collections/{code}/join/` | Join a PUBLIC collection you are browsing while signed in (self-join) — the half of login-to-act the anonymous `/auth/join/` can't serve, since a magic link is no use to a live session. Honours the same `COLLECTION_JOINS_PER_DAY` ceiling. Rate limited: 30/h |
| POST | `/api/v1/collections/{code}/leave/` | Leave a collection you're invited to (self-unlink) — refused for the owner and any co-owner. Deletes your things in that group (`things_deleted` in the answer) |
| POST | `/api/v1/collections/{code}/invite/propose/` | Members only, not a curator: recommend a guest to the owner. Nothing reaches the proposed address until a curator approves. Rate limited: 30/day |
| POST | `/api/v1/proposals/{code}/{approve\|reject}/` | A curator's answer to a member's recommendation (owner or co-owner) |
| POST | `/api/v1/collections/{code}/digest/` | A member or the founder: silence or un-silence this collection's digest (`{"muted": true\|false}`). Rate limited: 30/h. The bundled frontend calls it from the collection menu's "Mute the summary" entry; the footer link of each digest is the other way out |
| POST | `/api/v1/collections/{code}/invite/bulk/` | Bulk-invite guests from a CSV (owner or co-owner, rate limited: 5/h) |
| GET | `/api/v1/collections/{code}/stats/` | Download a 90-day activity CSV (owner or co-owner) |
| GET | `/api/v1/collections/{code}/export/` | Download the whole collection as one JSON file — members, things (whoever owns them), bookings, questions and handovers (owner or co-owner, rate limited: 10/day). A plain member gets 403, never a partial file |
| POST | `/api/v1/collections/{code}/calendar-export/` | Download the collection's upcoming LEND/RENT/RESERVE reservations as an iCalendar (`.ics`) file (owner or co-owner, rate limited: 20/h). Every upcoming reservation, every call — a stable per-booking UID lets the importing calendar dedupe a re-import, so there's no watermark to keep; `X-Calendar-Events` gives the count; upcoming reservations cancelled since they were confirmed ride along as `STATUS:CANCELLED` events under the same UID, counted in `X-Calendar-Cancelled`. POST kept for contract stability (the call used to mutate; it no longer does) |
| POST | `/api/v1/collections/{code}/email-note/test/` | Email the acting curator their `email_note` draft (`{email_note}`, unsaved), rendered exactly as a member will get it — every language version under its own name (owner or co-owner, rate limited: 10/h). Goes to the requester's own address only |
| POST | `/api/v1/collections/{code}/broadcast/` | Send a message to all invitees (owner or co-owner) |
| POST | `/api/v1/collections/{code}/things/bulk/` | Bulk-create things from a CSV (rate limited: 10/h). The `type` column is optional: the verb follows the fee, and a `type` that contradicts it is a row error |

### Things (ModelViewSet + Router)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/things/` | List own things |
| POST | `/api/v1/things/` | Create thing — in a collection: a body with no `collection_code` is a 400 |
| GET | `/api/v1/things/{code}/` | View thing (owner or invited) |
| PUT / PATCH | `/api/v1/things/{code}/` | Update thing — a **manager**: its owner, or a curator of a PROPRIETARY collection it's in (`IsThingManager`) |
| DELETE | `/api/v1/things/{code}/` | Delete thing — any collection owner, a co-curator of a PROPRIETARY collection it's in, or its own owner while it has never changed hands |
| POST | `/api/v1/things/{code}/request/` | Request reservation (invited only) |
| GET | `/api/v1/things/{code}/calendar/` | View booking calendar (any thing). A manager sees requester details; guests see dates + status only |
| GET | `/api/v1/things/{code}/transfers/` | View transfer history and stats (Loan Chain) |
| POST | `/api/v1/things/{code}/activate/` | Reactivate an inactive thing — a manager (`IsThingManager`) |
| POST | `/api/v1/things/{code}/hide/` | Set an active thing to inactive — a manager (`IsThingManager`) |
| POST | `/api/v1/things/{code}/report/` | Report a listing anonymously (logged-in non-owners) |

### Bookings
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/my-bookings/` | List my booking requests (with thing headline, owner name) |
| GET | `/api/v1/owner-bookings/` | Bookings on my things, plus every booking on a thing in a PROPRIETARY collection I curate (with requester name) |
| POST | `/api/v1/bookings/{code}/accept/` | Accept a pending booking — a manager of the thing (owner or PROPRIETARY-collection curator) |
| POST | `/api/v1/bookings/{code}/reject/` | Reject a pending booking — a manager of the thing |
| POST | `/api/v1/bookings/{code}/remind-return/` | "Remind them to return it": a manager of the thing mails the borrower of an overdue loan or rental, once a day per booking (429 `already_reminded_today` after that) |
| POST | `/api/v1/bookings/{code}/cancel/` | Cancel a booking. Own pending booking (requester); for a RESERVE_THING reservation that hasn't started, the requester or any curator (owner or co-curator) of the reservations collection |

### FAQ
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/things/{code}/faq/` | List FAQs for a thing |
| POST | `/api/v1/things/{code}/faq/` | Ask question — any signed-in reader who can view the thing, except its owner. On a PUBLIC collection that is anyone with an account, not only invitees (`thing.can_view()`, the same guard the read uses) |
| GET | `/api/v1/faq/{code}/` | View FAQ |
| POST | `/api/v1/faq/{code}/answer/` | Answer FAQ — a manager of the thing (owner or PROPRIETARY-collection curator) |
| POST | `/api/v1/faq/{code}/hide/` | Hide FAQ — a manager of the thing |
| POST | `/api/v1/faq/{code}/show/` | Show FAQ — a manager of the thing |

### Other
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/inbox/` | List in-app notifications for the current user |
| DELETE | `/api/v1/inbox/{code}/` | Dismiss an in-app notification |
| DELETE | `/api/v1/inbox/?group=bookings[&collection={code}]` | Dismiss, in one call, the request and reservation notices that are for the team managing them (the set the inbox folds into one summary card) |
| POST | `/api/v1/upload/ticket/` | Get a short-lived ticket to upload one file straight to object storage (rate limited: 120/h, of which 10/h for PDFs) |
| GET | `/api/v1/theeemes/` | List the twelve palettes a curator can pick for a collection |
| POST | `/api/v1/contact/` | Support/contact form (anonymous on purpose — a locked-out user is the main case; rate limited: 5/h per IP). Forwards the message to the operator with the sender as Reply-To; `kind: support\|collab` labels the subject (the `/contact` page sends none, which is `support`; no page sends `collab` since 2026-10-04) |
| GET | `/api/v1/health/` | Health check: verifies app **and** database (`SELECT 1`) — 200 ok / 503 degraded. Point your uptime monitor here (rate limited: 60/min per IP, GET and HEAD — far above any real monitor's cadence) |
| - | `/oiueei-admin/` | Django Admin (requires password) |

**Note:** Booking accept/reject actions (GIFT/SELL/LEND/RENT) can be performed via RSVP links sent by email or via authenticated API endpoints (`/bookings/{code}/accept/` and `/bookings/{code}/reject/`). Requesters can cancel their own pending bookings via `/bookings/{code}/cancel/`. **RESERVE_THING bookings skip this entirely** — they are auto-confirmed, so there is no accept/reject; `/bookings/{code}/cancel/` is open to the requester or any curator of the reservations collection while it hasn't started. Email links use RSVP codes as intermediaries to avoid exposing real codes in URLs.

## Deploying to Heroku

See [HEROKU.md](HEROKU.md) for a complete step-by-step guide covering buildpacks, config vars, font setup, custom domain, email, scheduled jobs and the backup restore drill.

## Running it for other people

This repository is the whole product, but not the layer an operator wraps around
it to run OIUEEI as a service: an open sign-up door, a queue of people asking to
be allowed to lend, a subscription. That is where an operator's judgement lives,
and it differs for every one of them.

So the mechanism is here and the policy is not. Four extension points let a
deployment add routes, decide who may create what, tell the frontend so it
stops offering what would be refused, and replace the SPA's pages and copy —
**without editing a file this repository also edits**, which is what makes an
upgrade a merge and not an argument. See [SELF_HOSTING.md](SELF_HOSTING.md).

## Development

```bash
# 1. Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env  # Configure environment variables

# 2. Database (run before starting the servers)
python manage.py makemigrations core
python manage.py migrate

# 3. Seed demo data — recommended before exploring the app or running the frontend.
#    Without it the app is empty and there is no account to sign in as.
#    (Lala, Lele, Lili, Lolo, Lulu and their collections — idempotent.)
#    Collection/thing text is ALWAYS seeded in all three languages at once
#    (inline {es,ca,en} maps — every reader sees their own); --lang only picks
#    the language of the plain-column text (user bios, FAQs).
python manage.py seed_demo                 # plain-column text in English (default)
python manage.py seed_demo --lang=es       # … in Spanish (also: --lang=ca)
python manage.py seed_demo --lang=es --reset   # wipe demos first, then re-seed
# On Heroku (quote the inner command — the Heroku CLI otherwise grabs inner flags like --lang as its own):
#   heroku run --app <your-app> "python manage.py seed_demo --lang=es"
# Pass --reset to wipe existing demo data first (leaves other users/collections untouched).
# Adding a new language: copy core/management/commands/seed_data/en.py to e.g. pt.py,
# translate the text fields, add the code to SUPPORTED_LANGS in seed_demo.py.

# 4. Run the servers
python manage.py runserver                 # backend → http://localhost:8000
cd frontend && npm install && npm run dev  # frontend → http://localhost:3000 (separate terminal)

# 5. Tests & linting
pytest -v --cov=core --cov-fail-under=96   # backend tests (SQLite locally)
cd frontend && npm test                    # frontend tests (smoke + accessibility)
# CI runs this same backend suite against PostgreSQL — see Testing below.
ruff check .                               # lint + import sort (replaces flake8 + isort)
ruff format .                              # formatting (replaces black)

# Create admin user
python manage.py createsuperuser

# Object storage: write the bucket's CORS rules — without them NOBODY CAN UPLOAD.
# The browser writes straight to the bucket, so it preflights, and a store with no
# rules answers that 403 before the file leaves the laptop. Photos already stored
# keep loading throughout, so the deployment looks healthy. Idempotent; re-run it
# whenever your domains change. With no --origin it uses CORS_ALLOWED_ORIGINS.
python manage.py set_bucket_cors --origin https://your-domain
python manage.py set_bucket_cors --show     # what the bucket allows right now

# Scheduled jobs (run via Heroku Scheduler in production — one daily job chains them)
python manage.py expire_bookings   # expire stale bookings
python manage.py cleanup_rsvps     # delete expired RSVPs (24h+)
python manage.py close_transfers   # close overdue loan transfers
python manage.py send_reminders    # loan pickup and return reminders (both sides) + reservation arrival reminders (daily)
python manage.py send_join_summaries  # who joined since the last summary, to each group's curators (daily, before send_digests)
python manage.py send_digests      # weekly/monthly digest emails (daily)

# Look at every email in a real mail client — sample data, every builder, one address.
# It can mail nobody but --to and it leaves the database untouched (see the module
# docstring); the links in the samples are decoys. Console backend by default.
python manage.py send_test_emails --list
python manage.py send_test_emails --to lulu@your-domain.test --lang es --only booking
python manage.py send_test_emails --to lulu@your-domain.test --lang all --yes   # 3 x every email, for real

# Retention sweep (GDPR art. 5.1.e) — the sixth link in that daily chain, and the
# one that makes "nothing is kept forever" below true rather than aspirational.
# DRY-RUN BY DEFAULT: it deletes real rows, so look at what it would do, decide
# your own RETENTION_* periods (0 keeps a category indefinitely), and only then
# add --commit to the scheduled chain. See HEROKU.md § Scheduled jobs.
python manage.py purge_expired_data           # count what is past its period
python manage.py purge_expired_data --commit  # anonymise / delete it
# Inactivity warnings are capped at 200 per run so a first-time backlog does not
# arrive at your mail provider in one burst. --max-warnings 0 lifts the cap.

# One-off: seed the Event analytics log from existing rows (idempotent).
# Run once, the day tracking ships, before forward events accumulate.
python manage.py backfill_events
```

## Testing

Backend `pytest` + `pytest-django`, frontend `vitest` + Testing Library + `jest-axe`.
Coverage floors are **ratchets, not targets** — they sit a couple of points under
the suite's real coverage so a regression is visible, and CI enforces both:
backend 96%, frontend 93/89/89/94 (statements/branches/functions/lines).

**CI runs the backend suite against PostgreSQL, not SQLite.** That is not parity
for its own sake. On SQLite, Django reports `has_select_for_update = False` and
*silently drops* the FOR UPDATE clause — no warning, the query just runs unlocked
— so every row-locked path (accepting, rejecting and cancelling a booking; the
capacity recheck on bulk import) would be proving its logic and never its lock.
That breaks with two concurrent requests, not two thousand. SQLite also doesn't
enforce `CharField(max_length=N)`, which PostgreSQL does.

`core/tests/integration/test_booking_row_locks.py` is the suite that depends on
this. It races two connections at one booking and asserts the second is still
blocked while the first holds the row — which is the only shape that can tell a
lock from the re-read beside it. Everything else in the suite is single-threaded
inside one transaction, where a FOR UPDATE never blocks against the transaction
that took it, so removing all six of them used to leave the whole run green.
Those three tests **skip** on SQLite rather than measure the unlocked behaviour.

A local `pytest` still runs on SQLite and needs no database server. To reproduce
a CI failure — or to run the lock tests at all — point `DATABASE_URL` at a
throwaway Postgres:

```bash
DATABASE_URL=postgres://user:pass@localhost:5432/oiueei_test pytest -q
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `JWT_SIGNING_KEY` | No | Signs JWTs independently of `DJANGO_SECRET_KEY`, so the two can be rotated separately (defaults to `DJANGO_SECRET_KEY` if unset). Setting/rotating it invalidates every issued access/refresh token — everyone re-logins via magic link — so change it deliberately, once, alongside a release. |
| `DJANGO_SETTINGS_MODULE` | No | Settings module (defaults to production) |
| `DJANGO_DEBUG` | No | Enables Django debug mode (default: `False` — fail-closed on a missing/typo'd value) |
| `DJANGO_ALLOWED_HOSTS` | No | Comma-separated allowed hosts |
| `DJANGO_TIME_ZONE` | Recommended | The deployment's wall clock, as an IANA name (`Europe/Madrid`); default `UTC`. It decides what "today" and "now" are for every date rule, and it is the zone an hourly space's opening hours are read in — so it is what lets the server refuse a slot that has already begun today. Leave it at `UTC` and "10:00" in an opening schedule means 10:00 UTC. A misspelt name fails the boot instead of quietly shifting every day boundary |
| `DATABASE_URL` | Prod | PostgreSQL connection string. Also read by `development.py` — that is how CI runs the suite on Postgres (see Testing) |
| `DEV_DB_NAME` | No | Dev only: points the SQLite file elsewhere, so a migration can be rehearsed on a throwaway DB (`DEV_DB_NAME=/tmp/rehearsal.sqlite3 python manage.py migrate core 0121`). Ignored when `DATABASE_URL` is set |
| `MAGIC_LINK_BASE_URL` | Prod | Base URL for magic link emails (default in dev: `http://localhost:3000/verify`) |
| `CORS_ALLOWED_ORIGINS` | Prod | Comma-separated allowed origins |
| `CSRF_TRUSTED_ORIGINS` | Prod | Comma-separated trusted origins |
| `EMAIL_HOST` | Prod | SMTP host (default: smtp.sendgrid.net) |
| `EMAIL_PORT` | No | SMTP port (default: `587`) |
| `EMAIL_HOST_USER` | Prod | SMTP username |
| `EMAIL_HOST_PASSWORD` | Prod | SMTP password |
| `EMAIL_TIMEOUT` | No | SMTP socket timeout in seconds (default: `10`) — caps a slow/hung provider so it can't stall a web dyno |
| `EMAIL_LANGUAGE` | No | **Default** language for outbound email (`en`\|`es`\|`ca`; default `en`) — the weakest level of the hierarchy **deployment → collection (`Collection.language`) → recipient (`User.language`)**, so it only speaks when neither the group nor the member has chosen. Catalogues live in `core/services/email_texts/`; unknown codes fall back to English |
| `VITE_FEEDBACK_URL` | No | Frontend build-time: points the in-app feedback link at your own form. **No default** — without it the link is not rendered at all, rather than quietly forwarding your users' feedback to the upstream project's own form |
| `DEFAULT_FROM_EMAIL` | Prod | Sender email address |
| `RSVP_BASE_URL` | Prod | Base URL for RSVP action links in emails (default in dev: `http://localhost:3000/rsvp`) |
| `SHARE_LINK_BASE_URL` | Prod | Base URL for public collection share links (default in dev: `http://localhost:3000/share`) |
| `OBJECT_STORAGE_ENDPOINT` | Uploads | S3-compatible endpoint, e.g. `https://fsn1.your-objectstorage.com` |
| `OBJECT_STORAGE_BUCKET` | Uploads | Bucket name. **Must be private and not listable** — objects are made public one by one at upload time, so a listable bucket would let anyone enumerate a private collection's photos |
| `OBJECT_STORAGE_REGION` | Uploads | Region the endpoint serves, e.g. `fsn1` |
| `OBJECT_STORAGE_ACCESS_KEY` | Uploads | S3 access key, scoped to that bucket alone |
| `OBJECT_STORAGE_SECRET_KEY` | Uploads | S3 secret key |
| `MEDIA_PUBLIC_BASE_URL` | Optional | Where files are **read** from. Defaults to the bucket's own URL; set it to put a CDN or a custom domain in front. Uploads are unaffected — a presigned URL is always signed for the bucket, so the Content-Security-Policy allows both hosts and splitting them does not break writing. A wrong value shows up as images that refuse to load |
| `CONTACT_EMAIL` | No | Recipient of the `/contact` support form (default: `DEFAULT_FROM_EMAIL` — the operator mails themselves) |
| `SEED_EMAIL_DOMAIN` | No | Domain of the five demo characters `seed_demo` creates (`lala@…`, `lele@…`…). Default `your-domain.test`: `.test` is a reserved domain, so a notice addressed to a demo character reaches nobody. Set a domain you control to receive those mails; re-run `seed_demo` to apply it (it updates the five accounts in place) |
| `INVITE_EMAILS_PER_DAY` | No | Cap on invitation **emails** one account may send per day — single, bulk and approved member recommendations combined, whether the owner approves in the app or from the link in their email. **Unset or `0` = no limit**, which is the standalone default: this guards *your* sending domain's reputation, so the number is yours to choose. Ignored when `RATELIMIT_ENABLE` is off. |
| `COLLECTION_THINGS_ALARM` | No | Per-collection thing count that quietly emails the superusers **once**, so an operator can notice unusual volume without touching anything. **Unset or `0` = off** (the default). The owner is never told. |
| `COLLECTION_THINGS_BLOCK` | No | Per-collection ceiling on things: adds that would cross it are refused, including whole CSV batches. **Unset or `0` = off** (the default). A superuser lifts it per collection with `capacity_unblocked` in the admin. |
| `COLLECTION_INVITES_ALARM` | No | The same silent, fire-once alert for a collection's **member** count. **Unset or `0` = off**. |
| `COLLECTION_INVITES_BLOCK` | No | Per-collection ceiling on members: invitations that would cross it are refused when **sent**, not when accepted. **Unset or `0` = off**. Same `capacity_unblocked` override. |
| `COLLECTION_JOINS_PER_DAY` | No | Cap on how many people **one collection** may be joined by per day through `POST /auth/join/` — the door that needs no account. `INVITE_EMAILS_PER_DAY` guards what an *account* sends; this guards the one anybody can push, where the address mailed is whatever a stranger typed and the collection code is public by construction. Without it the per-IP limit is all that stands between your sending domain and many IPs each mailing a different stranger once. Counted **per collection**, so abusing one group's public code costs that group its day and leaves the rest working — a deployment-wide counter would let one abuser switch joining off for everyone. A refusal answers with the endpoint's usual unified response (the operator gets a `security` log line; the visitor is never told, or the cap becomes a way to probe which codes are real). **Unset or `0` = no limit**, the standalone default: a share link pasted into a group chat can legitimately bring in hundreds in an evening. Ignored when `RATELIMIT_ENABLE` is off. |
| `ANON_API_RATE` | No | API requests one IP may make per window while **not signed in** (default `300/m`; a count, a slash and a period such as `20/s` or `1000/5m`, `0` = off). A PUBLIC collection is readable by anyone, so without a ceiling a script can scrape its things, calendars, FAQ and journeys as fast as your server answers. Counted per real client IP (`TRUSTED_PROXY_COUNT`) and **only** for requests with no session — a signed-in member is never throttled by it. Over the line the API answers `429` with `Retry-After`. The same count covers the two pages that ask the database on a visitor's behalf — the link preview of a collection, a thing or a share link, and the redirect off an old collection address — which, instead of an error, serve the plain page without asking anything. The count is kept in each web process's memory, never in the database: it costs no query, and it is approximate — every process counts on its own, so one address gets up to the rate times your web processes, and a restart forgets it. A value that is not a rate fails `manage.py check`. |
| `TRUSTED_PROXY_COUNT` | No | How many proxies in front of the app are trusted to have appended to `X-Forwarded-For`. It decides which entry every per-IP rate limit buckets on, counted from the **right** — only the tail of that header is written by a proxy; the rest is the caller's own text. Default `1` = one trusted proxy (the Heroku/Render/Fly router, or an nginx you run). **Set `0` if nothing trusted sits in front** (gunicorn facing the internet): otherwise the header is caller-supplied and one caller can mint a fresh bucket per request, defeating every rate limit below. `2+` for a CDN in front of the router. |
| `RETENTION_INACTIVE_ACCOUNT_MONTHS` | No | How long an account nobody signs into is kept before it is erased (default `24`). `GET /auth/me/` counts as signing in, so an account in daily use through the app is never dormant. An account that **owns a group other people are using is never auto-deleted** — `purge_expired_data` lists it for a person to decide instead. **`0` = keep indefinitely.** |
| `RETENTION_INACTIVE_WARNING_DAYS` | No | The grace period between the warning email and the erasure (default `30`). Nothing is ever deleted without that email first, and coming back once clears the mark *and* refreshes the clock, so returning genuinely saves the account. |
| `RETENTION_UNVISITED_GUEST_DAYS` | No | How long a `User` row created by somebody else's invitation and **never used** is kept (default `60`). That address came from a third party (art. 14) and was used for one thing: an invitation nobody answered. Anyone who accepted, owns anything, or still has a live invitation is excluded. **`0` = keep indefinitely.** |
| `RETENTION_EVENT_ANONYMISE_MONTHS` | No | When the analytics log stops being about a person (default `14`). **Anonymised, not deleted** — `actor_code` is cleared and the fact survives as aggregate, which is what art. 5.1.e asks for; deleting would throw away the history to achieve the same thing. **`0` = keep indefinitely.** |
| `RETENTION_DAILY_ACTIVITY_MONTHS` | No | How long the one-row-per-user-per-day activity log is kept (default `26`). **`0` = keep indefinitely.** |
| `RETENTION_NOTIFICATION_MONTHS` | No | How long in-app notifications are kept (default `12`). **`0` = keep indefinitely.** |
| `RETENTION_REPORT_MONTHS` | No | How long reports on things are kept, dated from `created` (default `12`). **`0` = keep indefinitely.** |

> **None of the `RETENTION_*` periods happens on its own.** `python manage.py purge_expired_data` is what enforces them and it is **dry-run by default** — a deployment that never adds `--commit` to its scheduled chain keeps everything forever. Set your own periods for your own regime first, run it once by hand and read what it says it would do, and only then arm it. See [HEROKU.md § Scheduled jobs](HEROKU.md).

## Onboarding & access

**There is no public self-registration.** An account exists because somebody chose to admit a specific person, and there are two ways that happens:

- **An owner invites you.** By email (the account is created when you accept), or through a public `/share/{token}` link — optionally as a QR — that the owner can rotate or revoke at any time. Either way you join **that one collection**.
- **You act on a PUBLIC collection.** Anyone can read a collection its owner made public; pressing an action button asks for your email and sends a magic link (`POST /auth/join/` with its code); pressing that link is what joins you to the collection, like accepting an invitation by email. It is login-to-act: reading needs nothing, acting needs an account.

`/login` (`POST /auth/request-link/`) is for people who already have an account. It always answers `200` — it never reveals whether an address is registered — and never creates users. `/auth/join/` likewise **creates nothing** unless the request carries a valid share token or public collection code, and answers identically whether or not it did.

Note what the second bullet means before you go public: **a PUBLIC collection's code is in its own URL**, so anyone who can read the collection can also ask your deployment to mail a magic link to any address they type. That is your sending domain, not theirs. `COLLECTION_JOINS_PER_DAY` caps how many people one collection may be joined by in a day and is the guard for it; it ships **off**, because only you know how big a share link you handed out.

**If your deployment wants an open door**, add one: a view of your own, mounted through `DEPLOYMENT_URLCONFS`, that creates the account and joins it to your `is_onboarding` collections. The mechanism is documented in [SELF_HOSTING.md](SELF_HOSTING.md); the policy is yours, which is why it is not shipped here.

## Security

### Implemented Measures

| Category | Measure | Description |
|----------|---------|-------------|
| Authentication | Magic Link | Passwordless auth via email (24h expiry, one-time use) |
| Authentication | JWT | HttpOnly cookie-based. 1-hour access, 7-day refresh with rotation and blacklist |
| Authentication | Invite-Only | New accounts come from an owner's invitation, an owner-enabled public share link/QR, or joining a PUBLIC collection to act on it. No endpoint creates an account that belongs to no collection. |
| Authentication | Admin 2FA | Django admin login requires a verified TOTP device (`django-otp` `OTPAdminSite`), on top of the password. Bootstrap the first device via `manage.py add_totp_device <email>`. |
| Authorization | DRF Permissions | Custom `IsThingOwner` / `IsThingManager` / `IsCollectionOwner` / `IsCollectionCurator` permission classes |
| Authorization | IDOR Protection | Profile access only via collection connections |
| Input Validation | XSS Prevention | HTML escaped in emails via `django.utils.html.escape()`. Headlines sanitized |
| Input Validation | Image ID | Alphanumeric validation prevents path traversal; each field is also bound to its own storage folder, so a key may not name another one |
| Rate Limiting | Anonymous reads | 300 req/min per IP and per web process for any API request with no session (`ANON_API_RATE`, `0` = off; counted in memory, at no database cost) — a PUBLIC collection is readable by anyone, so this is what keeps a script from scraping it. Never applies to a signed-in member; a 401/403 does not spend it |
| Rate Limiting | Auth | 5 req/min for magic link, 10 req/min for verify, 10 req/min for token refresh |
| Rate Limiting | Join (`/auth/join/`) | 5 req/min per IP + 5 req/hour per email |
| Rate Limiting | Joins per collection | Off by default; set `COLLECTION_JOINS_PER_DAY` to cap how many people **one collection** may be joined by per day. The two limits above cap one IP and one victim; this is what stops many IPs each mailing a different stranger once, using a public collection code as a relay onto the operator's sending domain. A refusal returns the endpoint's usual unified response, so the cap can't be used to probe which codes are real |
| Rate Limiting | Collection invite | 30 req/hour per user |
| Rate Limiting | Collection bulk invite | 5 req/hour per user |
| Rate Limiting | Invitation emails | Off by default; set `INVITE_EMAILS_PER_DAY` to cap per account — single, bulk and approved recommendations combined, on both of the owner's routes |
| Rate Limiting | Collection share-link | 30 req/hour per user |
| Rate Limiting | Share-link join (`/share/{token}/join/`) | 30 req/hour per user (plus the per-collection daily ceiling) |
| Rate Limiting | Thing request | 10 req/hour per user |
| Rate Limiting | Thing bulk create | 10 req/hour per user |
| Rate Limiting | Thing report | 10 req/hour per user |
| Rate Limiting | Upload signature | 30 req/hour per user |
| Rate Limiting | Broadcast | 5 req/day per user |
| Rate Limiting | Email-note test | 10 req/hour per user (to the curator's own address only) |
| Rate Limiting | FAQ question | 20 req/hour per user |
| Rate Limiting | Notifications token | GET 20/min, PATCH 10/min per IP |
| Rate Limiting | Health check | 60/min per IP (GET + HEAD) — the one anonymous endpoint that reaches the database on every hit |
| Rate Limiting | Which IP a limit counts | The entry `TRUSTED_PROXY_COUNT` says a trusted proxy appended, counted from the right, **validated as an IP** before use; anything unparseable falls back to `REMOTE_ADDR` and then to one shared bucket — never to a fresh allowance |
| Rate Limiting | Thing single create | 60 req/hour per user |
| Rate Limiting | Collection single create | 30 req/hour per user |
| Rate Limiting | Collection leave | 30 req/hour per user |
| Rate Limiting | Collection digest pref | 30 req/hour per user |
| Rate Limiting | Recommend a guest | 30 req/day per member |
| Rate Limiting | Digest mute by token | 10 req/min per IP |
| Rate Limiting | Account delete request | 3 req/hour per user |
| Rate Limiting | Contact form | 5 req/hour per IP |
| Headers | HSTS | 1-year strict transport security with preload |
| Headers | X-Frame-Options | DENY (prevents clickjacking) |
| Headers | Content-Type | nosniff (prevents MIME confusion) |
| Headers | Referrer-Policy | strict-origin-when-cross-origin |
| Headers | Content-Security-Policy | Applied in every environment via `SecurityHeadersMiddleware` (`core/middleware.py`), plus a `Permissions-Policy` disabling camera/microphone/geolocation/payment. Violations are reported to **our own** `POST /api/v1/csp-report/` (`report-uri` + `report-to`) and logged to the `security` logger — a hosted collector would be handed the URL of every page a member visits, which §9 rules out |
| Production | SSL | Forced HTTPS redirect, secure cookies |
| Production | Admin Path | Custom path (`/oiueei-admin/`) instead of `/admin/` |
| Production | API Renderer | JSON-only in production (BrowsableAPI disabled) |
| Pagination | Max 100 | Prevents DoS via large page requests |

### Security Roadmap

- [ ] Email validation via AbstractAPI
- [ ] Audit logging to external service

## Privacy

Everything below is written so you don't have to take my word for it. Each claim comes with the way to check it yourself — "we take your privacy seriously" is what a page says when it has nothing checkable to offer.

### What the app does not do

- **No advertising.** No ad slots, no ad SDK, no ad network, no sponsored placement. Nothing in the product is sold to anyone who wants your attention.
- **No tracking, of any kind.** No analytics SDK, no tag manager, no fingerprinting, no session replay, no heatmaps, no A/B-testing service, no "anonymous" telemetry that phones home.
- **No third-party code running in your browser.** The app ships 12 runtime dependencies (React, HDS, i18next, a router, a QR renderer, a CSV/ZIP parser) — all rendering and parsing libraries, none of which talks to anyone. No script from another origin is loaded, ever.
- **No cookie banner, because there is nothing to consent to.** The only cookies are the technical ones that keep you signed in (auth + CSRF). There is no third-party cookie, no advertising cookie, no tracker to ask permission for — so asking would be theatre.
- **No unnecessary browser storage either.** LSSI-CE art. 22.2 covers more than cookies — `localStorage`, `sessionStorage`, IndexedDB — so "no banner" has to be true of all of it, not just of what a cookie table shows.
- **No tracking pixels or wrapped links in emails.** Links go where they say they go; there is no open-tracking pixel, no click-redirect domain.
- **No sale, sharing, profiling or automated decisions** on user data. [DESIGN.md §9](DESIGN.md#9-user-data-is-never-a-product) lists what is forbidden here under any justification — it is a design rule, not a policy page.

### How to check all of that

| Claim | How to verify it |
|---|---|
| Third-party scripts *cannot* load | `curl -sI https://<your-domain>/ \| grep -i content-security-policy` — the policy is `default-src 'self'; script-src 'self'`. A third-party script is blocked by the browser, not by a promise. See `core/middleware.py`. |
| Nothing is sent anywhere | DevTools → Network, on any page. You will see this origin and the host the photos are served from — whatever `MEDIA_PUBLIC_BASE_URL` names. On a deployment that puts a CDN in front of its bucket the CSP allows one host more, the bucket itself, because that is where an upload is written even when reads come from the CDN. Two hosts at most, and that is the whole list. A tab left open for hours also asks this same origin for the app's front page, at most once every ten minutes and only when it comes back into view, to tell whether a newer version is out: no parameters, nothing of yours in it, nothing stored (`frontend/src/hooks/useNewVersion.js`). |
| No trackers in the bundle | `frontend/package.json` — 12 runtime dependencies, all listed above. |
| Only technical cookies | DevTools → Application → Cookies. |
| Browser storage is strictly necessary, nothing more | **Inventoried 2026-09-07, `sessionStorage` line updated 2026-09-29, `localStorage` reduced to one key 2026-10-24.** One `localStorage` key, session bookkeeping and nothing observed about you: `userCode` (which account is signed in). It used to be three: `theeemeColors` and `koro` (your display preferences) went when the palette became the collection's own (or the app's, served in the page) — the app no longer writes them and removes what an earlier visit left in your browser. `sessionStorage` holds one key, `staleChunkReloadAt`: the time of the last automatic reload of a tab that was open across an update and asked for a page's code that no longer exists. It is what stops a page that stays broken from reloading in a loop; it lives as long as the tab, nothing else reads it, and it is never sent anywhere. One more key exists but isn't ours to name in code: `i18next-browser-languagedetector` caches your chosen UI language as `i18nextLng` under its own default — same category, a dependency's own write. `frontend/src/test/browserStorage.test.jsx` sweeps every source file and fails the build if a key outside this list ever appears — a public claim like this one needs a test that breaks when it stops being true, not just a paragraph. |
| The metrics are first-party | `core/models/event.py` and `core/models/activity.py` — an append-only event log and one `(user, date)` row. They record *less* than any web server log, and never leave the database. |
| All of it | The whole codebase is public. Read it. |

### What does leave the server

Four outbound flows exist, all operational, all named — the app is a normal web service, not a magic box:

1. **Hosting and database** — where the operator deploys it.
2. **Email delivery** — the configured SMTP provider (magic links, invitations, activity notices).
3. **Images and documents** — the object-storage bucket the operator configured, which serves the photos to your browser and therefore sees the request.
4. **Error monitoring** — OIUEEI ships none. A deployment that adds one must scrub cookies, auth headers, IP and user identity before an event leaves (`send_default_pii=False` and a `before_send` hook, for Sentry).

### Your rights over your data

**Right to erasure is self-service, not a support ticket**: delete your own account from your profile (Edit profile → Delete account). Once confirmed via an emailed 24-hour link it is immediate and irreversible — the account, its collections, things, photos and pending requests are permanently deleted, stored files included (`core/services/asset_cleanup.py` runs on the delete). Questions you asked on other people's things and an item's transfer history survive **anonymised**: the content stays with the thing, your name goes ("former member").

**Portability is self-service too**: `GET /api/v1/auth/export/` hands you your whole account as a single JSON file — profile, collections, things, bookings, questions, handovers, notifications and your own activity rows. It carries no credentials (no `share_token`, no RSVP tokens) and no third-party data beyond what the app already shows you; photos and PDFs travel as links rather than bytes, which is why deleting the account breaks them — **download your images before you erase**. Collection owners get a second, separate download (`GET /api/v1/collections/{code}/export/`) with the whole group in it, so a library of things can be carried out rather than only deleted. That file holds other people's details, and whoever downloads it is the one answering for it.

**Nothing is kept forever.** Each category of data has a period, and `purge_expired_data` is what enforces it: inactive accounts (24 months, with an email first and 30 days to answer it), invited guests who never came in (60 days), daily-activity rows (26 months), in-app notifications (12 months), reports (12 months), and the record that an address was invited by email (12 months; it keeps only a fingerprint of the address, and unlike the others its period is a constant, not a setting, because the invitation email promises that year). The analytics log is **anonymised rather than deleted** at 14 months — what expires is the link to a person (`actor_code`), not the fact that something happened, so the aggregate history survives and stops being personal data. Every other period is a `RETENTION_*` setting and **0 means keep indefinitely**: the numbers above are the defaults one deployment settled on, and a self-hoster under a different regime sets their own.

**If somebody else's address reached you, you're told so in the same email.** Being invited to a collection means somebody else typed your address in, not you — art. 14 GDPR requires that to be disclosed the first time it happens, so the invitation email says where the address came from and that declining or ignoring it ends the relationship. Every email, that one included, links to the instance's `/legal` page in its footer, whether or not you can opt out of the category it belongs to (`core/services/email_service.py`, `_render_email`).

For access, rectification, objection or restriction, write to the operator of your instance — the address on its `/legal` page.


## Architecture Decisions

- **Service layer**: Business logic extracted into `core/services/` (email composition, booking accept/reject/cancel with `transaction.atomic()`). Views are thin controllers.
- **ModelViewSet + Router**: Collections and Things use DRF ModelViewSet with DefaultRouter for standard CRUD. Custom actions use `@action` decorator.
- **Proper FK/M2M**: All relationships use Django ForeignKey and ManyToManyField (migrated from JSONField arrays). This enables `select_related`/`prefetch_related`, cascade deletes, and referential integrity.
- **Centralized email**: All email HTML composition lives in `email_service.py` with `django.utils.html.escape()` for XSS prevention. Every send is routed through a preference pipeline that filters Cat. 2 (activity) and Cat. 3 (news) based on `User.notify_activity` / `notify_news`; Cat. 1 (magic links, invitations, revokes) is always delivered. Non-mandatory emails carry a footer with a `TimestampSigner`-signed link to `/me/notifications/{token}` so recipients can toggle preferences without logging in (see `NotificationsByTokenView`).
- **RSVP intermediary**: All email action links use RSVP codes. Real entity codes are never exposed in URLs.
- **Seed data out of migrations**: Demo fixtures (Lala/Lele/Lili/Lolo/Lulu and their collections) live in `core/management/commands/seed_demo.py` + `seed_data/{lang}.py`, not in migrations. Fresh environments start with a clean DB and only get demo data when `python manage.py seed_demo` is run explicitly. The command is idempotent (`update_or_create` / `get_or_create`). Collection/thing text is always seeded **in all three languages at once** as inline localized maps (`{"es": …, "ca": …, "en": …}` — every reader resolves their own, see the multilingual-content notes); `--lang=en|es|ca` (default English) only selects the language of the plain-column text (user bios, FAQs). The old seed migrations (`0037`–`0076`) are retained as no-ops to preserve migration history.

## Default Data

- Default Theeemes (system baseline, seeded by migration `0036`): the 12 canonical palettes (Bussi, Engel, Hopea, Kesä, Kupari, Kulta, Metro, Sumu, Spåra, Suomenlinna, Vaakuna, M&V).
- The app's own palette (`Braaanding`, seeded by migration `0164`), edited in the Django admin.
- Demo users/collections/things: **not** created automatically — run `python manage.py seed_demo` to populate.

## Important Notes

- **Superadmin must be created manually** after running migrations:
  ```bash
  python manage.py createsuperuser
  ```
  This is required to access `/oiueei-admin/`. Regular users authenticate via magic link and don't need passwords.

- **Admin login also requires 2FA**: `/oiueei-admin/` is an `OTPAdminSite` (`django-otp`) — password auth alone isn't enough. Bootstrap the first TOTP device (no admin login needed) with:
  ```bash
  python manage.py add_totp_device <email>
  ```
  Scan the printed `otpauth://` URI into an authenticator app. Additional staff can then have devices added via the admin's own TOTP device page once one verified login exists.

- **Booking expiration** - PENDING bookings expire after 72 hours. Run `python manage.py expire_bookings` periodically (Heroku Scheduler recommended).

## Accessibility

OIUEEI targets [WCAG 2.1 AA](https://www.w3.org/TR/WCAG21/) as a minimum across all views. This commitment is structural, not aspirational — accessibility decisions are embedded in the design system, the theeeme colour palettes, and the component library.

### Theeeme Colour Contrast

Every theeeme palette has been verified for WCAG contrast compliance across all six colour roles (koros section, primary and secondary buttons, body text). The table below summarises the results:

| Compliance | Theeemes |
|------------|----------|
| AAA for all colour roles | Bussi, Kupari, Engel, Hopea, Suomenlinna, M&V, Vaakuna |
| AAA for all roles except AA for normal text in koros section | Metro, Spåra |
| AAA for all roles except AA for normal text in primary button | Kesä, Sumu |
| AAA for all roles except AA for normal text in koros section and primary button | Kulta |

All theeemes meet AA or higher for every colour combination. No theeeme falls below AA for any role.

The app's own palette (`Braaanding`) lives in the database, so no test can see its values: the Django admin refuses to save one that fails 4.5:1 on any of those text-on-colour pairs (`Braaanding.clean`).

### HDS Accessibility Foundation

All UI components are sourced from the [Helsinki Design System](https://hds.hel.fi/), which is WCAG 2.1 AA audited. HDS provides accessible form controls (labels, error states, focus indicators), keyboard navigation, and screen reader support out of the box. Custom components follow HDS visual conventions and accessibility patterns.

### Implemented Measures

- **Semantic HTML** — proper heading hierarchy (`h1` for page titles, `h2` for sections), form elements with associated labels via HDS components
- **Decorative icons** — all HDS icons in info rows use `aria-hidden="true"` to avoid screen reader noise
- **Live regions** — toast notifications use `aria-live="polite"` for non-intrusive screen reader announcements
- **Accessible tooltips** — `TooltipButton` provides `aria-label` for icon-only actions
- **Image alt text** — thing thumbnails and gallery images include meaningful `alt` attributes derived from headlines
- **Page titles** — every page sets `document.title` via `useEffect` for meaningful browser tab titles and screen reader orientation
- **Language attribute** — `public/detect-lang.js` sets `<html lang>` synchronously before React mounts (mirroring `i18next-browser-languagedetector`'s own saved-choice → browser-language priority), so the very first paint and every crawler already see the right language; `App.jsx` keeps it in sync afterward via `i18n.on('languageChanged', ...)`. Outbound emails carry the same attribute on their own `<html>`, set from `resolve_email_language` (`core/services/email_service.py`)
- **Internationalisation** — all UI strings are externalised via `react-i18next` with automatic browser language detection (`i18next-browser-languagedetector`). Supported: English, Spanish, Catalan. Basque and Galician are paused (not deleted) and fall back to Spanish; Portuguese and any other unsupported language fall back to English

### Validation

Main pages are validated with [axe DevTools](https://www.deque.com/axe/devtools/) to detect WCAG violations. Automated accessibility checks are integrated into the frontend test suite via `jest-axe`.

## Contributing

**Pull requests are not being accepted for now** — one maintainer, and the time for reviewing outside code currently goes into finishing the product. Issues are welcome, though: bug reports, self-hosting problems, accessibility findings and translation corrections all get read. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Legal

The app ships a public **`/legal`** page (commitment, legal notice, privacy, basic terms — es/ca/en, following the UI language). Its content lives in `frontend/src/legal/{lang}.js` and is **per-deployment**:

- The standalone repo carries a **generic, operator-neutral** text. **If you self-host OIUEEI, you are the data controller of your instance**: edit those files with your identity, contact, legal bases and processors before inviting real users.
- A deployment replaces those files with its own legal text.

**Licence**: [EUPL-1.2](LICENSE). OIUEEI is licensed under the EUPL-1.2 — a strong copyleft licence that also covers use over a network. If you modify it and run it as a service, you owe your users the source. Production self-hosting is allowed; an unmodified deployment owes nothing beyond keeping the notices. The EUPL is published by the European Commission in 23 official languages of identical legal value, Spanish among them.

Everything published under the previous licence (Business Source License 1.1) keeps its Change Date and still converts to the MIT License on 2 February 2030. Everything from the relicensing onward is EUPL-1.2, which does not expire — so this is a wider grant than the BSL promised, not a narrower one.

### Need a hand running your own OIUEEI?

Self-hosting is allowed and encouraged. If you'd like help deploying your own instance, adapting it to your community, or building custom features on top of it, I offer exactly that as an on-demand service — write to **maintainer@oiueei.com** and tell me what you have in mind.

## Acknowledgements

This project uses components and design tokens from the [Helsinki Design System](https://hds.hel.fi/) by the [City of Helsinki](https://github.com/City-of-Helsinki), licensed under the [MIT License](https://github.com/City-of-Helsinki/helsinki-design-system/blob/master/LICENSE).

Instead of [Helsinki Grotesk](https://hds.hel.fi/foundation/design-tokens/typography/) by [Camelot Typefaces](https://camelot-typefaces.com) (the default shipped with HDS), we are using [Curiosa](https://fabiohaagtype.com/en/font/curiosa/) by [Fabio Haag Type](https://fabiohaagtype.com/en/) as the display typeface; a warm hug to the Haag team for their kindness.

QR codes for collection share links are rendered client-side with [qrcode.react](https://github.com/zpao/qrcode.react) by Paul O'Shannessy, licensed under the [MIT License](https://github.com/zpao/qrcode.react/blob/main/LICENSE).

CSV files for bulk-adding things are parsed client-side with [PapaParse](https://github.com/mholt/PapaParse) by Matt Holt, licensed under the [MIT License](https://github.com/mholt/PapaParse/blob/master/LICENSE).

The backend test suite builds model fixtures with [factory_boy](https://github.com/FactoryBoy/factory_boy) and freezes time deterministically with [time-machine](https://github.com/adamchainz/time-machine) by Adam Johnson, both licensed under the [MIT License](https://github.com/FactoryBoy/factory_boy/blob/master/LICENSE) (development-only dependencies).

This project is co-written with [Claude Code](https://claude.ai/code) by [Anthropic](https://www.anthropic.com/).
