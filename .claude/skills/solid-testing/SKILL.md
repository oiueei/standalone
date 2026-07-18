---
name: solid-testing
description: Design and strengthen RIGOROUS tests for OIUEEI's Django/DRF backend (pytest) and React frontend (vitest). Default mode audits every commit since the last push, grades its tests against a weak-test blocklist, then strengthens and extends them. Use when the user mentions tests, testing, cobertura, coverage, unit test, integration test, pytest, vitest, jest, TDD, mutation testing, stress/load testing — or when new Django/React code needs tests.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Solid Testing

Weak tests are worse than no tests: they buy a green checkmark and sell false
confidence. This skill exists to make every test in OIUEEI **protect a named
behaviour** — and to refuse the kind of test that only exists to move a
coverage number.

## The Prime Directive

> **Before writing or approving ANY test, state in one sentence which business
> behaviour it protects.** If you cannot name the behaviour — or the honest
> answer is "it covers lines" — do not write the test. Say so instead, and
> propose what a meaningful test of that code would look like.

Examples of named behaviours (from this repo's own suite):
- "A mail scanner's GET must never delete an account" → `test_get_previews_and_deletes_nothing`
- "A member joining once is counted once" → `TestMemberJoinedIsLoggedOncePerJoin`
- "Anonymous readers get the member count but no names" → `test_anonymous_reader_gets_member_count_but_no_names`

## Default workflow: audit the unpushed work

When invoked without a narrower request:

1. **Scope** — `git log --oneline @{push}..HEAD` (fall back to
   `origin/development..HEAD`). List the commits and the source files they
   touch (`git diff --stat @{push}..HEAD`).
2. **Map** — for each changed behaviour, find its tests (backend:
   `core/tests/{unit,integration,scenarios}/`; frontend: `src/test/`,
   colocated `*.test.jsx?`). Note behaviours with NO test.
3. **Grade** — read the existing tests for the changed code and grade each
   against the blocklist below. Quote the offending assertion when you flag one.
4. **Strengthen** — fix weak tests first (they are lying today), then add the
   missing ones. Follow the per-stack references:
   - [django-testing.md](django-testing.md) — models, serializers, views,
     permissions, transactions, migrations
   - [react-testing.md](react-testing.md) — states, interactions, hooks, a11y
   - [checklist.md](checklist.md) — the full smell catalogue with bad→good pairs
5. **Verify the verifiers** — for at least the most critical new test,
   re-introduce the bug (or mutate the condition) and confirm the test FAILS.
   A test you have never seen red is unproven. For broader sweeps, run
   `scripts/mutation_test.sh` (scoped to the changed files).
6. **Run everything** — backend `pytest -q --cov=core --cov-fail-under=80`,
   frontend `cd frontend && npm run test:coverage`, plus `ruff check .` and
   `npx eslint src`. The frontend coverage ratchet in `vite.config.js` must
   still pass; if your new code drops a metric below it, the code needs tests,
   not the ratchet lowering.
7. **Report** — end with the session summary (format below).

## The weak-test blocklist

Reject (or rewrite) any test that matches one of these. The full catalogue
with examples lives in [checklist.md](checklist.md).

| # | Smell | The lie it tells |
|---|-------|------------------|
| 1 | Asserts only "no exception" / bare `status_code == 200` with no body check | "The endpoint works" (it only *responds*) |
| 2 | Single happy path — no `None`/empty/boundary/wrong-type/concurrent case | "The logic is correct" (only for one input) |
| 3 | Mock configured but never verified (`assert_called_once_with` missing) | "The collaboration happens" (nobody checked) |
| 4 | "Integration" test with every collaborator mocked | "The pieces fit" (they never met) |
| 5 | Bug fixed without a regression test that fails on the old code | "It won't come back" (nothing guards the door) |
| 6 | Asserts coupled to implementation detail (internal call order, private attrs, exact HTML) | "Behaviour is pinned" (only today's implementation is) |
| 7 | Test passes with the assertion deleted (vacuous setup) | Everything |
| 8 | Frozen expectations copied from the code's own output ("golden" numbers nobody derived) | "The output is right" (it's merely unchanged) |

## OIUEEI conventions (respect them — don't re-invent)

**Backend** — `pytest-django`; fixtures in `core/tests/conftest.py`
(`user`, `user2`, `authenticated_client` with Bearer JWT, `collection`,
`thing`, `faq`); `factory_boy` for bulk fixtures; `time_machine` to freeze
time (never `sleep`); `django.core.mail.outbox` for email assertions; rate
limits are OFF in tests (`RATELIMIT_ENABLE`) — test quota logic by unit-testing
its function, not by hammering the endpoint; JSON parser only → always
`format="json"` on APIClient posts.

**Frontend** — vitest + Testing Library + jest-axe. Mock the network at the
boundary: `globalThis.fetch = vi.fn(...)` returning **realistic contract
shapes** (the same JSON the DRF serializer emits — copy a real response, don't
invent a convenient one). That seam is the repo convention; do not introduce
MSW here. Prefer `userEvent` for new tests that involve typing/tab/hover;
`fireEvent.click` is acceptable for plain clicks. Query by role/label (this
doubles as the AA accessibility check); never by class name. Remember the
repo gotcha: a textarea's value lives in its `textContent`, so scope
`getByText` with `ignore: 'script, style, textarea'` when asserting rendered copy.
Locale keys: adding any → all three (`en`/`es`/`ca`); `i18nParity.test.js`
enforces it.

**Both** — tests pin behaviour, not implementation. If refactoring the
internals (same behaviour) would break the test, the test is wrong.

## Coverage is a floor detector, not a goal

Run `python .claude/skills/solid-testing/scripts/coverage_report.py` to get
per-module gaps for both stacks. Use it to find **untested behaviours**, then
apply the Prime Directive to each gap. Never write a test whose only purpose
is to raise the number — that is how smells #7 and #8 are born.

## CI/CD and heavier layers

- CI expectations and upgrades (Postgres-service migrations job, post-deploy
  smoke against `/api/v1/health/`, prod build): [ci-cd-testing.md](ci-cd-testing.md)
- Load/stress/spike/soak testing (Locust, k6, pgbench) — **manual, before big
  releases or infra changes, NEVER in every CI run, NEVER against
  production**: [stress-testing.md](stress-testing.md) and
  `scripts/stress_test_locust.py`. Mind the plan limits documented there
  (essential-0 Postgres = 20 connections; Basic dyno).
- Mutation testing (scoped): `scripts/mutation_test.sh [<base-ref>]`.

## Session-end report (mandatory)

Close every testing session with:

```
## Testing report — <date>
**Scope:** <commits/files audited>
**Weak tests fixed:** <n> (list: file::test — smell #)
**New tests:** <n> (each with the behaviour it protects, one line)
**Mutation-verified:** <which tests were seen red, and how>
**Coverage:** backend <x>% (worst modules: …) · frontend <s/b/f/l> vs ratchet
**Critical gaps remaining:** <ranked list — behaviour, not file names>
**Next to test (prioritised):** 1… 2… 3…
```

The "critical gaps" section must be honest even when it is uncomfortable —
an empty gaps list on a young codebase is itself a smell.
