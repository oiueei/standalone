# OIUEEI - Development Guide

## Deployments built on this repository

This repository is the whole product: a fresh checkout runs, tests and deploys on its own, with
`CREATOR_POLICY` at `OpenCreatorPolicy` (no gate) and `frontend/src/deployment/` exporting empty
stubs. A deployment that adds a service layer (an open sign-up door, vetting, pages of its own, its
operator's legal identity) does so **only through the extension points in `SELF_HOSTING.md`**, in
an app and files of its own, in its own repository. `core/` never imports from a deployment, and
nothing here names one: no deployment's domain, forms, providers or decisions in code, tests,
comments or docs.

**A product fix always lands here first**, on `development`, even when a deployment surfaced it;
the deployment then takes it by merging. A `core/` change made in a deployment's repository is
invisible to this one and has to be re-applied by hand forever.

**Verify the current branch before editing.** `development` is where work happens; `main` is what
releases are cut from.

## Agent sessions (local or cloud)

- **The git author is the maintainer, never the model.** An environment where an agent commits —
  a cloud sandbox included — is configured with the maintainer's `user.name` / `user.email`
  before the first commit. The model appears only in the `AI-assistant:` trailer (see Commit
  attribution): a model cannot hold copyright, and the author field is the one every tool reads.
- **An agent commits on a branch and stops there**: pushes, merges, tags and deploys are the
  maintainer's.
- **A session works with the repository it was given.** It never brings another repository's
  history into this one (no pushing a deployment's branch here so a session can read it): that
  repository is connected to the session instead.
- **One session per branch or worktree**: two agents in one working tree overwrite each other.

## Project Conventions

- **Single Django app**: all product code lives in `core/`.
- **Settings**: Split into `base.py`, `development.py`, `production.py` under `config/settings/`
- **Code style**: Ruff (100-char lines) — `ruff check` (lint + import sort) and `ruff format`; replaces black/isort/flake8. Pre-commit hooks in `.pre-commit-config.yaml` (run `pre-commit install`).
- **Test structure**: `core/tests/unit/`, `core/tests/integration/`, `core/tests/scenarios/`. Five fixtures are **shared with the frontend**: `frontend/src/test/hourlyGridParity.json` holds the hourly-reservation cases both `core/tests/unit/test_hourly_grid_parity.py` and `frontend/src/utils/hourlyGridParity.test.js` read, so the starts the request page offers and the ones the server accepts cannot drift apart; a case may carry `units` (how many identical ones the space has, 1 if absent) and `served_periods` (what the server serves the browser as taken, from `saturated_periods`; the bookings themselves if absent), and the server test also checks that `saturated_periods(bookings, units)` gives exactly them, so the page is fed what the server would serve; a case may also carry `pause` (`[from, until]` in days from that Monday, both included), served as one more whole-day stretch and refused by the request; `frontend/src/test/nextPathParity.json` holds the accepted/rejected `safe_next_path` tables both `core/tests/unit/test_safe_next_path.py` and `frontend/src/utils/nextPath.test.js` read, so the server's open-redirect gate and the browser's defence in depth stay one rule; `frontend/src/test/inboxGroupParity.json` holds which in-app notices the inbox folds into its summary card, which both `core/tests/integration/test_inbox_group_dismiss.py` (the server's `DELETE /inbox/?group=bookings`) and `frontend/src/utils/inboxGroups.test.js` read, so the card never shows a notice the server keeps or hides one it deletes; `frontend/src/test/markdownLinkParity.json` holds `[text](url)` cases with the target each should give (or `null` when it is no link), which both `frontend/src/test/markdown.test.jsx` (the app's Markdown) and `core/tests/unit/test_email_note.py` (the email note's engine) read, so a link means the same in the app and in the email; `frontend/src/test/kindVerbParity.json` holds the verbs each collection kind carries and the verb a price makes in each (`kinds`, `cases`), which both `core/tests/unit/test_kind_verb_parity.py` (`KIND_THING_TYPES`, `derive_thing_type`) and `frontend/src/constants/things.test.js` (`KIND_THING_TYPES`, `deriveThingType`) read, so the form never blocks a send the server accepts or lets through one it refuses. Moving or renaming any of them breaks a suite on each side; new cases go in the file, not in either test.
- **Coverage minimum**: backend **96%**, frontend **93/90/90/95** (statements/branches/functions/lines), both enforced by CI. The frontend numbers live in `frontend/vite.config.js` (`test.coverage.thresholds`), which is the one that CI actually enforces — raise them there and here in the same commit. They are **ratchets, not targets** — each sits ~2 points under the suite's real coverage so a genuine regression is visible. Raise them as coverage grows; never lower one to make a red build pass. New code owes tests that name a behaviour, not lines.
- **All PKs**: 6-character alphanumeric codes generated via `secrets.choice()` (not auto-increment)
- **Dependencies are pinned, not ranged**: `requirements/*.txt` uses `==` on every direct dependency, so the `pip-audit` run in CI and the Heroku build resolve the same versions — a range let a release published between them reach production unaudited. Transitives are still unpinned; a full `pip-compile --generate-hashes` lock has to be resolved on Python 3.12 (`.python-version`), not on whatever is local. CI audits **both** `production.txt` and `development.txt`. Frontend: `npm ci` + `package-lock.json` already give this, gated by `frontend/scripts/audit-gate.mjs`.
- **Emails**: All user content escaped via `django.utils.html.escape()`
- **String length in migrations**: SQLite (local) does NOT enforce `CharField(max_length=N)` at the DB level — PostgreSQL (Heroku/production, **and CI**) does. CI runs the backend suite on Postgres (`DATABASE_URL` in `.github/workflows/tests.yml`), so an overflow now fails a build instead of reaching production — but a local `pytest` still won't see it. Always verify that seed data fits within the model's `max_length` before committing. Key limits: `headline` = 64, `description` = 2000 per language (Thing/Collection `description` are now `TextField` — long-form Markdown — with a per-language visible cap the serializer enforces, `LOCALIZED_DESCRIPTION_*` in `core/validators.py`; no column width to overflow), `name` = 32, `email` = 64, `question` = 64, `answer` = 256, `location` = 64 (widened from 32 for RESERVE addresses), `about` (User Markdown bio) = 2000, each `tags` label (Collection/Thing) = 32 (max 12 tags), `deposit_policy` (Collection) = 256 / 1024 stored (still `CharField`), `request_info` (Collection, the request-page note for every verb) = 512 / 2048 stored (256 was too short), `email_note` (Collection, the owner's note in the requester's emails) = 512 / 2048, `BookingPeriod.project_note` (RESERVE only) = 512, `BookingPeriod.contact_phone` (RESERVE only, the optional phone a shed may ask for) = 32. `BookingPeriod.quantity` (LEND/RENT with several units, 1 to `Thing.units`, default 1) carries a `db_default=1` as well as the Python default, for the previous release's dynos (migration 0176). `contact_phone` and `Collection.reservation_asks_phone` carry a `db_default` as well as the Python default: the previous release's dynos insert without naming the columns while the release phase runs. `Thing.type` column = 16. `Thing.units` (1–20, default 1, RESERVE_THING, LEND_THING and RENT_THING — how many identical ones a shed's space or a library's thing has, so that many reservations or loans can overlap, each loan request holding `BookingPeriod.quantity` of them) carries a `db_default=1` as well as the Python default, for the previous release's dynos. `Collection.reservation_max_days` (1–7) / `reservation_horizon_days` (1–365, default 90) / `reservation_max_active_per_member` (1–50, default 10) — RESERVE collections only. `Collection.reservation_unit` (DAY/HOUR) / `opening_hours` (JSON, HOUR only) / `reservation_min_minutes` / `reservation_max_minutes` (1–720 each, defaults 60/180, HOUR only, minutes — replaced hour-granular `reservation_max_hours` in migration 0150; the maximum applies to the full-day span too, no exception; `reservation_max_hours` left the model in 0152 and its column — kept meanwhile with a database default of 3 — was dropped in 0153, one release later on purpose: dropping it in the same release would have broken the previous release's dynos, which still name it in every query while the release phase runs). `Collection.home_page` = 128 (`URLField`, serializer-capped too).
- **Owner content can be multilingual**: on **Thing and Collection**, `headline`, `description` and each `tags` label may hold one text per language as inline JSON — `{"es": "Las cosas de mamá", "ca": "Les coses de mama"}` — and every reader sees theirs (`core.utils.parse_localized` / `resolve_localized`, `frontend/src/utils/localized.js`). Anything that isn't a strict `{lang: text}` map over `es`/`ca`/`en` renders **verbatim**, so an owner writing prose never notices. Consequently the limits above are **per language**: Thing/Collection `headline` = 64 visible / 256 stored, `description` = 2000 visible (a `TextField` — no column cap; the serializer's `storage_max_length` 6400 is only a sanity bound), tag label = 32 / 160 (JSONField), Collection `deposit_policy` = 256 / 1024, `request_info` = 512 / 2048, `email_note` = 512 / 2048. The serializer (`LocalizedHeadlineField` / `LocalizedTextField`) is what enforces the visible limit — the column no longer does (and for `description` there is no column limit at all). `Report.thing_headline` snapshots `Thing.headline`, so it tracks its width.
- **Collections have a kind, fixed at creation**: `STALL` (gift/sell, `SINGLE_USE_TYPES`), `LIBRARY` (lend/rent out, `RETURNABLE_TYPES`) or `SHED` (book, `ON_SITE_TYPES`, always PROPRIETARY). One map, `KIND_THING_TYPES` in `core/models/collection.py`, says which verbs each holds; the app's address for a collection is `/{kind}/{code}` (`Collection.path()`), and `/collections/{code}` is only a 301 to it. `allowed_thing_types` stays, as the verbs *within* the kind and never empty. A **reservations collection is a shed** (`Collection.is_reservations_collection()` is `kind == SHED`, not a look at the verb list), and a thing's verb is not chosen: the server derives it from the kind and the price (`derive_thing_type`).
- **Demo data lives in a command, not migrations**: `python manage.py seed_demo` populates Lala/Lele/Lili/Lolo/Lulu and their collections. Idempotent (`update_or_create`), and it touches only its own characters: in a demo collection's `invites` and `co_owners` it adds and removes the five demo users and leaves any other member or co-curator where they are. Fresh DBs start empty; run the command explicitly (also on Heroku: `heroku run --app <app> "python manage.py seed_demo"` — quote the inner command, otherwise the Heroku CLI intercepts inner flags like `--lang`/`--reset` as its own). Every demo collection's title starts with `DEMO · ` in all three languages (the visible 64 still hold; the things inside are not marked); relaunching `seed_demo` renames the ones already in a database. Collection/thing text is always seeded in **all three languages at once** (inline `{es,ca,en}` localized maps, tag labels and `Collection.deposit_policy` included — the constants in `seed_data/common.py`); `--lang=en|es|ca` only picks the language of the plain-column text (user bios, FAQs), and `--reset` wipes demos before re-seeding. The shared structure lives in `seed_data/common.py` and each language's text in `seed_data/{lang}.py`, merged by `seed_demo.load_seed_data` (parity + length limits pinned by `core/tests/unit/test_seed_localized.py`). Don't add new demo data to migrations — edit the relevant `seed_data/*.py` and re-run. To add a new language, copy `en.py` → `{lang}.py` and translate only the text (keep the same codes/keys — the structure stays in `common.py`, respecting model max_length), then add the code to `SUPPORTED_LANGS` in `seed_demo.py`.

## Model selection

- **Session default: `opusplan`** (`~/.claude/settings.json`). Opus reasons in plan
  mode, Sonnet executes.
- **A code review runs on Opus, never Sonnet** — whether it is asked for in the
  chat or run through `/prerelease`. A review is judgement, not typing, and the
  session default puts Sonnet on everything that is not plan mode.
  - `/prerelease` pins it itself: `model: opus` in its SKILL.md frontmatter, which
    overrides the session model for the turn that invokes it and is not saved to
    settings. Verified against the official skills frontmatter schema, which
    accepts the same values as `/model`.
  - The **bundled** `/code-review` cannot be pinned this way: its frontmatter is
    not ours, `skillOverrides` controls visibility only, and shadowing the name
    with a local skill would replace the review itself rather than its model. Set
    the session model to Opus before invoking it.

## Commit attribution

Claude Code's own trailer is switched off (`"attribution": {"commit": ""}` in
`~/.claude/settings.json`), so the trailer below is the only one a commit carries.
There is exactly one format:

```
AI-assistant: Claude Code (<model name and version>)
```

- **The model name comes from the live model**, read from whichever model is actually
  running: `Claude Opus 5`, `Claude Sonnet 5`, `GLM-5.3 [1m]`. Never copied from a
  constant, a config file, or a previous commit — when a new version ships, the
  line must reflect it on its own. It is the readable name, not the API id, so
  `claude-opus-5` is written `Claude Opus 5` and `glm-5.3` `GLM-5.3`.
- **The tool is always named**, whoever built the model: the line says what wrote
  the code, and through what. A different assistant names itself in that slot.
- **The parentheses hold the model as it announces itself and nothing else** — not the
  subject of the commit, a summary of the task, a date, a branch name, or an issue id.
  A second value *about* the model is added by asking, not by inventing.
- **A variant marker inside the model's own identifier travels with the name**, because
  it is part of what the model says it is rather than a claim about it: GLM announces
  itself as `glm-5.3[1m]`, so the line reads `GLM-5.3 [1m]`. Claude models announce no
  variant (the id is `claude-opus-5`), so there is nothing to carry and **a
  context-window marker is never added by hand**. The old format's `(1M context)` was
  exactly that hand-added claim and is retired: on the 177 `Claude Opus 4.8` commits it
  described a variant nobody could read off the model, while on the 25 `GLM-5.2` ones it
  was this same `[1m]` paraphrased — two different things in one parenthesis.
- **No email address.** The old format carried one and it was pure syntax: a model
  is not an author and holds no copyright, so no mailbox belongs to it. Inventing
  one is what produced the `opus5@anthropic.com` errors of August 2026.
- **Not `Co-Authored-By:`, deliberately** (changed 2026-09-27). Git, GitHub and DCO
  practice all read that trailer as *another author with standing*, and this
  codebase's licensing rests on all copyright sitting in one pair of hands
  (`CONTRIBUTING.md`, and the CLA that closes before launch). A model cannot be a
  co-author, so claiming it in the one field a reader checks was the wrong claim in
  the most sensitive place. `AI-assistant:` says what actually happened and leaves
  `Co-Authored-By:` for people.
- **Exactly one `AI-assistant:` line — never two on the same commit.** A commit
  names the model that actually produced *that commit's* changes. Under `opusplan`
  that is almost always Sonnet, since Opus only reasons in plan mode and writes
  nothing to the tree itself; name Opus instead only when Opus's own output, not
  just its plan, is what landed in that diff. If two models' work truly can't be
  told apart within one commit, that is a sign the commit should have been split by
  concern — not a reason to stack trailers.
- **Never copy a trailer from git history.** The body's style is worth imitating;
  the trailers are not. Every commit up to and including `6dbf8e2` (2026-09-22)
  carries the old `Co-Authored-By:` format, and the history is **not** being
  rewritten — so `git log` has two eras and the older one is not a precedent.
  Inside it, the commits of August 2026 are wrong even for their own era (a task
  descriptor in the parenthesis, invented addresses, and some stacking two trailers
  on one change); those were left in place deliberately too.

Valid — one trailer per commit:

```
AI-assistant: Claude Code (Claude Sonnet 5)
```

```
AI-assistant: Claude Code (Claude Opus 5)
```

```
AI-assistant: Claude Code (GLM-5.3 [1m])
```

Invalid — two models stacked on one commit, even when both genuinely took part:

```
AI-assistant: Claude Code (Claude Opus 5)
AI-assistant: Claude Code (Claude Sonnet 5)
```

When in doubt about how to compose the line, ask rather than decide.

## Commit messages, code comments and docs

The repositories are public, and whoever reads them later was not in the conversation that produced a change.
Write for them.

- **What changed and why, impersonally**, as a fact about the code or the product: "Request emails now carry
  the requester's address as Reply-To, so a manager's reply reaches them." Not who asked for it.
- **Never name the people who asked for, approved or decided a change** — no "CA", no "the user" meaning whoever
  gave the instructions, no "X approved the wording", no "X moved it to Y". The roles inside the product
  (requester, owner, member, manager, operator) are fine, and so are the demo personas (Lala…Lulu) where the seed
  or a test uses them.
- **No task or round ids** ("E1", "TLH2", "round G", "as before this round", "E2 had added…"): they point to
  working notes that are never committed. If the history is the reason, say what the code did before.
- **No references to working files** (`*_TASKS.md` and the like).
- **Dates only when the date itself matters** — two migrations that must ship one release apart, an announced
  removal. `git blame` already dates every line.
- **Subject line short and imperative.** The body says the what and the why when the diff does not make them
  obvious; it is not an account of how the change was arrived at.
- **Attribution is the one `AI-assistant:` trailer** described under "Commit attribution", with the live model's
  name. Nothing else in a commit attributes it.

Commits written before 2026-10-06 do not follow this and are not rewritten; the comments and docs were cleaned
once, on that date.

## Project Documentation

For complete information about OIUEEI — project structure, tech stack, API endpoints, development setup, environment variables, security measures, and roadmap — see [`README.md`](README.md).

## Detailed Models Documentation

For complete field-by-field documentation, business rules, methods, and reverse relations for each model, see [`core/models/CLAUDE.md`](core/models/CLAUDE.md).

## Detailed Views Documentation

For endpoint definitions, permissions, request/response formats, and business logic for each Django view, see [`core/views/CLAUDE.md`](core/views/CLAUDE.md).

## Detailed Serializers Documentation

For serializer patterns (security fields, prefetch-aware computed fields, asset URLs), naming conventions, and field-by-field documentation for each serializer, see [`core/serializers/CLAUDE.md`](core/serializers/CLAUDE.md).

## Detailed Services Documentation

For booking business logic (atomic transactions, row-level locking) and centralised email service (XSS prevention, dual format, action links), see [`core/services/CLAUDE.md`](core/services/CLAUDE.md).

## Frontend Documentation

For React routes, pages, tech stack, Vite configuration, and authentication flow, see [`frontend/CLAUDE.md`](frontend/CLAUDE.md).

## Design Guidelines

When designing or reviewing any frontend view, component, or copy, consult [`DESIGN.md`](DESIGN.md) and apply all twelve principles. Use the checklist at the end of that document before considering any view complete.
