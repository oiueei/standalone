# OIUEEI — Design Guidelines

These guidelines define how OIUEEI looks, feels, and communicates. They apply to every view, component, and piece of copy in the product. When designing or reviewing any new view, each principle below must be considered and respected.

---

## 1. Helsinki Design System (HDS) First

All frontend components must be based on the [Helsinki Design System](https://hds.hel.fi/) React library. Before building a custom component, check whether HDS already provides it. Custom components are only acceptable when HDS has no equivalent, and must follow HDS visual conventions to remain consistent.

There are two key references to consult:

- **[HDS Foundation](https://hds.hel.fi/foundation/)** — the design tokens that underpin everything: colour system, typography scale, spacing values, responsive breakpoints, shadows, and layout grid. These must be used instead of arbitrary values in custom code.
- **[HDS Components](https://hds.hel.fi/components/)** — the full library of ready-made React components, including buttons, form elements, navigation, cards, notifications, tables, tags, icons, and more.

**When designing a new view:** check HDS Components first. For any visual decisions (colour, spacing, typography), use HDS Foundation tokens. Only reach for custom solutions when HDS cannot meet the requirement.

---

## 2. Tone and Voice — Warm, Inclusive, Informal

We speak like a trusted neighbour, not a corporation or a cool startup. Our tone is:

- **Inclusive** — language that welcomes everyone, avoids jargon, and does not assume technical knowledge
- **Warm and friendly** — approachable and human, never cold or bureaucratic
- **Informal but respectful** — conversational without being flippant or trying too hard to be clever
- **Direct** — say what you mean, clearly and briefly

**When writing copy for a new view:** read it aloud. Does it sound like a person you'd trust? Rewrite anything that sounds corporate, pushy, or condescending.

---

## 3. Minimal, Clever, and Grounded

We are not an enterprise product. We are not a trendy tech startup. We are something simpler and closer to the people who use us. Our design reflects that:

- **Minimal** — show only what is necessary. Remove anything decorative that does not serve a purpose.
- **Clever** — solve problems elegantly. A good solution should feel obvious in hindsight.
- **Elegant** — clean layouts, generous whitespace, considered typography. Beauty through restraint.
- **Grounded** — avoid visual trends that prioritise novelty over usability. Timeless over fashionable.
- **Human** — beyond visibility and convenience, OIUEEI must foster emotional connections, honour the cultural meaning of each group, and strengthen the bonds between its members.

**When designing a new view:** ask what can be removed. If a UI element cannot be justified, it should not be there.

---

## 4. Mobile First

Mobile is the primary target. The experience must be excellent on a small screen before considering larger breakpoints. Tablets and desktops are secondary adaptations, not the default.

- Design and review every view at mobile viewport first
- Touch targets must be large enough (minimum 44×44px)
- Navigation, forms, and key actions must work flawlessly with one hand
- Tablet and desktop layouts are progressive enhancements, not the baseline

**Official HDS breakpoints** — these are the canonical six values from [HDS Foundation — Breakpoints](https://hds.hel.fi/foundation/design-tokens/breakpoints/). OIUEEI uses four of them and deliberately skips `breakpoint-s` (576 px) and `breakpoint-xxl` (1440 px). Use only these exact values in media queries — never invent ad-hoc breakpoints.

| Token | Min-width | Container width | HDS grid columns | Margin | OIUEEI uses |
|---|---|---|---|---|---|
| `breakpoint-xs` | 320px | 288px | 4 | 16px | ✓ (mobile default) |
| `breakpoint-s` | 576px | 544px | 4 | 16px | — (skipped) |
| `breakpoint-m` | 768px | 720px | 8 | 24px | ✓ |
| `breakpoint-l` | 992px | 944px | 12 | 24px | ✓ |
| `breakpoint-xl` | 1248px | 1200px | 12 | 24px | ✓ |
| `breakpoint-xxl` | 1440px | 1200px | 12 | 24px | — (skipped) |

**When designing a new view:** design mobile first, then adapt upwards. Never design desktop first and shrink down.

---

## 5. Accessible by Default — WCAG AA Minimum

Accessibility is not optional or an afterthought. A platform that values closeness and inclusion cannot exclude people.

- Meet [WCAG 2.1 AA](https://www.w3.org/TR/WCAG21/) as a minimum across all views
- Sufficient colour contrast, keyboard navigability, and screen reader support are baseline requirements
- HDS components provide strong accessibility foundations — use them correctly and do not override their accessible defaults
- Write meaningful labels, alt text, and ARIA attributes where needed

**When designing a new view:** verify colour contrast, ensure all interactive elements are keyboard accessible, and test with a screen reader where possible.

---

## 6. No Dark Patterns — Ever

We do not manipulate users. Our design must be honest and transparent at every interaction:

- No artificial urgency ("Only 2 left!", countdown timers that reset)
- No misleading consent flows or pre-ticked opt-ins
- No notifications designed to create anxiety or compulsion
- No interfaces that make it harder to cancel, unsubscribe, or opt out than to sign up
- No confirmshaming ("No thanks, I don't want to save money")
- **Notices have a budget.** One notice per fact and per person; what only informs is folded by default; no new notice type ships without saying whether it informs or asks for an action (`InAppNotification`'s two lists, held by a test).

**When designing a new view:** if a pattern benefits us at the expense of the user's understanding or autonomy, remove it.

---

## 7. Performance as a Value

Not everyone has the latest device or a fast connection. A minimal design must also be a fast design. Performance is a form of respect for our users.

- Favour lightweight components and avoid unnecessary dependencies
- Optimise images and assets
- Avoid animations or effects that add weight without clear UX benefit
- Target good performance on mid-range Android devices on a 4G connection, not just flagship phones on Wi-Fi

**When designing a new view:** consider its asset weight and rendering cost. Simplicity and speed reinforce each other.

---

## 8. Internationalisation from Day One

OIUEEI is built for real communities, which means linguistic diversity must be considered from the start — not retrofitted later.

- All UI text must be externalised and translatable — no hardcoded strings
- Layouts must accommodate longer strings (Basque, Catalan, and other languages can be significantly longer than English or Spanish)
- Avoid fixed-width containers for text-heavy elements
- Icons and visuals should not rely on culturally specific references without a text label

**When designing a new view:** test the layout with longer placeholder strings. Nothing should break or overflow.

---

## 9. User Data is Never a Product

This is a founding commitment, not a feature. OIUEEI does not sell, share, or use user data against users — not for advertising, profiling, scoring, or influence. The floor is: *would a user be uncomfortable if they read the data we hold on them?*

OIUEEI ships with **no third-party analytics**. We don't load a tracking SDK, we don't send events anywhere, and we don't ask users to consent to anything before using the app. If at some point we decide we need to measure how the product is used, the rules below apply — starting from "do we really need it?"

### Forbidden under any justification

- Selling, leasing, or sharing user data with third parties.
- Tracking pixels in emails for individual open monitoring.
- Behavioural advertising SDKs (Meta Pixel, Google Ads, TikTok Pixel, etc.).
- Fingerprinting libraries that bypass consent.
- Session replay tools that record individual user behaviour (Hotjar, FullStory, etc.).
- "Personalised recommendations" that are a pretext for profiling.
- UI patterns that nudge users into sharing more data than the service requires.

### Permitted, narrowly

- **Operational error and performance monitoring** (Sentry-style), if added. Scrub user content from stack traces and breadcrumbs; PII never leaves our servers.
- **Server-side aggregate counters** for things we genuinely need to operate the service — e.g. counting how many bookings were created last week. Computed from existing data, never by sending events to a third party.
- **A period on the log itself.** Those counters stop being pseudonymous and become genuinely aggregate at 14 months: `actor_code` is blanked, the fact survives, and what was a record about a person stops being one (`purge_expired_data`). A counter that never forgets who it counted is not the narrow permission above — it is the thing this section refuses, arrived at slowly.
- **A person's own rows of that log, in their own data export.** The rule above protects the analytics log as an aggregate *product* surface: nothing in the app lets anyone read how other people behave. It was never meant to withhold from someone the observed data we hold about *them*, which is exactly what a data-portability copy is for. Scoped to `actor_code == request.user.code`, in a file only they can ask for (`core/services/export_service.py`).

If at any point we find ourselves about to add a third-party analytics SDK, that is a signal to stop and ask: what specific question does it answer that we can't answer from our own database? If the answer is vague, the SDK does not get added.

**When designing a new view:** for any data the view collects or transmits, ask two questions: *Could a user read it without surprise or discomfort?* And *does anyone outside our team get it?* If either answer is wrong, change the design.

---

## 10. Koros Wave Pattern and Theeeme Color System

All pages use a consistent `form-hero` + `Koros` layout pattern. The HDS Hero component is not used; instead, a custom `form-hero` section provides the page header, followed by an HDS `Koros` component (48px high) that creates a wave transition into the page content.

**The palette and the wave belong to a collection, not to the reader.** The people who run a collection choose its six colours and its koro type (basic, beat, calm, pulse, vibration or wave) on its Appearance page, and every page of that collection wears them for everyone who opens it. Nothing about it is chosen by the reader or stored in their browser. Outside a collection (home, profile, login, legal, the 404…) the app paints with its own palette, `Braaanding`, a row edited by whoever runs the deployment. Design a view for the palette in force, whichever it is; never assume one. The detail (which pages declare a palette, how it reaches the first paint) is in [`frontend/CLAUDE.md`](frontend/CLAUDE.md), *Whose palette: the collection's, or the app's own*.

### Layout Structure

Every page follows this structure: a full-width `form-hero` with theeeme-driven background colour, containing a `form-hero-content` block (max-width 1248px) for the title, description, and back link. Below the hero, the `Koros` wave bridges into a `page-container` (max-width 1248px) for the main content.

### Theeeme Color Roles

Each palette defines six colours used consistently across the interface:

| Token | Role |
|-------|------|
| `color_01` | Primary button background + secondary button border |
| `color_02` | Body background + Koros SVG fill |
| `color_03` | Koros section background |
| `color_04` | Body text + secondary button text |
| `color_05` | Koros text (title, description, back-link) via the `--hero-text-color` CSS custom property |
| `color_06` | Primary button text |

This system ensures that every page of a collection is visually coherent: changing a collection's palette recolours its koros, background, buttons and text in one step, for everyone who opens it, and the koro type adds a motif of the collection's own choosing. Pages outside a collection stay in the app's palette.

---

## 11. Icons Are Always Black

HDS icons must always render in the default black (`--color-black-90`). Never colour icons blue, red, or any other brand or semantic colour. If an icon is disabled or inactive, use `--color-black-40`. Colour must never be used to convey meaning through an icon alone — use labels, status tags, or contextual placement instead.

**When adding icons to a view:** do not set a custom colour on them unless the intent is to show a disabled/faded state using `--color-black-40`.

**One recorded exception — an icon inside a button.** When an icon sits in a button's label (`iconStart`), it is part of that label, not an icon in its own right, and it takes the button's text colour: theeeme `color_06` on a primary, `color_04` on a secondary. Forcing it black would make it vanish on the darker `color_01` backgrounds — the rule would defeat the legibility it exists to protect. HDS icons render `fill: currentColor`, so this happens on its own; the point is not to "fix" it back to black. The rule stands unchanged everywhere else: an icon on its own, in an info row or a card, is black.

This is used on the four irreversible confirms, which deliberately do **not** use HDS's red `variant="danger"` — a fixed red would fight every theeeme. The signal is the icon plus the page's own warning copy: `IconTrash` on delete thing / delete collection, `IconCrossCircle` on remove guest, `IconSignout` on leave the group.

---

## 12. Responsive Breakpoints

OIUEEI uses four of the six HDS breakpoints (xs / m / l / xl). `breakpoint-s` (576 px) and `breakpoint-xxl` (1440 px) are intentionally skipped — see §4 above for the full canonical HDS table.

| HDS breakpoint | Min-width | Container width | OIUEEI card-grid columns |
|------|-----------|---------------|---------|
| `breakpoint-xs` | 320 px | 288 px | 1 |
| `breakpoint-m` | 768 px | 720 px | 2 |
| `breakpoint-l` | 992 px | 944 px | 3 |
| `breakpoint-xl` | 1248 px | 1200 px | 4 |

Note: the "columns" here are OIUEEI card-grid columns (`things-grid` and any future card grid), not the HDS 12-column layout grid. HDS grid column counts live in §4.

**`collections-grid` is deliberately not one of them.** Collections render as image-less full-width rows, one under another, at every breakpoint — thing cards keep their thumbnail grid, and that difference is what tells a collection row apart from a thing card on sight. It never goes multi-column. A new card grid follows the progression above unless it has a reason of this kind, written down beside it.

**Rules for all layout code:**

- Write CSS **mobile-first**: start with the xs (1-column) layout as the default, then use `@media (min-width: ...)` to add columns progressively.
- Use only these three `min-width` values in media queries: `768px`, `992px`, `1248px`. Never use `576px`, `480px`, `944px`, or any other ad-hoc value. `max-width: 767px` is also acceptable for mobile-only overrides.
- Card grids (`things-grid` and any future card grid) follow the OIUEEI column progression: 1 → 2 → 3 → 4. `collections-grid` and `.kind-cards` are the two exceptions: the first for the reason in the note above the table, the second because it holds three cards — one column, then three in a row from 992px, with no two-column step, which would leave a single card alone on a second row.
- The `page-container` and `form-hero-content` max-width is `1248px` (matching breakpoint-xl total width).

**When writing a new layout:** start at 1 column, add `min-width: 768px` for 2 columns, `min-width: 992px` for 3, `min-width: 1248px` for 4. Never design desktop-first and collapse downward.

---

## Using These Guidelines in Practice

When asked to design or review a view, apply this checklist:

1. Are all components sourced from HDS where possible?
2. Is the copy warm, inclusive, and direct?
3. Has everything non-essential been removed?
4. Was it designed mobile first?
5. Does it meet WCAG AA?
6. Are there any dark patterns present?
7. Is it performant on modest hardware?
8. Will it hold up in other languages?
9. Does it collect only the data it strictly needs?
10. Does it use the form-hero + Koros layout with the palette in force (the collection's or the app's)?
11. Are all icons black (or `--color-black-40` when disabled)?
12. Do all media queries use only the three approved breakpoints (768px / 992px / 1248px) in `min-width` order, with xs as the mobile default?
