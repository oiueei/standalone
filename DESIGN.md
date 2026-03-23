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

**When designing a new view:** ask what can be removed. If a UI element cannot be justified, it should not be there.

---

## 4. Mobile First

Mobile is the primary target. The experience must be excellent on a small screen before considering larger breakpoints. Tablets and desktops are secondary adaptations, not the default.

- Design and review every view at mobile viewport first
- Touch targets must be large enough (minimum 44×44px)
- Navigation, forms, and key actions must work flawlessly with one hand
- Tablet and desktop layouts are progressive enhancements, not the baseline

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

This is a founding commitment, not a feature. We do not use user data for advertising, cross-selling, or profiling. We do not share or sell data to third parties under any justification.

This principle has concrete design consequences:

- No tracking pixels, third-party analytics scripts, or ad SDKs
- Cookie consent flows must be honest and minimal — we should have very little to ask consent for
- No "personalised recommendations" that are a pretext for behavioural profiling
- No UI patterns that nudge users into sharing more data than the service requires

**When designing a new view:** question every data point the view collects or transmits. If it is not strictly necessary for the feature to function, do not collect it.

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
