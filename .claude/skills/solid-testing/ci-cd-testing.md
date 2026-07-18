# CI/CD testing reference (GitHub Actions + Heroku)

What the pipeline already guarantees, and the upgrades worth proposing. The
workflow lives in `.github/workflows/tests.yml` — actions pinned by commit
SHA, gitleaks checksummed (supply-chain hardening from the 2026-07 security
round). Keep both properties when editing.

## Already enforced — don't regress it

- Backend suite with `--cov-fail-under=80`; frontend `npm run test:coverage`
  with the vite.config ratchet (the CI-visible floor).
- `python manage.py makemigrations --check` on a bare checkout — no phantom
  migrations.
- `npm run build` — the production bundle must build (catches import errors
  the jsdom suite can't).
- ruff + ESLint; gitleaks secret scan.
- Coverage-instrumented runs are ~2× slower on GH runners: `testTimeout:
  20000` in vite.config exists for the axe smokes — don't "fix" flakes by
  deleting it.

## Upgrade 1 — run the backend job against real Postgres

Local dev and CI use SQLite; production is PostgreSQL. SQLite doesn't enforce
`max_length`, differs on constraint timing and has no real locks — a class of
bug invisible until the Heroku release phase. Add a second backend job (keep
the fast SQLite one for signal speed):

```yaml
  test-postgres:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16        # match the Heroku PG major version
        env: { POSTGRES_PASSWORD: ci, POSTGRES_DB: oiueei_ci }
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready" --health-interval 5s
          --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgres://postgres:ci@localhost:5432/oiueei_ci
    steps:
      # …checkout/setup as the sqlite job (pin by SHA), then:
      - run: python manage.py migrate --noinput   # migrations on real PG — the release-phase rehearsal
      - run: pytest -q
```

This is exactly the test that would have caught the 2026-06-30
`cannot ALTER TABLE "things" because it has pending trigger events` in CI
instead of during a production release.

## Upgrade 2 — post-deploy smoke

`/api/v1/health/` now verifies the database (200 ok / 503 degraded). After
every deploy, one request answers "did the release actually serve?":

```bash
# scripts/smoke.sh <base-url> — exits non-zero on any failure
set -euo pipefail
BASE="${1:?usage: smoke.sh https://www.example.com}"
curl -fsS --max-time 10 "$BASE/api/v1/health/" | grep -q '"status": *"ok"'
curl -fsS --max-time 10 -o /dev/null "$BASE/"
echo "smoke OK"
```

Wire it as a `workflow_dispatch` job (run it by hand right after "Deploy
Branch") — Heroku's release phase can't curl the new dynos itself. UptimeRobot
covers *continuous* uptime; the smoke covers *this specific release, right now*.

## Upgrade 3 — env-var validation

`config/settings/production.py::_require_env` already fails the release fast
on missing critical vars (that's the designed guard — a failed release never
goes live, the previous one keeps serving). When adding a new required var,
add it to `_require_env` in the same commit; that IS the test. Optional vars
get safe defaults and a line in README's env table.

## What CI must NOT do

- No load/stress tests in the pipeline (see stress-testing.md — manual, rare).
- No mutation testing on every push (scoped + manual via
  `scripts/mutation_test.sh`).
- No tests that hit third parties (Cloudinary, SMTP) — CI uses the locmem
  email backend and mocked externals; the contract with real services is
  verified by the post-deploy smoke and the operational monitors
  (UptimeRobot/Sentry), not by CI.
