# OIUEEI Frontend Documentation

React frontend using HDS (Helsinki Design System) from npm with OIUEEI customization layer (fonts, colors, icons). Vite dev server on `localhost:3000`. All API requests are proxied to the Django backend on `localhost:8000`. All UI strings are in British English.

---

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | `HomePage` | Dashboard with collections overview and all things |
| `/login` | `LoginPage` | Email input form for requesting a magic link |
| `/logout` | `LogoutPage` | Clears auth cookies and localStorage, redirects to `/login` |
| `/verify/:code` | `VerifyPage` | Processes magic link / RSVP verification |
| `/rsvp/:code` | `VerifyPage` | Alias for /verify/:code |
| `/me` | `UserPage` | Own profile (fetches userCode from `/auth/me/` if needed) |
| `/me/edit` | `EditProfilePage` | Edit own profile |
| `/collections/new` | `CreateCollectionPage` | Create a new collection |
| `/collections/:code` | `CollectionPage` | Collection detail with things and invites |
| `/collections/:code/edit` | `EditCollectionPage` | Edit a collection |
| `/collections/:code/invites` | `ManageInvitesPage` | Manage collection invites |
| `/collections/:code/add` | `AddThingPage` | Add a thing to a collection |
| `/collections/:code/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (from collection context) |
| `/collections/:code/things/:thingCode/edit` | `EditThingPage` | Edit a thing (from collection context) |
| `/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (standalone) |
| `/things/:thingCode/edit` | `EditThingPage` | Edit a thing (standalone) |
| `/collections/:code/things/:thingCode/request` | `RequestThingPage` | Request page for date-based/order things (collection context) |
| `/things/:thingCode/request` | `RequestThingPage` | Request page for date-based/order things (standalone) |
| `/collections/:code/things/:thingCode/delete` | `DeleteThingPage` | Confirm and delete a thing (collection context) |
| `/things/:thingCode/delete` | `DeleteThingPage` | Confirm and delete a thing (standalone) |
| `/collections/:code/invites/remove` | `RemoveGuestPage` | Confirm and remove a guest from a collection |
| `/my-bookings` | `MyBookingsPage` | Lists user's booking requests with cancel option |
| `/welcome` | `WelcomePage` | Static informational page about OIUEEI |
| `/:userCode` | `UserPage` | Displays a user's public profile |

---

## Page Titles

Every page sets `document.title` via `useEffect` for meaningful browser tab titles and bookmarks. Dynamic pages (CollectionPage, ThingPage, UserPage, etc.) update the title when data loads. Format: `{Page context} — OIUEEI`.

---

## Page Layout Pattern

All pages use a consistent `form-hero` + `Koros` layout (the HDS Hero component is not used):

```
form-page
├── form-hero          (full-width, theeeme color_03 background)
│   ├── form-hero-content  (max-width 1248px, text color from --hero-text-color CSS var using theeeme color_04)
│   │   └── [back link, title, description]
│   └── Koros          (HDS Koros component, type from user.koro preference, 60px height, fill = theeeme color_02)
└── page-container     (max-width 1248px, page content)
```

### Theeeme Color Roles

| Token | Role |
|-------|------|
| `color_01` | Primary buttons |
| `color_02` | Page background + Koros fill |
| `color_03` | Hero background |
| `color_04` | Hero text color (title, description, back-link) via `--hero-text-color` |
| `color_05` | Button label color |

All buttons across the app use theeeme colors (`btnStyle` for primary, `btnSecondaryStyle` for secondary).

Pages using this pattern: HomePage, CollectionPage, CreateCollectionPage, EditCollectionPage, EditProfilePage, ManageInvitesPage, MyBookingsPage, EditThingPage, ThingPage, WelcomePage, RequestThingPage, DeleteThingPage, RemoveGuestPage, UserPage.

---

## Pages

### LoginPage (`src/pages/LoginPage.jsx`)

- **API:** `POST /api/v1/auth/request-link/` with `{ email }` and CSRF token
- Uses the standard `form-hero` + `Koros` layout with theeeme colors from localStorage (if available from a previous session).
- Sends a magic link to the provided email address.
- After submission, replaces the form with a `Notification` component:
  - `success` — Unified message displayed (backend returns 200 regardless of email existence for anti-enumeration)
  - `error` — Server or network error
- CSRF token is read from the `csrftoken` cookie via `getCsrfToken()`.

### VerifyPage (`src/pages/VerifyPage.jsx`)

- **API:** `GET /api/v1/auth/verify/{code}/`
- Fetches on mount using the `:code` route parameter.
- On `COLLECTION_REJECT` action: shows success `Notification` confirming the invitation was declined and the owner was notified. Shows "Go to login" button. No login/redirect.
- On success: stores `userCode` in `localStorage`. Auth tokens are set as HttpOnly cookies by the backend. If `data.invited_collection` is present (COLLECTION_INVITE flow), navigates to `/collections/{code}` with `{ state: { fromInvite: true } }`; otherwise navigates to `/`.
- On failure: shows error `Notification` with helpful guidance and "Go to login" button (resolves dead-end for expired links).

### WelcomePage (`src/pages/WelcomePage.jsx`)

- Static informational page about OIUEEI.
- `← Home` link navigates to `/`.
- **Action buttons:** "Create collection" links to `/collections/new` and "Edit profile" links to `/me/edit`, both passing `{ state: { backPath: '/welcome', backLabel: 'Welcome' } }` for return navigation.
- Sets `seenWelcome = 'true'` in `localStorage` on mount, permanently suppressing the Welcome Linkbox on `CollectionPage` for this browser.

### HomePage (`src/pages/HomePage.jsx`)

- **APIs:** `GET /api/v1/auth/me/`, `GET /api/v1/things/`, `GET /api/v1/invited-things/`, `GET /api/v1/my-invitations/` (authenticated via HttpOnly cookies)
- Redirects to `/login` if no `userCode` in `localStorage`.
- On 401/403: clears `userCode` and redirects to `/login`.
- Stores `userCode`, `theeemeColors`, `koro`, and `seenWelcome` in `localStorage` on successful fetch. `seenWelcome` suppresses the first-time Welcome Linkbox on `CollectionPage`.
- Displays greeting, "Create collection" button linking to `/collections/new`, "My profile" button linking to `/me`, and "My requests" button linking to `/my-bookings`.
- **Pending invitations**: fetches `GET /api/v1/my-invitations/` on mount. Shows one dismissible HDS `Notification` (type `info`) per pending invite, above the things section. Each notification shows the owner name as label, collection headline in bold, and "Accept invitation" / "Decline invitation" links pointing to `/verify/{accept_code}` and `/verify/{reject_code}`. Dismissed notifications are removed from local state only (RSVP remains until acted on).
- **Things section**: lists all non-inactive own and invited things using the `ThingLinkbox` component in a responsive `things-grid` (3 columns, 2 at <=992px, 1 at <=576px), sorted by creation date descending.
- **Inactive things section**: shown only to the owner, below the Things section, when at least one own inactive thing exists. Lists all own `INACTIVE` things using the same `ThingLinkbox` component (invited things are never inactive for guests).

### CollectionPage (`src/pages/CollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/`
- Redirects to `/login` if no `userCode` in `localStorage`.
- Handles 403 (not authorised) and 404 (not found) with specific error messages.
- Displays hero image (`hero_url`, falls back to `thumbnail_url`, then `image-m` placeholder), collection headline, description, and status.
- **Things** are rendered using the `ThingLinkbox` component (see below).
- **"Edit collection" button** visible only to collection owner, links to `/collections/{code}/edit`.
- **"Add thing" button** visible only to collection owner, links to `/collections/{code}/add-thing`.
- **"Manage guests" button** visible only to collection owner, links to `/collections/{code}/invites`.
- **Welcome Linkbox**: shown only when user arrives from a COLLECTION_INVITE flow (`location.state.fromInvite`) AND `seenWelcome` is not set in `localStorage` (first-time users only). Links to `/welcome`. Disappears after first click. The "Home" back link is hidden while the Welcome Linkbox is visible. Uses `linkbox-full-width` CSS class for 100% width.
- **Owner attribution**: guests see "Owner. {name}" below the description in the hero, linking to `/{owner_code}` (the owner's public profile). Uses `owner_name` from `CollectionSerializer`.
- **INACTIVE notice**: when the collection status is `INACTIVE` and the viewer is the owner, a `Notification` informs them "This collection is inactive. It is not visible to guests." Guests cannot access inactive collections (backend returns 403).
- **Things section**: shows all non-inactive things for both owners and guests (responsive 3-column grid).
- **Inactive things section**: shown only to the owner, below the Things section, when at least one inactive thing exists. Lists all `INACTIVE` things using the same `ThingLinkbox` component.

### ThingLinkbox (`src/components/ThingLinkbox.jsx`)

Reusable component for rendering a thing as an HDS `Card`. Used by `CollectionPage` and `HomePage`.

- **Card**: the component uses HDS `Card` (a `<div>`-based container) instead of `Linkbox`, since it contains interactive elements (buttons, links). The thumbnail and headline are wrapped in `<Link>` components for navigation to `ThingPage` (`/collections/{code}/things/{thingCode}` or `/things/{thingCode}`). No `stopPropagation` hacks needed.
- **Tags row** (before headline): HDS `Tag` components in a flex row showing:
  - **Type** tag (always): Gift, Sale, Order, Rental, Lend, Share.
  - **Requested** tag (owner only, `status === 'TAKEN'`): amber background.
  - **Inactive** tag (owner only, `status === 'INACTIVE'`): grey background.
  - **Pending questions** tag (owner only, `pending_questions > 0`): amber background — uses the `pending_questions` serializer field (count of unanswered FAQs).
- Displays thumbnail (or placeholder with `srcSet` for @2x/@3x), headline, description, and info rows with HDS icons for type (`IconTicket`), price (`IconEuroSign`), availability (`IconCalendar`), location (`IconLocation`), and condition (`IconShield`). Uses a plain `<div>` container (not HDS Card) to avoid style conflicts with HDS Tag components.
- **Owner bookings display**: fetches `GET /api/v1/things/{code}/calendar/` on mount for date-based/order types and for any TAKEN thing (GIFT/SELL with a pending request). Shows future pending and confirmed bookings with requester name, request date, date ranges/delivery info, and status. Bookings with no dates (GIFT/SELL) are always shown regardless of date. The active pending booking is tracked in local `activePendingCode` state (initialised from `thing.pending_booking`, then synced to the first PENDING from the calendar on load) and marked bold with `*` when multiple pending exist.
- **Themed buttons**: all buttons use theeeme colors (`btnStyle` for primary, `btnSecondaryStyle` for secondary).
- **Owner button matrix** (based on `thing.status`):
  - `ACTIVE` (no pending hold): "Edit" (**primary**), "Hide" (secondary). "Hide" is suppressed when pending bookings exist.
  - `ACTIVE` (date-based/order with pending hold): "Confirm hold" (primary) + "Cancel hold" (secondary) targeting `activePendingCode`, then "Edit" (secondary).
  - `TAKEN`: "Confirm hold" (primary), "Cancel hold" (secondary), "Edit" (secondary). After each accept/cancel, `activePendingCode` advances to the next pending.
  - `INACTIVE`: "Reactivate" (primary, calls `POST /api/v1/things/{code}/activate/`), "Edit" (secondary), "Delete" (secondary, navigates to `DeleteThingPage` with `{ state: { backPath, backLabel } }`).
- **Reservation button** logic (non-owners only):
  - `ACTIVE`: enabled "Hold" button.
  - `TAKEN`: disabled button. Label is "Waiting for confirmation" if `thing.my_pending_booking` (or local `requested` state) is set, otherwise "Reserved".
  - `INACTIVE`: not shown (guests cannot see INACTIVE things).
- **Reservation request** adapts to thing type:
  - `GIFT_THING`, `SELL_THING` — button submits directly via `POST /api/v1/things/{code}/request/`, no extra fields.
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — button navigates to `RequestThingPage` for date selection.
  - `ORDER_THING` — button navigates to `RequestThingPage` for delivery date and quantity.
- **Back navigation**: passes `{ state: { backPath, backLabel } }` to RequestThingPage and ThingPage based on context (collection headline or home).

### ThingPage (`src/pages/ThingPage.jsx`)

Detail page for a thing with full information and FAQs section.

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/faq/` (FAQs), `POST /api/v1/things/{thingCode}/faq/` (ask question), `POST /api/v1/faq/{faqCode}/answer/` (answer), `POST /api/v1/faq/{faqCode}/hide/` and `/show/` (toggle visibility)
- Accessible from `/collections/:code/things/:thingCode` (collection context) or `/things/:thingCode` (standalone).
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Tags row** (before headline): same HDS `Tag` components as ThingLinkbox (type, Taken, Inactive, Pending questions).
- Displays thumbnail, headline, description, creation date, fee, availability, location, condition, and photo gallery (`pictures_urls`).
- **Back link**: shows collection headline or "Home" depending on navigation context (via `location.state.backLabel`).
- **Owner bookings display**: fetches `GET /api/v1/things/{thingCode}/calendar/` for date-based/order types and for any TAKEN thing (GIFT/SELL). Same logic as ThingLinkbox: filters past bookings, syncs `activePendingCode` to the first PENDING from the calendar, shows bookings list with requester name, request date, date ranges/delivery info, and status. Active pending booking is bold; starred when multiple pending exist.
- **Owner actions:** Full parity with ThingLinkbox button matrix:
  - `ACTIVE` (no pending): "Edit" (**primary**) + "Hide" (secondary, suppressed when pending bookings exist).
  - `ACTIVE` (date-based/order with pending): "Confirm hold" + "Cancel hold" + "Edit" (secondary).
  - `TAKEN`: "Confirm hold" (primary) → "Cancel hold" (secondary) → "Edit" (secondary). `activePendingCode` advances to next pending after each action.
  - `INACTIVE`: "Reactivate" (primary) + "Edit" (secondary) + "Delete" (secondary).
  - Delete navigates to `DeleteThingPage` with `{ state: { backPath, backLabel } }`.
- **Reservation:** Non-owners see "Hold" button. GIFT/SELL types submit directly; date-based and order types navigate to `RequestThingPage` with `{ state: { backPath, backLabel } }`.
- **FAQs section:**
  - Lists all FAQs with question, `questioner_name`, and answer. Hidden FAQs shown with reduced opacity (owner only).
  - **Owner:** inline `TextArea` to answer unanswered questions, "Hide"/"Show" toggle button per FAQ.
  - **Non-owner:** `Fieldset`-wrapped form to ask a new question.

### RequestThingPage (`src/pages/RequestThingPage.jsx`)

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/calendar/` (blocked periods for date-based types), `POST /api/v1/things/{thingCode}/request/` (submit request)
- Accessible from `/collections/:code/things/:thingCode/request` (collection context) or `/things/:thingCode/request` (standalone).
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Back link**: uses `location.state.backPath` and `location.state.backLabel` passed from ThingLinkbox or ThingPage.
- **Page title**: `Hold: {thing.headline}` with fee display when present.
- **Form fields** adapt to thing type:
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — `DateInput` for start and end dates with blocked-date validation.
  - `ORDER_THING` — `DateInput` for delivery date + `NumberInput` for quantity.
- **Date validation**: `minDate` today, `maxDate` today + 90 days. Blocked dates fetched from calendar API.
- **Buttons**: Cancel (navigates back) + Hold (submits request).
- On success: shows an inline HDS `Notification` ("You're all set! We've let the owner know — they'll get back to you soon.") with a "Back to {backLabel}" button. Does not navigate automatically.
- On error: toast notification (top-right, auto-close).

### DeleteThingPage (`src/pages/DeleteThingPage.jsx`)

- **API:** `GET /api/v1/things/{thingCode}/` (to display headline), `DELETE /api/v1/things/{thingCode}/` (to confirm delete)
- Accessible from `/collections/:code/things/:thingCode/delete` or `/things/:thingCode/delete`.
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Back link**: uses `location.state.backPath` and `location.state.backLabel` passed from ThingLinkbox, ThingPage, or EditThingPage.
- **Page title**: `Delete: {thing.headline}` in the hero.
- **Buttons**: Delete (primary, theeeme `btnStyle`) + Cancel (secondary, navigates back). No form fields.
- On success: navigates to `backPath`.
- On error: toast notification (top-right, auto-close).

### RemoveGuestPage (`src/pages/RemoveGuestPage.jsx`)

- **API:** `DELETE /api/v1/collections/{code}/invite/` with `{ user_code: guestCode }` body
- Accessible from `/collections/:code/invites/remove`.
- Redirects to `/login` if no `userCode` in `localStorage`. Redirects to invites page if `guestCode` state is missing.
- **State**: receives `{ guestCode, guestName, backLabel }` from `ManageInvitesPage`.
- **Page title**: `Remove: {guestName}` in the hero. Back link always goes to `/collections/:code/invites`.
- **Buttons**: Remove (primary, theeeme `btnStyle`) + Cancel (secondary, navigates back).
- On success: navigates to `/collections/:code/invites`.
- On error: toast notification (top-right, auto-close).

### MyBookingsPage (`src/pages/MyBookingsPage.jsx`)

- **API:** `GET /api/v1/my-bookings/`, `POST /api/v1/bookings/{code}/cancel/` to cancel
- Redirects to `/login` if no `userCode` in `localStorage`.
- Lists all booking requests made by the current user.
- Each booking card shows: thing type tag, status tag (Pending/Confirmed/Rejected/Cancelled/Expired), thing headline (linked to thing page), owner name, dates/quantity, and creation date.
- PENDING bookings show a "Cancel request" button.
- Accessible from HomePage via "My requests" button.

### LogoutPage (`src/pages/LogoutPage.jsx`)

- Calls `POST /api/v1/auth/logout/` to clear auth cookies on the backend.
- Clears `userCode` from `localStorage`.
- Navigates to `/login` immediately.

### AddThingPage (`src/pages/AddThingPage.jsx`)

- **API:** `POST /api/v1/things/` with `collection_code` in body
- Redirects to `/login` if no `userCode` in `localStorage`.
- Simple form with h1 title + `form-grid` layout:
  - `Select` for thing type, `TextInput` for headline (required, max 64), `TextArea` for description, `TextInput` for pictures (comma-separated IDs), `NumberInput` for fee (required for SELL/RENT/ORDER types, hidden for others). For GIFT/SELL/LEND/SHARE types (`DETAIL_TYPES`): `Select` for availability, `TextInput` for location (max 32), `Select` for condition.
  - "Create" button below the form. Validates on submit.
- On success: navigates to `/collections/{code}`.
- On error: toast notification (top-right, auto-close).

### EditThingPage (`src/pages/EditThingPage.jsx`)

- **API:** `GET /api/v1/things/{thingCode}/` to load, `PATCH /api/v1/things/{thingCode}/` to save, `DELETE /api/v1/things/{thingCode}/` to delete
- Accessible from `/collections/:code/things/:thingCode/edit` or `/things/:thingCode/edit`.
- Simple form with h1 title + `form-grid` layout (same fields as AddThingPage, including conditional availability/location/condition fields for `DETAIL_TYPES`).
- Pre-populates all fields from the existing thing.
- "Save" button (primary, full width) and "Delete" button (secondary, full width) below the form. Delete navigates to `DeleteThingPage` with `{ state: { backPath: returnPath, backLabel: returnLabel } }`.
- On success: navigates back to collection or home.

### EditProfilePage (`src/pages/EditProfilePage.jsx`)

- **API:** `GET /api/v1/auth/me/` to load, `GET /api/v1/theeemes/` to list themes, `PUT /api/v1/users/{userCode}/` to save
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- Simple form with h1 title + `form-grid` layout:
  - `TextInput` for name, `TextArea` for headline (bio), `Select` for theeeme (from API, shows theeeme `name` field as label), `Select` for koro (basic, beat, calm, pulse, vibration, wave).
  - "Save" button below the form.
- Pre-populates all fields from the current user profile.
- On success: navigates to `/`.

### ManageInvitesPage (`src/pages/ManageInvitesPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/` to load invites, `POST /api/v1/collections/{code}/invite/` to invite, `DELETE /api/v1/collections/{code}/invite/` to remove
- Accessible from `/collections/:code/invites`.
- Simple page with h1 title:
  - Lists current invites by name/email. Pending invites show "Pending" label with "Resend" and "Remove" buttons. Owner sees "Remove" button per accepted invite.
  - Owner sees email input + "Invite" button below the guest list.
- Resend is an immediate API call. Remove navigates to `RemoveGuestPage` with `{ state: { guestCode, guestName, backLabel } }`.
- Resend cleans up old RSVPs and creates fresh ones.

### EditCollectionPage (`src/pages/EditCollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/` to load, `PATCH /api/v1/collections/{code}/` to save
- Accessible from `/collections/:code/edit`.
- Simple form with h1 title + `form-grid` layout:
  - `TextInput` for headline (required), `TextArea` for description, `Select` for status (ACTIVE/INACTIVE).
  - "Save" button below the form.
- Pre-populates all fields from the existing collection.
- On success: navigates to `/collections/{code}`.

### CreateCollectionPage (`src/pages/CreateCollectionPage.jsx`)

- **API:** `POST /api/v1/collections/`
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- Simple form with h1 title + `form-grid` layout:
  - `TextInput` for headline (required), `TextArea` for description.
  - "Create" button below the form.
- On success: navigates to `/collections/{code}`.

### UserPage (`src/pages/UserPage.jsx`)

- **API:** `GET /api/v1/users/{userCode}/`
- Also serves as `/me` route: when no `userCode` param, fetches `/api/v1/auth/me/` to resolve own code.
- Redirects to `/login` if no `userCode` in `localStorage`.
- Handles 403 (no permission) and 404 (user not found) with specific error messages.
- Uses the standard `form-hero` + `Koros` layout with theeeme colors (own profile uses `theeeme_colors` from API, other profiles fall back to localStorage).
- Hero follows the WelcomePage pattern: BackLink, spacer, headline as Heading M subtitle, name as h1 title, "Member since" date.
- **Own profile:** shows "Edit profile" button in the hero, "My collections" (ACTIVE), "Inactive collections" (INACTIVE, only shown if any exist), and "Shared with me" sections below.
- **Other profiles:** shows "Collections in common" section with shared collections (where both users are connected as owner/invite) as HDS Linkbox components.

---

## Shared Modules

### API Service (`src/services/api.js`)

- `apiFetch(url, options)` — Centralised fetch wrapper. Uses `credentials: 'include'` for cookie-based auth, sets `Content-Type: application/json` for requests with body. On 401: silently attempts token refresh via `POST /api/v1/auth/refresh/`. Only `userCode` is stored in localStorage (for ownership checks).

### Shared Components

- **`BackLink`** (`src/components/BackLink.jsx`) — Reusable `← {label}` back navigation link. Props: `to`, `label`.
- **`Toast`** (`src/components/Toast.jsx`) — Reusable toast notification wrapping HDS `Notification`. Props: `toast` (`{ type, message }`), `onClose`. Renders at `position="top-right"` with auto-close.
- **`LoadingSpinner`** (`src/components/LoadingSpinner.jsx`) — Wrapper around HDS `LoadingSpinner` component.
- **`ThingTags`** (`src/components/ThingTags.jsx`) — Shared tag row for thing type, status, availability, and pending questions. Props: `thing`, `isOwner`. Uses `TAG_THEMES` from constants.

### Constants (`src/constants/things.js`)

Central source of truth for thing type definitions:
- `TYPE_OPTIONS` — Array of `{ label, value }` for Select dropdowns.
- `TYPE_LABELS` — Map from type value to display label.
- `DATE_TYPES` — Types requiring start/end dates (`LEND_THING`, `RENT_THING`, `SHARE_THING`).
- `ORDER_TYPE` — `ORDER_THING` constant.
- `FEE_TYPES` — Types with a fee field (`SELL_THING`, `RENT_THING`, `ORDER_THING`).
- `DETAIL_TYPES` — Types with availability/location/condition fields (`GIFT_THING`, `SELL_THING`, `LEND_THING`, `SHARE_THING`).
- `AVAILABILITY_OPTIONS` / `AVAILABILITY_LABELS` — Options and display labels for thing availability (Immediate, Next week, End of month, Next month).
- `CONDITION_OPTIONS` / `CONDITION_LABELS` — Options and display labels for thing condition (New, Good condition, Fair, Used, Well used, Almost junk).
- `TAG_THEMES` — Theme objects for status tags (taken, inactive, pending).

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
- **Logos & brand assets** (`src/assets/`) — OIUEEI logos, placeholders, and favicon.

## Key Configuration (`vite.config.js`)

- **React deduplication** — Aliases `react` and `react-dom` to frontend's `node_modules` to prevent dual-copy hook errors (some HDS internal deps declare React 17 peer dep)
- **Proxy** — `/api` requests forwarded to `http://localhost:8000`
- **Dev server** on port 3000

## Authentication Flow

1. User enters email on `/login`
2. Backend sends magic link email pointing to `localhost:3000/verify/{rsvp_code}`
3. `/verify/:code` calls the backend, which sets JWT tokens as HttpOnly cookies on the response
4. `userCode` is stored in `localStorage` (for ownership checks only — auth tokens are never in localStorage)
5. Authenticated pages use `credentials: 'include'` to send cookies automatically. On 401, `apiFetch` silently attempts token refresh via `POST /api/v1/auth/refresh/`
6. `userCode` is used to determine ownership (e.g. hide reservation button on own things)
7. CSRF cookie is obtained on app load via a GET to `/api/v1/auth/me/`
