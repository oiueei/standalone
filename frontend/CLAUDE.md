# OIUEEI Frontend Documentation

React frontend using oiueeiDS (design system) with Vite dev server on `localhost:3000`. All API requests are proxied to the Django backend on `localhost:8000`.

---

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | `HomePage` | Dashboard with collections overview and all things |
| `/login` | `LoginPage` | Email input form for requesting a magic link |
| `/logout` | `LogoutPage` | Clears localStorage tokens and redirects to `/login` |
| `/verify/:code` | `VerifyPage` | Processes magic link / RSVP verification |
| `/me` | `UserPage` | Own profile (fetches userCode from `/auth/me/` if needed) |
| `/collections` | `MyCollectionsPage` | Lists the user's own collections |
| `/collections/new` | `CreateCollectionPage` | Wizard to create a new collection |
| `/collections/:code` | `CollectionPage` | Collection detail with things and invites |
| `/collections/:code/add-thing` | `AddThingPage` | Wizard to add a thing to a collection |
| `/collections/:code/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (from collection context) |
| `/collections/:code/edit-thing/:thingCode` | `EditThingPage` | Wizard to edit a thing (from collection context) |
| `/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (standalone) |
| `/things/:thingCode/edit` | `EditThingPage` | Wizard to edit a thing (standalone) |
| `/invited-collections` | `InvitedCollectionsPage` | Lists collections the user has been invited to |
| `/:userCode` | `UserPage` | Displays a user's public profile |

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
- On `COLLECTION_REJECT` action: shows success `Notification` confirming the invitation was declined and the owner was notified. No login/redirect.
- On success (with token): stores `token`, `refresh`, and `userCode` in `localStorage`, navigates to `/`.
- On failure: shows error `Notification`.

### HomePage (`src/pages/HomePage.jsx`)

- **APIs:** `GET /api/v1/auth/me/`, `GET /api/v1/collections/`, `GET /api/v1/invited-collections/`, `GET /api/v1/things/`, `GET /api/v1/invited-things/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- On 401/403: clears tokens and redirects to `/login`.
- Stores `userCode` in `localStorage` on successful fetch.
- Displays greeting, links to own collections and invited collections with counts, and "Crear coleccion" button linking to `/collections/new`.
- Lists all things (own + invited) using the `ThingCard` component, sorted by creation date descending.

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
- **Things** are rendered using the `ThingCard` component (see below).
- **"Añadir cosa" button** visible only to collection owner, links to `/collections/{code}/add-thing`.
- **Invites section:** "Invitados (N)" heading is a clickable link that opens an oiueeiDS `Dialog`.
  - Lists invited users by `userCode`.
  - **Owner only:** "Eliminar" button per invite (`DELETE /api/v1/collections/{code}/invite/`), and email input + "Invitar" button (`POST /api/v1/collections/{code}/invite/`).
  - Duplicate invites are rejected by the backend (400).

### ThingCard (`src/components/ThingCard.jsx`)

Reusable component for rendering a thing as an oiueeiDS `Card`. Used by `CollectionPage` and `HomePage`.

- **Clickable card**: the entire card navigates to `ThingPage` on click (`/collections/{code}/things/{thingCode}` or `/things/{thingCode}`). Interactive elements (buttons, links) use `stopPropagation` to prevent navigation.
- Displays thumbnail (or placeholder), headline, description, type label, creation date, and fee (when present).
- **"Editar" button** (owner only): links to edit page (collection context or standalone).
- **"Eliminar" button** (owner only): calls `DELETE /api/v1/things/{code}/` and notifies parent via `onDelete`.
- **Accept/Reject buttons** (owner only): When `thing.pending_booking` exists (PENDING booking code from serializer):
  - "Aceptar" → `POST /api/v1/bookings/{code}/accept/` → updates thing status to `INACTIVE` locally, clears `pending_booking`, shows success toast.
  - "Rechazar" → `POST /api/v1/bookings/{code}/reject/` → updates thing status to `ACTIVE` locally, clears `pending_booking`, shows success toast.
  - Both buttons are disabled while a booking action is in progress.
- **Reservation button** logic:
  - Owner's own things: no button (compares `thing.owner` with `userCode`).
  - `ACTIVE`: enabled "Reservar" button.
  - `TAKEN`: disabled "Reservar" button.
  - `INACTIVE`: no button.
- **Reservation request** (`POST /api/v1/things/{code}/request/`) adapts to thing type:
  - `GIFT_THING`, `SELL_THING` — button submits directly, no extra fields.
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — button opens `Dialog` with `DateInput` for `start_date` / `end_date`.
  - `ORDER_THING` — button opens `Dialog` with `DateInput` for `delivery_date` + `NumberInput` for quantity.
- **Date validation**: `minDate` today, `maxDate` today + 90 days. Blocked dates (LEND/RENT/SHARE) fetched from calendar API.

### ThingPage (`src/pages/ThingPage.jsx`)

Detail page for a thing with full information and FAQs section.

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/faq/` (FAQs), `GET /api/v1/things/{thingCode}/calendar/` (blocked periods), `POST /api/v1/things/{thingCode}/faq/` (ask question), `POST /api/v1/faq/{faqCode}/answer/` (answer), `POST /api/v1/faq/{faqCode}/hide/` and `/show/` (toggle visibility)
- Accessible from `/collections/:code/things/:thingCode` (collection context) or `/things/:thingCode` (standalone).
- Redirects to `/login` if no token in `localStorage`.
- Displays thumbnail, headline, description, type, status, creation date, fee, and photo gallery (`pictures_urls`).
- **"Volver" link**: navigates back to collection or home depending on context.
- **Owner actions:** "Editar" button links to edit page. Accept/Reject buttons when `pending_booking` exists.
- **Reservation:** Non-owners see "Reservar" button with same dialog logic as ThingCard.
- **FAQs section:**
  - Lists all FAQs with question, `questioner_name`, and answer. Hidden FAQs shown with reduced opacity (owner only).
  - **Owner:** inline `TextArea` to answer unanswered questions, "Ocultar"/"Mostrar" toggle button per FAQ.
  - **Non-owner:** `Fieldset`-wrapped form to ask a new question.

### LogoutPage (`src/pages/LogoutPage.jsx`)

- Clears `token`, `refresh`, and `userCode` from `localStorage` on mount.
- Navigates to `/login` immediately.

### AddThingPage (`src/pages/AddThingPage.jsx`)

- **API:** `POST /api/v1/things/` with `Bearer` token and `collection_code` in body
- Redirects to `/login` if no token in `localStorage`.
- 3-step wizard using oiueeiDS `StepByStep`:
  - **Step 1 (Tipo):** `Select` to choose thing type (Regalo, Venta, Pedido, Alquiler, Prestamo, Compartir).
  - **Step 2 (Detalles):** `TextInput` for headline (required, max 64), `TextArea` for description, `TextInput` for thumbnail (Cloudinary ID, optional), `TextInput` for pictures (comma-separated IDs), `NumberInput` for fee (required for SELL/RENT/ORDER types, hidden for others).
  - **Step 3 (Resumen):** Read-only summary, "Cancelar" and "Crear" buttons. Validates on submit.
- On success: navigates to `/collections/{code}`.
- On error: toast notification (top-right, auto-close).

### EditThingPage (`src/pages/EditThingPage.jsx`)

- **API:** `GET /api/v1/things/{thingCode}/` to load, `PATCH /api/v1/things/{thingCode}/` to save
- Accessible from `/collections/:code/edit-thing/:thingCode` or `/things/:thingCode/edit`.
- 3-step wizard using oiueeiDS `StepByStep` (same layout as AddThingPage).
- Pre-populates all fields from the existing thing.
- On success: navigates back to collection or home.

### CreateCollectionPage (`src/pages/CreateCollectionPage.jsx`)

- **API:** `POST /api/v1/collections/` with `Bearer` token
- 2-step wizard using oiueeiDS `StepByStep`:
  - **Step 1 (Detalles):** `TextInput` for headline (required), `TextArea` for description, `TextInput` for thumbnail and hero (Cloudinary IDs).
  - **Step 2 (Resumen):** Read-only summary, "Cancelar" and "Crear" buttons.
- On success: navigates to `/collections/{code}`.

### InvitedCollectionsPage (`src/pages/InvitedCollectionsPage.jsx`)

- **API:** `GET /api/v1/invited-collections/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- Displays invited collections with headline, status, thing count, and invite count.
- Each collection links to `/collections/{code}`.

### UserPage (`src/pages/UserPage.jsx`)

- **API:** `GET /api/v1/users/{userCode}/` with `Bearer` token
- Also serves as `/me` route: when no `userCode` param, fetches `/api/v1/auth/me/` to resolve own code.
- Redirects to `/login` if no token in `localStorage`.
- Handles 403 (no permission) and 404 (user not found) with specific error messages.
- Displays user name and raw JSON profile data.

---

## Tech Stack

- **React 19** + **Vite 7** + **React Router 7**
- **oiueeiDS-react** — Design system components (local link to `../../oiueei-ds/packages/react`)
- **oiueeiDS-design-tokens** — CSS tokens (local link to `../../oiueei-ds/packages/design-tokens`)
- **hds-core** — Helsinki Design System core CSS (fonts and base styles)

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
