---
name: ship
description: Pre-commit checklist for OIUEEI — review changes, run backend and frontend tests, identify missing tests, update .md documentation, confirm branch is `development`, then commit in British English as co-author. Use when the user says they are ready to commit or ship work.
disable-model-invocation: true
---

# Ship — Pre-Commit Checklist

## Live Context

- Current branch: !`git branch --show-current`
- Working tree: !`git status --short`
- Changes since last commit: !`git diff HEAD --stat`

---

You are about to help the user ship their work. Work through each phase below in order. Do not skip any phase. Report clearly on what you find at each step.

## Phase 1 — Review Recent Changes

Run `git diff HEAD` (or `git diff main..HEAD` if there are multiple commits) to understand what changed. Summarise:
- Which files were modified and why
- What features, fixes, or refactors were introduced
- Any obvious concerns (commented-out code, debug prints, TODO left in, hardcoded secrets)

## Phase 2 — Run Backend Tests

Run:
```
pytest -v --cov=core --cov-report=term-missing --cov-fail-under=80
```

- If tests fail, stop and report the failures to the user. Do not proceed to the commit.
- If coverage drops below 80%, stop and report it to the user.
- If all tests pass and coverage is ≥ 80%, report the result and continue.

## Phase 3 — Run Frontend Tests

Run:
```
cd frontend && npm test
```

- If tests fail, stop and report the failures to the user. Do not proceed to the commit.
- If all tests pass, report the result and continue.

## Phase 4 — Check for Missing Tests

Review the changed files from Phase 1 and evaluate:

**Backend** — for each new or modified view, serializer, service, or model method:
- Is there a corresponding unit or integration test in `core/tests/`?
- Does the test cover the main happy path and at least one error path?

**Frontend** — for each new or modified component or hook:
- Is there a corresponding Vitest test?

List any gaps you find. If there are gaps, ask the user whether they want to add tests now before committing, or ship anyway with a note.

## Phase 5 — Check .md Documentation

Review the following documentation files against the changes made. Update any file whose content is now out of date:

- `README.md` — project overview, environment variables, API endpoints
- `core/models/CLAUDE.md` — model fields, business rules, methods
- `core/views/CLAUDE.md` — endpoint definitions, permissions, request/response formats
- `core/serializers/CLAUDE.md` — serializer fields and patterns
- `core/services/CLAUDE.md` — service logic and email patterns
- `frontend/CLAUDE.md` — React routes, pages, components
- `DESIGN.md` — design principles (rarely needs updating)

For each file, state clearly: **up to date** or **updated** (with a brief summary of what changed).

## Phase 6 — Confirm Branch

Verify the current branch is `development`. If it is not, stop and warn the user before proceeding.

## Phase 7 — Commit

Once all phases above are green (or the user has explicitly approved any exceptions):

1. Stage all relevant changes: `git add` specific files — never `git add -A` blindly.
2. Write a commit message in **British English** that:
   - Uses the imperative mood in the subject line (e.g. "Add", "Fix", "Update", not "Added")
   - Has a concise subject (≤ 72 characters)
   - Has a body that explains *what* changed and *why*, covering all meaningful changes
   - Ends with the co-author line using your actual current model name, e.g.:
     ```
     Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
     ```
     (Replace "Opus 4.6" with whatever model you currently are.)
3. Run the commit using a HEREDOC to preserve formatting.
4. Confirm the commit was created successfully with `git log -1 --oneline`.
