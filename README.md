## What is OIUEEI?

An open-source web application for people to share their belongings with friends and others around. Users can create collections (wishlists, gift lists, items for sale) and share them with friends who can then reserve items or ask questions.

## Authorship & Development

OIUEEI is designed and led by Carlos Alberto, a designer, and co-written with [Claude Code](https://claude.ai/code), Anthropic's command-line coding assistant. UI and UX design decisions, product scope, tone and voice, and the choice to build on HDS are Carlos Alberto's; Claude carries a large share of the Django, DRF, and React implementation under direction. Every commit involves Claude, is reviewed before it ships, and is signed with a `Co-Authored-By: Claude` trailer — the contribution history is fully transparent.

## Try it (and tell me what breaks)

OIUEEI is in **alpha**: nothing is finished, nothing is at 100%, and you'll find rough edges. That's exactly why your hands on it would help.

You can explore a live demo environment at **[oiueei.com/popin](https://www.oiueei.com/popin)** — instant access to a populated account so you can see what collections, things, and the different sharing modes look and feel like.

What I'm looking for is honest feedback from people willing to poke at it: things that confuse you, flows that break, words that don't make sense, design decisions you'd push back on. If something annoys you, that's signal.

**[→ Tell me what you found](https://tally.so/r/A76Xkz)** (2 minutes, no signup needed)

## Tech Stack

- **Backend**: Django 5.x + Django REST Framework
- **Frontend**: React (same repo, work in progress)
- **Auth**: Magic link authentication (passwordless for users, password enabled for admin access)
- **Database**: SQLite (dev), PostgreSQL (prod via `dj-database-url`)
- **Deployment**: Heroku (Procfile + `.python-version` included)
- **Static files**: WhiteNoise
- **PWA**: installable web app manifest + icons ("Add to Home Screen"); no service worker yet
- **Scheduled tasks**: one daily Heroku Scheduler job chains `expire_bookings`, `cleanup_rsvps`, `close_transfers`, `send_reminders`, `send_digests` and `stats_summary` (see [HEROKU.md](HEROKU.md))

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
- **Open source (MIT)** — Fully compatible with OIUEEI's open-source license.
- **Production-proven** — Used across hundreds of City of Helsinki digital services.
- **React-native support** — Aligns with our tech stack (React + Vite).

## Project Structure

```
config/
  settings/
    base.py          # Shared settings
    development.py   # Dev overrides (SQLite, DEBUG=True)
    production.py    # Prod overrides (PostgreSQL, security headers)
  urls.py            # Root URL config (admin at /oiueei-admin/)
  wsgi.py            # WSGI entry point (defaults to production)
core/
  models/            # User, Collection, Thing, FAQ, Theeeme, RSVP, BookingPeriod
  views/             # Auth, collections, things, bookings, FAQ, users
  serializers/       # DRF serializers per model
  services/          # Business logic layer
    email_service.py   # All email composition and sending (categorised opt-out pipeline)
    booking_service.py # Accept/reject booking logic (transaction.atomic)
  permissions.py     # Custom DRF permissions (IsThingOwner, IsCollectionOwner)
  validators.py      # Input validation (image IDs, headlines, etc.)
  utils.py           # ID generation, client IP, Cloudinary URLs
  pagination.py      # StandardResultsPagination (max 100)
  management/
    commands/
      expire_bookings.py  # Batch expire stale PENDING bookings
      cleanup_rsvps.py    # Delete expired RSVPs (24h+)
      close_transfers.py  # Close overdue loan transfers
      send_reminders.py   # Daily booking/delivery reminders
      send_digests.py     # Weekly/monthly digest emails
      stats_summary.py    # First-party product stats (stdout + Monday email)
      backfill_events.py  # One-off: seed the Event log from existing rows
      seed_demo.py        # Populate demo data (idempotent; --lang=en|es)
      seed_data/
        common.py         # non-translatable (transfers)
        en.py             # English demo content
        es.py             # Spanish demo content
  tests/
    unit/            # Model, serializer, validator, security tests
    integration/     # View and booking integration tests
    scenarios/       # End-to-end user flow tests
```

## Data Models

| Model | Purpose |
|-------|---------|
| **User** | Custom user with `code` as PK (6-char alphanumeric). Magic link auth, no passwords. `notify_activity` (default on) and `notify_news` (default off — an explicit opt-in, DESIGN §6) control Cat. 2 / Cat. 3 email delivery (magic links and invitations are always sent). Optional profile extras: `about` (free Markdown bio) and `photo` (Cloudinary profile photo, exposed as `photo_url`) |
| **Collection** | Lists of things owned by a user. Shared via M2M `invites`. FK to `Theeeme`. Mode: PROPRIETARY (only owner adds things) or COMMUNITY (invited users can add their own things). `is_swap` flag enables item swapping (COMMUNITY only). `is_share` flag restricts to SHARE_THING only (COMMUNITY only, mutually exclusive with `is_swap`). `newsletter_enabled` sends weekly activity newsletter on Mondays (requires `is_share`). `share_token` is a 22-char URL-safe bearer credential generated on demand for the public `/share/{token}` link — never exposed in any read serializer. `tags` is an owner-defined free-text tag vocabulary (max 12) that the collection's things can be tagged with; removing a tag here cascade-strips it from those things. |
| **Thing** | Items in collections. Types: GIFT_THING, SELL_THING, RENT_THING, LEND_THING, SHARE_THING, WISH_THING, SWAP_THING. `status` controls both visibility and reservation state (ACTIVE/TAKEN/INACTIVE). WISH_THING ("Pedido") is a request a member posts on a community board: instead of a reservation it collects structured `WishResponse` answers; resolving it sets `status=INACTIVE` so it leaves the active board. WISH_THING and SHARE_THING are restricted to COMMUNITY collections. SHARE_THING transfers ownership to the requester on booking acceptance; after the first transfer, only the collection owner can hide it. SWAP_THING enables item swapping in swap collections (`is_swap=True`); requester offers own things, on acceptance all things transfer ownership bilaterally. `gallery` JSONField holds up to 8 additional photos (exposed as `gallery_urls`), shown as an image carousel. For date-based types (LEND/RENT), `available_today`/`next_available` expose live availability computed from the booking calendar. `tags` holds owner-defined labels chosen from the collection's `tags` vocabulary, shown as HDS Tags on the card and detail |
| **FAQ** | Questions/answers about things. FK to Thing and User (questioner) |
| **Theeeme** | Colour palettes (6 HDS colour token names) for customising collections |
| **RSVP** | One-time-use tokens (24h expiry) for auth and email actions. FK to User |
| **BookingPeriod** | Unified booking model for all thing types (72h expiry). FKs to Thing, User (requester), User (owner). `offered_things` M2M for SWAP_THING exchange proposals |
| **WishResponse** | An answer to a wish (WISH_THING). FK to Thing (`wish`) and User (`responder`). `kind`: HAVE_THIS (links a real listing via FK `thing`), KNOW_WHERE (text + `url`), CAN_MAKE (text + `fee`). `status`: PENDING or ACCEPTED. The creator accepts one answer; accepting is scoped to the answer, not the wish |
| **Event** | Append-only first-party analytics log. Text **snapshots** (`actor_code`/`collection_code`/`thing_code`), not FKs, so rows outlive hard-deleted objects. `kind` covers the tracked actions (user joined, collection/thing added/removed, member joined/left, FAQ asked, hold requested/accepted). Written by one-line instrumentation next to the notification/email each action already fires; consumed only by `stats_summary`. Never exposed to users |
| **DailyActivity** | One `(user, date)` row per user per active day, written by `DailyActivityMiddleware` (cache-gated to ≤1 DB write per user per day). Powers WAU/MAU and retention. Records less than the web-server logs already hold and never leaves our DB |

## Key Relationships

All relationships use proper Django ForeignKey and ManyToManyField:

- `Collection.owner` -> FK to User
- `Collection.things` -> M2M to Thing (via `collection_things` table)
- `Collection.invites` -> M2M to User (via `collection_invites` table)
- `Collection.theeeme` -> FK to Theeeme (PROTECT)
- `Thing.owner` -> FK to User
- `Thing.deal` -> M2M to User (via `thing_deals` table)
- `WishResponse.wish` -> FK to Thing (a WISH_THING; reverse `responses`)
- `WishResponse.responder` -> FK to User (reverse `wish_responses`)
- `WishResponse.thing` -> FK to Thing (the offered listing, HAVE_THIS only; SET_NULL)
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
| POST | `/api/v1/auth/request-link/` | Request magic link (rate limited: 5/min) |
| POST | `/api/v1/auth/pop-in/` | Open-door onboarding: get_or_create user, add to onboarding collections OR (if `share_token` provided) to that shared collection, send magic link (rate limited: 5/min) |
| GET / POST | `/api/v1/auth/verify/{rsvp_code}/` | Verify magic link / process an RSVP action (rate limited: 10/min). Booking accept/reject only **preview** on GET and require a **POST** to commit, so an email link-scanner or prefetch can't auto-decide a hold; login/invite actions resolve on GET |
| GET / POST | `/api/v1/rsvp/{rsvp_code}/` | Alias for verify endpoint |
| POST | `/api/v1/auth/refresh/` | Rotate access/refresh tokens via HttpOnly cookies |
| GET | `/api/v1/auth/me/` | Get authenticated user |
| POST | `/api/v1/auth/logout/` | Log out (clears auth cookies) |

### Users
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/users/{user_code}/` | View profile (requires collection connection) |
| PUT | `/api/v1/users/{user_code}/` | Update own profile (name, headline, `about` Markdown bio, `photo`, koro, theeeme, `notify_activity`, `notify_news`) |
| GET | `/api/v1/notifications/token/{token}/` | Read `notify_activity`/`notify_news` via signed token (no login required; linked from every Cat. 2/3 email footer) |
| PATCH | `/api/v1/notifications/token/{token}/` | Update `notify_activity`/`notify_news` via signed token |

### Collections (ModelViewSet + Router)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/collections/` | List own collections |
| POST | `/api/v1/collections/` | Create collection |
| GET | `/api/v1/collections/{code}/` | View collection (owner or invited) |
| PUT | `/api/v1/collections/{code}/` | Update collection (owner only) |
| DELETE | `/api/v1/collections/{code}/` | Delete collection (owner only) |
| POST | `/api/v1/collections/{code}/add-thing/` | Add thing to collection (owner; invited users in COMMUNITY mode) |
| POST | `/api/v1/collections/{code}/remove-thing/` | Remove thing from collection (owner; thing owner in COMMUNITY mode) |
| POST | `/api/v1/collections/{code}/invite/` | Invite user (owner only, resend-safe) |
| DELETE | `/api/v1/collections/{code}/invite/` | Remove invitee (owner only) |
| POST | `/api/v1/collections/{code}/share-link/` | Generate or rotate the public share token (owner only). Returns `share_url` and `share_token`. Pass `{"rotate": true}` to force a fresh token. Rate limited: 30/h. |
| DELETE | `/api/v1/collections/{code}/share-link/` | Revoke the public share token (owner only) |
| GET | `/api/v1/invited-collections/` | List collections where invited |
| GET | `/api/v1/my-invitations/` | List my pending collection invitations |
| POST | `/api/v1/collections/{code}/leave/` | Leave a collection you're invited to (self-unlink) |
| POST | `/api/v1/collections/{code}/invite/bulk/` | Bulk-invite guests from a CSV (owner only, rate limited: 5/h) |
| GET | `/api/v1/collections/{code}/stats/` | Download a 90-day activity CSV (owner only) |
| POST | `/api/v1/collections/{code}/broadcast/` | Send a message to all invitees (owner only) |
| POST | `/api/v1/collections/{code}/things/bulk/` | Bulk-create things from a CSV (rate limited: 10/h) |

### Things (ModelViewSet + Router)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/things/` | List own things |
| POST | `/api/v1/things/` | Create thing (`WISH_THING` may set `notify_group`, default true, to email the collection group) |
| GET | `/api/v1/things/{code}/` | View thing (owner or invited) |
| PUT | `/api/v1/things/{code}/` | Update thing (owner only) |
| DELETE | `/api/v1/things/{code}/` | Delete thing (owner only) |
| POST | `/api/v1/things/{code}/request/` | Request reservation (invited only) |
| GET | `/api/v1/things/{code}/calendar/` | View booking calendar (LEND/RENT/SHARE) |
| GET | `/api/v1/things/{code}/transfers/` | View transfer history and stats (Loan Chain). For SHARE_THING in COMMUNITY collections, includes `original_owner`, `original_owner_name`, and `is_share_in_community` fields |
| GET | `/api/v1/things/{code}/responses/` | List answers to a wish (creator sees all; a responder sees their own) |
| POST | `/api/v1/things/{code}/responses/` | Answer a wish — `kind` HAVE_THIS / KNOW_WHERE / CAN_MAKE (invited, not owner; rate limited: 20/h). Emails the creator |
| POST | `/api/v1/things/{code}/resolve/` | Mark a wish resolved (creator only): hides it from the active board and thanks the accepted responder |
| POST | `/api/v1/wish-responses/{code}/accept/` | Accept one answer to a wish (creator only) |
| POST | `/api/v1/things/{code}/activate/` | Reactivate an inactive thing (owner only) |
| POST | `/api/v1/things/{code}/hide/` | Set an active thing to inactive (owner only) |
| POST | `/api/v1/things/{code}/report/` | Report a listing anonymously (logged-in non-owners) |
| GET | `/api/v1/invited-things/` | List things from invited collections |

### Bookings
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/my-bookings/` | List my booking requests (with thing headline, owner name) |
| GET | `/api/v1/owner-bookings/` | List bookings for my things (with requester name) |
| POST | `/api/v1/bookings/{code}/accept/` | Accept a pending booking (owner only) |
| POST | `/api/v1/bookings/{code}/reject/` | Reject a pending booking (owner only) |
| POST | `/api/v1/bookings/{code}/cancel/` | Cancel own pending booking (requester only) |

### FAQ
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/things/{code}/faq/` | List FAQs for a thing |
| POST | `/api/v1/things/{code}/faq/` | Ask question (invited users only, not owner) |
| GET | `/api/v1/faq/{code}/` | View FAQ |
| POST | `/api/v1/faq/{code}/answer/` | Answer FAQ (owner only) |
| POST | `/api/v1/faq/{code}/hide/` | Hide FAQ (owner only) |
| POST | `/api/v1/faq/{code}/show/` | Show FAQ (owner only) |

### Other
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/inbox/` | List in-app notifications for the current user |
| DELETE | `/api/v1/inbox/{code}/` | Dismiss an in-app notification |
| POST | `/api/v1/upload/signature/` | Get a signed Cloudinary upload signature (rate limited: 30/h) |
| GET | `/api/v1/theeemes/` | List all available theeemes |
| GET | `/api/v1/health/` | Health check endpoint |
| - | `/oiueei-admin/` | Django Admin (requires password) |

**Note:** Reservation accept/reject actions can be performed via RSVP links sent by email or via authenticated API endpoints (`/bookings/{code}/accept/` and `/bookings/{code}/reject/`). Requesters can cancel their own pending bookings via `/bookings/{code}/cancel/`. Email links use RSVP codes as intermediaries to avoid exposing real codes in URLs.

## Deploying to Heroku

See [HEROKU.md](HEROKU.md) for a complete step-by-step guide covering buildpacks, config vars, font setup, and the deployment branch workflow.

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
#    Without it the Welcome page example collections and the /popin demo land on empty/404 pages.
#    (Lala, Lele, Lili, Lolo, Lulu and their collections — idempotent.)
python manage.py seed_demo                 # English (default)
python manage.py seed_demo --lang=es       # Spanish
python manage.py seed_demo --lang=es --reset   # wipe demos, re-seed in Spanish
# On Heroku (quote the inner command — the Heroku CLI otherwise grabs inner flags like --lang as its own):
#   heroku run --app <your-app> "python manage.py seed_demo --lang=es"
# Pass --reset to wipe existing demo data first (leaves other users/collections untouched).
# Adding a new language: copy core/management/commands/seed_data/en.py to e.g. ca.py,
# translate the text fields, add the code to SUPPORTED_LANGS in seed_demo.py.

# 4. Run the servers
python manage.py runserver                 # backend → http://localhost:8000
cd frontend && npm install && npm run dev  # frontend → http://localhost:3000 (separate terminal)

# 5. Tests & linting
pytest -v --cov=core --cov-fail-under=80   # backend tests
cd frontend && npm test                    # frontend tests (smoke + accessibility)
ruff check .                               # lint + import sort (replaces flake8 + isort)
ruff format .                              # formatting (replaces black)

# Create admin user
python manage.py createsuperuser

# Scheduled jobs (run via Heroku Scheduler in production — one daily job chains them)
python manage.py expire_bookings   # expire stale bookings
python manage.py cleanup_rsvps     # delete expired RSVPs (24h+)
python manage.py close_transfers   # close overdue loan transfers
python manage.py send_reminders    # return/delivery reminders (daily)
python manage.py send_digests      # weekly/monthly digest emails (daily)
python manage.py stats_summary     # product stats (prints daily; emails on STATS_EMAIL_WEEKDAY, default Monday)

# One-off: seed the Event analytics log from existing rows (idempotent).
# Run once, the day tracking ships, before forward events accumulate.
python manage.py backfill_events
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `JWT_SIGNING_KEY` | No | Signs JWTs independently of `DJANGO_SECRET_KEY`, so the two can be rotated separately (defaults to `DJANGO_SECRET_KEY` if unset). Setting/rotating it invalidates every issued access/refresh token — everyone re-logins via magic link — so change it deliberately, once, alongside a release. |
| `DJANGO_SETTINGS_MODULE` | No | Settings module (defaults to production) |
| `DJANGO_DEBUG` | No | Enables Django debug mode (default: `False` — fail-closed on a missing/typo'd value) |
| `DJANGO_ALLOWED_HOSTS` | No | Comma-separated allowed hosts |
| `DATABASE_URL` | Prod | PostgreSQL connection string |
| `MAGIC_LINK_BASE_URL` | Prod | Base URL for magic link emails (default in dev: `http://localhost:3000/verify`) |
| `CORS_ALLOWED_ORIGINS` | Prod | Comma-separated allowed origins |
| `CSRF_TRUSTED_ORIGINS` | Prod | Comma-separated trusted origins |
| `EMAIL_HOST` | Prod | SMTP host (default: smtp.sendgrid.net) |
| `EMAIL_PORT` | No | SMTP port (default: `587`) |
| `EMAIL_HOST_USER` | Prod | SMTP username |
| `EMAIL_HOST_PASSWORD` | Prod | SMTP password |
| `EMAIL_TIMEOUT` | No | SMTP socket timeout in seconds (default: `10`) — caps a slow/hung provider so it can't stall a web dyno |
| `EMAIL_LANGUAGE` | No | Language for ALL outbound email (`en`\|`es`\|`ca`; default `en`). Per-deployment, not per-user — catalogues live in `core/services/email_texts/`; unknown codes fall back to English |
| `VITE_FEEDBACK_URL` | No | Frontend build-time: points the in-app feedback link at your own form (default: the project's Tally form) |
| `DEFAULT_FROM_EMAIL` | Prod | Sender email address |
| `RSVP_BASE_URL` | Prod | Base URL for RSVP action links in emails (default in dev: `http://localhost:3000/rsvp`) |
| `SHARE_LINK_BASE_URL` | Prod | Base URL for public collection share links (default in dev: `http://localhost:3000/share`) |
| `CLOUDINARY_URL` | Uploads | Cloudinary credentials for image uploads: `cloudinary://api_key:api_secret@cloud_name` (free account at cloudinary.com) |
| `STATS_EMAIL` | No | Recipient for the weekly `stats_summary` command email (`--email` forces a send). Unset skips the email — third-party deploys don't email metrics anywhere by default. |
| `STATS_EMAIL_WEEKDAY` | No | Weekday for the weekly `stats_summary` email: 0=Monday (default) … 6=Sunday. |

## Onboarding & access

OIUEEI has no open public self-registration on its main model — accounts are created only by an owner's action. There are three distinct ways in:

- **`/login` — for people who already have an account.** Enter your email and receive a magic link. The endpoint always returns `200` (it never reveals whether an email is registered), but a link is only ever sent to an existing account; it never creates users.
- **Owner-controlled invites and public share links — the real membership model.** A collection owner either invites someone by email (the account is created when they accept) or enables a public `/share/{token}` link, with an optional QR code, that the owner can rotate or revoke. Anyone with that link joins only that one collection.
- **`/popin` — a separate, intentional demo gate.** It deliberately lets anyone in: it creates an account on the spot, adds them to the `is_onboarding` demo collections (Lala/Lele/Lili/Lolo/Lulu) and emails a magic link. This is how the live demo at [oiueei.com/popin](https://www.oiueei.com/popin) works; it is not open registration for the main product.

## Security

### Implemented Measures

| Category | Measure | Description |
|----------|---------|-------------|
| Authentication | Magic Link | Passwordless auth via email (24h expiry, one-time use) |
| Authentication | JWT | HttpOnly cookie-based. 1-hour access, 7-day refresh with rotation and blacklist |
| Authentication | Invite-Only | New accounts come from an owner's invitation to a collection or an owner-enabled public share link/QR. The `/popin` demo endpoint is a separate, intentional open onboarding gate. |
| Authentication | Admin 2FA | Django admin login requires a verified TOTP device (`django-otp` `OTPAdminSite`), on top of the password. Bootstrap the first device via `manage.py add_totp_device <email>`. |
| Authorization | DRF Permissions | Custom `IsThingOwner`, `IsCollectionOwner` permission classes |
| Authorization | IDOR Protection | Profile access only via collection connections |
| Input Validation | XSS Prevention | HTML escaped in emails via `django.utils.html.escape()`. Headlines sanitized |
| Input Validation | Image ID | Alphanumeric validation prevents path traversal |
| Rate Limiting | Auth | 5 req/min for magic link, 10 req/min for verify, 10 req/min for token refresh |
| Rate Limiting | Pop-in | 5 req/min per IP + 5 req/hour per email |
| Rate Limiting | Collection invite | 30 req/hour per user |
| Rate Limiting | Collection bulk invite | 5 req/hour per user |
| Rate Limiting | Collection share-link | 30 req/hour per user |
| Rate Limiting | Thing request | 10 req/hour per user |
| Rate Limiting | Thing bulk create | 10 req/hour per user |
| Rate Limiting | Thing report | 10 req/hour per user |
| Rate Limiting | Upload signature | 30 req/hour per user |
| Rate Limiting | Broadcast | 5 req/day per user |
| Rate Limiting | FAQ question | 20 req/hour per user |
| Rate Limiting | Wish response | 20 req/hour per user |
| Rate Limiting | Notifications token | GET 20/min, PATCH 10/min per IP |
| Rate Limiting | Thing single create | 60 req/hour per user |
| Rate Limiting | Collection single create | 30 req/hour per user |
| Rate Limiting | Collection add-thing | 60 req/hour per user |
| Rate Limiting | Wish response accept | 30 req/hour per user |
| Rate Limiting | Collection leave | 30 req/hour per user |
| Headers | HSTS | 1-year strict transport security with preload |
| Headers | X-Frame-Options | DENY (prevents clickjacking) |
| Headers | Content-Type | nosniff (prevents MIME confusion) |
| Headers | Referrer-Policy | strict-origin-when-cross-origin |
| Headers | Content-Security-Policy | Applied in every environment via `SecurityHeadersMiddleware` (`core/middleware.py`), plus a `Permissions-Policy` disabling camera/microphone/geolocation/payment |
| Production | SSL | Forced HTTPS redirect, secure cookies |
| Production | Admin Path | Custom path (`/oiueei-admin/`) instead of `/admin/` |
| Production | API Renderer | JSON-only in production (BrowsableAPI disabled) |
| Pagination | Max 100 | Prevents DoS via large page requests |

### Security Roadmap

- [ ] Email validation via AbstractAPI
- [ ] Audit logging to external service

## Privacy

OIUEEI does not sell or share user data with third parties. There is **no third-party analytics SDK** in the app: nothing is loaded, nothing is sent, no consent banner is needed. The only outbound data flows are the operational ones the user expects — email delivery via the configured SMTP provider, image hosting via Cloudinary, and the user's own session cookies.

Product metrics are **first-party only**: an append-only `Event` log and a `(user, date)` `DailyActivity` record, both computed into an aggregate `stats_summary` that is printed and emailed to the operator. They record less than the web-server logs already hold, never leave our DB, and are never wrapped in tracking pixels or redirect links. Demo/seed activity is reported separately so it can't inflate the real numbers.

Full ethical commitment and the rules I follow: [DESIGN.md §9](DESIGN.md#9-user-data-is-never-a-product).


## Architecture Decisions

- **Service layer**: Business logic extracted into `core/services/` (email composition, booking accept/reject/cancel with `transaction.atomic()`). Views are thin controllers.
- **ModelViewSet + Router**: Collections and Things use DRF ModelViewSet with DefaultRouter for standard CRUD. Custom actions use `@action` decorator.
- **Proper FK/M2M**: All relationships use Django ForeignKey and ManyToManyField (migrated from JSONField arrays). This enables `select_related`/`prefetch_related`, cascade deletes, and referential integrity.
- **Centralized email**: All email HTML composition lives in `email_service.py` with `django.utils.html.escape()` for XSS prevention. Every send is routed through a preference pipeline that filters Cat. 2 (activity) and Cat. 3 (news) based on `User.notify_activity` / `notify_news`; Cat. 1 (magic links, invitations, revokes) is always delivered. Non-mandatory emails carry a footer with a `TimestampSigner`-signed link to `/me/notifications/{token}` so recipients can toggle preferences without logging in (see `NotificationsByTokenView`).
- **RSVP intermediary**: All email action links use RSVP codes. Real entity codes are never exposed in URLs.
- **Seed data out of migrations**: Demo fixtures (Lala/Lele/Lili/Lolo/Lulu and their collections) live in `core/management/commands/seed_demo.py` + `seed_data/{lang}.py`, not in migrations. Fresh environments start with a clean DB and only get demo data when `python manage.py seed_demo` is run explicitly. The command is idempotent (`update_or_create` / `get_or_create`) and supports multiple languages (`--lang=en|es`, default English). Text content per language lives in its own module so you can switch the same DB between languages just by re-running the command. The old seed migrations (`0037`–`0076`) are retained as no-ops to preserve migration history.

## Default Data

- Default Theeemes (system baseline, seeded by migration `0036`): the 12 canonical palettes (Bussi, Engel, Hopea, Kesä, Kupari, Kulta, Metro, Sumu, Spåra, Suomenlinna, Vaakuna, M&V).
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

### HDS Accessibility Foundation

All UI components are sourced from the [Helsinki Design System](https://hds.hel.fi/), which is WCAG 2.1 AA audited. HDS provides accessible form controls (labels, error states, focus indicators), keyboard navigation, and screen reader support out of the box. Custom components follow HDS visual conventions and accessibility patterns.

### Implemented Measures

- **Semantic HTML** — proper heading hierarchy (`h1` for page titles, `h2` for sections), form elements with associated labels via HDS components
- **Decorative icons** — all HDS icons in info rows use `aria-hidden="true"` to avoid screen reader noise
- **Live regions** — toast notifications use `aria-live="polite"` for non-intrusive screen reader announcements
- **Accessible tooltips** — `TooltipButton` provides `aria-label` for icon-only actions
- **Image alt text** — thing thumbnails and gallery images include meaningful `alt` attributes derived from headlines
- **Page titles** — every page sets `document.title` via `useEffect` for meaningful browser tab titles and screen reader orientation
- **Language attribute** — `<html lang>` is set dynamically on the document root via `i18n.on('languageChanged', ...)` in `App.jsx`
- **Internationalisation** — all UI strings are externalised via `react-i18next` with automatic browser language detection (`i18next-browser-languagedetector`). Supported: English, Spanish, Catalan. Brazilian Portuguese, European Portuguese, Basque, and Galician are paused (not deleted) and fall back to Spanish

### Validation

Main pages are validated with [axe DevTools](https://www.deque.com/axe/devtools/) to detect WCAG violations. Automated accessibility checks are integrated into the frontend test suite via `jest-axe`.

## Acknowledgements

This project uses components and design tokens from the [Helsinki Design System](https://hds.hel.fi/) by the [City of Helsinki](https://github.com/City-of-Helsinki), licensed under the [MIT License](https://github.com/City-of-Helsinki/helsinki-design-system/blob/master/LICENSE).

Instead of [Helsinki Grotesk](https://hds.hel.fi/foundation/design-tokens/typography/) by [Camelot Typefaces](https://camelot-typefaces.com) (the default shipped with HDS), we are using [Curiosa](https://fabiohaagtype.com/en/font/curiosa/) by [Fabio Haag Type](https://fabiohaagtype.com/en/) as the display typeface; a warm hug to the Haag team for their kindness.

QR codes for collection share links are rendered client-side with [qrcode.react](https://github.com/zpao/qrcode.react) by Paul O'Shannessy, licensed under the [MIT License](https://github.com/zpao/qrcode.react/blob/main/LICENSE).

CSV files for bulk-adding things are parsed client-side with [PapaParse](https://github.com/mholt/PapaParse) by Matt Holt, licensed under the [MIT License](https://github.com/mholt/PapaParse/blob/master/LICENSE).

The backend test suite builds model fixtures with [factory_boy](https://github.com/FactoryBoy/factory_boy) and freezes time deterministically with [time-machine](https://github.com/adamchainz/time-machine) by Adam Johnson, both licensed under the [MIT License](https://github.com/FactoryBoy/factory_boy/blob/master/LICENSE) (development-only dependencies).

This project is co-written with [Claude Code](https://claude.ai/code) by [Anthropic](https://www.anthropic.com/).
