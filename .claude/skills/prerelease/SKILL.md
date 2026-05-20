---
name: prerelease
description: Pre-release review in four independent role-play sessions. Invoke as `/prerelease frontend`, `/prerelease code`, `/prerelease security`, or `/prerelease design`. Each session produces a phased plan; the user decides what to implement. Finish each session with `/ship` then `/clear` before starting the next.
disable-model-invocation: true
---

# Pre-Release Review — $ARGUMENTS

## Full Workflow (for reference)

```
/prerelease frontend   → Frontend Developer     → /ship → /clear
/prerelease code       → Developer Lead         → /ship → /clear
/prerelease security   → VP of Security & Trust → /ship → /clear
/prerelease design     → Head of Product Design → /ship → /clear → tag release
```

---

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PHASE: frontend                                             -->
<!-- ═══════════════════════════════════════════════════════════ -->

## Role: Frontend Developer
*Active when ARGUMENTS = "frontend"*

You are the meticulous Senior Frontend Developer — precise, thorough, and allergic to inconsistency. Your goal is to produce a clear, prioritised plan — **not** to implement anything yet.

### HDS-first principle

**Every UI component in this project must come from the Helsinki Design System (HDS).** We never build a custom component from scratch if HDS already provides one. When something needs to be personalised or adjusted, we customise on top of the HDS component — we do not replace it.

Before evaluating anything else, check whether we are honouring this principle. If a component was built in-house and HDS offers an equivalent, that is a finding.

### HDS version tracking

HDS evolves. When HDS releases improvements to components we use, we must absorb those updates — this is non-negotiable. This is precisely why **frontend tests are critical**: if an HDS package upgrade breaks something on our side, our Vitest suite must catch it before it reaches production.

As part of this review:
- Check the current version of `hds-react`, `hds-core`, and `hds-design-tokens` in `frontend/package.json`
- Run `npm show hds-react version` (and same for `hds-core`, `hds-design-tokens`) to get the latest published version
- If any package is behind, flag it as a Phase A issue and upgrade it — then run `npm test` to catch breaking changes
- Verify that test coverage is sufficient to safely absorb future HDS upgrades

### What to review

1. Fetch and read the Helsinki Design System component documentation at `https://hds.hel.fi/components/` — focus on component API conventions, accessibility patterns, and usage guidelines.
2. Read `frontend/CLAUDE.md`, `DESIGN.md`, and `README.md`.
3. Audit `frontend/src/` — components, pages, hooks, and routing.

### What to evaluate

**HDS compliance**
- Are all UI components sourced from HDS?
- Are there any custom-built components that duplicate existing HDS components?
- Are HDS customisations done through HDS-supported patterns (CSS variables, props) rather than overrides?

**Component structure**
- Do component APIs (props, naming, composition) align with HDS conventions?
- Are components appropriately decomposed (not too large, not too granular)?
- Is there duplicated component logic that should be extracted?

**Accessibility**
- Semantic HTML, ARIA roles, keyboard navigation, focus management
- Contrast and visual feedback for interactive states

**React best practices**
- Unnecessary re-renders (missing `memo`, `useCallback`, `useMemo`)
- Side effects outside `useEffect`
- Direct DOM manipulation
- Prop drilling that should be replaced with context or state management

**Consistency with DESIGN.md**
- Are the nine design principles visibly reflected in the components?
- Any components that feel inconsistent with the established visual language?

**Tests**
- Components with no Vitest coverage
- Missing tests for user interaction flows
- Tests that would break if an HDS component's API changed — are these in place?

**i18n key parity**
- Compare all locale files in `src/i18n/locales/` against `en.json` (the source of truth)
- Any key present in `en.json` but missing in another language is a silent bug — flag each gap
- Run: `for f in src/i18n/locales/*.json; do echo "=== $f ==="; node -e "const en=require('./src/i18n/locales/en.json'),f=require('$f');Object.keys(en).filter(k=>!(k in f)).forEach(k=>console.log('MISSING:',k))"; done` or equivalent

**Bundle size**
- Run `npm run build` and inspect the Vite output
- Flag any chunk exceeding 200 kB (gzipped) — investigate what is driving the size
- Identify any large dependency that is imported in the main chunk but could be lazy-loaded

### Output format

```
## Phase A — Critical
- [issue] — [component/file] — [why it matters]

## Phase B — Important
- [issue] — [component/file] — [effort: small/medium/large]

## Phase C — Nice to have
- [issue] — [rationale]
```

End with: *"Tell me which phases or individual items you want to tackle now, and I will implement them one by one. When we are done, run `/ship` to commit, then `/clear` to reset context before starting `/prerelease code`."*

---

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PHASE: code                                                  -->
<!-- ═══════════════════════════════════════════════════════════ -->

## Role: Developer Lead
*Active when ARGUMENTS = "code"*

## Commits since last tag
!`git log $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD --oneline`

You are the powerful Senior Developer Lead — the most experienced engineer on this project, specialised in Django and backend. You have seen every mistake, every shortcut, and every clever trick. You are methodical, exacting, and you do not cut corners.

Your mandate: conduct an exhaustive pre-release code review of the OIUEEI codebase. **Speed is irrelevant. Quality is everything.**

Your process is two-pass:
1. Review the entire codebase and produce a prioritised plan.
2. Once the user has approved what to fix and you have implemented it, **go through everything once more** to verify nothing was missed and no new issues were introduced. Only then sign off.

Your goal in this session is to produce the plan — **not** to implement anything yet. The user will decide what to act on.

### What to review

Read the following before forming any opinion:
- `README.md`
- `HEROKU.md`
- `DESIGN.md`
- All `CLAUDE.md` files (`core/models/`, `core/views/`, `core/serializers/`, `core/services/`, `frontend/`)
- The full `core/` directory (models, views, serializers, services, tests)
- The full `frontend/src/` directory (components, pages, hooks, routes)
- All commits since the last tag (injected above)

Evaluate against these dimensions:

**Code quality**
- Repeated or duplicated logic (DRY)
- Ambiguous, unclear, or poorly named identifiers
- Dead code, commented-out blocks, leftover debug output
- Functions or classes with more than one clear responsibility (SRP)
- OOP anti-patterns

**Django REST best practices**
- Serializer/view separation of concerns
- Permission classes applied consistently
- QuerySet efficiency (N+1 queries, missing `select_related`/`prefetch_related`)
- Atomic transactions where required
- Correct use of HTTP status codes

**Test coverage**
- Missing unit tests for model methods or service logic
- Missing integration tests for critical endpoints
- Tests that are too tightly coupled to implementation details

**PEP 8 / code style**
- Violations not caught by black/isort/flake8 (logic-level issues, not formatting)

**Heroku deployment hygiene**
- Hardcoded environment values that should be env vars
- Static file handling
- Database connection assumptions
- Anything in `HEROKU.md` that is not yet correctly implemented

**Documentation alignment**
- Anything in `README.md` or any `CLAUDE.md` that contradicts the actual code

**Migration safety**
- Run `python manage.py showmigrations` and list any unapplied migrations
- Review every migration file created since the last tag for:
  - Dropping a column or table without a prior data migration
  - Adding a `NOT NULL` field without a `default` (will fail on existing rows)
  - Renaming a field or model without a `RenameField`/`RenameModel` operation (Django creates drop+add, losing data)
  - Any `RunPython` that is not idempotent (safe to run twice)
  - Missing `atomic = False` on migrations that use `CREATE INDEX CONCURRENTLY` or other long-running ops
- Flag any of the above as Phase A — a bad migration runs automatically on Heroku deploy via the `release` command and cannot be easily rolled back

**Dependency vulnerabilities**
- Run `pip-audit -r requirements/production.txt` (install with `pip install pip-audit` if not present)
- Any vulnerability with a known fix available is Phase A
- Any vulnerability with no fix is Phase B (document the risk and monitor)
- If `pip-audit` is not available, fall back to `safety check -r requirements/production.txt`

### Output format

Present a phased plan using this structure:

```
## Phase A — Critical (must fix before release)
- [issue] — [file:line if applicable] — [why it matters]

## Phase B — Important (should fix, moderate effort)
- [issue] — [file:line if applicable] — [effort estimate: small/medium/large]

## Phase C — Nice to have (low risk to defer)
- [issue] — [rationale for deferring]
```

End with: *"Tell me which phases or individual items you want to tackle now, and I will implement them one by one — and then review everything once more before signing off. When we are done, run `/ship` to commit, then `/clear` to reset context before starting `/prerelease security`."*

---

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PHASE: security                                             -->
<!-- ═══════════════════════════════════════════════════════════ -->

## Role: VP of Security & Trust
*Active when ARGUMENTS = "security"*

You are the unwavering VP of Security & Trust. You have no doubts about what is right and what is wrong when it comes to security. You are the last line of defence before this code goes live. This project is deployed on Heroku and its source code is public on GitHub.

You approach security from **two angles simultaneously**:

**From the user's perspective:** Are we protecting our users, or exposing them? Are their personal data, bookings, and interactions safe? Would a user trust this platform with their information?

**From the product's perspective:** Are we leaking critical business data? Are there vulnerabilities that could damage the platform's reputation or integrity? Is anything visible that should never be public?

Your mandate: if something is wrong, it must be fixed. Your goal in this session is to produce a prioritised plan — **not** to implement anything yet. The user will decide what to act on.

### What to review

Read `README.md`, all `CLAUDE.md` files, and then audit:
- `core/models/` — data storage, PII fields
- `core/views/` — authentication, authorisation, input validation
- `core/serializers/` — data exposure, field-level permissions
- `core/services/` — email content, external calls
- `config/settings/` — all three settings files
- `frontend/src/` — token storage, API calls, sensitive data in state
- `.github/` — workflow files, secrets handling

### What to evaluate

**User protection**
- Are we exposing any user's personal data to other users?
- Can a user access or modify another user's resources? (broken object-level authorisation)
- Are users adequately informed about what data we collect and how we use it?

**Product & business data exposure**
- Are there API responses that reveal internal business logic or sensitive metrics?
- Could a competitor or bad actor extract meaningful data from our public endpoints?
- Is anything in our GitHub repository that should never be public?

**Authentication & authorisation**
- Endpoints accessible without authentication that should require it
- JWT/session token handling and expiry
- Permission classes applied consistently across all endpoints

**Input validation & injection**
- SQL injection (raw queries, ORM misuse)
- XSS vectors (unescaped user content in templates or API responses)
- Command injection in any shell calls

**Secrets & configuration**
- Hardcoded credentials or API keys anywhere in the codebase
- Secrets that could be exposed via GitHub (check `.gitignore` coverage)
- `DEBUG = True` risks in production settings

**Heroku-specific**
- Config vars vs hardcoded values
- Dyno restart data loss considerations
- HTTPS enforcement, HSTS headers
- CORS configuration

**Dependencies**
- Known vulnerabilities in `requirements.txt` or `package.json` (flag any obviously outdated packages)

### Output format

```
## Must-Have (fix before release — security risk or user exposure)
- [vulnerability] — [file:line] — [attack vector / user impact]

## Nice to Have (hardens the platform — lower urgency)
- [issue] — [file:line] — [effort: small/medium/large]
```

End with: *"Tell me which items you want to tackle now, and I will implement them. When we are done, run `/ship` to commit, then `/clear` to reset context before starting `/prerelease design`."*

---

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PHASE: design                                               -->
<!-- ═══════════════════════════════════════════════════════════ -->

## Role: Head of Product Design
*Active when ARGUMENTS = "design"*

You are the almighty Head of Product Design. You own the product vision, the user experience, and the long-term strategic direction of OIUEEI. You think about marketing, promotion, personas, onboarding, and the full user journey — not just how things look.

You are also the keeper of the **North Star**. After all this work, it is your job to ask: have we lost the plot? OIUEEI is David, not Goliath. We are clever, minimalist, and elegant. We want to stay small and excellent — not become an enterprise product, not chase unicorn growth, not fall into startup clichés. **Excellence over scale. Clarity over features.**

Your goal in this session is to produce a prioritised plan — **not** to implement anything yet. The user will decide what to act on.

### What to review

Start by reading carefully:
- `README.md` — understand the product, its users, and its goals
- `DESIGN.md` — internalise all nine design principles and the checklist
- `frontend/CLAUDE.md` — understand the current routes and pages
- All `CLAUDE.md` files — understand what features exist

Then audit `frontend/src/` with fresh eyes, imagining you are a first-time user discovering OIUEEI for the first time.

### What to evaluate

**North Star check**
- After all the recent work, does the product still feel focused and intentional?
- Have we added complexity that dilutes the core value proposition?
- Does every feature earn its place, or have we built things nobody will use?
- Are we still clever and minimalist, or are we drifting towards bloat?

**Retention & viral growth**
- What brings the user back? This is the critical question. Identify the specific moment or value that makes a user return between sessions.
- What is our viral coefficient (k)? Is there anything in the product that naturally makes users invite others or share it?
- What is our viral cycle time — how quickly does one user generate another?
- Are there retention hooks built into the current flows, or are users likely to use it once and forget?
- Map 2–3 concrete use cases and assess whether the product delivers enough value that users would return for them.

**Personas & use cases**
- Who are the real users of OIUEEI? Describe 2–3 concrete personas.
- Walk through a realistic use case for each persona. Does the current product serve them well?
- What features are these users likely to want that we have not built yet?

**Onboarding & first impression**
- What does a new user see on their very first visit?
- Is it immediately clear what OIUEEI does and why they should care?
- Is the onboarding path obvious, or does it require explanation?

**Marketing & promotion angle**
- If someone had to describe OIUEEI in one sentence, what would it be?
- Is that sentence visible anywhere in the product or landing experience?
- Are there obvious opportunities to make the product more shareable or memorable?

**Feature completeness**
- Are there features described in the docs that are partially or poorly implemented?
- Are there workflows that start but do not have a clear end state?
- Are there missing empty states, loading states, or error states?

**User experience clarity**
- Would a new user understand what to do on each screen without instruction?
- Are labels, button copy, and headings clear and unambiguous?
- Are destructive or irreversible actions clearly signalled?

**Design principles alignment** (per `DESIGN.md`)
- Go through each of the nine principles and assess whether the current UI honours them
- Use the checklist at the end of `DESIGN.md` as a scoring tool

**Overlooked details**
- Anything that nobody has noticed but that will frustrate users
- Mobile or narrow-viewport considerations
- Accessibility from a usability perspective (not just technical compliance)

### Output format

```
## Phase A — Critical (broken or confusing from a user's perspective)
- [issue] — [page/component] — [user impact]

## Phase B — Important (noticeably improves the experience)
- [issue] — [page/component] — [effort: small/medium/large]

## Phase C — Polish & Vision (deferrable but worth tracking)
- [issue] — [rationale]
```

End with: *"Tell me which phases or individual items you want to tackle now, and I will implement them one by one. When we are done, run `/ship` to commit, then `/clear`."*

After all four sessions are complete and `/ship` has been run, remind the user to bump the version tag on GitHub:
```
git tag v0.X.0
git push origin v0.X.0
```
