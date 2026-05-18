# OIUEEI Frontend Documentation

React frontend using HDS (Helsinki Design System) from npm with OIUEEI customization layer (fonts, colors, icons). Vite dev server on `localhost:3000`. All API requests are proxied to the Django backend on `localhost:8000`. All UI strings are externalised via `react-i18next` (British English, `src/i18n/locales/en.json`).

---

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | `HomePage` | Dashboard: My collections + Shared with me (collection Linkbox grid) |
| `/login` | `LoginPage` | Email input form for requesting a magic link |
| `/logout` | `LogoutPage` | Clears auth cookies and localStorage, redirects to `/login` |
| `/verify/:code` | `VerifyPage` | Processes magic link / RSVP verification |
| `/rsvp/:code` | `VerifyPage` | Alias for /verify/:code |
| `/me` | `UserPage` | Own profile (fetches userCode from `/auth/me/` if needed) |
| `/me/edit` | `EditProfilePage` | Edit own profile |
| `/me/notifications/:token` | `NotificationsPage` | Manage email preferences via 6-char `prefs_token` from email footer link. Without `:token` redirects to `/me/edit`. |
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
| `/popin` | `PopInPage` | Open-door onboarding: enter email, get magic link, join onboarding collections |
| `/share/:token` | `SharePage` | Public collection share-link landing: enter email, get magic link, join the collection identified by `:token` |
| `/:userCode` | `UserPage` | Displays a user's public profile |
| `*` | `NotFoundPage` | 404 page for unknown routes |

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
| `color_01` | Primary button background + secondary button border |
| `color_02` | Body background + Koros SVG fill |
| `color_03` | Koros section background |
| `color_04` | Body text + secondary button text |
| `color_05` | Koros text (title, description, back-link) via `--hero-text-color` |
| `color_06` | Primary button text |

All buttons across the app use theeeme colors (`btnStyle` for primary, `btnSecondaryStyle` for secondary). Secondary buttons always have a white background; `color_01` drives the border and `color_04` the text.

Pages using this pattern: HomePage, CollectionPage, CreateCollectionPage, EditCollectionPage, EditProfilePage, ManageInvitesPage, MyBookingsPage, EditThingPage, ThingPage, WelcomePage, RequestThingPage, DeleteThingPage, RemoveGuestPage, UserPage.

---

## Breakpoints

OIUEEI follows the official [HDS breakpoint tokens](https://hds.hel.fi/foundation/design-tokens/breakpoints/). HDS defines six breakpoints; OIUEEI uses four of them and intentionally skips `breakpoint-s` (576px) and `breakpoint-xxl` (1440px). Use only these exact `min-width` values in media queries — never use arbitrary pixel values.

| Token | Min-width | Container width | HDS grid columns | Margin |
|---|---|---|---|---|
| `breakpoint-xs` | 320px | 288px | 4 | 16px |
| `breakpoint-m` | 768px | 720px | 8 | 24px |
| `breakpoint-l` | 992px | 944px | 12 | 24px |
| `breakpoint-xl` | 1248px | 1200px | 12 | 24px |

The `page-container` and `form-hero-content` max-width is **1248px** (aligned with `breakpoint-xl`). The complementary `max-width: 767px` query (below `breakpoint-m`) is also valid for mobile-only overrides.

---

## Pages

### LoginPage (`src/pages/LoginPage.jsx`)

- **API:** `POST /api/v1/auth/request-link/` with `{ email }` and CSRF token
- Uses the standard `form-hero` + `Koros` layout with theeeme colors from localStorage (if available from a previous session).
- Shows a brief description of OIUEEI above the form (`login.description` i18n key).\n- Shows an open source paragraph with a link to the GitHub repository (`login.openSource` i18n key, rendered via `Trans` for the inline link).
- Sends a magic link to the provided email address.
- After submission, replaces the form with a `Notification` component:
  - `success` — Unified message displayed (backend returns 200 regardless of email existence for anti-enumeration)
  - `error` — Server or network error
- CSRF token is read from the `csrftoken` cookie via `getCsrfToken()`.

### VerifyPage (`src/pages/VerifyPage.jsx`)

- **API:** `GET /api/v1/auth/verify/{code}/`
- Fetches on mount using the `:code` route parameter.
- On `COLLECTION_REJECT` action: shows success `Notification` confirming the invitation was declined and the owner was notified. Shows "Go to login" button. No login/redirect.
- On success: stores `userCode` in `localStorage`. Auth tokens are set as HttpOnly cookies by the backend. If `data.invited_collection` is present (COLLECTION_INVITE flow), navigates to `/collections/{code}` with `{ state: { fromInvite: true } }`; if `seenWelcome` is not set in `localStorage` (new user — e.g. from `/popin`), navigates to `/welcome`; otherwise navigates to `/`.
- On failure: shows error `Notification` with helpful guidance and "Go to login" button (resolves dead-end for expired links).

### WelcomePage (`src/pages/WelcomePage.jsx`)

- Static informational page about OIUEEI.
- `← Home` link navigates to `/`.
- **Action buttons:** "Create collection" links to `/collections/new` and "Edit profile" links to `/me/edit`, both passing `{ state: { backPath: '/welcome', backLabel: 'Welcome' } }` for return navigation.
- **Personas section:** below the description, shows "Who uses OIUEEI?" heading with five persona stories (Lala, Lele, Lili, Lolo, Lulu — the demo users) illustrating different use cases. Each persona uses `persona{Name}Title` (bold) + `persona{Name}Body` i18n keys.
- Sets `seenWelcome = 'true'` in `localStorage` on mount, permanently suppressing the Welcome Linkbox on `CollectionPage` for this browser.

### HomePage (`src/pages/HomePage.jsx`)

- **APIs:** `GET /api/v1/auth/me/`, `GET /api/v1/collections/`, `GET /api/v1/invited-collections/`, `GET /api/v1/my-invitations/` (authenticated via HttpOnly cookies)
- Redirects to `/login` if no `userCode` in `localStorage`.
- Stores `userCode`, `theeemeColors`, `koro`, and `seenWelcome` in `localStorage` on successful fetch. `seenWelcome` suppresses the first-time Welcome Linkbox on `CollectionPage`.
- Displays greeting, "Create collection" button linking to `/collections/new`, "My profile" button linking to `/me`, and "My requests" button linking to `/my-bookings`.
- **Pending invitations**: fetches `GET /api/v1/my-invitations/` on mount. Shows one dismissible HDS `Notification` (type `info`) per pending invite, above the collections. Each notification shows the owner name as label, collection headline in bold, and "Accept invitation" / "Decline invitation" links pointing to `/verify/{accept_code}` and `/verify/{reject_code}`. Dismissed notifications are removed from local state only (RSVP remains until acted on).
- **My collections section**: shows own ACTIVE collections as HDS `Linkbox` cards (`collections-grid`). Each card shows headline and `{N} things · {N} guests`. Empty state links to `/collections/new`.
- **Inactive collections section**: shown below My collections when at least one own INACTIVE collection exists.
- **Shared with me section**: shows invited ACTIVE collections as HDS `Linkbox` cards. Empty state shows a no-shared message.

### CollectionPage (`src/pages/CollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/`
- Redirects to `/login` if no `userCode` in `localStorage`.
- Handles 403 (not authorised) and 404 (not found) with specific error messages.
- Displays collection headline, description, and status. Shows `thumbnail_url` in the card if present.
- **Things** are rendered using the `ThingLinkbox` component (see below).
- **"Edit collection" button** visible only to collection owner, links to `/collections/{code}/edit`.
- **"Add thing" button** visible to collection owner (always) and to invited users in COMMUNITY mode, links to `/collections/{code}/add`.
- **"Manage guests" button** visible only to collection owner, links to `/collections/{code}/invites`.
- **Community tag**: when `collection.mode === 'COMMUNITY'`, an HDS `Tag` with "Community" label is shown next to the headline.
- **Swap tag**: when `collection.is_swap`, an HDS `Tag` with "Swap collection" label is shown next to the headline (in addition to the Community tag).
- **Album tag**: when `collection.is_minimalist`, an HDS `Tag` with "Album" label is shown next to the headline.
- **Welcome Linkbox**: shown only when user arrives from a COLLECTION_INVITE flow (`location.state.fromInvite`) AND `seenWelcome` is not set in `localStorage` (first-time users only). Links to `/welcome`. Disappears after first click. The "Home" back link is hidden while the Welcome Linkbox is visible. Uses `linkbox-full-width` CSS class for 100% width.
- **Owner attribution**: guests see "Owner. {name}" below the description in the hero, linking to `/{owner_code}` (the owner's public profile). Uses `owner_name` from `CollectionSerializer`.
- **INACTIVE notice**: when the collection status is `INACTIVE` and the viewer is the owner, a `Notification` informs them "This collection is inactive. It is not visible to guests." Guests cannot access inactive collections (backend returns 403).
- **Pause banner**: when `collection.is_paused` is true, a fixed non-dismissible HDS `Notification` (type `alert`) is shown at the top of the page content area, with label `pause.bannerLabel` and body `collection.pause_message`. Shown to both owner and guests. `isPaused={collection.is_paused}` is passed to every `ThingLinkbox` so Hold buttons are disabled while paused.
- **Share menu**: directly under the owner action buttons in the hero, shown only to the owner. Renders `<ShareCollectionMenu>` (HDS `Select` with `IconEnvelope` / `IconShare` / `IconWhatsapp` icons). On first interaction calls `POST /api/v1/collections/{code}/share-link/` to lazily generate the public token, caches the URL in component state, and dispatches the chosen share action: `mailto:`, `navigator.clipboard.writeText`, or `https://wa.me/?text=`. Email subject/body and WhatsApp text are pre-filled with the collection headline and the resulting `/share/{token}` URL, all translated to the owner's language.
- **Broadcast section**: shown to the owner when the collection has invitees. A "Send a message to guests" button opens an inline form with subject (TextInput, max 64) and message (TextArea, max 256) fields. Submits to `POST /api/v1/collections/{code}/broadcast/`. Shows success/error Notification inline. Closable via "Close" button.
- **Things section**: shows all non-inactive things for both owners and guests (responsive 3-column grid).
- **Inactive things section**: shown only to the owner, below the Things section, when at least one inactive thing exists. Lists all `INACTIVE` things using the same `ThingLinkbox` component.

### ThingLinkbox (`src/components/ThingLinkbox.jsx`)

Reusable component for rendering a thing as an HDS `Card`. Used by `CollectionPage` and `HomePage`.

- **Card**: the component uses HDS `Card` (a `<div>`-based container) instead of `Linkbox`, since it contains interactive elements (buttons, links). The thumbnail and headline are wrapped in `<Link>` components for navigation to `ThingPage` (`/collections/{code}/things/{thingCode}` or `/things/{thingCode}`). No `stopPropagation` hacks needed.
- **Minimalist mode**: accepts `minimalist` prop. When true, renders a photo-album card: photo fills a `3/4` aspect-ratio container (`object-fit: cover`), action buttons are overlaid at the bottom of the photo (`.thing-card-minimalist-buttons`, `position: absolute`), and the headline appears below as a small centred caption (`.thing-card-caption`). No description, info rows, or link to ThingPage. Owner sees confirm/cancel hold (if pending), hide/reactivate. Guest sees "Hold" button (direct POST for GIFT/SHARE, navigates to RequestThingPage for SWAP).
- **Community attribution** (before headline, COMMUNITY collections only): when `collectionMode === 'COMMUNITY'`, renders a `thing-card-meta` paragraph showing `owner_name` and the creation date formatted as dd/mm (`toLocaleDateString('es', { day: '2-digit', month: '2-digit' })`). Uses the `collectionMode` prop passed from `CollectionPage`.
- **Tags row** (before headline): HDS `Tag` components in a flex row showing:
  - **Type** tag (always): Gift, Sale, Order, Rental, Lend, Share, Event, Wish.
  - **Requested** tag (owner only, `status === 'TAKEN'`): amber background.
  - **Inactive** tag (owner only, `status === 'INACTIVE'`): grey background.
  - **Pending questions** tag (owner only, `pending_questions > 0`): amber background — uses the `pending_questions` serializer field (count of unanswered FAQs).
- Displays thumbnail (or placeholder with `srcSet` for @2x/@3x), headline, description, and info rows with HDS icons for type (`IconTicket`), price (`IconEuroSign`), availability (`IconCalendar`), location (`IconLocation`), condition (`IconShield`), event date (`IconCalendar`, for EVENT_THING), booking unit (`IconCalendar`, for ASSET_THING — shows "Day" or "Hour"), slot duration (`IconCalendar`, for APPOINTMENT_THING — shows duration in minutes), attendee count (`IconHome`, for EVENT_THING), helper count (`IconHome`, for WISH_THING), and transfer count (`IconHome`, shown when `thing.transfer_count > 0` — uses type-specific i18n keys: `transfers.lendCount`, `transfers.rentCount`, `transfers.shareCount`, `transfers.swapCount`, `transfers.orderCount` based on `thing.type`). Uses a plain `<div>` container (not HDS Card) to avoid style conflicts with HDS Tag components.
- **Shared calendar for ASSET_THING and APPOINTMENT_THING**: guests also fetch `GET /api/v1/things/{code}/calendar/` for ASSET_THING and APPOINTMENT_THING and see full booking details (requester name, dates, times). The bookings list is visible to both owners and guests for these types. Hourly bookings display time ranges (e.g. "09:00–12:00") alongside dates.
- **Owner bookings display**: fetches `GET /api/v1/things/{code}/calendar/` on mount for date-based/order types and for any TAKEN thing (GIFT/SELL with a pending request). Shows future pending and confirmed bookings with requester name, request date, date ranges/delivery info, and status. Bookings with no dates (GIFT/SELL) are always shown regardless of date. The active pending booking is tracked in local `activePendingCode` state (initialised from `thing.pending_booking`, then synced to the first PENDING from the calendar on load) and marked bold with `*` when multiple pending exist.
- **Themed buttons**: all buttons use theeeme colors (`btnStyle` for primary, `btnSecondaryStyle` for secondary). Secondary buttons always have a white background (`--background-color: white`); the theeeme `color_01` is used for the border, and `color_04` for the text.
- **Owner button matrix** (based on `thing.status`):
  - `ACTIVE` (no pending hold): "Edit" (**primary**), "Hide" (secondary). "Hide" is suppressed when pending bookings exist. For SHARE_THING after transfer (`transfer_count > 0`), "Hide" is only shown to the collection owner (not the thing owner).
  - `ACTIVE` (date-based/order with pending hold): "Confirm hold" (primary) + "Cancel hold" (secondary) targeting `activePendingCode`, then "Edit" (secondary).
  - `TAKEN`: "Confirm hold" (primary), "Cancel hold" (secondary), "Edit" (secondary). After each accept/cancel, `activePendingCode` advances to the next pending.
  - `INACTIVE`: "Reactivate" (primary, calls `POST /api/v1/things/{code}/activate/`), "Edit" (secondary), "Delete" (secondary, navigates to `DeleteThingPage` with `{ state: { backPath, backLabel } }`).
- **Wish help button** (non-owners, WISH_THING only): "I can help"/"Helping" toggle button. Calls `POST /api/v1/things/{code}/offer-help/`.
- **Reservation button** logic (non-owners, non-event, non-wish only):
  - `ACTIVE`: enabled "Hold" button. Disabled (but still showing "Hold") when `isPaused` prop is true.
  - `TAKEN`: disabled button. Label is "Waiting for confirmation" if `thing.my_pending_booking` (or local `requested` state) is set, otherwise "Reserved".
  - `INACTIVE`: not shown (guests cannot see INACTIVE things).
  - `isPaused` prop: passed from `CollectionPage` via `collection.is_paused`. Disables all Hold/propose-swap buttons for non-owners without changing button label.
- **Reservation request** adapts to thing type:
  - `GIFT_THING`, `SELL_THING` — button submits directly via `POST /api/v1/things/{code}/request/`, no extra fields.
  - `LEND_THING`, `RENT_THING`, `SHARE_THING` — button navigates to `RequestThingPage` for date selection.
  - `ORDER_THING` — button navigates to `RequestThingPage` for delivery date and quantity.
  - `SWAP_THING` — "Propose swap" button navigates to `RequestThingPage` for swap item selection. Owner bookings display shows offered thing headlines for swap requests. **Minimum-items gate**: when `thing.collection_swap_minimum_items > 0` and `thing.my_swap_count_in_collection` is below it, the button is disabled and an inline HDS `Notification` (`type="info"`, `size="small"`) is rendered below it via `swap.minimumNotMetLabel` + `swap.minimumNotMetBody` (with `count` interpolation). The same gate is mirrored in `ThingPage`. Backend backstops it in `core/views/reservations.py::_handle_swap_request`.
  - `APPOINTMENT_THING` — "Hold" button navigates to `ThingPage` (not `RequestThingPage`); booking is done via the `WeeklySchedule` slot grid.
- **Back navigation**: passes `{ state: { backPath, backLabel } }` to RequestThingPage and ThingPage based on context (collection headline or home).

### ThingPage (`src/pages/ThingPage.jsx`)

Detail page for a thing with full information and FAQs section.

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/faq/` (FAQs), `POST /api/v1/things/{thingCode}/faq/` (ask question), `POST /api/v1/faq/{faqCode}/answer/` (answer), `POST /api/v1/faq/{faqCode}/hide/` and `/show/` (toggle visibility), `GET /api/v1/things/{thingCode}/transfers/` (transfer history), `GET /api/v1/things/{thingCode}/attendees/` (event attendees), `POST /api/v1/things/{thingCode}/attend/` (toggle attendance), `GET /api/v1/things/{thingCode}/helpers/` (wish helpers), `POST /api/v1/things/{thingCode}/offer-help/` (toggle help offer), `GET /api/v1/things/{thingCode}/stats/` (usage statistics)
- Accessible from `/collections/:code/things/:thingCode` (collection context) or `/things/:thingCode` (standalone).
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Tags row** (before headline): same HDS `Tag` components as ThingLinkbox (type, Taken, Inactive, Pending questions).
- Displays thumbnail (if present), headline, description, creation date, fee, availability, location, condition, event date (for EVENT_THING), booking unit (for ASSET_THING — "Day" or "Hour"), and slot duration (for APPOINTMENT_THING).
- **Weekly schedule**: For APPOINTMENT_THING with `slot_duration`, shows `WeeklySchedule` component below info section. Available slots are clickable for non-owners, navigating to RequestThingPage with pre-filled date/time.
- **Back link**: shows collection headline or "Home" depending on navigation context (via `location.state.backLabel`).
- **Owner bookings display**: fetches `GET /api/v1/things/{thingCode}/calendar/` for date-based/order types and for any TAKEN thing (GIFT/SELL). Same logic as ThingLinkbox: filters past bookings, syncs `activePendingCode` to the first PENDING from the calendar, shows bookings list with requester name, request date, date ranges/delivery info, and status. Active pending booking is bold; starred when multiple pending exist. For ASSET_THING, the bookings list is visible to all users (not just owner). Hourly bookings display time ranges alongside dates.
- **Usage statistics**: for ASSET_THING, fetches `GET /api/v1/things/{thingCode}/stats/` and displays total bookings, unique users, and a monthly per-user breakdown table. Shown below the Journey/transfers section.
- **Owner actions:** Full parity with ThingLinkbox button matrix:
  - `ACTIVE` (no pending): "Edit" (**primary**) + "Hide" (secondary, suppressed when pending bookings exist).
  - `ACTIVE` (date-based/order with pending): "Confirm hold" + "Cancel hold" + "Edit" (secondary).
  - `TAKEN`: "Confirm hold" (primary) → "Cancel hold" (secondary) → "Edit" (secondary). `activePendingCode` advances to next pending after each action.
  - `INACTIVE`: "Reactivate" (primary) + "Edit" (secondary) + "Delete" (secondary).
  - Delete navigates to `DeleteThingPage` with `{ state: { backPath, backLabel } }`.
- **Event attendance:** For EVENT_THING, non-owners see "Attend"/"Attending" toggle button instead of "Hold". Calls `POST /api/v1/things/{code}/attend/`. Attendees section shows list of attendees fetched from `GET /api/v1/things/{code}/attendees/`.
- **Wish help:** For WISH_THING, non-owners see "I can help"/"Helping" toggle button. Calls `POST /api/v1/things/{code}/offer-help/`. Helpers section shows list of helpers fetched from `GET /api/v1/things/{code}/helpers/`.
- **Reservation:** For non-event/non-wish/non-appointment types, non-owners see "Hold" button (or "Propose swap" for SWAP_THING). GIFT/SELL types submit directly; date-based, order, and swap types navigate to `RequestThingPage` with `{ state: { backPath, backLabel } }`. Owner bookings for SWAP_THING display offered thing headlines. APPOINTMENT_THING has no "Hold" button — booking is done via `WeeklySchedule` slot clicks.
- **FAQs section:**
  - Lists all FAQs with question, `questioner_name`, and answer. Hidden FAQs shown with reduced opacity (owner only).
  - **Owner:** inline `TextArea` to answer unanswered questions, "Hide"/"Show" toggle button per FAQ.
  - **Non-owner:** `Fieldset`-wrapped form to ask a new question.
- **Journey section** (below FAQs): fetches `GET /api/v1/things/{thingCode}/transfers/` on mount. Shown only when `total_transfers > 0`. For SHARE_THING in COMMUNITY collections (`is_share_in_community`): shows "Sharing history" heading, "Originally shared by {name}" block, "Shared by N people" narrative, and a CSS timeline (`.share-timeline`). For other things: displays the standard journey view with journey count (unique homes), current holder name, and a timeline of transfers (from → to, lent date, returned date).

### RequestThingPage (`src/pages/RequestThingPage.jsx`)

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/calendar/` (blocked periods for date-based types), `POST /api/v1/things/{thingCode}/request/` (submit request)
- Accessible from `/collections/:code/things/:thingCode/request` (collection context) or `/things/:thingCode/request` (standalone).
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Back link**: uses `location.state.backPath` and `location.state.backLabel` passed from ThingLinkbox or ThingPage.
- **Page title**: `Hold: {thing.headline}` with fee display when present.
- **Form fields** adapt to thing type:
  - `SWAP_THING` — Fetches user's own SWAP_THING items in the same collection. Shows HDS `Checkbox` per item for multi-select. Submits `{ offered_thing_codes: [...] }`. "Propose swap" button disabled until at least one item selected.
  - `APPOINTMENT_THING` — `DateInput` for date (day-of-week filtered against `availability_schedule`) + HDS `Select` showing precomputed 1-hour slots (e.g. "14:00 – 15:00") for the chosen date. Accepts pre-filled values from `location.state`: `prefillDate`, `prefillStartTime`, `prefillEndTime` (set by WeeklySchedule slot clicks).
  - `ASSET_THING` with `booking_unit=HOUR` — `DateInput` for date + two HDS `Select` components for start/end time (hourly options 00:00–23:00, end filtered to > start). All `Select` components use `language="en"` (required — default is Finnish "fi").
  - `LEND_THING`, `RENT_THING`, `SHARE_THING`, `ASSET_THING` (day) — `DateInput` for start and end dates with blocked-date validation.
  - `ORDER_THING` — `DateInput` for delivery date + `NumberInput` for quantity.
- **Date validation**: `minDate` today, `maxDate` today + 90 days. Blocked dates fetched from calendar API.
- **Buttons**: Cancel (navigates back) + Hold/Propose swap (submits request).
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
- PENDING bookings show a "Cancel request" button. Non-pending bookings are grouped under "Past requests".
- Accessible from HomePage via "My requests" button.

### NotFoundPage (`src/pages/NotFoundPage.jsx`)

- Catch-all 404 page for unknown routes.
- Uses the standard `form-hero` + `Koros` layout with theeeme colors from localStorage (or defaults).
- Shows a "Page not found" title and message with a button to go home or login.

### SharePage (`src/pages/SharePage.jsx`)

- **API:** `POST /api/v1/auth/pop-in/` with `{ email, share_token }`.
- Public route at `/share/:token`. The owner has previously generated this token via the `ShareCollectionMenu` in CollectionPage; anyone with the link can land here and join the collection.
- Same UX as `PopInPage`: email input + magic link sent. After submit shows an inline `Notification`.
- Invalid / revoked / inactive-collection tokens return 200 with the same magic-link response (anti-enumeration). The user gets a magic link; if the token was invalid they simply land on `/welcome` or `/` rather than on the target collection.
- Uses the standard `form-hero` + `Koros` layout with theeeme colours from localStorage (or defaults when the recipient has no prior session).

### LogoutPage (`src/pages/LogoutPage.jsx`)

- Calls `POST /api/v1/auth/logout/` to clear auth cookies on the backend.
- Clears `userCode` from `localStorage`.
- Navigates to `/login` immediately.

### AddThingPage (`src/pages/AddThingPage.jsx`)

- **API:** `POST /api/v1/things/` with `collection_code` in body
- Redirects to `/login` if no `userCode` in `localStorage`.
- Simple form with h1 title + `form-grid` layout:
  - `Select` for thing type (WISH_THING, SHARE_THING, and ASSET_THING only shown when collection is COMMUNITY; SWAP_THING hidden — auto-selected for swap collections). The select is also filtered down to `collection.allowed_thing_types` when that field is non-empty (PROPRIETARY collections set this on Create/Edit). When the allowlist contains a single type, it is pre-selected so downstream fields show right away. Immediately after the type selector: `ToggleButton` for "Sin límite / Endless" (shown only for GIFT/SELL types). When collection `is_swap`: auto-selects SWAP_THING, hides type selector. When collection `is_minimalist`: filters type selector to GIFT/SHARE/SWAP only, hides fee/availability/location/condition fields, makes ImageUpload label show "Photo (required)", hides DocumentUpload. `TextInput` for headline (required, max 64), `TextArea` for description, `TextInput` with `type="datetime-local"` for event date (shown only for EVENT_THING), `Select` for booking unit DAY/HOUR (shown only for ASSET_THING). For APPOINTMENT_THING: `Select` for slot duration (15/30/60 min), schedule builder with one HDS `Select multiSelect` for days (Mon–Sun, value is the ISO weekday number 1–7) and time range inputs per window, "Add time window" button. Selected days render as chips/tags below the trigger; multiple days can be picked from the dropdown. `NumberInput` for fee (required for SELL/RENT/ORDER types, hidden for others). For GIFT/SELL/LEND/SHARE types (`DETAIL_TYPES`): `Select` for availability, `TextInput` for location (max 32), `Select` for condition. `ImageUpload` for thumbnail (last, before button, folder `oiueei/things`).
  - "Create" button below the form. Validates on submit.
- On success: navigates to `/collections/{code}`.
- On error: toast notification (top-right, auto-close).

### EditThingPage (`src/pages/EditThingPage.jsx`)

- **API:** `GET /api/v1/things/{thingCode}/` to load, `PATCH /api/v1/things/{thingCode}/` to save, `DELETE /api/v1/things/{thingCode}/` to delete
- Accessible from `/collections/:code/things/:thingCode/edit` or `/things/:thingCode/edit`.
- Same fields as AddThingPage (type, then `ToggleButton` for Endless immediately after type for GIFT/SELL, headline, description, event date for EVENT_THING, booking unit for ASSET_THING, fee, availability/location/condition for `DETAIL_TYPES`, `ImageUpload` for thumbnail last). Pre-populates all fields including existing `thumbnail_url` for preview, `event_date` for events, and `booking_unit` for assets.
- "Save" button (primary, full width) and "Delete" button (secondary, full width) below the form. Delete navigates to `DeleteThingPage` with `{ state: { backPath: returnPath, backLabel: returnLabel } }`.
- On success: navigates back to collection or home.

### EditProfilePage (`src/pages/EditProfilePage.jsx`)

- **API:** `GET /api/v1/auth/me/` to load, `GET /api/v1/theeemes/` to list themes, `PUT /api/v1/users/{userCode}/` to save
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- Simple form with h1 title + `form-grid` layout:
  - `TextInput` for name, `TextArea` for headline (bio), `TheeemeSelector` for theeeme (visual colour swatch grid from API), `KoroSelector` for koro (visual Koros SVG preview grid).
  - **Email preferences section** (h2 heading + `notifications.intro` paragraph + `form-grid`): three HDS `ToggleButton` components (wrapped in `.toggle-left`) — "Sign-in links and invitations" (always checked, `disabled`, renders black pill, Cat. 1), "Activity between users" (`notify_activity`, Cat. 2), and "News and announcements" (`notify_news`, Cat. 3). Each has a sub-label helper text rendered as a `<span>` inside the label prop. Preferences are saved together with profile fields via a single Save button.
  - "Save" button below the preferences section.
- Pre-populates all fields (including `notify_activity`/`notify_news`) from the current user profile.
- On success: navigates to `/`.

### NotificationsPage (`src/pages/NotificationsPage.jsx`)

- **API:** `GET /api/v1/notifications/token/{token}/`, `PATCH /api/v1/notifications/token/{token}/`.
- Accessible from `/me/notifications/:token` — the 6-char `prefs_token` is included in the footer of every Cat. 2 / Cat. 3 email for unauthenticated preference editing.
- **Without `:token`**: redirects immediately to `/me/edit` (preferences are now embedded in EditProfilePage).
- **Token mode**: no `userCode` required in localStorage, no BackLink. Invalid tokens render a `Notification type="error"` with a fallback message and no form.
- **Form:** three HDS `ToggleButton` components (wrapped in `.toggle-left`):
  1. "Sign-in links and invitations" — always checked, `disabled`, renders black pill (Cat. 1, cannot be toggled).
  2. "Activity between users (recommended)" — controls `notify_activity` (Cat. 2).
  3. "News and announcements (optional)" — controls `notify_news` (Cat. 3).
  Each toggle has a sub-label helper text rendered as a `<span>` inside the label prop.
- Save button persists via `PATCH /api/v1/notifications/token/{token}/`. On success shows an inline `Notification type="success"` ("Preferences saved.").
- Uses the standard `form-hero` + `Koros` layout with theeeme colours from localStorage when available.

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
  - `TextInput` for headline (required), `TextArea` for description, `Select` for status (ACTIVE/INACTIVE), `Select` for mode (Proprietary/Community), `ToggleButton` for "Enable item swapping" and `ToggleButton` for "Exclusively SHARE things" (visible only when mode is COMMUNITY; swap and share are mutually exclusive with each other), `ToggleButton` for "Require 3 items before swapping" (visible only when swap is enabled; saves `swap_minimum_items=3` when on, `0` when off), `ToggleButton` for "Weekly activity newsletter" (visible when share is enabled), `ToggleButton` for "Minimalist (album)" (always visible; independent of swap), `Select multiSelect` for allowed thing types (visible for PROPRIETARY always, and for COMMUNITY when neither `is_swap` nor `is_share` is on; default `[]` so the user must explicitly pick at least one. PROPRIETARY: 7 types or `[GIFT_THING]` locked when `is_minimalist` is on. COMMUNITY: 10 types or `[GIFT, SHARE]` when `is_minimalist` is on. Toggling any of `is_swap`/`is_share`/`is_minimalist`/mode resets the value. Save fails with 400 from backend if narrowing would orphan existing things — the response detail names the offending types and is surfaced via Toast.), `Select` for digest frequency (None/Weekly/Monthly), `ImageUpload` for thumbnail (folder `oiueei/collections`). All toggles use the `.toggle-left` wrapper class.
  - "Save" button below the form, then "Delete" button below that (navigates to `DeleteCollectionPage`).
- **Pause section** below the Delete button (separated by a border):
  - When NOT paused: `TextArea` for a custom message to guests + "Pause collection" button (disabled until message is non-empty). Submits `PATCH { pause_message: message }`.
  - When paused: shows the current message in a styled `<blockquote>` + "Resume collection" button. Submits `PATCH { pause_message: "" }`.
  - Both actions are independent PATCHes from the main Save; no page reload.
  - Shows success toast on pause/resume.
- Pre-populates all fields from the current collection data, including existing `thumbnail_url` for preview.
- On save: navigates to `/collections/{code}`.

### CreateCollectionPage (`src/pages/CreateCollectionPage.jsx`)

- **API:** `POST /api/v1/collections/`
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- Simple form with h1 title + `form-grid` layout:
  - `TextInput` for headline (required), `TextArea` for description, `Select` for mode (Proprietary/Community), `ToggleButton` for "Enable item swapping" and `ToggleButton` for "Exclusively SHARE things" (visible only when mode is COMMUNITY; swap and share are mutually exclusive with each other), `ToggleButton` for "Require 3 items before swapping" (visible only when swap is enabled; saves `swap_minimum_items=3` when on, `0` when off), `ToggleButton` for "Weekly activity newsletter" (visible when share is enabled), `ToggleButton` for "Minimalist (album)" (always visible; independent of swap), `Select multiSelect` for allowed thing types (visible for PROPRIETARY always, and for COMMUNITY when neither `is_swap` nor `is_share` is on; default empty, user must pick at least one. PROPRIETARY: 7 types or `[GIFT_THING]` locked when `is_minimalist` is on. COMMUNITY: 10 types or `[GIFT, SHARE]` when `is_minimalist` is on. Toggling any of `is_swap`/`is_share`/`is_minimalist`/mode resets the value). All toggles use the `.toggle-left` wrapper class.
  - "Create" button below the form.
- On success: navigates to `/collections/{code}`.

### UserPage (`src/pages/UserPage.jsx`)

- **API:** `GET /api/v1/users/{userCode}/`
- Also serves as `/me` route: when no `userCode` param, fetches `/api/v1/auth/me/` to resolve own code.
- Redirects to `/login` if no `userCode` in `localStorage`.
- Handles 403 (no permission) and 404 (user not found) with specific error messages.
- Uses the standard `form-hero` + `Koros` layout with theeeme colors (own profile uses `theeeme_colors` from API, other profiles fall back to localStorage).
- Hero follows the WelcomePage pattern: BackLink, spacer, headline as Heading M subtitle, name as h1 title, "Member since" date.
- **Own profile:** shows "Edit profile" and "Log out" buttons in the hero. No collections listed — those are now on the HomePage (`/`).
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
- **`ImageUpload`** (`src/components/ImageUpload.jsx`) — Single-image upload using HDS `FileInput`. Gets a short-lived Cloudinary signature from `POST /api/v1/upload/signature/`, resizes images client-side to max 1216px, uploads directly to Cloudinary, and calls `onChange(publicId)`. Shows a preview with a Remove button when an image is present; the FileInput is hidden while a preview exists. Button label and accept hint are translated via i18n. Button colours follow the current theeeme. Props: `id`, `label`, `value` (public_id), `onChange`, `currentUrl`, `folder` (Cloudinary folder, default `oiueei/users`), `helperText`. Used in AddThingPage, EditThingPage.
- **`DocumentUpload`** (`src/components/DocumentUpload.jsx`) — Multi-document upload using HDS `FileInput`. Uploads raw files to Cloudinary via `POST /api/v1/upload/signature/` with `resource_type: 'raw'` and `folder: 'oiueei/documents'`. Max 5 documents, max 1 MB each. Accepts PDF, Word, Excel, and Markdown files. Shows uploaded file list with remove buttons. Props: `documents` (array of `{public_id, filename, content_type}`), `onChange`. Used in AddThingPage, EditThingPage.
- **`TheeemeSelector`** (`src/components/TheeemeSelector.jsx`) — Visual theeeme picker. Renders a grid of buttons; each button shows three 20 px circular swatches (`color_01`, `color_02`, `color_03`) and the theeeme name, with a checkmark when selected. `aria-pressed` and `aria-label` for accessibility. Props: `theeemes` (array from API), `value` (selected code), `onChange`. Used in EditProfilePage.
- **`KoroSelector`** (`src/components/KoroSelector.jsx`) — Visual koro picker. Renders a grid of buttons; each button shows a live `<Koros>` SVG preview (white fill on black background, 50 px tall, scaled to fit) and the koro label. Props: `value` (selected type string), `onChange`. Used in EditProfilePage.
- **`ShareCollectionMenu`** (`src/components/ShareCollectionMenu.jsx`) — Owner-only share menu rendered in the CollectionPage hero. HDS `Select` with three options (`IconEnvelope` for email, `IconShare` for copy-link, `IconWhatsapp` for WhatsApp). Calls `POST /api/v1/collections/{code}/share-link/` lazily on first interaction, caches the resulting URL via `useRef`, and dispatches the action: `mailto:` for email, `navigator.clipboard.writeText` + Toast for copy, `https://wa.me/?text=` for WhatsApp. The Select's value is reset on every change so it acts as a one-shot menu rather than a form input. Strings live in the `shareMenu` i18n namespace. Props: `collectionCode`, `collectionHeadline`, `ownerName`.
- **`WeeklySchedule`** (`src/components/WeeklySchedule.jsx`) — Weekly appointment slot grid for APPOINTMENT_THING. Fetches `GET /api/v1/things/{code}/slots/?week_start=...` and renders an HDS `Table` with time slots as rows and days as columns. Available slots are clickable buttons that navigate to `RequestThingPage` with pre-filled date/time. Booked/pending slots show "Booked"/"Pending" only — requester names are never shown (privacy by default, regardless of ownership). Week navigation via prev/next buttons. Props: `thingCode`, `isOwner`, `requestPath`. Used in ThingPage.

### Constants (`src/constants/things.js`)

Central source of truth for thing type definitions. Display labels are handled by i18n — use `t('types.GIFT_THING')` etc.
- `TYPE_VALUES` — Array of type value strings (no labels — labels come from i18n).
- `SHARE_TYPE` — `SHARE_THING` constant (used for share-specific UI logic — hide button restriction after transfer).
- `EVENT_TYPE` — `EVENT_THING` constant (used for event-specific UI logic).
- `WISH_TYPE` — `WISH_THING` constant (used for wish-specific UI logic).
- `SWAP_TYPE` — `SWAP_THING` constant (used for swap-specific UI logic — swap request form, "Propose swap" button).
- `APPOINTMENT_TYPE` — `APPOINTMENT_THING` constant (used for appointment-specific UI logic — weekly schedule table, slot booking).
- `ASSET_TYPE` — `ASSET_THING` constant (used for asset-specific UI logic).
- `DATE_TYPES` — Types requiring start/end dates (`LEND_THING`, `RENT_THING`, `SHARE_THING`, `ASSET_THING`, `APPOINTMENT_THING`).
- `ORDER_TYPE` — `ORDER_THING` constant.
- `FEE_TYPES` — Types with a fee field (`SELL_THING`, `RENT_THING`, `ORDER_THING`).
- `DETAIL_TYPES` — Types with availability/location/condition fields (`GIFT_THING`, `SELL_THING`, `LEND_THING`, `SHARE_THING`).
- `AVAILABILITY_VALUES` — Array of availability value strings (labels from i18n).
- `CONDITION_VALUES` — Array of condition value strings (labels from i18n).
- `TAG_THEMES` — Theme objects for status tags (taken, inactive, pending).

---

## Internationalisation (i18n)

All UI strings are externalised via `react-i18next`. No hardcoded strings in components.

- **Setup:** `src/i18n/index.js` initialises i18next with `i18next-browser-languagedetector`, which reads `navigator.language` on every load (no cache) and falls back to `en` for unsupported languages.
- **Supported languages:** English (`en`), Spanish (`es`), Catalan (`ca`), Brazilian Portuguese (`pt-BR`), European Portuguese (`pt-PT`), Basque (`eu`), Galician (`gl`).
- **Locale files:** `src/i18n/locales/{lang}.json` — one JSON file per language with ~280 strings organised by namespace (common, titles, login, verify, home, collectionPage, thingPage, types, availability, condition, etc.).
- **`html[lang]`:** updated dynamically in `App.jsx` via `i18n.on('languageChanged', ...)`.
- **Usage:** every page and component imports `useTranslation` and calls `t('namespace.key')`. Select options are built inline: `TYPE_VALUES.map(v => ({ label: t('types.' + v), value: v }))`.
- **Initialisation:** `import './i18n'` in `App.jsx` (before HDS imports).

---

## Analytics

OIUEEI ships with **no third-party analytics**. There is no SDK, no event-tracking service, no consent banner, no opt-out toggle. See [DESIGN.md §9](../DESIGN.md#9-user-data-is-never-a-product) for the underlying principle.

---

## Testing

Smoke tests and automated accessibility checks using vitest + testing-library + jest-axe.

- **Run tests:** `npm test` (single run) or `npm run test:watch` (watch mode).
- **Config:** `vite.config.js` — `test` block with jsdom environment, `src/test/setup.js` as setup file.
- **Setup:** `src/test/setup.js` — imports `@testing-library/jest-dom`, initialises i18n mock, provides `localStorage`, `CSS.supports`, and `ResizeObserver` polyfills for jsdom.
- **Smoke tests:** `src/test/smoke.test.jsx` — renders every page component with mocked API responses and runs `jest-axe` to detect WCAG violations. Covers 17 pages.
- **i18n mock:** `src/test/i18n-mock.js` — initialises i18next with the real `en.json` for test rendering.

---

## Tech Stack

- **React 19** + **Vite 7** + **React Router 7**
- **hds-react** — Helsinki Design System React components (npm `^5.0.0`)
- **hds-design-tokens** — HDS CSS custom property tokens (npm `^5.0.0`)
- **hds-core** — HDS core CSS and base styles (npm `^5.0.0`)

### HDS Select quirks (v5)

All `<Select>` components must include `language="en"` — the HDS default is `"fi"` which produces Finnish placeholder text ("Valitse yksi"). Additional API notes: `value` is an array (`[{ label, value }]`), `onChange` receives an array (`(sel) => sel[0].value`), error text uses the `error` prop (string), not `errorText`.

### HDS ToggleButton quirks (v5)

Four non-obvious behaviours:

1. **`onChange` receives the current value, not the new one.** Always negate: `onChange={(val) => setState(!val)}`.
2. **`style` prop targets the inner `<button>`, not the flex container.** Flex layout overrides via `style` have no effect. Use `<div className="toggle-left">` wrapper instead — the `.toggle-left` CSS class in `App.css` reverses the flex direction to put the pill on the left.
3. **`disabled + checked` renders light grey by default.** Overridden to `--color-black-90` in `App.css` via `.toggle-left button[aria-pressed="true"][disabled]`.
4. **Multi-line labels (title + `<br/>` + long helper) wrap the pill onto a new row.** HDS's inline container allows wrap by default; a long helper makes the label wider than the available row and the pill drops below. Fixed in `.toggle-left` with `flex-wrap: nowrap; align-items: flex-start` on the container plus `flex-shrink: 0` on the inner button.

## OIUEEI Customization Layer

The project consumes HDS directly from npm and applies three local overrides:

- **Fonts** (`src/fonts/oiueei-fonts.css`) — GraebenbachTRIAL `.otf` files registered as `font-family: HelsinkiGroteskPro` (matching the HDS `--font-default` token) so all HDS components use them transparently.
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
