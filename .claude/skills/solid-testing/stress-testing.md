# Stress & load testing reference (OIUEEI on Heroku)

**Manual, occasional, deliberate.** These tests are slow, cost money, and can
knock services over — they run before big releases or infra changes (dyno/plan
migrations, connection-pool changes), **never** in the regular CI pipeline and
**NEVER against production**. OIUEEI has no permanent staging: spin up a
disposable target first (same pattern as the Postgres restore drill).

## Vocabulary

| Kind | Question it answers | Shape |
|---|---|---|
| **Load** | Does expected traffic feel fine? | steady N users, 5–10 min |
| **Stress** | Where is the breaking point? | ramp until error rate > 1–5 % or p95 explodes |
| **Spike** | Does a sudden rush (viral link) recover? | 0 → burst → 0, watch recovery |
| **Soak** | Does an hour of load degrade it (leaks)? | modest load, 30–60 min, watch memory drift |

Minimum metrics per run: **p95/p99 latency · RPS · error rate**, plus server
side `heroku ps -a <staging-app>` (dyno load/memory) and
`heroku pg:info` (connections) *during* the run.

## Disposable staging (the safe target)

```bash
heroku create oiueei-staging --region eu
heroku addons:create heroku-postgresql:essential-0 -a oiueei-staging
heroku config:set DJANGO_SECRET_KEY=$(openssl rand -hex 32) DJANGO_ALLOWED_HOSTS=oiueei-staging-<hash>.herokuapp.com ... -a oiueei-staging
git push https://git.heroku.com/oiueei-staging.git heroku:main
heroku run -a oiueei-staging "python manage.py seed_demo --lang=es"
# …run the tests…
heroku apps:destroy oiueei-staging --confirm oiueei-staging   # afterwards, always
```

Costs cents for an afternoon. Emails: point EMAIL_HOST at nothing or leave
credentials unset — a load test must not send thousands of real emails.

## HTTP layer — Locust (primary)

`scripts/stress_test_locust.py` is the house locustfile. Two OIUEEI-specific
realities baked into it:

1. **Auth is magic-link — there is no password to log in with.** Authenticated
   load therefore uses **pre-generated Bearer tokens**: create N users on the
   staging target and dump tokens with a one-off dyno, feed the file to Locust
   (`TOKENS_FILE`). Never generate tokens against production.
2. **Anonymous traffic is real traffic** (PUBLIC collections, /legal, /health)
   — the anonymous user class exercises it without any token.

```bash
pip install locust
heroku run -a oiueei-staging "python manage.py shell -c \"
from core.models import User
from rest_framework_simplejwt.tokens import RefreshToken
users = User.objects.filter(email__endswith='@loadtest.local')[:50]
print('\n'.join(str(RefreshToken.for_user(u).access_token) for u in users))\"" > tokens.txt

locust -f .claude/skills/solid-testing/scripts/stress_test_locust.py \
  --host https://oiueei-staging-<hash>.herokuapp.com \
  -u 50 -r 5 --run-time 10m --headless \
  --csv results  # writes p95/p99/RPS/error tables
```

Scenario presets: load `-u 50 -r 5 -t 10m` · stress `-u 300 -r 10 -t 15m`
(stop at >5 % errors — that's the number you came for) · spike: start 5 users,
then a second locust with `-u 200 -r 200 -t 2m` · soak `-u 30 -r 2 -t 45m`
watching `heroku ps` memory.

**k6 alternative** (single Go binary, JS scenarios, friendlier for a scripted
one-shot): same scenarios, `k6 run --vus 50 --duration 10m script.js`. Choose
one tool per campaign; comparing across tools is noise.

## Database layer — pgbench (separate campaign)

pgbench measures **the database alone** — run it *after* an HTTP campaign to
learn whether the bottleneck is the app (queries, N+1, serialization) or the
DB itself. Ships with `postgresql-contrib` (`brew install libpq` locally).

**Plan-reality first (essential-0):** the connection limit is **20** and
Heroku keeps a few for itself. `-c 100` doesn't measure your database — it
measures the error message. Realistic grid for this plan:

```bash
# Target: a THROWAWAY essential-0 (the restore-drill pattern), seeded via
# pg:backups:restore of a recent backup — real schema, real data shape.
# NEVER the production DATABASE_URL. Get its URL:
DB=$(heroku config:get HEROKU_POSTGRESQL_<COLOR>_URL -a oiueei)

pgbench -i -s 10 "$DB"          # ~160 MB synthetic side-tables; enough at this scale
pgbench -c 5  -j 2 -T 300 "$DB"          # normal mixed load
pgbench -S -c 10 -j 2 -T 300 "$DB"       # read-only (dashboards/listings shape)
pgbench -N -c 8  -j 2 -T 300 "$DB"       # write-heavy (skip vacuum-sensitive updates)
pgbench -c 16 -j 4 -T 300 "$DB"          # near the 20-conn ceiling — the break test
pgbench -C -c 10 -j 2 -T 120 "$DB"       # reconnect-per-transaction: no-pooling pain
```

Capture: **TPS · per-transaction p95/p99 (`-r`) · active connections vs limit
(`heroku pg:info`) · locks/deadlocks** (`pg:diagnose`).

**Interpretation rule:** if the HTTP campaign saturates while pgbench shows
the DB comfortable → the bottleneck is Django (profile queries, check
`select_related`/`prefetch_related`). If connections exhaust before the app
breaks a sweat → connection pooling time: fewer/persistent Django conns
(`conn_max_age` is already 600), then PgBouncer / Heroku's pooling add-on,
then a bigger PG plan — in that order.

## Reporting

A campaign without a written result never happened. Record: date, target,
scenario, the three metric tables, the identified bottleneck, and the decision
(nothing / code fix / plan change). File it with the release notes of whatever
release triggered the campaign.
