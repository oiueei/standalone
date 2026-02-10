# OIUEEI Frontend Documentation

React frontend using oiueeiDS (design system) with Vite dev server on `localhost:3000`. All API requests are proxied to the Django backend on `localhost:8000`.

---

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/login` | `LoginPage` | Email input form for requesting a magic link |
| `/verify/:code` | `VerifyPage` | Processes magic link verification, stores JWT, redirects to `/me` |
| `/me` | `HomePage` | Displays the authenticated user's own profile data |
| `/collections` | `MyCollectionsPage` | Lists the user's own collections |
| `/collections/:code` | `CollectionPage` | Collection detail with things (Card + reservation) and invites |
| `/invited-collections` | `InvitedCollectionsPage` | Lists collections the user has been invited to |
| `/:userCode` | `UserPage` | Displays a friend's public profile |

---

## Pages

### LoginPage (`src/pages/LoginPage.jsx`)

- **API:** `POST /api/v1/auth/request-link/` with `{ email }` and CSRF token
- Sends a magic link to the provided email address.
- After submission, replaces the form with a `Notification` component:
  - `success` — Magic link sent
  - `alert` — Email not found (404)
  - `error` — Server or network error
- CSRF token is read from the `csrftoken` cookie via `getCsrfToken()`.

### VerifyPage (`src/pages/VerifyPage.jsx`)

- **API:** `GET /api/v1/auth/verify/{code}/`
- Fetches on mount using the `:code` route parameter.
- On success: stores `token`, `refresh`, and `userCode` in `localStorage`, navigates to `/me`.
- On failure: shows error `Notification`.

### HomePage (`src/pages/HomePage.jsx`)

- **API:** `GET /api/v1/auth/me/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- On 401/403: clears tokens and redirects to `/login`.
- Stores `userCode` in `localStorage` on successful fetch (ensures existing sessions have it).
- Displays user name and raw JSON profile data.

### MyCollectionsPage (`src/pages/MyCollectionsPage.jsx`)

- **API:** `GET /api/v1/collections/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- Displays own collections with headline, status, thing count, and invite count.
- Each collection links to `/collections/{code}`.

### CollectionPage (`src/pages/CollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- Handles 403 (not authorised) and 404 (not found) with specific error messages.
- Displays collection headline, status, description, and theeeme.
- **Things** are rendered as oiueeiDS `Card` components (headline + description).
- **Reservation button** logic per thing:
  - Owner's own things: no button (compares `thing.owner` with `userCode` from `localStorage`).
  - `ACTIVE`: enabled "Reservar" button.
  - `TAKEN`: disabled "Reservar" button.
  - `INACTIVE`: no button.
- **Reservation request** (`POST /api/v1/things/{code}/request/`) adapts body to thing type:
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — date pickers for `start_date` / `end_date`.
  - `ORDER_THING` — date picker for `delivery_date` + quantity input.
  - `GIFT_THING`, `SELL_THING` — no extra fields.
- On success: button becomes disabled, toast notification (auto-close, top-right).
- On error (400, 409): toast notification with error message.

### InvitedCollectionsPage (`src/pages/InvitedCollectionsPage.jsx`)

- **API:** `GET /api/v1/invited-collections/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- Displays invited collections with headline, status, thing count, and invite count.
- Each collection links to `/collections/{code}`.

### UserPage (`src/pages/UserPage.jsx`)

- **API:** `GET /api/v1/users/{userCode}/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- Handles 403 (no permission) and 404 (user not found) with specific error messages.
- Displays user name and raw JSON profile data.

---

## Tech Stack

- **React 19** + **Vite 7** + **React Router 7**
- **oiueeiDS-react** — Design system components (local link to `../../oiueei-ds/packages/react`)
- **oiueeiDS-design-tokens** — CSS tokens (local link to `../../oiueei-ds/packages/design-tokens`)

## Key Configuration (`vite.config.js`)

- **Resolve aliases** for oiueeiDS packages pointing to `lib/` directories (local packages not built via npm)
- **React deduplication** — Aliases `react` and `react-dom` to frontend's `node_modules` to prevent dual-copy hook errors with oiueeiDS (React 17 peer dep vs React 19)
- **Proxy** — `/api` requests forwarded to `http://localhost:8000`
- **Dev server** on port 3000

## Authentication Flow

1. User enters email on `/login`
2. Backend sends magic link email pointing to `localhost:3000/verify/{rsvp_code}`
3. `/verify/:code` calls the backend, receives JWT tokens
4. Tokens stored in `localStorage` (`token`, `refresh`, `userCode`)
5. Authenticated pages send `Authorization: Bearer {token}` header
6. `userCode` is used to determine ownership (e.g. hide reservation button on own things)
7. CSRF cookie is obtained on app load via a GET to `/api/v1/auth/me/`
