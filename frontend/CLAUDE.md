# OIUEEI Frontend Documentation

React frontend using oiueeiDS (design system) with Vite dev server on `localhost:3000`. All API requests are proxied to the Django backend on `localhost:8000`.

---

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/login` | `LoginPage` | Email input form for requesting a magic link |
| `/logout` | `LogoutPage` | Clears localStorage tokens and redirects to `/login` |
| `/verify/:code` | `VerifyPage` | Processes magic link verification, stores JWT, redirects to `/me` |
| `/me` | `HomePage` | Displays the authenticated user's own profile data |
| `/collections` | `MyCollectionsPage` | Lists the user's own collections |
| `/collections/:code` | `CollectionPage` | Collection detail with things (Card + reservation) and invites |
| `/collections/:code/add-thing` | `AddThingPage` | 3-step wizard to add a thing to a collection |
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
- **Things** are rendered as oiueeiDS `Card` components with thumbnail image (or oiueeiDS `image-s.png` placeholder when no thumbnail), headline, description, and fee (when present).
- **"Añadir cosa" button** visible only to collection owner (`localStorage.userCode === collection.owner`), links to `/collections/{code}/add-thing`.
- **Reservation button** logic per thing:
  - Owner's own things: no button (compares `thing.owner` with `userCode` from `localStorage`).
  - `ACTIVE`: enabled "Reservar" button.
  - `TAKEN`: disabled "Reservar" button.
  - `INACTIVE`: no button.
- **Reservation request** (`POST /api/v1/things/{code}/request/`) adapts body to thing type:
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — oiueeiDS `DateInput` for `start_date` / `end_date`.
  - `ORDER_THING` — oiueeiDS `DateInput` for `delivery_date` + oiueeiDS `NumberInput` for quantity.
  - `GIFT_THING`, `SELL_THING` — no extra fields.
- **Date validation rules** (all `DateInput` components):
  - `minDate`: today (cannot select past dates).
  - `maxDate`: today + 90 days.
  - Error text shown when date is outside range.
  - Required fields show error on submit attempt if empty.
- **Blocked dates** (LEND/RENT/SHARE only): fetches `GET /api/v1/things/{code}/calendar/` on mount to get existing PENDING/ACCEPTED booking periods, disables those dates via `isDateDisabledBy`. Manual entry of a blocked date shows "La fecha se solapa con otra reserva."
- On success: button becomes disabled, toast notification (auto-close, top-right).
- On error (400, 409): toast notification with error message.

### LogoutPage (`src/pages/LogoutPage.jsx`)

- Clears `token`, `refresh`, and `userCode` from `localStorage` on mount.
- Navigates to `/login` immediately.

### AddThingPage (`src/pages/AddThingPage.jsx`)

- **API:** `POST /api/v1/things/` with `Bearer` token and `collection_code` in body
- Redirects to `/login` if no token in `localStorage`.
- 3-step wizard using oiueeiDS `Stepper` with `StepState` enum:
  - **Step 1 (Tipo):** `Select` to choose thing type (Regalo, Venta, Pedido, Alquiler, Prestamo, Compartir).
  - **Step 2 (Detalles):** `TextInput` for headline (required, max 64), `TextArea` for description, `TextInput` for thumbnail (Cloudinary ID, optional), `TextInput` for pictures (comma-separated IDs), `NumberInput` for fee (required for SELL/RENT/ORDER types, hidden for others).
  - **Step 3 (Resumen):** Read-only summary of all fields, "Crear" button to submit.
- Validates required fields (headline, fee for SELL/RENT/ORDER) before advancing from step 2.
- On success: navigates to `/collections/{code}`.
- On error: toast notification (top-right, auto-close).

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
