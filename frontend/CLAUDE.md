# OIUEEI Frontend Documentation

React frontend using HDS (Helsinki Design System) from npm with OIUEEI customization layer (fonts, colors, icons). Vite dev server on `localhost:3000`. All API requests are proxied to the Django backend on `localhost:8000`. All UI strings are in British English.

---

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | `HomePage` | Dashboard with collections overview and all things |
| `/login` | `LoginPage` | Email input form for requesting a magic link |
| `/logout` | `LogoutPage` | Clears localStorage tokens and redirects to `/login` |
| `/verify/:code` | `VerifyPage` | Processes magic link / RSVP verification |
| `/me` | `UserPage` | Own profile (fetches userCode from `/auth/me/` if needed) |
| `/me/edit` | `EditProfilePage` | Wizard to edit own profile |
| `/collections/new` | `CreateCollectionPage` | Wizard to create a new collection |
| `/collections/:code` | `CollectionPage` | Collection detail with things and invites |
| `/collections/:code/edit` | `EditCollectionPage` | Wizard to edit a collection |
| `/collections/:code/invites` | `ManageInvitesPage` | Wizard to manage collection invites |
| `/collections/:code/add-thing` | `AddThingPage` | Wizard to add a thing to a collection |
| `/collections/:code/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (from collection context) |
| `/collections/:code/edit-thing/:thingCode` | `EditThingPage` | Wizard to edit a thing (from collection context) |
| `/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (standalone) |
| `/things/:thingCode/edit` | `EditThingPage` | Wizard to edit a thing (standalone) |
| `/collections/:code/things/:thingCode/request` | `RequestThingPage` | Request page for date-based/order things (collection context) |
| `/things/:thingCode/request` | `RequestThingPage` | Request page for date-based/order things (standalone) |
| `/my-bookings` | `MyBookingsPage` | Lists user's booking requests with cancel option |
| `/welcome` | `WelcomePage` | Static informational page about OIUEEI |
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
- On `COLLECTION_REJECT` action: shows success `Notification` confirming the invitation was declined and the owner was notified. Shows "Go to login" button. No login/redirect.
- On success (with token): stores `token`, `refresh`, and `userCode` in `localStorage`. If `data.invited_collection` is present (COLLECTION_INVITE flow), navigates to `/collections/{code}` with `{ state: { fromInvite: true } }`; otherwise navigates to `/`.
- On failure: shows error `Notification` with helpful guidance and "Go to login" button (resolves dead-end for expired links).

### WelcomePage (`src/pages/WelcomePage.jsx`)

- Static informational page about OIUEEI.
- `← Home` link navigates to `/`.
- **Action buttons:** "Create collection" links to `/collections/new` and "Edit profile" links to `/me/edit`, both passing `{ state: { backPath: '/welcome', backLabel: 'Welcome' } }` for return navigation.

### HomePage (`src/pages/HomePage.jsx`)

- **APIs:** `GET /api/v1/auth/me/`, `GET /api/v1/collections/`, `GET /api/v1/invited-collections/`, `GET /api/v1/things/`, `GET /api/v1/invited-things/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- On 401/403: clears tokens and redirects to `/login`.
- Stores `userCode` in `localStorage` on successful fetch.
- Displays greeting, "Create collection" button linking to `/collections/new`, "Edit profile" button linking to `/me/edit`, and "My requests" button linking to `/my-bookings`.
- Shows inline lists of own collections and invited collections (headline, status, thing count, invite count) with links to `/collections/{code}`.
- Lists all things (own + invited) using the `ThingLinkbox` component in a responsive `things-grid` (3 columns, 2 at <=768px, 1 at <=430px), sorted by creation date descending.

### CollectionPage (`src/pages/CollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/` with `Bearer` token
- Redirects to `/login` if no token in `localStorage`.
- Handles 403 (not authorised) and 404 (not found) with specific error messages.
- Displays hero image (`hero_url`, falls back to `thumbnail_url`, then `image-m` placeholder), collection headline, description, and status.
- **Things** are rendered using the `ThingLinkbox` component (see below).
- **"Edit collection" button** visible only to collection owner, links to `/collections/{code}/edit`.
- **"Add thing" button** visible only to collection owner, links to `/collections/{code}/add-thing`.
- **"Manage guests" button** visible only to collection owner, links to `/collections/{code}/invites`.
- **Welcome Linkbox**: shown only when user arrives from a COLLECTION_INVITE flow (`location.state.fromInvite`). Links to `/welcome`. Disappears after first click. The "Home" back link is hidden while the Welcome Linkbox is visible. Uses `linkbox-full-width` CSS class for 100% width.
- **INACTIVE notice**: when the collection status is `INACTIVE` and the viewer is not the owner, a `Notification` informs them "This collection is currently inactive. Reservations are paused." Hold buttons are hidden.
- **Things grid**: responsive 3-column layout (2 columns at <=768px, 1 column at <=430px).
- Passes `collectionHeadline` and `collectionInactive` to each `ThingLinkbox` for back navigation context and reservation gating.

### ThingLinkbox (`src/components/ThingLinkbox.jsx`)

Reusable component for rendering a thing as an HDS `Card`. Used by `CollectionPage` and `HomePage`.

- **Card**: the component uses HDS `Card` (a `<div>`-based container) instead of `Linkbox`, since it contains interactive elements (buttons, links). The thumbnail and headline are wrapped in `<Link>` components for navigation to `ThingPage` (`/collections/{code}/things/{thingCode}` or `/things/{thingCode}`). No `stopPropagation` hacks needed.
- **Tags row** (before headline): HDS `Tag` components in a flex row showing:
  - **Type** tag (always): Gift, Sale, Order, Rental, Lend, Share.
  - **Requested** tag (owner only, `status === 'TAKEN'`): amber background.
  - **Inactive** tag (owner only, `status === 'INACTIVE'`): grey background.
  - **Unavailable** tag (owner only, `available === false`): red background.
  - **Pending questions** tag (owner only, `pending_questions > 0`): amber background — uses the `pending_questions` serializer field (count of unanswered FAQs).
- Displays thumbnail (or placeholder), headline, description, creation date, and fee (when present).
- **Owner bookings display** (date-based/order types only): fetches `GET /api/v1/things/{code}/calendar/` on mount. Shows future confirmed and pending bookings with requester name, date ranges, and status. The active pending booking (matching `thing.pending_booking`) is marked with `*`.
- **"Edit" button** (owner only): links to edit page (collection context or standalone).
- **"Remove from collection" button** (owner only, collection context): calls `POST /api/v1/collections/{code}/remove-thing/` and notifies parent via `onRemoveFromCollection`. The thing is not deleted, only unlinked.
- **Accept/Reject buttons** (owner only): When `thing.pending_booking` exists (PENDING booking code from serializer):
  - "Accept" → `POST /api/v1/bookings/{code}/accept/` → updates thing locally, finds next pending booking from local state, shows success toast.
  - "Reject" → `POST /api/v1/bookings/{code}/reject/` → updates thing locally, finds next pending booking from local state, shows success toast.
  - Both buttons are disabled while a booking action is in progress.
- **Reservation button** logic:
  - Owner's own things: no button (compares `thing.owner` with `userCode`).
  - `ACTIVE`: enabled "Hold" button.
  - `TAKEN`: disabled "Hold" button.
  - `INACTIVE`: no button.
- **Reservation request** adapts to thing type:
  - `GIFT_THING`, `SELL_THING` — button submits directly via `POST /api/v1/things/{code}/request/`, no extra fields.
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — button navigates to `RequestThingPage` for date selection.
  - `ORDER_THING` — button navigates to `RequestThingPage` for delivery date and quantity.
- **Back navigation**: passes `{ state: { backPath, backLabel } }` to RequestThingPage and ThingPage based on context (collection headline or home).

### ThingPage (`src/pages/ThingPage.jsx`)

Detail page for a thing with full information and FAQs section.

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/faq/` (FAQs), `POST /api/v1/things/{thingCode}/faq/` (ask question), `POST /api/v1/faq/{faqCode}/answer/` (answer), `POST /api/v1/faq/{faqCode}/hide/` and `/show/` (toggle visibility)
- Accessible from `/collections/:code/things/:thingCode` (collection context) or `/things/:thingCode` (standalone).
- Redirects to `/login` if no token in `localStorage`.
- **Tags row** (before headline): same HDS `Tag` components as ThingLinkbox (type, Taken, Inactive, Unavailable, Pending questions).
- Displays thumbnail, headline, description, creation date, fee, and photo gallery (`pictures_urls`).
- **Back link**: shows collection headline or "Home" depending on navigation context (via `location.state.backLabel`).
- **Owner actions:** "Edit" button links to edit page. Accept/Reject buttons when `pending_booking` exists.
- **Reservation:** Non-owners see "Hold" button. GIFT/SELL types submit directly; date-based and order types navigate to `RequestThingPage` with `{ state: { backPath, backLabel } }`.
- **FAQs section:**
  - Lists all FAQs with question, `questioner_name`, and answer. Hidden FAQs shown with reduced opacity (owner only).
  - **Owner:** inline `TextArea` to answer unanswered questions, "Hide"/"Show" toggle button per FAQ.
  - **Non-owner:** `Fieldset`-wrapped form to ask a new question.

### RequestThingPage (`src/pages/RequestThingPage.jsx`)

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/calendar/` (blocked periods for date-based types), `POST /api/v1/things/{thingCode}/request/` (submit request)
- Accessible from `/collections/:code/things/:thingCode/request` (collection context) or `/things/:thingCode/request` (standalone).
- Redirects to `/login` if no token in `localStorage`.
- **Back link**: uses `location.state.backPath` and `location.state.backLabel` passed from ThingLinkbox or ThingPage.
- **Page title**: `Hold: {thing.headline}` with fee display when present.
- **Form fields** adapt to thing type:
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — `DateInput` for start and end dates with blocked-date validation.
  - `ORDER_THING` — `DateInput` for delivery date + `NumberInput` for quantity.
- **Date validation**: `minDate` today, `maxDate` today + 90 days. Blocked dates fetched from calendar API.
- **Buttons**: Cancel (navigates back) + Hold (submits request).
- On success: navigates back to collection page or thing page.
- On error: toast notification (top-right, auto-close).

### MyBookingsPage (`src/pages/MyBookingsPage.jsx`)

- **API:** `GET /api/v1/my-bookings/` with `Bearer` token, `POST /api/v1/bookings/{code}/cancel/` to cancel
- Redirects to `/login` if no token in `localStorage`.
- Lists all booking requests made by the current user.
- Each booking card shows: thing type tag, status tag (Pending/Confirmed/Rejected/Cancelled/Expired), thing headline (linked to thing page), owner name, dates/quantity, and creation date.
- PENDING bookings show a "Cancel request" button.
- Accessible from HomePage via "My requests" button.

### LogoutPage (`src/pages/LogoutPage.jsx`)

- Clears `token`, `refresh`, and `userCode` from `localStorage` on mount.
- Navigates to `/login` immediately.

### AddThingPage (`src/pages/AddThingPage.jsx`)

- **API:** `POST /api/v1/things/` with `Bearer` token and `collection_code` in body
- Redirects to `/login` if no token in `localStorage`.
- 3-step wizard using HDS `StepByStep`:
  - **Step 1 (Type):** `Select` to choose thing type (Gift, Sale, Order, Rental, Lend, Share).
  - **Step 2 (Details):** `TextInput` for headline (required, max 64), `TextArea` for description, `TextInput` for thumbnail (Cloudinary ID, optional), `TextInput` for pictures (comma-separated IDs), `NumberInput` for fee (required for SELL/RENT/ORDER types, hidden for others).
  - **Step 3 (Summary):** Read-only summary, "Cancel" and "Create" buttons. Validates on submit.
- On success: navigates to `/collections/{code}`.
- On error: toast notification (top-right, auto-close).

### EditThingPage (`src/pages/EditThingPage.jsx`)

- **API:** `GET /api/v1/things/{thingCode}/` to load, `PATCH /api/v1/things/{thingCode}/` to save
- Accessible from `/collections/:code/edit-thing/:thingCode` or `/things/:thingCode/edit`.
- 3-step wizard using HDS `StepByStep` (same layout as AddThingPage).
- Pre-populates all fields from the existing thing.
- On success: navigates back to collection or home.

### EditProfilePage (`src/pages/EditProfilePage.jsx`)

- **API:** `GET /api/v1/auth/me/` to load, `GET /api/v1/theeemes/` to list themes, `PUT /api/v1/users/{userCode}/` to save
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- 2-step wizard using HDS `StepByStep`:
  - **Step 1 (Details):** `TextInput` for name, `TextArea` for headline (bio), `TextInput` for thumbnail and hero (Cloudinary IDs), `Select` for theeeme (from API).
  - **Step 2 (Summary):** Read-only summary, "Save" button.
- Pre-populates all fields from the current user profile.
- On success: navigates to `/`.

### ManageInvitesPage (`src/pages/ManageInvitesPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/` to load invites, `POST /api/v1/collections/{code}/invite/` to invite, `DELETE /api/v1/collections/{code}/invite/` to remove
- Accessible from `/collections/:code/invites`.
- 2-step wizard using HDS `StepByStep`:
  - **Step 1 (Current guests):** Lists current invites by name/email. Pending invites show "Pending" label with "Resend" and "Remove" buttons. Owner sees "Remove" button per accepted invite. "Back" button navigates to collection.
  - **Step 2 (Invite):** Owner sees email input + "Invite" button. Non-owners see a message. "Back" button navigates to collection.
- Each invite/remove/resend is an immediate API call (no final submit). Resend cleans up old RSVPs and creates fresh ones.

### EditCollectionPage (`src/pages/EditCollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/` to load, `PATCH /api/v1/collections/{code}/` to save
- Accessible from `/collections/:code/edit`.
- 2-step wizard using HDS `StepByStep`:
  - **Step 1 (Details):** `TextInput` for headline (required), `TextArea` for description, `TextInput` for thumbnail and hero (Cloudinary IDs), `Select` for status (ACTIVE/INACTIVE).
  - **Step 2 (Summary):** Read-only summary, "Cancel" and "Save" buttons.
- Pre-populates all fields from the existing collection.
- On success: navigates to `/collections/{code}`.

### CreateCollectionPage (`src/pages/CreateCollectionPage.jsx`)

- **API:** `POST /api/v1/collections/` with `Bearer` token
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- 2-step wizard using HDS `StepByStep`:
  - **Step 1 (Details):** `TextInput` for headline (required), `TextArea` for description, `TextInput` for thumbnail and hero (Cloudinary IDs).
  - **Step 2 (Summary):** Read-only summary, "Cancel" and "Create" buttons.
- On success: navigates to `/collections/{code}`.

### UserPage (`src/pages/UserPage.jsx`)

- **API:** `GET /api/v1/users/{userCode}/` with `Bearer` token
- Also serves as `/me` route: when no `userCode` param, fetches `/api/v1/auth/me/` to resolve own code.
- Redirects to `/login` if no token in `localStorage`.
- Handles 403 (no permission) and 404 (user not found) with specific error messages.
- Displays hero image, avatar, user name (or email fallback), headline, email tag (own profile only), and "Member since" date.
- Own profile shows "Edit profile" button.

---

## Shared Modules

### API Service (`src/services/api.js`)

- `apiFetch(url, options)` — Centralised fetch wrapper. Adds `Authorization: Bearer` header from localStorage, sets `Content-Type: application/json` for requests with body. On 401: clears tokens and redirects to `/login`.

### Shared Components

- **`BackLink`** (`src/components/BackLink.jsx`) — Reusable `← {label}` back navigation link. Props: `to`, `label`.
- **`Toast`** (`src/components/Toast.jsx`) — Reusable toast notification wrapping HDS `Notification`. Props: `toast` (`{ type, message }`), `onClose`. Renders at `position="top-right"` with auto-close.
- **`ThingTags`** (`src/components/ThingTags.jsx`) — Shared tag row for thing type, status, availability, and pending questions. Props: `thing`, `isOwner`. Uses `TAG_THEMES` from constants.

### Constants (`src/constants/things.js`)

Central source of truth for thing type definitions:
- `TYPE_OPTIONS` — Array of `{ label, value }` for Select dropdowns.
- `TYPE_LABELS` — Map from type value to display label.
- `DATE_TYPES` — Types requiring start/end dates (`LEND_THING`, `RENT_THING`, `SHARE_THING`).
- `ORDER_TYPE` — `ORDER_THING` constant.
- `FEE_TYPES` — Types with a fee field (`SELL_THING`, `RENT_THING`, `ORDER_THING`).
- `TAG_THEMES` — Theme objects for status tags (taken, inactive, unavailable, pending).

---

## Tech Stack

- **React 19** + **Vite 7** + **React Router 7**
- **hds-react** — Helsinki Design System React components (npm `^4.10.0`)
- **hds-design-tokens** — HDS CSS custom property tokens (npm `^4.10.0`)
- **hds-core** — HDS core CSS and base styles (npm `^4.10.0`)

## OIUEEI Customization Layer

The project consumes HDS directly from npm and applies three local overrides:

- **Fonts** (`src/fonts/oiueei-fonts.css`) — GraebenbachTRIAL `.otf` files registered as `font-family: HelsinkiGrotesk` so all HDS components use them transparently.
- **Colors** (`src/styles/oiueei-theme.css`) — CSS custom property overrides for the "Theeemes" color palette, imported after `hds-design-tokens` to take precedence.
- **Custom icons** (`src/components/icons/`) — Any icons not available in HDS. Follow HDS icon prop conventions (`size`, `color`, `className`).
- **Logos & brand assets** (`src/assets/`) — OIUEEI logos, placeholders, and favicon.

## Key Configuration (`vite.config.js`)

- **React deduplication** — Aliases `react` and `react-dom` to frontend's `node_modules` to prevent dual-copy hook errors (some HDS internal deps declare React 17 peer dep)
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
