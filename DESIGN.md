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

**Official HDS breakpoints** — use these exact values in all media queries. Never use arbitrary pixel values.

| Token | Min-width | Max content width | Columns | Margin |
|---|---|---|---|---|
| `breakpoint-xs` | 320px | 288px | 4 | 16px |
| `breakpoint-m` | 768px | 720px | 8 | 24px |
| `breakpoint-l` | 992px | 944px | 12 | 24px |
| `breakpoint-xl` | 1248px | 1200px | 12 | 24px |

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

Operating a product responsibly requires understanding how it is used. OIUEEI collects a small amount of pseudonymous product analytics for **our own insight only**, never to monetise the user.

### Forbidden under any justification

- Selling, leasing, or sharing user data with third parties.
- Tracking pixels in emails for individual open monitoring. *(To measure email engagement, prefix outbound links with a one-shot click-through path, e.g. `/digest/...`, that records the click on landing and redirects to the destination. We measure **clicks, not opens**.)*
- Behavioural advertising SDKs (Meta Pixel, Google Ads, TikTok Pixel, etc.).
- Fingerprinting libraries that bypass consent.
- Session replay tools that record individual user behaviour (Hotjar, FullStory, etc.).
- "Personalised recommendations" that are a pretext for profiling.
- UI patterns that nudge users into sharing more data than the service requires.

### Permitted under strict conditions

- **Product analytics** (currently Mixpanel). Allowed because we cannot improve a product we cannot measure. Must obey **all** of:
  1. **Pseudonymous identifiers only.** Events are tagged with the 6-char `User.code` — never email, name, IP, or any other PII.
  2. **No user content in event properties.** Never send `headline`, `description`, message bodies, or anything a user typed. Properties are categorical or structural only (`thing_type`, `collection_mode`, counts, durations).
  3. **Provider acts as a data processor on our behalf only.** No resale, no enrichment, no cross-customer sharing. Re-audit the provider's terms whenever they change.
  4. **Visible opt-out** in the user profile, and a plain-language disclosure in the privacy policy.
  5. **Aggregate outputs.** Dashboards surface counts, funnels and distributions — not individual user journeys. Per-user views, if ever used, are restricted to debugging by the team and never exposed.
- **Operational error and performance monitoring** (Sentry-style). Same PII rules apply: scrub user content from stack traces and breadcrumbs.
- **Cookie consent** must be honest and minimal: list every category we collect for, name every provider, allow granular opt-out.

**When designing a new view:** for any data the view collects or transmits, ask two questions: *Could a user read it without surprise or discomfort?* And *does anyone outside our team get it?* If either answer is wrong, change the design.

---

## 10. Koros Wave Pattern and Theeeme Color System

All pages use a consistent `form-hero` + `Koros` layout pattern. The HDS Hero component is not used; instead, a custom `form-hero` section provides the page header, followed by an HDS `Koros` component (60px height) that creates a wave transition into the page content. Each user can choose their preferred Koros wave type (basic, beat, calm, pulse, vibration, or wave) via the `koro` field on their profile. The chosen type is stored in `localStorage` and applied across all pages.

### Layout Structure

Every page follows this structure: a full-width `form-hero` with theeeme-driven background colour, containing a `form-hero-content` block (max-width 1248px) for the title, description, and back link. Below the hero, the `Koros` wave bridges into a `page-container` (max-width 1248px) for the main content.

### Theeeme Color Roles

Each theeeme defines six colours used consistently across the interface:

| Token | Role |
|-------|------|
| `color_01` | Primary button background + secondary button border |
| `color_02` | Body background + Koros SVG fill |
| `color_03` | Koros section background |
| `color_04` | Body text + secondary button text |
| `color_05` | Koros text (title, description, back-link) via the `--hero-text-color` CSS custom property |
| `color_06` | Primary button text |

This system ensures that every user's experience is visually coherent: changing a theeeme recolours the entire interface — koros, background, buttons, and text — in one step. The koro wave type adds a further layer of personalisation, letting each user choose the wave motif that best suits their taste.

---

## 11. Icons Are Always Black

HDS icons must always render in the default black (`--color-black-90`). Never colour icons blue, red, or any other brand or semantic colour. If an icon is disabled or inactive, use `--color-black-40`. Colour must never be used to convey meaning through an icon alone — use labels, status tags, or contextual placement instead.

**When adding icons to a view:** do not set a custom colour on them unless the intent is to show a disabled/faded state using `--color-black-40`.

---

## 12. Responsive Breakpoints

OIUEEI uses four breakpoints. HDS `breakpoint-s` (576 px) is **not used** — skip it entirely.

| Name | Min-width | Content width | Columns | Margin |
|------|-----------|---------------|---------|--------|
| `breakpoint-xs` | 320 px | 288 px | 1 | 16 px |
| `breakpoint-m` | 768 px | 720 px | 2 | 24 px |
| `breakpoint-l` | 944 px | 944 px | 3 | 24 px |
| `breakpoint-xl` | 1248 px | 1200 px | 4 | 24 px |

**Rules for all layout code:**

- Write CSS **mobile-first**: start with the xs (1-column) layout as the default, then use `@media (min-width: ...)` to add columns progressively.
- Use only these four `min-width` values in media queries: `768px`, `944px`, `1248px`. Never use `576px`, `480px`, `992px`, or any other ad-hoc value.
- Card grids (`things-grid`, `collections-grid`, and any future card grid) follow the column progression: 1 → 2 → 3 → 4.
- The `page-container` and `form-hero-content` max-width is `1248px` (matching breakpoint-xl total width).

**When writing a new layout:** start at 1 column, add `min-width: 768px` for 2 columns, `min-width: 944px` for 3, `min-width: 1248px` for 4. Never design desktop-first and collapse downward.

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
10. Does it use the form-hero + Koros layout with theeeme colours?
11. Are all icons black (or `--color-black-40` when disabled)?
12. Do all media queries use only the four approved breakpoints (768px / 944px / 1248px) in `min-width` order, with xs as the mobile default?
