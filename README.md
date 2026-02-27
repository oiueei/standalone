## What is OIUEEI?

An open-source web application for people to share their belongings with friends and others around. Users can create collections (wishlists, gift lists, items for sale) and share them with friends who can then reserve items or ask questions.

## Tech Stack

- **Backend**: Django 5.x + Django REST Framework
- **Frontend**: React (same repo, work in progress)
- **Auth**: Magic link authentication (passwordless for users, password enabled for admin access)
- **Database**: SQLite (dev), PostgreSQL (prod via `dj-database-url`)
- **Deployment**: Heroku (Procfile + runtime.txt included)
- **Static files**: WhiteNoise
- **Scheduled task**: `python manage.py expire_bookings` for booking expiration cleanup (run via Heroku Scheduler or cron)

## UI & Design System

OIUEEI's user interface is built on top of the [Helsinki Design System (HDS)](https://hds.hel.fi/), an open-source design system created by the City of Helsinki. We consume HDS at multiple levels:

- **React components** — via [`hds-react`](https://github.com/City-of-Helsinki/helsinki-design-system/tree/master/packages/react)
- **Design tokens** — colours, spacing, typography, and breakpoints from [`hds-design-tokens`](https://github.com/City-of-Helsinki/helsinki-design-system/tree/master/packages/design-tokens)
- **Core styles** — base CSS from [`hds-core`](https://github.com/City-of-Helsinki/helsinki-design-system/tree/master/packages/core)

### What we customise

HDS is designed for City of Helsinki services, so we adapt it to fit OIUEEI's context:

| Layer | HDS baseline | OIUEEI adaptation |
|---|---|---|
| Brand colours | Helsinki blue/black palette | Custom palette reflecting OIUEEI identity |
| Typography | HDS type scale | Same scale, different primary typeface (GraebenbachTRIAL) |
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
    email_service.py   # All email composition and sending (8 functions)
    booking_service.py # Accept/reject booking logic (transaction.atomic)
  permissions.py     # Custom DRF permissions (IsThingOwner, IsCollectionOwner)
  validators.py      # Input validation (image IDs, headlines, etc.)
  utils.py           # ID generation, client IP, Cloudinary URLs
  pagination.py      # StandardResultsPagination (max 100)
  management/
    commands/
      expire_bookings.py  # Batch expire stale PENDING bookings
  tests/
    unit/            # Model, serializer, validator, security tests
    integration/     # View and booking integration tests
    scenarios/       # End-to-end user flow tests
```

## Data Models

| Model | Purpose |
|-------|---------|
| **User** | Custom user with `code` as PK (6-char alphanumeric). Magic link auth, no passwords |
| **Collection** | Lists of things owned by a user. Shared via M2M `invites`. FK to `Theeeme` |
| **Thing** | Items in collections. Types: GIFT, SELL, ORDER, RENT, LEND, SHARE. `available` controls visibility, `status` controls reservation state (ACTIVE/TAKEN/INACTIVE) |
| **FAQ** | Questions/answers about things. FK to Thing and User (questioner) |
| **Theeeme** | Colour palettes (6 hex colours) for customising collections |
| **RSVP** | One-time-use tokens (24h expiry) for auth and email actions. FK to User |
| **BookingPeriod** | Unified booking model for all thing types (72h expiry). FKs to Thing, User (requester), User (owner) |

## Key Relationships

All relationships use proper Django ForeignKey and ManyToManyField:

- `Collection.owner` -> FK to User
- `Collection.things` -> M2M to Thing (via `collection_things` table)
- `Collection.invites` -> M2M to User (via `collection_invites` table)
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
| POST | `/api/v1/auth/request-link/` | Request magic link (rate limited: 5/min) |
| GET | `/api/v1/auth/verify/{rsvp_code}/` | Verify magic link or process any RSVP action (rate limited: 10/min) |
| GET | `/api/v1/auth/me/` | Get authenticated user |
| POST | `/api/v1/auth/logout/` | Log out (blacklists refresh token) |

### Users
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/users/{user_code}/` | View profile (requires collection connection) |
| PUT | `/api/v1/users/{user_code}/` | Update own profile |

### Collections (ModelViewSet + Router)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/collections/` | List own collections |
| POST | `/api/v1/collections/` | Create collection |
| GET | `/api/v1/collections/{code}/` | View collection (owner or invited) |
| PUT | `/api/v1/collections/{code}/` | Update collection (owner only) |
| DELETE | `/api/v1/collections/{code}/` | Delete collection (owner only) |
| POST | `/api/v1/collections/{code}/add-thing/` | Add thing to collection (owner only) |
| POST | `/api/v1/collections/{code}/remove-thing/` | Remove thing from collection (owner only) |
| POST | `/api/v1/collections/{code}/invite/` | Invite user (owner only, resend-safe) |
| DELETE | `/api/v1/collections/{code}/invite/` | Remove invitee (owner only) |
| GET | `/api/v1/invited-collections/` | List collections where invited |

### Things (ModelViewSet + Router)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/things/` | List own things |
| POST | `/api/v1/things/` | Create thing |
| GET | `/api/v1/things/{code}/` | View thing (owner or invited) |
| PUT | `/api/v1/things/{code}/` | Update thing (owner only) |
| DELETE | `/api/v1/things/{code}/` | Delete thing (owner only) |
| POST | `/api/v1/things/{code}/request/` | Request reservation (invited only) |
| GET | `/api/v1/things/{code}/calendar/` | View booking calendar (LEND/RENT/SHARE) |
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
| GET | `/api/v1/health/` | Health check endpoint |
| - | `/oiueei-admin/` | Django Admin (requires password) |

**Note:** Reservation accept/reject actions can be performed via RSVP links sent by email or via authenticated API endpoints (`/bookings/{code}/accept/` and `/bookings/{code}/reject/`). Requesters can cancel their own pending bookings via `/bookings/{code}/cancel/`. Email links use RSVP codes as intermediaries to avoid exposing real codes in URLs.

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env  # Configure environment variables

# Run backend server
python manage.py runserver

# Run frontend (in a separate terminal)
cd frontend
npm install
npm run dev  # Starts on http://localhost:3000

# Run tests
pytest -v --cov=core --cov-fail-under=80

# Linting
black .
isort .
flake8 .

# Migrations
python manage.py makemigrations core
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Expire stale bookings (run via Heroku Scheduler in production)
python manage.py expire_bookings
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `DJANGO_SETTINGS_MODULE` | No | Settings module (defaults to production) |
| `DJANGO_ALLOWED_HOSTS` | No | Comma-separated allowed hosts |
| `DATABASE_URL` | Prod | PostgreSQL connection string |
| `MAGIC_LINK_BASE_URL` | No | Base URL for magic link emails |
| `CORS_ALLOWED_ORIGINS` | Prod | Comma-separated allowed origins |
| `CSRF_TRUSTED_ORIGINS` | Prod | Comma-separated trusted origins |
| `EMAIL_HOST` | Prod | SMTP host (default: smtp.sendgrid.net) |
| `EMAIL_HOST_USER` | Prod | SMTP username |
| `EMAIL_HOST_PASSWORD` | Prod | SMTP password |
| `DEFAULT_FROM_EMAIL` | No | Sender email address |
| `RSVP_BASE_URL` | No | Base URL for RSVP action links in emails |
| `CLOUDINARY_CLOUD_NAME` | No | Cloudinary cloud name (default: oiueei) |

## Security

### Implemented Measures

| Category | Measure | Description |
|----------|---------|-------------|
| Authentication | Magic Link | Passwordless auth via email (24h expiry, one-time use) |
| Authentication | JWT | 1-hour access tokens, 7-day refresh with rotation and blacklist |
| Authentication | Invite-Only | New users must be invited to a collection first |
| Authorization | DRF Permissions | Custom `IsThingOwner`, `IsCollectionOwner` permission classes |
| Authorization | IDOR Protection | Profile access only via collection connections |
| Input Validation | XSS Prevention | HTML escaped in emails via `django.utils.html.escape()`. Headlines sanitized |
| Input Validation | Image ID | Alphanumeric validation prevents path traversal |
| Input Validation | Quantity Limit | Orders capped at 99 items max |
| Rate Limiting | Auth | 5 req/min for magic link, 10 req/min for verify |
| Headers | HSTS | 1-year strict transport security with preload |
| Headers | X-Frame-Options | DENY (prevents clickjacking) |
| Headers | Content-Type | nosniff (prevents MIME confusion) |
| Headers | Referrer-Policy | strict-origin-when-cross-origin |
| Production | SSL | Forced HTTPS redirect, secure cookies |
| Production | Admin Path | Custom path (`/oiueei-admin/`) instead of `/admin/` |
| Production | API Renderer | JSON-only in production (BrowsableAPI disabled) |
| Pagination | Max 100 | Prevents DoS via large page requests |

### Security Roadmap

- [ ] Email validation via AbstractAPI
- [ ] 2FA for admin users
- [ ] Audit logging to external service
- [ ] Content Security Policy (CSP) headers

## Architecture Decisions

- **Service layer**: Business logic extracted into `core/services/` (email composition, booking accept/reject/cancel with `transaction.atomic()`). Views are thin controllers.
- **ModelViewSet + Router**: Collections and Things use DRF ModelViewSet with DefaultRouter for standard CRUD. Custom actions use `@action` decorator.
- **Proper FK/M2M**: All relationships use Django ForeignKey and ManyToManyField (migrated from JSONField arrays). This enables `select_related`/`prefetch_related`, cascade deletes, and referential integrity.
- **Centralized email**: All email HTML composition lives in `email_service.py` with `django.utils.html.escape()` for XSS prevention.
- **RSVP intermediary**: All email action links use RSVP codes. Real entity codes are never exposed in URLs.

## Default Data

- Default Theeeme: "B4s1C0" (code: HDS000)

## Important Notes

- **Superadmin must be created manually** after running migrations:
  ```bash
  python manage.py createsuperuser
  ```
  This is required to access `/oiueei-admin/`. Regular users authenticate via magic link and don't need passwords.

- **Booking expiration** - PENDING bookings expire after 72 hours. Run `python manage.py expire_bookings` periodically (Heroku Scheduler recommended).

## Acknowledgements

This project uses components and design tokens from the [Helsinki Design System](https://hds.hel.fi/) by the [City of Helsinki](https://github.com/City-of-Helsinki), licensed under the [MIT License](https://github.com/City-of-Helsinki/helsinki-design-system/blob/master/LICENSE).