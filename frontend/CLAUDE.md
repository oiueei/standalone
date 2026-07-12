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
| `/magic-link/:code` | `VerifyPage` | Alias for /verify/:code |
| `/me` | `UserPage` | Own profile (fetches userCode from `/auth/me/` if needed) |
| `/me/edit` | `EditProfilePage` | Edit own profile |
| `/me/notifications/:token` | `NotificationsPage` | Manage email preferences via a signed (`TimestampSigner`, ~1y TTL) token from the email footer link. Without `:token` redirects to `/me/edit`. |
| `/collections/new` | `CreateCollectionPage` | Create a new collection |
| `/collections/:code` | `CollectionPage` | Collection detail with things and invites. **Public route** — anonymous read when the collection is PUBLIC (gated server-side by `can_view`). |
| `/collections/:code/edit` | `EditCollectionPage` | Edit a collection |
| `/collections/:code/delete` | `DeleteCollectionPage` | Confirm and delete a collection |
| `/collections/:code/invites` | `ManageInvitesPage` | Manage collection invites |
| `/collections/:code/add` | `AddThingPage` | Add a thing to a collection |
| `/collections/:code/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (from collection context). **Public route** — anonymous read on a PUBLIC collection. |
| `/collections/:code/things/:thingCode/edit` | `EditThingPage` | Edit a thing (from collection context) |
| `/things/:thingCode` | `ThingPage` | Thing detail page with FAQs (standalone). **Public route** — anonymous read on a PUBLIC collection. |
| `/things/:thingCode/edit` | `EditThingPage` | Edit a thing (standalone) |
| `/collections/:code/things/:thingCode/request` | `RequestThingPage` | Request page for date-based/order things (collection context) |
| `/things/:thingCode/request` | `RequestThingPage` | Request page for date-based/order things (standalone) |
| `/collections/:code/things/:thingCode/respond/:kind` | `RespondWishPage` | Answer a wish — "Sé dónde" / "Puedo hacértelo" short form (collection context) |
| `/things/:thingCode/respond/:kind` | `RespondWishPage` | Answer a wish — short form (standalone). `:kind` is `know-where` or `can-make` |
| `/collections/:code/things/:thingCode/delete` | `DeleteThingPage` | Confirm and delete a thing (collection context) |
| `/things/:thingCode/delete` | `DeleteThingPage` | Confirm and delete a thing (standalone) |
| `/collections/:code/invites/remove` | `RemoveGuestPage` | Confirm and remove a guest from a collection |
| `/collections/:code/leave` | `LeaveCollectionPage` | Confirm and leave a collection you're an invited member of (self-unlink) |
| `/my-bookings` | `MyBookingsPage` | Lists user's booking requests with cancel option |
| `/welcome` | `WelcomePage` | Static informational page about OIUEEI |
| `/popin` | `PopInPage` | Open-door onboarding: enter email, get magic link, join onboarding collections |
| `/share/:token` | `SharePage` | Public collection share-link landing: enter email, get magic link, join the collection identified by `:token` |
| `/collections/:code/join` | `JoinPage` | **Public route** — login-to-act landing for a PUBLIC collection. An anonymous visitor who clicks an action button (reserve/order/respond) on a public collection lands here; enters email → pop-in joins them to `:code` + magic link → after verifying they're dropped back on the collection, able to act. |
| `/:userCode` | `UserPage` | Displays a user's public profile |
| `*` | `NotFoundPage` | 404 page for unknown routes |

**Public read of PUBLIC collections (anonymous visitors):** `/collections/:code`, `/collections/:code/things/:thingCode` and `/things/:thingCode` sit in the **public** route block (outside `RequireAuth`). The backend's `can_view` gates them, so only PUBLIC, ACTIVE collections are readable without a session. When unauthenticated, `CollectionPage` shows the thing **action buttons as usual** (via `ThingLinkbox`'s `loginToAct` prop — passed `!isAuthenticated`): the cards look the same as for a member, but each action's click (reserve/hold/order/propose-swap/respond) **navigates to `/collections/:code/join`** (`JoinPage`) instead of performing it. There the visitor enters their email → `/auth/pop-in/` with the collection code joins them to the PUBLIC collection and emails a magic link; because pop-in now stamps the collection as the RSVP `target_code`, verifying the link **drops them back on the collection** (`_handle_magic_link` returns `invited_collection`), now a member who can act. `ThingLinkbox` also still accepts a `canAct` prop (used elsewhere); `loginToAct` is the anonymous-on-public mode. **`ThingPage`, the standalone detail view, uses the same login-to-act pattern**: an anonymous visitor sees the reserve / answer buttons (via `useThingActions`' `loginToAct` option, set to `!isAuthenticated && !!collectionCode`), and each click **navigates to `/collections/:code/join`** rather than showing an inline prompt. (The `JoinToAct` component now renders only inside `JoinPage`.) The owner sets a collection's PUBLIC/PRIVATE state with the **visibility toggle** in the Create/Edit forms (rendered by `CollectionForm`), defaulting by mode on create (COMMUNITY→public, PROPRIETARY→private); a Public/Private `Tag` is shown to the owner in the `CollectionPage` hero.

---

## Page Titles

Every page sets `document.title` via `useEffect` for meaningful browser tab titles and bookmarks. Dynamic pages (CollectionPage, ThingPage, UserPage, etc.) update the title when data loads. Format: `{Page context} — OIUEEI`.

---

## Page Layout Pattern

All pages use a consistent `form-hero` + `Koros` layout (the HDS Hero component is not used):

```
form-page
├── form-hero          (full-width, theeeme color_03 background)
│   ├── form-hero-content  (max-width 1248px, text color from --hero-text-color CSS var using theeeme color_05)
│   │   └── [back link, title, description]
│   ├── ::after         (OIUEEI logo watermark, 40px — see below)
│   └── Koros          (HDS Koros component, type from user.koro preference, 60px height, fill = theeeme color_02)
└── page-container     (max-width 1248px, page content)
```

**OIUEEI logo in the hero (S9):** brand presence via `public/oiueei-logo.svg` (monochrome, 556×161, tinted with a CSS `mask` so it inherits whatever colour var is in scope — the same technique for both uses below).

- **Watermark** — every `form-hero` gets a `::after` pseudo-element (40px tall, ~138px wide, `App.css`), anchored to the right edge of the hero's *content column* at every width (`right: calc((100% - min(100%, 1248px)) / 2 + var(--spacing-s))`, matching `.form-hero-content`'s own centring math, not the raw viewport edge), filled `var(--hero-logo-color, var(--color-black-90))` — theeeme `color_02`, exposed via inline style on `.form-hero` itself (same mechanism as `--hero-text-color`) in `PageLayout.jsx` and the 8 pages that build a hero manually (`CollectionPage`, `HomePage`, `JoinPage`, `LoginPage`, `NotFoundPage`, `UserPage`, `VerifyPage`, `WelcomePage`). Decorative only — a pseudo-element has no accessibility surface. Suppressed below `breakpoint-m` (767px, collision risk with wrapped hero text — unverified without a live viewport) via `.form-hero--photo::after`/`.form-hero--no-watermark::after` (see below).
- **Title replacement** — the one hero `<h1 class="form-hero-title">` whose text is the *literal* string "OIUEEI" (verified by grep across every locale: only `login.title` — `popin.title` is "Come meet us!", `share.pageTitle` is "Join us on OIUEEI", `notFound.title` is "Page not found", none qualify) renders `.form-hero-title-logo` (80px, `var(--hero-text-color)` — white on `/login`) instead of the text, and the `<h1>` carries `aria-label={t('login.title')}` so the accessible name survives. That page's `.form-hero` also gets the `form-hero--no-watermark` modifier class so there's never a double logo.
- **Hero-photo pages (S7/S8)** — the watermark is suppressed there too (`.form-hero--photo::after { display: none }`): whether it stays legible over the diagonal-wedge/photo composition can't be confirmed without a screenshot, so this errs conservative rather than risk an illegible logo.

### Theeeme Color Roles

| Token | Role |
|-------|------|
| `color_01` | Primary button background + secondary button border |
| `color_02` | Body background + Koros SVG fill + hero logo watermark (`--hero-logo-color`) |
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

## PWA

The app ships a web app manifest (`public/manifest.webmanifest`) plus icons (`public/oiueei-icon-192.png` / `-512.png` — the orange O over the engel/bus koros split), so OIUEEI can be installed from the browser ("Add to Home Screen"). The `purpose: maskable` slot points at a **separate** `public/oiueei-icon-512-maskable.png`: the same art scaled to 80% inside the maskable safe zone with the two brand colours bled out to the edges (generated by clamping the border pixels), so an Android launcher masking to a circle/squircle keeps the whole logo instead of clipping the koros waves. The plain `-512.png` stays full-bleed for the `any` purpose (and the 192 remains the crisp favicon/apple-touch source). `index.html` links the manifest, sets `theme-color`, and uses the 192px icon as favicon + `apple-touch-icon` (this also replaced the previously-broken `/vite.svg` favicon reference — the file never existed in `public/`). All colours are HDS tokens sampled from the icon itself: background `#ffe977` (engel), theme `#0000bf` (bus), the O `#fd4f00` (metro). In production Vite's `base: '/static/'` rewrites the `index.html` URLs and the manifest's icon `src`s are relative, so everything resolves under `/static/` via WhiteNoise. **No service worker** — installability only, no offline caching; kept deliberately minimal (DESIGN §7).

---

## Pages

### LoginPage (`src/pages/LoginPage.jsx`)

- **API:** `POST /api/v1/auth/request-link/` with `{ email }` and CSRF token
- Uses the standard `form-hero` + `Koros` layout with theeeme colors from localStorage (if available from a previous session).
- **Hero title is the OIUEEI logo (S9)**: the only hero `<h1>` in the app whose text is the literal string "OIUEEI" — it renders `.form-hero-title-logo` (an 80px masked `oiueei-logo.svg`, coloured via `--hero-text-color`) instead, with `aria-label={t('login.title')}` on the `<h1>` for the accessible name. The hero also carries `form-hero--no-watermark` to suppress the standard 40px logo watermark (see Page Layout Pattern) — no double logo.
- Leads with a one-sentence pitch (`login.pitch` i18n key), then a brief description of OIUEEI (`login.description` i18n key).
- Shows an open source paragraph with a link to the GitHub repository (`login.openSource` i18n key, rendered via `Trans` for the inline link).
- Shows a one-line manifesto under the open-source paragraph (`login.manifesto`): "No ads, no trackers. Your data is not the product."
- Sends a magic link to the provided email address.
- After submission, replaces the form with a `Notification` component:
  - `success` — Unified message displayed (backend returns 200 regardless of email existence for anti-enumeration)
  - `error` — Server or network error
- CSRF token is read from the `csrftoken` cookie via `getCsrfToken()`.

### VerifyPage (`src/pages/VerifyPage.jsx`)

- **API:** `GET /api/v1/auth/verify/{code}/` (resolve) and `POST` of the same URL (commit a booking decision).
- Fetches (GET) on mount using the `:code` route parameter.
- **Booking accept/reject — one-click auto-commit:** when the GET returns `requires_confirmation` (a `BOOKING_ACCEPT`/`BOOKING_REJECT` preview, no mutation), the page **immediately fires the committing `POST`** from within the load effect, showing the "Verifying…" screen until it resolves to the confirmed/rejected success screen. The owner's single click (opening the email link) is enough — no second on-page button. Safety is preserved because the commit only runs from **real JS execution**: an email link-scanner or prefetch does a bare GET, runs no JS, and so still can't decide a hold (the backend also refuses to commit on GET). A `committedRef` guard stops React 19 StrictMode's dev-only double-invoked effect from POSTing twice.
- On `COLLECTION_REJECT` action: shows success `Notification` confirming the invitation was declined and the owner was notified. Shows "Go to login" button. No login/redirect.
- On success: stores `userCode` in `localStorage`. Auth tokens are set as HttpOnly cookies by the backend. If `data.invited_collection` is present (COLLECTION_INVITE flow), navigates to `/collections/{code}` with `{ state: { fromInvite: true } }`; if `seenWelcome` is not set in `localStorage` (new user — e.g. from `/popin`), navigates to `/welcome`; otherwise navigates to `/`.
- On failure: shows error `Notification` with helpful guidance and "Go to login" button (resolves dead-end for expired links).

### WelcomePage (`src/pages/WelcomePage.jsx`)

- Static informational page about OIUEEI.
- `← Home` link navigates to `/`.
- **Action buttons:** "Create collection" links to `/collections/new` and "Edit profile" links to `/me/edit`, both passing `{ state: { backPath: '/welcome', backLabel: 'Welcome' } }` for return navigation.
- **Commitment section** (before the personas): "Our commitment" heading + two short paragraphs (`welcome.commitmentTitle/Body1/Body2`) stating the DESIGN §9 stance in product copy — no ads, no third-party analytics, data never sold or shared, open code. `commitmentBody2` links (via `Trans`) to DESIGN.md §9 on GitHub.
- **Personas section:** below the description, shows "Who uses OIUEEI?" heading with five persona stories (Lala, Lele, Lili, Lolo, Lulu — the demo users) illustrating different use cases. Each persona uses `persona{Name}Title` (bold) + `persona{Name}Body` i18n keys.
- Sets `seenWelcome = 'true'` in `localStorage` on mount, permanently suppressing the Welcome Linkbox on `CollectionPage` for this browser.
- **Feedback line**: `<FeedbackLink />` at the foot of the page content.

### HomePage (`src/pages/HomePage.jsx`)

- **APIs:** `GET /api/v1/auth/me/`, `GET /api/v1/collections/`, `GET /api/v1/invited-collections/`, `GET /api/v1/my-invitations/` (authenticated via HttpOnly cookies)
- Redirects to `/login` if no `userCode` in `localStorage`.
- Stores `userCode`, `theeemeColors`, `koro`, and `seenWelcome` in `localStorage` on successful fetch. `seenWelcome` suppresses the first-time Welcome Linkbox on `CollectionPage`.
- Displays greeting and a button row: "Create collection" (`/collections/new`, primary), "My profile" (`/me`, view own public profile — `home.myProfile`), and "My requests" (`/my-bookings`). "Edit profile" and "Log out" live only on the `/me` profile page, not here.
- **Inbox notifications**: fetches `GET /api/v1/inbox/` on mount and renders one dismissible HDS `Notification` per item, keyed by `type` (label + body via `home.*` i18n). `inboxNotificationLink()` returns a `{to, label}` deep link to the object that originated the notification: the three wish types (`WISH_POSTED`/`WISH_RESPONSE`/`WISH_ACCEPTED`) link to the wish page (`home.viewWish`), `BROADCAST` links to the collection `/collections/{collection_code}` (`home.viewCollection`), and `THING_REPORTED` links to the reported thing `/things/{thing_code}` (`home.viewThing`, rendered as an `alert`). Dismiss does `DELETE /api/v1/inbox/{code}/`.
- **Pending invitations**: fetches `GET /api/v1/my-invitations/` on mount. Shows one dismissible HDS `Notification` (type `info`) per pending invite, above the collections. Each notification shows the owner name as label, collection headline in bold, and "Accept invitation" / "Decline invitation" links pointing to `/verify/{accept_code}` and `/verify/{reject_code}`. Dismissed notifications are removed from local state only (RSVP remains until acted on).
- **My collections section**: shows own ACTIVE collections as `CollectionLinkbox` rows (`collections-grid` — a vertical stack of image-less, full-width rows, one per line at every breakpoint; see Shared Components). Each row shows headline and `{N} things · {N} guests`. Empty state links to `/collections/new`.
- **Inactive collections section**: shown below My collections when at least one own INACTIVE collection exists.
- **Shared with me section**: shows invited ACTIVE collections as `CollectionLinkbox` rows. Empty state shows a no-shared message.
- **Feedback line**: `<FeedbackLink />` at the foot of the page content.

### CollectionPage (`src/pages/CollectionPage.jsx`)

- **API:** `GET /api/v1/collections/{code}/`
- Redirects to `/login` if no `userCode` in `localStorage`.
- Handles 403 (not authorised) and 404 (not found) with specific error messages.
- Displays collection headline, description, and status. **Hero photo (S8):** when `collection.thumbnail_url` is present, the hero gets the `form-hero--photo` class and renders `HeroPhoto` (see Shared Components / UserPage's "Profile photo" note for the full ≥768px layered / <768px stacked behaviour) as a sibling of the wrapping `.form-hero-split`. The hero content itself (back link, title + mode/swap/share/visibility tags, description, owner line, owner action buttons, share menu, invite nudge) sits inside that same `.form-hero-split`, unchanged — the photo composition sits behind/below it. No thumbnail ⇒ plain hero exactly as before (no `.form-hero-split` styling applies without the `--photo` modifier).
- **Things** are rendered using the `ThingLinkbox` component (see below).
- **"Edit collection" button** visible only to collection owner, links to `/collections/{code}/edit`.
- **"Add thing" button** visible to collection owner (always) and to invited users in COMMUNITY mode, links to `/collections/{code}/add`.
- **"Manage guests" button** visible only to collection owner, links to `/collections/{code}/invites`.
- **Community tag**: when `collection.mode === 'COMMUNITY'`, an HDS `Tag` with "Community" label is shown next to the headline.
- **Swap tag**: when `collection.is_swap`, an HDS `Tag` with "Swap collection" label is shown next to the headline (in addition to the Community tag).
- **Welcome Linkbox**: shown only when user arrives from a COLLECTION_INVITE flow (`location.state.fromInvite`) AND `seenWelcome` is not set in `localStorage` (first-time users only). Links to `/welcome`. Disappears after first click. The "Home" back link is hidden while the Welcome Linkbox is visible. Uses `linkbox-full-width` CSS class for 100% width.
- **Owner attribution**: guests see "Owner. {name}" below the description in the hero, linking to `/{owner_code}` (the owner's public profile). Uses `owner_name` from `CollectionSerializer`.
- **INACTIVE notice**: when the collection status is `INACTIVE` and the viewer is the owner, a `Notification` informs them "This collection is inactive. It is not visible to guests." Guests cannot access inactive collections (backend returns 403).
- **Pause banner**: when `collection.is_paused` is true, a fixed non-dismissible HDS `Notification` (type `alert`) is shown at the top of the page content area, with label `pause.bannerLabel` and body `collection.pause_message`. Shown to both owner and guests. `isPaused={collection.is_paused}` is passed to every `ThingLinkbox` so Hold buttons are disabled while paused.
- **Share menu**: directly under the owner action buttons in the hero, shown only to the owner. Renders `<ShareCollectionMenu>` (HDS `Select` with `IconEnvelope` / `IconShare` / `IconWhatsapp` icons, plus a QR action). It receives `isPublic={collection.visibility === 'PUBLIC'}`. For a **PRIVATE** collection it calls `POST /api/v1/collections/{code}/share-link/` on first interaction to lazily generate the public token and shares the `/share/{token}` pop-in URL (recipient must enter their email to join). For a **PUBLIC** collection it **skips the token entirely** and shares the collection page directly (`${window.location.origin}/collections/{code}`) — anyone can read it without an account, so no email gate; a visitor who wants to *act* is asked to log in only then (login-to-act). Either way the resolved URL is cached in a `useRef` and dispatched to the chosen action: `mailto:`, `navigator.clipboard.writeText`, `https://wa.me/?text=`, or the QR dialog. Email subject/body and WhatsApp text are pre-filled with the collection headline and the URL, translated to the owner's language.
- **Broadcast section**: shown to the owner when the collection has invitees. A "Send a message to guests" button opens an inline form with just a message (TextArea, max 256) field — the subject is auto-generated server-side as `Hey! {collection}`. Submits to `POST /api/v1/collections/{code}/broadcast/`. Shows success/error Notification inline. Closable via "Close" button.
- **Things section**: shows all non-inactive things for both owners and guests (responsive 3-column grid).
- **Inactive things section**: shown only to the owner, below the Things section, when at least one inactive thing exists. Lists all `INACTIVE` things using the same `ThingLinkbox` component.

### ThingLinkbox (`src/components/ThingLinkbox.jsx`)

Reusable component for rendering a thing as an HDS `Card`. Used by `CollectionPage` and `HomePage`.

- **Card**: the component uses HDS `Card` (a `<div>`-based container) instead of `Linkbox`, since it contains interactive elements (buttons, links). The thumbnail and headline are wrapped in `<Link>` components for navigation to `ThingPage` (`/collections/{code}/things/{thingCode}` or `/things/{thingCode}`). No `stopPropagation` hacks needed.
- **Community attribution** (before headline, COMMUNITY collections only): when `collectionMode === 'COMMUNITY'`, renders a `thing-card-meta` paragraph showing `owner_name` — linked to the member's profile (`/{thing.owner}`, `.thing-card-owner-link`) — and the creation date formatted as dd/mm (`toLocaleDateString(i18n.language, { day: '2-digit', month: '2-digit' })`). Uses the `collectionMode` prop passed from `CollectionPage`.
- **Tags row** (before headline): HDS `Tag` components in a flex row showing:
  - **Type** tag (always): Gift, Sale, Order, Rental, Lend, Share, Wish.
  - **Requested** tag (owner only, `status === 'TAKEN'`): amber background.
  - **Inactive** tag (owner only, `status === 'INACTIVE'`): grey background.
  - **Pending questions** tag (owner only, `pending_questions > 0`): amber background — uses the `pending_questions` serializer field (count of unanswered FAQs).
- Displays the photo (when a thing has more than one photo — cover `thumbnail_url` + `gallery_urls` — it renders `<ImageCarousel variant="card" to={thingPath}>` so you can browse in-card; a single photo, or none, falls back to the static thumbnail/placeholder with `srcSet` for @2x/@3x), headline, description, and info rows with HDS icons for type (`IconTicket`), price (`IconEuroSign`), availability (`IconCalendar` — for date-based types LEND/RENT the live indicator: `availability.IMMEDIATE` when available today, else the `next_available` day/month date or `availability.noneSoon`; static enum hint otherwise), location (`IconLocation`), condition (`IconShield`), answer count (`IconSpeechbubbleText`, for WISH_THING, shown when `thing.response_count > 0`), and transfer count (`IconHome`, shown when `thing.transfer_count > 0` — uses type-specific i18n keys: `transfers.lendCount`, `transfers.rentCount`, `transfers.shareCount`, `transfers.swapCount` based on `thing.type`). Uses a plain `<div>` container (not HDS Card) to avoid style conflicts with HDS Tag components.
- **Owner bookings display**: fetches `GET /api/v1/things/{code}/calendar/` on mount for date-based/order types and for any TAKEN thing (GIFT/SELL with a pending request). Shows future pending and confirmed bookings with requester name, request date, date ranges/delivery info, and status. Bookings with no dates (GIFT/SELL) are always shown regardless of date. The active pending booking is tracked in local `activePendingCode` state (initialised from `thing.pending_booking`, then synced to the first PENDING from the calendar on load) and marked bold with `*` when multiple pending exist.
- **Themed buttons**: all buttons use theeeme colors (`btnStyle` for primary, `btnSecondaryStyle` for secondary). Secondary buttons always have a white background (`--background-color: white`); the theeeme `color_01` is used for the border, and `color_04` for the text.
- **Owner button matrix** (based on `thing.status`):
  - `ACTIVE` (no pending hold): "Edit" (**primary**), "Delete" (secondary). "Delete" is suppressed when pending bookings exist. For SHARE_THING after transfer (`transfer_count > 0`), "Delete" is only shown to the collection owner (not the thing owner). There is no dedicated "Hide" button — hiding a thing is done by setting it `INACTIVE` from `EditThingPage`.
  - `ACTIVE` (date-based/order with pending hold): "Confirm hold" (primary) + "Cancel hold" (secondary) targeting `activePendingCode`, then "Edit" (secondary).
  - `TAKEN`: "Confirm hold" (primary), "Cancel hold" (secondary), "Edit" (secondary). After each accept/cancel, `activePendingCode` advances to the next pending.
  - `INACTIVE`: "Reactivate" (primary, calls `POST /api/v1/things/{code}/activate/`), "Edit" (secondary), "Delete" (secondary, navigates to `DeleteThingPage` with `{ state: { backPath, backLabel } }`).
- **Wish answer menu** (non-owners, WISH_THING only): renders `<RespondMenu>` — the "Contestar" dropdown (HDS `Select`) with three options (Tengo esto / Sé dónde / Puedo hacértelo). "Tengo esto" routes to `AddThingPage` in respond mode (publishes a listing, links it back as a HAVE_THIS answer); the other two route to `RespondWishPage`. When the viewer has already answered (`thing.my_response`), a small status line replaces the menu. The card also shows a `response_count` row (`IconSpeechbubbleText`) when there are answers.
- **Reservation button** logic (non-owners, non-wish only). The label is computed once (`buttonLabel`) so a disabled button always states its reason (P1-2):
  - `ACTIVE`: enabled button showing the per-type action verb (`thingCard.action.{type}`, default `thingCard.hold`).
  - `TAKEN`: disabled. Label is "Waiting for confirmation" to the viewer holding the pending booking (`thing.my_pending_booking` or local `requested`), and "Not available" (`thingCard.notAvailable`) to everyone else.
  - **Paused**: when `isPaused`, disabled and labelled "Paused" (`thingCard.paused`).
  - **Below the swap minimum**: disabled and labelled "Need {N} more items" (`thingCard.needMoreItems`); the detailed `swap.minimumNotMet*` notification still renders below.
  - `INACTIVE`: not shown (guests cannot see INACTIVE things).
  - `isPaused` prop: passed from `CollectionPage` via `collection.is_paused`. Disables all Hold/propose-swap buttons for non-owners.
- **Reservation request** adapts to thing type:
  - `GIFT_THING`, `SELL_THING` — button submits directly via `POST /api/v1/things/{code}/request/`, no extra fields.
  - `LEND_THING`, `RENT_THING` — button navigates to `RequestThingPage` for date selection.
  - `SHARE_THING` — button submits directly via `POST /api/v1/things/{code}/request/` (no dates). Ownership transfers to the requester on the owner's **accept**; the thing stays `ACTIVE` so it keeps circulating (it is `needsPage`-excluded, unlike LEND/RENT).
  - `SWAP_THING` — "Propose swap" button navigates to `RequestThingPage` for swap item selection. Owner bookings display shows offered thing headlines for swap requests. **Minimum-items gate**: when `thing.collection_swap_minimum_items > 0` and `thing.my_swap_count_in_collection` is below it, the button is disabled and an inline HDS `Notification` (`type="info"`, `size="small"`) is rendered below it via `swap.minimumNotMetLabel` + `swap.minimumNotMetBody` (with `count` interpolation). The same gate is mirrored in `ThingPage`. Backend backstops it in `core/services/booking_service.py::request_swap_booking`.
- **Back navigation**: passes `{ state: { backPath, backLabel } }` to RequestThingPage and ThingPage based on context (collection headline or home).

### ThingPage (`src/pages/ThingPage.jsx`)

Detail page for a thing with full information and FAQs section.

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/faq/` (FAQs), `POST /api/v1/things/{thingCode}/faq/` (ask question), `POST /api/v1/faq/{faqCode}/answer/` (answer), `POST /api/v1/faq/{faqCode}/hide/` and `/show/` (toggle visibility), `GET /api/v1/things/{thingCode}/transfers/` (transfer history), `GET /api/v1/things/{thingCode}/responses/` (wish answers), `POST /api/v1/wish-responses/{code}/accept/` (accept an answer), `POST /api/v1/things/{thingCode}/resolve/` (resolve a wish)
- Accessible from `/collections/:code/things/:thingCode` (collection context) or `/things/:thingCode` (standalone). **Public route** — an anonymous visitor can read a thing in a PUBLIC, ACTIVE collection (gated server-side by `can_view`); no redirect to `/login`.
- **Anonymous login-to-act**: for a signed-out visitor the reserve / answer buttons are shown (via `useThingActions`' `loginToAct` option) but each click **navigates to `/collections/:code/join`** (`JoinPage`) instead of acting — the same pattern as `ThingLinkbox` on `CollectionPage`. (The old inline `JoinToAct` box was removed.) Member-only sections (FAQ ask form, report footer, wish responses) stay hidden until they log in.
- **Tags row** (before headline): same HDS `Tag` components as ThingLinkbox (type, Taken, Inactive, Pending questions).
- Displays photos, headline, description, creation date, fee, availability, location, and condition. Photos render via `ImageCarousel` when the thing has more than one (cover `thumbnail_url` + `gallery_urls`); a single photo shows as a plain image.
- **Live availability** (date-based types LEND/RENT): read from the `available_today` / `next_available` serializer fields (computed from the booking calendar). When available today it shows the **same label as SELL things**, `t('availability.IMMEDIATE')` ("Immediate"/"Inmediata") — no green styling; otherwise the `next_available` date as day/month (e.g. "14/6") via `availability.nextAvailable`, or `availability.noneSoon` ("No"). Replaces the static `availability` enum row for date-based types only; non-date types keep the static enum hint. Also surfaced on `RequestThingPage` (above the date pickers, prefixed with the availability label).
- **Back link**: shows collection headline or "Home" depending on navigation context (via `location.state.backLabel`).
- **Owner bookings display**: fetches `GET /api/v1/things/{thingCode}/calendar/` for date-based/order types and for any TAKEN thing (GIFT/SELL). Same logic as ThingLinkbox: filters past bookings, syncs `activePendingCode` to the first PENDING from the calendar, shows bookings list with requester name, request date, date ranges/delivery info, and status. Active pending booking is bold; starred when multiple pending exist.
- **Owner actions:** Full parity with ThingLinkbox button matrix:
  - `ACTIVE` (no pending): "Edit" (**primary**) + "Delete" (secondary, suppressed when pending bookings exist). No "Hide" button — hiding is setting the thing `INACTIVE` via `EditThingPage`.
  - `ACTIVE` (date-based/order with pending): "Confirm hold" + "Cancel hold" + "Edit" (secondary).
  - `TAKEN`: "Confirm hold" (primary) → "Cancel hold" (secondary) → "Edit" (secondary). `activePendingCode` advances to next pending after each action.
  - `INACTIVE`: "Reactivate" (primary) + "Edit" (secondary) + "Delete" (secondary).
  - Delete navigates to `DeleteThingPage` with `{ state: { backPath, backLabel } }`.
- **Wish answers:** For WISH_THING, non-owners see the `<RespondMenu>` "Contestar" dropdown (or a status line if they already answered via `thing.my_response`). A **Responses** section lists answers (the creator sees all via `GET /things/{code}/responses/`; a responder sees only their own) with responder name, kind, message/link/price, and the linked listing for "Tengo esto". The creator gets an **Accept** button per pending answer (`POST /wish-responses/{code}/accept/`) and a **Marcar como resuelto** button (`POST /things/{code}/resolve/`), which hides the wish. Both actions notify another person, so each opens an inline consequence-confirm before it commits (the `.thing-report-confirm` pattern — `aria-expanded`, no modal, per DESIGN §3).
- **Reservation:** For non-wish types, non-owners see "Hold" button (or "Propose swap" for SWAP_THING). GIFT/SELL/SHARE types submit directly via `POST .../request/`; date-based (LEND/RENT), order, and swap types navigate to `RequestThingPage` with `{ state: { backPath, backLabel } }`. Owner bookings for SWAP_THING display offered thing headlines.
- **FAQs section:**
  - Lists all FAQs with question, `questioner_name`, and answer. Hidden FAQs shown with reduced opacity (owner only).
  - **Owner:** inline `TextArea` to answer unanswered questions, "Hide"/"Show" toggle button per FAQ.
  - **Non-owner:** `Fieldset`-wrapped form to ask a new question.
- **Journey section** (below FAQs): fetches `GET /api/v1/things/{thingCode}/transfers/` on mount. Shown only when `total_transfers > 0`. For SHARE_THING in COMMUNITY collections (`is_share_in_community`): shows "Sharing history" heading, "Originally shared by {name}" block, "Shared by N people" narrative, and a CSS timeline (`.share-timeline`). For other things: displays the standard journey view with journey count (unique homes), current holder name, and a timeline of transfers (from → to, lent date, returned date).
- **Report footer** (#12): a quiet supplementary `Button` with `IconAlertCircleFill` (`.thing-report-footer`), shown only to logged-in non-owners. Clicking **expands an inline confirm right below the button** (`.thing-report-confirm`, `aria-expanded` on the button — no modal): "Report this listing?" + a note that the owner is told *someone* reported it, never who, and Report/Cancel actions. Confirming `POST`s `/api/v1/things/{thingCode}/report/` and shows a thank-you Toast (`thingPage.reportThanks`). The backend records an anonymous `Report` (moderation log) and sends the owner an anonymous `THING_REPORTED` notification + email. Reporting is authenticated-only and idempotent per member.

### RequestThingPage (`src/pages/RequestThingPage.jsx`)

- **APIs:** `GET /api/v1/things/{thingCode}/` (detail), `GET /api/v1/things/{thingCode}/calendar/` (blocked periods for date-based types), `POST /api/v1/things/{thingCode}/request/` (submit request)
- Accessible from `/collections/:code/things/:thingCode/request` (collection context) or `/things/:thingCode/request` (standalone).
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Back link**: uses `location.state.backPath` and `location.state.backLabel` passed from ThingLinkbox or ThingPage.
- **Page title**: `Hold: {thing.headline}` with fee display when present.
- **Form fields** adapt to thing type:
  - `SWAP_THING` — Fetches user's own SWAP_THING items in the same collection. Shows HDS `Checkbox` per item for multi-select. Submits `{ offered_thing_codes: [...] }`. "Propose swap" button disabled until at least one item selected.
  - `LEND_THING`, `RENT_THING` — `DateInput` for start and end dates with blocked-date validation. (SHARE_THING never routes here — it submits directly from the card/detail page.) **Rental rules (#7):** when the thing's collection defines `rental_durations` (from `ThingSerializer`), the free start/end pickers are replaced by a **duration `Select`** (the collection's fixed lengths) + a single **pickup `DateInput`**; the return date is derived (`pickup + length`, shown as "Return by …" — a one-week rental picked up on a Wednesday returns the NEXT Wednesday, so a single allowed weekday stays satisfiable). The pickup picker (`isPickupDisabled`, via `utils/rental.js`) disables days whose weekday — or the computed return day's weekday — isn't in `rental_weekdays`, and any day whose range overlaps a booking. The request POSTs `collection_code` so the backend applies the right collection's rules.
- **Date validation**: `minDate` today, `maxDate` today + 90 days. Blocked dates fetched from calendar API. The DateInputs display **DD/MM/YYYY** (`DISPLAY_DATE_FORMAT` from `utils/rental.js`); field state holds the display string and converts to ISO at the consumption boundaries (`displayToIso` for the POST body and the derived return date, which renders back via `isoToDisplay`). When the collection offers a **single** fixed rental length, it is preselected so the pickup picker is usable straight away.
- **Buttons**: Cancel (navigates back) + Hold/Propose swap (submits request).
- On success: shows an inline HDS `Notification` ("You're all set! We've let the owner know — they'll get back to you soon.") with a "Back to {backLabel}" button. Does not navigate automatically.
- On error: toast notification (top-right, auto-close).

### RespondWishPage (`src/pages/RespondWishPage.jsx`)

- **API:** `POST /api/v1/things/{thingCode}/responses/`
- Short answer form for a wish, reached from the `<RespondMenu>` "Contestar" dropdown. `:kind` (`know-where` or `can-make`) maps to the backend `kind` via `WISH_KIND_BY_SLUG`. (The third option, "Tengo esto", uses `AddThingPage` in respond mode instead.)
- **Fields:** `TextArea` for the message (required) plus — for "Sé dónde" — a `TextInput` for an optional link, or — for "Puedo hacértelo" — a `NumberInput` for an optional offer/price.
- Standard `form-hero` + `Koros` layout. On success shows an inline `Notification` with a "Back" button; on error a toast.

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

### LeaveCollectionPage (`src/pages/LeaveCollectionPage.jsx`)

- **API:** `POST /api/v1/collections/{code}/leave/` (no body).
- Accessible from `/collections/:code/leave` (protected route). Reached from the **"Leave the group"** button in the `CollectionPage` hero, shown to invited members (`collection.is_member && !isOwner`); the button passes `{ state: { headline } }`.
- Confirmation page (same pattern as `RemoveGuestPage`/`DeleteThingPage`): shows the collection headline, a warning, and **Leave the group** (primary) + **Cancel** (secondary, back to the collection).
- On success: navigates to Home (`/`) — for a PRIVATE collection the user has just lost access. On error: toast.
- The backend removes the user from `invites` and notifies the owner (`MEMBER_LEFT` in-app). The owner and non-members never see the button (`is_member` gate).

### MyBookingsPage (`src/pages/MyBookingsPage.jsx`)

- **API:** `GET /api/v1/my-bookings/`, `POST /api/v1/bookings/{code}/cancel/` to cancel
- Redirects to `/login` if no `userCode` in `localStorage`.
- Lists all booking requests made by the current user.
- Each booking card shows: thing type tag, status label (HDS `StatusLabel`, semantic — Pending/Confirmed/Rejected/Cancelled/Expired), thing headline (linked to thing page), owner name, dates/quantity, and creation date.
- PENDING bookings show a "Cancel request" button. Non-pending bookings are grouped under "Past requests".
- Accessible from HomePage via "My requests" button.

### NotFoundPage (`src/pages/NotFoundPage.jsx`)

- Catch-all 404 page for unknown routes.
- Uses the standard `form-hero` + `Koros` layout with theeeme colors from localStorage (or defaults).
- Shows a "Page not found" title and message with a button to go home or login.

### SharePage (`src/pages/SharePage.jsx`)

- **API:** `POST /api/v1/auth/pop-in/` with `{ email, share_token }`.
- Public route at `/share/:token`. The owner has previously generated this token via the `ShareCollectionMenu` in CollectionPage; anyone with the link can land here and join the collection.
- Same UX as `PopInPage` — both pages render the shared `MagicLinkJoinPage` component (see Shared Components) with their own copy; SharePage additionally sends `share_token` in the POST body.
- Invalid / revoked / inactive-collection tokens return 200 with the same magic-link response (anti-enumeration). The user gets a magic link; if the token was invalid they simply land on `/welcome` or `/` rather than on the target collection.
- Uses the standard `form-hero` + `Koros` layout with theeeme colours from localStorage (or defaults when the recipient has no prior session).

### LogoutPage (`src/pages/LogoutPage.jsx`)

- Calls `POST /api/v1/auth/logout/` **via `apiFetch`** to clear auth cookies on the backend. It used a raw `fetch` with no `X-CSRFToken` header, so the POST was rejected by `CookieJWTAuthentication.enforce_csrf` (403) before `LogoutView` ran: the cookies survived, the refresh token was never blacklisted, and the session resurrected on the next page load — while the `.finally()` navigated to `/login` and made it *look* logged out. `LogoutView` now authenticates nothing either, so the request can't fail (see `core/views/CLAUDE.md`).
- Clears `userCode` and `seenWelcome` from `localStorage`.
- Navigates to `/login` immediately.

### AddThingPage (`src/pages/AddThingPage.jsx`)

- **API:** `POST /api/v1/things/` with `collection_code` in body
- Redirects to `/login` if no `userCode` in `localStorage`.
- **Wish creation:** when `type === WISH_THING`, an "Avisar al grupo" `ToggleButton` (default on) appears and its value is sent as `notify_group` so the backend broadcasts the new wish to the group.
- **Respond mode:** when reached with `location.state.respondWishCode` (from the "Tengo esto" answer option), an info banner is shown, `WISH_THING` is removed from the type selector, and on successful create the page chains a `POST /api/v1/things/{respondWishCode}/responses/` with `kind=HAVE_THIS` to link the new listing as an answer, then navigates back to the wish.
- Simple form with h1 title + `form-grid` layout:
  - `Select` for thing type (WISH_THING and SHARE_THING only shown when collection is COMMUNITY; SWAP_THING is not a generic option — it is offered only in swap-only collections). The select is also filtered down to `collection.allowed_thing_types` when that field is non-empty (PROPRIETARY collections set this on Create/Edit). When the allowlist contains a single type, it is pre-selected so downstream fields show right away. Immediately after the type selector: `ToggleButton` for "Sin límite / Endless" (shown only for GIFT/SELL types). When collection `is_swap`: the selector is shown with `[SWAP_THING, WISH_THING]` (default SWAP_THING); when `is_share`: shown with `[SHARE_THING, WISH_THING]` (default SHARE_THING) — swap-only/share-only collections also accept wishes. In both, the selector is hidden only in respond mode (a wish can't answer a wish). `TextInput` for headline (required, max 64), `TextArea` for description. `NumberInput` for fee (required for SELL/RENT/ORDER types, hidden for others). For GIFT/SELL/LEND/SHARE types (`DETAIL_TYPES`): `Select` for availability, `TextInput` for location (max 32), `Select` for condition. `ImageUpload` for thumbnail (last, before button, folder `oiueei/things`).
  - "Create" button below the form. Validates on submit.
- On success: navigates to `/collections/{code}`.
- On error: toast notification (top-right, auto-close).

### EditThingPage (`src/pages/EditThingPage.jsx`)

- **API:** `GET /api/v1/things/{thingCode}/` to load, `PATCH /api/v1/things/{thingCode}/` to save, `DELETE /api/v1/things/{thingCode}/` to delete
- Accessible from `/collections/:code/things/:thingCode/edit` or `/things/:thingCode/edit`.
- Same fields as AddThingPage (type, then `ToggleButton` for Endless immediately after type for GIFT/SELL, headline, description, fee, availability/location/condition for `DETAIL_TYPES`, `ImageUpload` for thumbnail last). Pre-populates all fields including existing `thumbnail_url` for preview.
- "Save" button (primary, full width) and "Delete" button (secondary, full width) below the form. Delete navigates to `DeleteThingPage` with `{ state: { backPath: returnPath, backLabel: returnLabel } }`.
- On success: navigates back to collection or home.

### EditProfilePage (`src/pages/EditProfilePage.jsx`)

- **API:** `GET /api/v1/auth/me/` to load, `GET /api/v1/theeemes/` to list themes, `PUT /api/v1/users/{userCode}/` to save
- **Back link**: dynamic via `location.state.backPath` / `location.state.backLabel` (defaults to `← Home` / `/`).
- Simple form with h1 title + `form-grid` layout:
  - `TextInput` for name, `TextArea` for headline (short "Bio", max 64), `TextArea` for `about` (long free-form Markdown profile content, max 2000, "Markdown supported" helper), `ImageUpload` for the profile `photo` (folder `oiueei/users`), `TheeemeSelector` for theeeme (visual colour swatch grid from API), `KoroSelector` for koro (visual Koros SVG preview grid). All five are saved with the profile via the single PUT.
  - **Email preferences section** (h2 heading + `notifications.intro` paragraph + `form-grid`): three HDS `ToggleButton` components (wrapped in `.toggle-left`) — "Sign-in links and invitations" (always checked, `disabled`, renders black pill, Cat. 1), "Activity between users" (`notify_activity`, Cat. 2), and "News and announcements" (`notify_news`, Cat. 3). Each has a sub-label helper text rendered as a `<span>` inside the label prop. Preferences are saved together with profile fields via a single Save button.
  - "Save" button below the preferences section.
- Pre-populates all fields (including `notify_activity`/`notify_news`) from the current user profile.
- On success: navigates to `/`.

### NotificationsPage (`src/pages/NotificationsPage.jsx`)

- **API:** `GET /api/v1/notifications/token/{token}/`, `PATCH /api/v1/notifications/token/{token}/`.
- Accessible from `/me/notifications/:token` — a signed (`TimestampSigner`, ~1y TTL) token is included in the footer of every Cat. 2 / Cat. 3 email for unauthenticated preference editing.
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
  - `TextInput` for headline (required), `TextArea` for description, `Select` for status (ACTIVE/INACTIVE), an HDS `RadioButton` group (fieldset/legend) for mode (Proprietary/Community) with a per-option inline description (`createCollection.modeProprietaryDesc`/`modeCommunityDesc`), `ToggleButton` for "Enable item swapping" and `ToggleButton` for "Exclusively SHARE things" (visible only when mode is COMMUNITY; swap and share are mutually exclusive with each other), `ToggleButton` for "Require 3 items before swapping" (visible only when swap is enabled; saves `swap_minimum_items=3` when on, `0` when off), `ToggleButton` for "Weekly activity newsletter" (visible when share is enabled), `Select multiSelect` for allowed thing types (visible for PROPRIETARY always, and for COMMUNITY when neither `is_swap` nor `is_share` is on; default `[]` so the user must explicitly pick at least one. Toggling any of `is_swap`/`is_share`/mode preserves the still-valid intersection of the current selection (`reconcileAllowedTypes`) instead of clearing it — locked combos (swap/share) snap to their single forced type — and "pick at least one" is validated live after the first submit attempt. Save fails with 400 from backend if narrowing would orphan existing things — the response detail names the offending types and is surfaced via Toast.), `Select` for digest frequency (None/Weekly/Monthly), `ImageUpload` for thumbnail (folder `oiueei/collections`). All toggles use the `.toggle-left` wrapper class. **Rental rules (#7):** rendered by `CollectionForm` via `utils/rental.js` for non-swap/non-share collections — a `Select multiSelect` for rental lengths plus a `[L M X J V S D]` **weekday chip row** (`.weekday-chips`, accessible toggle `<button>`s with `aria-pressed` + full-name `aria-label`, narrow letters via `Intl`) for pickup/return days. They save `rental_durations` (days) + `rental_weekdays` (0=Mon…6=Sun).
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
  - `TextInput` for headline (required), `TextArea` for description, an HDS `RadioButton` group (fieldset/legend) for mode (Proprietary/Community) with a per-option inline description (`createCollection.modeProprietaryDesc`/`modeCommunityDesc`), `ToggleButton` for "Enable item swapping" and `ToggleButton` for "Exclusively SHARE things" (visible only when mode is COMMUNITY; swap and share are mutually exclusive with each other), `ToggleButton` for "Require 3 items before swapping" (visible only when swap is enabled; saves `swap_minimum_items=3` when on, `0` when off), `ToggleButton` for "Weekly activity newsletter" (visible when share is enabled), `Select multiSelect` for allowed thing types (visible for PROPRIETARY always, and for COMMUNITY when neither `is_swap` nor `is_share` is on; default empty, user must pick at least one. Toggling any of `is_swap`/`is_share`/mode preserves the still-valid intersection of the current selection (`reconcileAllowedTypes`) instead of clearing it — locked combos snap to their single forced type — and "pick at least one" is validated live after the first submit attempt). All toggles use the `.toggle-left` wrapper class. **Rental rules (#7):** rendered by `CollectionForm` via `utils/rental.js` for non-swap/non-share collections — a `Select multiSelect` for rental lengths plus a `[L M X J V S D]` **weekday chip row** (`.weekday-chips`, accessible toggle `<button>`s with `aria-pressed` + full-name `aria-label`, narrow letters via `Intl`) for pickup/return days. They save `rental_durations` (days) + `rental_weekdays` (0=Mon…6=Sun).
  - "Create" button below the form.
- On success: navigates to `/collections/{code}`.

### UserPage (`src/pages/UserPage.jsx`)

- **API:** `GET /api/v1/users/{userCode}/`
- Also serves as `/me` route: when no `userCode` param, fetches `/api/v1/auth/me/` to resolve own code.
- Redirects to `/login` if no `userCode` in `localStorage`.
- Handles 403 (no permission) and 404 (user not found) with specific error messages.
- Uses the standard `form-hero` + `Koros` layout with theeeme colors (own profile uses `theeeme_colors` from API, other profiles fall back to localStorage).
- Hero follows the WelcomePage pattern: BackLink, spacer, headline as Heading M subtitle, name as h1 title, "Member since" date.
- **Profile photo:** when `user.photo_url` is present, rendered via the shared `HeroPhoto` component (see Shared Components). **≥768px** keeps the original **layered** composition, pixel-identical: the photo (`.hero-photo-wrap`) is a full-bleed background (z0); a `color_03` `Koros` wedge (`.hero-photo-diag`) sits above it (z1) — a large solid fill block plus the `Koros` wave rotated 135° as one unit, anchored at the hero centre (`translateY` sizes the wedge) — carving a diagonal so the text reads on the colour band while the photo shows through the wedge; the content (`.form-hero-split` → title/name/buttons) sits on top (z2). The decorative Koros keeps its natural 85px height (no override) so its fill meets the block with no gap; both are `aria-hidden` and filled with theeeme `color_03`. **<768px** switches to a stacked "image bottom" hero (HDS reference pattern): `.form-hero-split` flows normally above on the `color_03` band, `.hero-photo-diag` is hidden, `.hero-photo-top-koros` (a second `Koros`, `display:none` by default so it never shows ≥768px) appears biting the photo's top edge (`margin-bottom: -14px`, same overlap technique as the bottom `.form-hero-koros`), and `.hero-photo-wrap`/`.hero-photo` switch from `position: absolute` to a plain full-width `static` block (`height: 260px`, `object-fit: cover`). The photo gets an `alt` of the user's name. When absent, the plain hero is unchanged at every width.
- **About box:** when `user.about` is present, a "{{userPage.aboutHeading}}" section in the page container renders the Markdown via the shared `MarkdownText` component (no new dependency). Shown on both own and other profiles.
- **Own profile:** shows "Edit profile" and "Log out" buttons in the hero. No collections listed — those are now on the HomePage (`/`).
- **Other profiles:** shows "Collections in common" section with shared collections (where both users are connected as owner/invite) as `CollectionLinkbox` rows (image-less, full-width — see HomePage's "My collections section" note and Shared Components).

---

## Shared Modules

### API Service (`src/services/api.js`)

- `apiFetch(url, options)` — Centralised fetch wrapper. Uses `credentials: 'include'` for cookie-based auth, sets `Content-Type: application/json` for requests with body. On 401: silently attempts token refresh via `POST /api/v1/auth/refresh/`. Only `userCode` is stored in localStorage (for ownership checks).

### Custom Hooks

- **`useThingBooking`** (`src/hooks/useThingBooking.js`) — The lower-level booking **engine**: owns the reservation state, the owner-calendar fetch (`AbortController`-guarded, re-runs by `thing.code`), and the three async handlers (`handleRequest`, `handleActivate`, `handleBookingAction`). The card-vs-page differences are options (`initialActivePending`, `initialRequested`, `fetchOnEndless`, `bookingKeepsStatus`, `activateSuccessMessage`). Returns `{ submitting, requested, bookingAction, bookingActionVerb, activating, bookings, activePendingCode, handleRequest, handleActivate, handleBookingAction }`.
- **`useThingActions`** (`src/hooks/useThingActions.js`) — The **view-model** layer wrapping `useThingBooking`, shared by `ThingLinkbox` and `ThingPage` so the owner-button-matrix / reserve-button logic lives in one place. Derives the type flags (`isOwner`, `isCollectionOwner`, `isWish`, `isShare`, `isSwap`, `isDateBased`, `needsPage`, `canDelete`, `hasPendingBookings`), the swap-minimum gate (`swapMinimumNotMet`, `swapItemsMissing`), and the reserve button's `showButton` / `buttonDisabled` / `loginButtonDisabled` / `buttonLabel` — plus everything `useThingBooking` returns. The genuine differences are options: `isPaused` (card on a paused collection; the page passes false), `canAct` (the page passes `isAuthenticated`), `loginToAct` (anonymous-on-public — buttons show but each click routes to `/collections/:code/join`), `collectionOwner`, and the `useThingBooking` seeds. `bookingKeepsStatus` (`needsPage || is_endless`) is derived here so callers don't repeat it. Signature: `useThingActions(thing, userCode, options)`.

### Shared Components

- **`BackLink`** (`src/components/BackLink.jsx`) — Reusable `← {label}` back navigation link. Props: `to`, `label`.
- **`Toast`** (`src/components/Toast.jsx`) — Reusable toast notification wrapping HDS `Notification`. Props: `toast` (`{ type, message }`), `onClose`. Renders at `position="top-right"` with auto-close.
- **`LoadingSpinner`** (`src/components/LoadingSpinner.jsx`) — Wrapper around HDS `LoadingSpinner` component.
- **`MagicLinkJoinPage`** (`src/components/MagicLinkJoinPage.jsx`) — Shared pop-in landing page rendered by `PopInPage` and `SharePage`: a `PageLayout` hero + email form that POSTs to `/api/v1/auth/pop-in/` and swaps into a sent/error `Notification` (with the "you can close this tab" line on success). Props: `ns` (`'popin'` | `'share'` — namespace for the form strings and the `{ns}-email` input id), `docTitleKey` / `titleKey` / `descriptionKey` (full i18n keys — their names differ per page), `extraBody` (extra POST fields, e.g. SharePage's `share_token`). `JoinToAct` (JoinPage's variant of the same flow) deliberately stays separate — it renders unboxed inside another page's hero and reports errors inline.
- **`FeedbackLink`** (`src/components/FeedbackLink.jsx`) — Quiet one-line alpha-feedback prompt ("Something odd? An idea? Tell me →") linking to the Tally form (`tally.so/r/A76Xkz` by default — same one as the README; a deployment can point it elsewhere with the `VITE_FEEDBACK_URL` build-time env var, e.g. a Heroku config var picked up by the `heroku-postbuild` build). Rendered at the foot of HomePage and WelcomePage (`.feedback-link`, muted `--color-black-60`).
- **`ThingTags`** (`src/components/ThingTags.jsx`) — Shared tag row for thing type, status, pending questions, and the thing's **owner-defined tags** (`thing.tags`, rendered with `TAG_THEMES.custom`). Props: `thing`, `isOwner`. Uses `TAG_THEMES` from constants.
- **`ThingReportFooter`** (`src/components/ThingReportFooter.jsx`) — The quiet "report this listing" footer on `ThingPage` (logged-in non-owners). Owns its open/submitting state + the report POST; expands an inline confirm (`.thing-report-confirm`, `aria-expanded`, no modal) and reports feedback via `onToast`. Props: `thingCode`, `onToast`.
- **`ThingFaqSection`** (`src/components/ThingFaqSection.jsx`) — The FAQ block on `ThingPage`: question list (owner sees hidden ones + answer / hide-show controls), a "Load more" pager, and the ask-a-question form for logged-in non-owners. Self-contained — owns its FAQ list + form state and fetches its own FAQs on mount (by `thingCode`). Props: `thingCode`, `isOwner`, `isAuthenticated`, `btnStyle`, `btnSecondaryStyle`, `tc`, `onToast`.
- **`WishResponsesList`** (`src/components/WishResponsesList.jsx`) — The wish-answers section on `ThingPage` (creator sees all + accept/resolve inline confirms; a responder sees their own). Owns the answers list + its fetch (on mount, by `thing.code`) and the accept/resolve handlers; calls `onResolved` so the parent flips the wish to INACTIVE. Only mounted for an authenticated creator/responder. Props: `thing`, `isOwner`, `code`, `btnStyle`, `btnSecondaryStyle`, `onToast`, `onResolved`.
- **`TagInput`** (`src/components/TagInput.jsx`) — Chip-style free-text editor for the collection owner to define the collection's tag vocabulary. `TextInput` + "Add" (and Enter) appends a removable HDS `Tag` (via `onDelete`); trims, dedupes case-insensitively, caps at 12 tags / 32 chars each (mirrors the backend `_normalize_tags`). Props: `tags`, `onChange`, `label`, `placeholder`, `helperText`, `max`. Used in CreateCollectionPage, EditCollectionPage. The thing forms (Add/EditThingPage) instead use an HDS `Select multiSelect` populated from the collection's `tags` / `collection_tags` to assign a subset to a thing.
- **`ImageUpload`** (`src/components/ImageUpload.jsx`) — Single-image upload using HDS `FileInput`. Gets a short-lived Cloudinary signature from `POST /api/v1/upload/signature/`, resizes images client-side to max 1216px, uploads directly to Cloudinary, and calls `onChange(publicId)`. Shows a preview with a Remove button when an image is present; the FileInput is hidden while a preview exists. Button label and accept hint are translated via i18n. Button colours follow the current theeeme. Props: `id`, `label`, `value` (public_id), `onChange`, `currentUrl`, `folder` (Cloudinary folder, default `oiueei/users`), `helperText`. Used in AddThingPage, EditThingPage, and EditProfilePage (profile photo). The client-side resize-to-1216px helper lives in `src/utils/resizeImage.js` and is shared with `GalleryUpload`.
- **`GalleryUpload`** (`src/components/GalleryUpload.jsx`) — Multi-image upload for a thing's extra photos (the `gallery` field). Same Cloudinary signed-upload + client resize as `ImageUpload` (folder `oiueei/things`), max 8 images. Renders a thumbnail row with remove buttons. Items are `{publicId, url}` pairs so the parent can preview and submit `items.map(i => i.publicId)`. Props: `items`, `onChange`. Used in AddThingPage, EditThingPage.
- **`CollectionLinkbox`** (`src/components/CollectionLinkbox.jsx`) — A collection row (HDS `Linkbox`, deliberately **no thumbnail** — S8) used by HomePage's three collection grids and UserPage's "Collections in common". Rendered inside `.collections-grid` (`display:flex; flex-direction:column` — a vertical stack of full-width rows at every breakpoint, not a multi-column grid; the global `max-width:400px` Linkbox cap is neutralised the same way `linkbox-full-width` does elsewhere). Props: `collection` (`{code, headline, things?, invites?}`), `showInfo` (shows the "{N} things · {N} guests" line — the Home grids pass counts, the profile grid omits it).
- **`HeroPhoto`** (`src/components/HeroPhoto.jsx`) — The photo block for a `.form-hero.form-hero--photo` hero (see the UserPage "Profile photo" note above for the full ≥768px/<768px behaviour). Render as a sibling of `.form-hero-split`, inside `.form-hero.form-hero--photo`. Props: `photoUrl`, `alt`, `koroType` (the viewer's koro preference), `color03` (the hero's `color_03` theeeme token name, for the wedge/wave fill). Generic — no page-specific classes — used unchanged by both `UserPage` (profile photo) and `CollectionPage` (collection thumbnail, S8).
- **`InfoPopover`** (`src/components/InfoPopover.jsx`) — Generic (i) icon button that reveals an info panel on hover/focus/click, closing on mouse-leave/blur. **The positioning class (`.info-popover-panel`) lives on the wrapper `<div id={id}>`, never passed as `className` to the HDS `Notification`** — Notification's rendered root already carries HDS's own `position: relative` at the same selector specificity as a single custom class, so which one wins the cascade depends on style-injection order (the original bug: BulkInviteCsv's popover sometimes rendered in flow instead of absolutely positioned, squeezing the layout). `aria-controls` is only set while open (axe-valid — a collapsed trigger never references an absent id). Pair with the `.info-popover-row` class (`display:flex; justify-content:space-between`) so the icon sits flush at the row's right edge, keeping the `right: 0`-anchored panel inside the viewport. Props: `title` (panel label + button's accessible name), `children` (panel body), `id` (panel id, referenced by `aria-controls`). Used by `BulkInviteCsv` and `BulkAddCsv`.
- **`BulkAddCsv`** (`src/components/BulkAddCsv.jsx`) — CSV/ZIP bulk-add of things (F-9). Accepts either a plain `.csv` or a `.zip` (CSV + image files). Parses the CSV client-side with **PapaParse** (`header:true`, lower-cased headers), maps the recognised columns (type, headline, description, fee, availability, location, condition), plus `tags` (a single cell holding a `|`-separated list — pipe, not comma, since `;`/`,` clash with CSV field delimiters across locales) and `photo` (a filename, ZIP only). For a ZIP it lazy-loads **JSZip** (dynamic `import()` → separate bundle chunk), finds the CSV + images by basename, and on import uploads each referenced photo to Cloudinary via the shared `uploadImageToCloudinary` helper (`src/utils/uploadImage.js`, same signed-upload + 1216px resize path as `ImageUpload`/`GalleryUpload`), then sends the resulting public_id as `thumbnail` per row. POSTs `{rows}` to `POST /api/v1/collections/{code}/things/bulk/` (atomic all-or-nothing; server rejects HTML, line breaks and `=+-@` spreadsheet-formula injection per field, and validates `tags` against the collection vocabulary + `thumbnail` as a path-safe Cloudinary id). Client-side guards: ≤100 rows, every row needs a `headline`, every referenced `photo` must exist in the ZIP. The visible section is just a short help line, the `FileInput`, and an `InfoPopover` (i) — the long column reference, tags/ZIP-photo explanation, `EXAMPLE_CSV` and the "Download example (ZIP)" link all live inside the popover. Props: `collectionCode`, `onImported(count)`. Rendered in AddThingPage in its own section (hidden in respond-wish mode).
- **`BulkInviteCsv`** (`src/components/BulkInviteCsv.jsx`) — CSV bulk-invite of collection guests. Parses a CSV (`email` required, `name` optional) client-side with PapaParse, previews the addresses, then POSTs to the best-effort batch endpoint `POST /collections/{code}/invite/bulk/`; valid new addresses are invited and emailed, the rest come back as skipped with a reason (invalid/duplicate/already a member/already invited), shown in the result summary. The CSV format reference (`formatTitle`/`formatBody` + an example table) lives in an `InfoPopover` next to the short help line. Props: `collectionCode`, `onInvited()`. Rendered in ManageInvitesPage.
- **`ImageCarousel`** (`src/components/ImageCarousel.jsx`) — Lightweight image carousel ("Image pagination"). Prev/next arrows only (HDS `IconAngleLeft`/`IconAngleRight`, black icons; disabled — black-40 — at the first/last image, non-cyclic), plus touch swipe and keyboard arrows. No autoplay, no dots; per-slide `aria-label` ("image X of N"). Rendered when a thing has more than one photo (cover `thumbnail_url` first, then `gallery_urls`); a single photo falls back to a plain `<img>`. Used by `ThingPage` (`variant="detail"`) and by `ThingLinkbox` on the collection grid (`variant="card"` — matches the card cover sizing). Props: `images` (URL array), `alt` (thing headline), `variant` (`detail`|`card`), `to` (optional route — when set the image links to the thing while the arrows only change the photo).
- **`TheeemeSelector`** (`src/components/TheeemeSelector.jsx`) — Visual theeeme picker. Renders a grid of buttons; each button shows three 20 px circular swatches (`color_01`, `color_02`, `color_03`) and the theeeme name, with a checkmark when selected. `aria-pressed` and `aria-label` for accessibility. Props: `theeemes` (array from API), `value` (selected code), `onChange`. Used in EditProfilePage.
- **`KoroSelector`** (`src/components/KoroSelector.jsx`) — Visual koro picker. Renders a grid of buttons; each button shows a live `<Koros>` SVG preview (white fill on black background, 50 px tall, scaled to fit) and the koro label. Props: `value` (selected type string), `onChange`. Used in EditProfilePage.
- **`RespondMenu`** (`src/components/RespondMenu.jsx`) — The "Contestar" dropdown for a wish (shown to non-owners on `ThingLinkbox` and `ThingPage`). HDS `Select` used as a one-shot menu (like `ShareCollectionMenu`) with three options: "Tengo esto" routes to `AddThingPage` in respond mode, "Sé dónde" / "Puedo hacértelo" route to `RespondWishPage`. Strings live in the `wishes` i18n namespace. Props: `thingCode`, `collectionCode`, `backPath`, `backLabel`.
- **`ShareCollectionMenu`** (`src/components/ShareCollectionMenu.jsx`) — Owner-only share menu rendered in the CollectionPage hero. HDS `Select` with four share options (`IconEnvelope` for email, `IconShare` for copy-link, `IconWhatsapp` for WhatsApp, `IconCamera` for a QR dialog). URL resolution depends on the `isPublic` prop: **private** collections call `POST /api/v1/collections/{code}/share-link/` lazily on first interaction and share the `/share/{token}` pop-in link; **public** collections skip that call and share the collection URL directly (`${window.location.origin}/collections/{code}`) — no email gate, since public collections are anonymously readable. The resolved URL is cached via `useRef` and dispatched: `mailto:` for email, `navigator.clipboard.writeText` + Toast for copy, `https://wa.me/?text=` for WhatsApp, an HDS `Dialog` with a `qrcode.react` QR for the QR action. For **PRIVATE** collections the menu also offers **Rotate link** and **Stop sharing** — each opens a consequence-confirm `Dialog`, then `POST {rotate: true}` / `DELETE`s the share token so the owner can pull back a bearer credential they've handed out (DESIGN §9); PUBLIC collections omit these (no token to revoke). The Select's value is reset on every change so it acts as a one-shot menu rather than a form input. Strings live in the `shareMenu` i18n namespace. Props: `collectionCode`, `collectionHeadline`, `ownerName`, `isPublic`.

### Constants (`src/constants/things.js`)

Central source of truth for thing type definitions. Display labels are handled by i18n — use `t('types.GIFT_THING')` etc.
- `TYPE_VALUES` — Array of type value strings (no labels — labels come from i18n).
- `SHARE_TYPE` — `SHARE_THING` constant (used for share-specific UI logic — hide button restriction after transfer).
- `WISH_TYPE` — `WISH_THING` constant (used for wish-specific UI logic).
- `WISH_KIND_SLUGS` / `WISH_KIND_BY_SLUG` / `WISH_KIND_I18N` — the URL-slug and i18n-key mappings for the three wish answer kinds (`HAVE_THIS`, `KNOW_WHERE`, `CAN_MAKE`), used by `RespondMenu`, `RespondWishPage`, and the responses list.
- `SWAP_TYPE` — `SWAP_THING` constant (used for swap-specific UI logic — swap request form, "Propose swap" button).
- `DATE_TYPES` — Types requiring start/end dates (`LEND_THING`, `RENT_THING`).
- `FEE_TYPES` — Types with a fee field (`SELL_THING`, `RENT_THING`).
- `DETAIL_TYPES` — Types with availability/location/condition fields (`GIFT_THING`, `SELL_THING`, `LEND_THING`, `SHARE_THING`).
- `AVAILABILITY_VALUES` — Array of availability value strings (labels from i18n).
- `CONDITION_VALUES` — Array of condition value strings (labels from i18n).
- `TAG_THEMES` — Theme objects for status tags (taken, inactive, pending).

---

## Internationalisation (i18n)

All UI strings are externalised via `react-i18next`. No hardcoded strings in components.

- **Setup:** `src/i18n/index.js` initialises i18next with `i18next-browser-languagedetector` (detection order `localStorage` → `navigator`, the chosen language cached in `localStorage`), falling back per `fallbackLng` for unsupported languages. **English (the fallback) is bundled eagerly** in `resources` so the first paint is always translated; Spanish and Catalan load on demand through a tiny custom i18next backend (`partialBundledLanguages: true`, `load: 'currentOnly'`) — see Locale files.
- **Supported languages:** English (`en`), Spanish (`es`), Catalan (`ca`).
- **Retired languages:** Brazilian Portuguese (`pt-BR`), European Portuguese (`pt-PT`), Basque (`eu`), and Galician (`gl`) were dropped from `supportedLngs`/`resources` 2026-07 (paused, not deleted — the locale JSONs are recoverable from git history). `fallbackLng` is an object mapping each retired code (plus bare `pt`) to `['es']`, with `default: ['en']` for any other unsupported browser language.
- **Locale files:** `src/i18n/locales/{lang}.json` — one JSON file per language with ~280 strings organised by namespace (common, titles, login, verify, home, collectionPage, thingPage, types, availability, condition, etc.). Only `en.json` ships in the main bundle; `es.json`/`ca.json` (~35 kB each) are **code-split into their own Vite chunks** via the backend's `import()` of the locale JSON and fetched only when that language is active (a non-English visitor briefly sees English before the chunk lands — `react: { useSuspense: false }`, so no spinner).
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
- **Smoke tests:** `src/test/smoke.test.jsx` — renders every page component with mocked API responses and runs `jest-axe` to detect WCAG violations. Covers all 26 page components.
- **i18n mock:** `src/test/i18n-mock.js` — initialises i18next with the real `en.json` for test rendering.

---

## Tech Stack

- **React 19** + **Vite 7** + **React Router 7**
- **hds-react** — Helsinki Design System React components (npm `^6.0.3`)
- **hds-design-tokens** — HDS CSS custom property tokens (npm `^6.0.3`)
- **hds-core** — HDS core CSS and base styles (npm `^6.0.3`)

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

- **Fonts** (`src/fonts/oiueei-fonts.css`) — the **Curiosa** variable font (`public/fonts/curiosa/Curiosa-Variable.woff2`, weight + italic axes), declared via `@font-face` honestly as `font-family: "Curiosa"` and served by Vite at `/fonts/curiosa/`. The HDS `--font-default` token's *value* is overridden to `"Curiosa", Arial, sans-serif` in `src/styles/oiueei-theme.css` — the token *name* is kept, so all HDS components resolve it transparently. The font binary is gitignored (licence); a clone without it falls back to Arial / system sans.
- **Colors** (`src/styles/oiueei-theme.css`) — CSS custom property overrides for the "Theeemes" color palette, imported after `hds-design-tokens` to take precedence.
- **Logos & brand assets** (`src/assets/`) — OIUEEI logos, placeholders, and favicon.

## Key Configuration (`vite.config.js`)

- **React deduplication** — Aliases `react` and `react-dom` to frontend's `node_modules` to prevent dual-copy hook errors (some HDS internal deps declare React 17 peer dep)
- **Proxy** — `/api` requests forwarded to `http://localhost:8000`
- **Dev server** on port 3000
- **Code splitting** — every page is `React.lazy`-loaded in `App.jsx` (the `Routes` block is wrapped in a `Suspense` whose fallback is `LoadingSpinner`), so each route ships as its own chunk and page-only deps (papaparse, qrcode, jszip) load on demand. `build.rollupOptions.output.manualChunks` further splits `vendor-react` and `vendor-hds` from app code for long-term caching (`chunkSizeWarningLimit` is raised to 600 kB because the shared `hds-react` chunk is ~575 kB raw / ~152 kB gzipped).

## Authentication Flow

1. User enters email on `/login`
2. Backend sends magic link email pointing to `localhost:3000/verify/{rsvp.token}` — the high-entropy token, never the 6-char RSVP code
3. `/verify/:code` calls the backend, which sets JWT tokens as HttpOnly cookies on the response
4. `userCode` is stored in `localStorage` (for ownership checks only — auth tokens are never in localStorage)
5. Authenticated pages use `credentials: 'include'` to send cookies automatically. On 401, `apiFetch` silently attempts token refresh via `POST /api/v1/auth/refresh/`
6. `userCode` is used to determine ownership (e.g. hide reservation button on own things)
7. CSRF cookie is obtained on app load via a GET to `/api/v1/auth/me/`
