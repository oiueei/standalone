# Deploying OIUEEI to Heroku

This guide covers deploying OIUEEI on a single Heroku Dyno. Django serves both the API and the React SPA — React is compiled during the build phase and served as static files via WhiteNoise.

## Architecture

```
Build phase (runs once on each deploy):
  Node buildpack  → npm run build → frontend/dist/
  Python buildpack → collectstatic → copies frontend/dist/ to staticfiles/

Runtime (single gunicorn process):
  /api/*      → Django REST Framework
  /static/*   → WhiteNoise serves JS, CSS, fonts
  /*          → Django serves index.html → React Router handles routing
```

## Prerequisites

- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed and logged in
- A Heroku account
- **Three external services** the app cannot run without:
  - **PostgreSQL** — the database (added as a Heroku add-on below)
  - **Cloudinary** — image uploads, free account at [cloudinary.com](https://cloudinary.com)
  - **An SMTP provider** — magic-link sign-in emails, e.g. Mailgun or SendGrid

## Font Notice

The Curiosa typeface (by [Fabio Haag Type](https://fabiohaagtype.com)) used in this project is **not included in this repository** — its licence does not permit redistribution. The font binary (`frontend/public/fonts/curiosa/Curiosa-Variable.woff2`) is listed in `.gitignore`.

You have two options before deploying:

**Option A — Supply the font**
Place `Curiosa-Variable.woff2` in `frontend/public/fonts/curiosa/`. It is a variable font (weight + italic axes) and Vite serves it during the build.

**Option B — Use a different typeface**
Edit `frontend/src/fonts/oiueei-fonts.css` and replace the `@font-face` declarations with your chosen font, keeping (or updating) the `Curiosa` family name so the HDS `--font-default` token resolves to it.

> In either case, the app works without the font — browsers fall back to a system sans. Fonts only affect visual appearance.

## Fonts in the build

The font files are gitignored (see [Font Notice](#font-notice)), so a fresh clone does not contain them. Heroku compiles the frontend during the build, so the fonts must be present on the branch you deploy. Add them locally before deploying — a normal `git add` skips them, so force-add:

```bash
# place Curiosa-Variable.woff2 in frontend/public/fonts/curiosa/, then:
git add -f frontend/public/fonts/curiosa/*.woff2
git commit -m "Add fonts for deployment"
```

If you skip this the app still works — it falls back to system fonts (see Option B above).

## Step-by-step Setup

### 1. Create the Heroku app

Create the app via the [Heroku Dashboard](https://dashboard.heroku.com/) (recommended if you want to choose the Europe region) or via CLI:

```bash
heroku create your-app-name
```

Then link your local repo to the app:

```bash
heroku git:remote -a your-app-name
```

### 2. Add buildpacks

Order matters — Node must run before Python so the React build happens before `collectstatic`.

```bash
heroku buildpacks:add heroku/nodejs -a your-app-name
heroku buildpacks:add heroku/python -a your-app-name
```

### 3. Add PostgreSQL

```bash
heroku addons:create heroku-postgresql:essential-0 -a your-app-name
```

This automatically sets the `DATABASE_URL` config var.

### 4. Set config vars

Generate a secure secret key first:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Then set all required variables (replace `your-app-name` and the values as appropriate):

```bash
heroku config:set \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  DJANGO_SECRET_KEY='<your generated key>' \
  DJANGO_ALLOWED_HOSTS='your-app-name.herokuapp.com' \
  CSRF_TRUSTED_ORIGINS='https://your-app-name.herokuapp.com' \
  MAGIC_LINK_BASE_URL='https://your-app-name.herokuapp.com/verify' \
  RSVP_BASE_URL='https://your-app-name.herokuapp.com/rsvp' \
  SHARE_LINK_BASE_URL='https://your-app-name.herokuapp.com/share' \
  CLOUDINARY_URL='cloudinary://<api_key>:<api_secret>@<cloud_name>' \
  NPM_CONFIG_PRODUCTION=false \
  -a your-app-name
```

> **Cloudinary:** `CLOUDINARY_URL` powers image uploads. Create a free account at [cloudinary.com](https://cloudinary.com) and copy the value of *API environment variable* from your dashboard (Settings → API Keys). Format: `cloudinary://api_key:api_secret@cloud_name`. Without it the app runs, but image uploads fail.

> **Email** is configured separately — see the [Email](#email) section below. Magic-link sign-in does not work until SMTP is set.

> **Note:** Heroku sometimes appends a random suffix to the hostname (e.g. `your-app-name-a1b2c3d4.herokuapp.com`). Check the exact URL after the first deploy and update `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` if needed.

### 5. Deploy

Heroku deploys from its `main` branch. Push whichever local branch has your fonts committed:

```bash
git push heroku HEAD:main
```

### 6. Run migrations

The `Procfile` release command runs migrations automatically on each deploy. If for any reason you need to run them manually:

```bash
heroku run python manage.py migrate -a your-app-name
```

### 7. Create a superuser (optional)

Required to access the Django admin at `/oiueei-admin/`:

```bash
heroku run python manage.py createsuperuser -a your-app-name
```

The admin also requires 2FA (`django-otp`) — bootstrap a TOTP device for that superuser and scan the printed `otpauth://` URI into an authenticator app:

```bash
heroku run --app your-app-name "python manage.py add_totp_device <email>"
```

### 8. Seed demo data (optional)

Populate the database with the demo users (Lala/Lele/Lili/Lolo/Lulu) and their collections. Idempotent — safe to re-run.

```bash
heroku run -a your-app-name "python manage.py seed_demo"                  # English (default)
heroku run -a your-app-name "python manage.py seed_demo --lang=es"        # Spanish
heroku run -a your-app-name "python manage.py seed_demo --lang=es --reset"  # wipe demos and re-seed
```

**Quote the inner command.** Without quotes (or a `--` separator), the Heroku CLI intercepts inner flags such as `--lang` and `--reset` as its own and fails with `Nonexistent flag`. Equivalent forms that also work:

```bash
heroku run -a your-app-name -- python manage.py seed_demo --lang=es
```

`--reset` only deletes demo data (the seeded users/collections/things), leaving any other users and content intact.

### 9. Open the app

```bash
heroku open -a your-app-name
```

## Custom Domain & SSL

### 1. Add domains to Heroku

```bash
heroku domains:add your-domain.com -a your-app-name
heroku domains:add www.your-domain.com -a your-app-name
```

Note the DNS targets returned for each domain — you will need them for your DNS provider.

### 2. Configure DNS

**For `www.your-domain.com`** — add a CNAME record pointing to the DNS target Heroku gave you:

| Type  | Host | Value |
|-------|------|-------|
| CNAME | www  | `<dns-target-from-heroku>` |

**For the root `your-domain.com`** — most DNS providers do not allow a CNAME on the root (`@`). Use your provider's domain forwarding / redirect feature to forward `your-domain.com` → `https://www.your-domain.com`.

> Example (IONOS): Go to Domains → your domain → Domain Forwarding. Set source to `your-domain.com`, destination to `https://www.your-domain.com`, type HTTP redirect (301).

### 3. Enable Automated Certificate Management (SSL)

```bash
heroku certs:auto:enable -a your-app-name
```

After DNS propagates (up to 48 h), Heroku will issue a free TLS certificate for your domain. Check status with:

```bash
heroku domains -a your-app-name
```

Look for `Cert issued` next to your domains.

### 4. Update config vars

```bash
heroku config:set \
  DJANGO_ALLOWED_HOSTS='www.your-domain.com,your-app-name.herokuapp.com' \
  CSRF_TRUSTED_ORIGINS='https://www.your-domain.com,https://your-app-name.herokuapp.com' \
  MAGIC_LINK_BASE_URL='https://www.your-domain.com/verify' \
  RSVP_BASE_URL='https://www.your-domain.com/rsvp' \
  SHARE_LINK_BASE_URL='https://www.your-domain.com/share' \
  -a your-app-name
```

> **Note:** The root domain (`your-domain.com`) will show "Failing - Incorrect DNS Settings" in `heroku domains` because Heroku verifies via DNS CNAME, which cannot be set on the root. This is expected — your DNS provider's redirect will forward users from `your-domain.com` to `https://www.your-domain.com` transparently.

## Email

Sign-in uses magic links, so a working SMTP provider is **mandatory** — without it nobody can log in. Any provider works; below is an example for Mailgun (for SendGrid, set `EMAIL_HOST=smtp.sendgrid.net` and `EMAIL_HOST_USER=apikey`):

```bash
heroku config:set \
  EMAIL_HOST='smtp.mailgun.org' \
  EMAIL_PORT=587 \
  EMAIL_HOST_USER='postmaster@your-domain.com' \
  EMAIL_HOST_PASSWORD='<your SMTP password or API key>' \
  DEFAULT_FROM_EMAIL='noreply@your-domain.com' \
  -a your-app-name
```

| Variable | Description |
|----------|-------------|
| `EMAIL_HOST` | SMTP host (default: `smtp.sendgrid.net`) |
| `EMAIL_PORT` | SMTP port (default: `587`) |
| `EMAIL_HOST_USER` | SMTP username (default: `apikey`) |
| `EMAIL_HOST_PASSWORD` | SMTP password or API key |
| `DEFAULT_FROM_EMAIL` | Sender address |

## Scheduled jobs (cron)

The app relies on six management commands run on [Heroku Scheduler](https://devcenter.heroku.com/articles/scheduler). In production they run as **one daily job at 05:00 UTC** chaining all six with `&&`, so any failure stops the chain and surfaces in scheduler-monitor:

```
python manage.py expire_bookings && python manage.py cleanup_rsvps && python manage.py close_transfers && python manage.py send_reminders && python manage.py send_digests && python manage.py stats_summary
```

Heroku Scheduler config lives in the dashboard, so the intended schedule is versioned here — keep the dashboard in sync with this table.

| Command | Cadence | What it does |
|---|---|---|
| `python manage.py expire_bookings` | daily (chained) | Expires PENDING bookings past 72h; restores single-use things to ACTIVE. |
| `python manage.py cleanup_rsvps` | daily (chained) | Deletes RSVP tokens that expired 24h+ ago. |
| `python manage.py close_transfers` | daily (chained) | Sets `returned_date` on transfers whose ACCEPTED booking's `end_date` has passed. |
| `python manage.py send_reminders` | daily (chained) | Return/delivery reminders for bookings due tomorrow. |
| `python manage.py send_digests` | daily (chained) | Weekly digests + newsletters (Mondays) and monthly digests (1st); the command no-ops on other days. |
| `python manage.py stats_summary` | daily (chained) | First-party product stats; prints every day, emails `STATS_EMAIL` on Mondays (skipped if unset). |

The daily commands are safe to run every day — each checks the date internally and no-ops when there's nothing to do.

`stats_summary`'s weekly email is opt-in — set `STATS_EMAIL` to receive it (`heroku config:set STATS_EMAIL='you@your-domain.com' -a your-app-name`); it always prints to the log regardless.

**Not in the daily chain:** `cleanup_orphan_images` (delete orphaned Cloudinary uploads) is a separate, manual command — dry-run by default, `--commit` to actually delete. It's destructive and gated behind Heroku shell access, so it isn't auto-scheduled; run it by hand roughly weekly. Quote the inner command so the Heroku CLI doesn't eat the flag: `heroku run --app <app> "python manage.py cleanup_orphan_images --commit"`.

## Troubleshooting

**Bad Request (400)** — Check `DJANGO_ALLOWED_HOSTS`. The actual Heroku hostname may include a random suffix. Run `heroku open -a your-app-name` to confirm the exact URL.

**Build fails on collectstatic** — Font files may be missing. See the Font Notice section above.

**Release command fails (migrate)** — `DATABASE_URL` may not be set. Verify with `heroku config -a your-app-name` and ensure the Postgres add-on was created.

**App works but fonts look wrong** — Font files were not included in the build. See Option A or Option B in the Font Notice section.

**`ERR_SSL_UNRECOGNIZED_NAME_ALERT` on custom domain** — SSL cert not yet issued. Run `heroku certs:auto:enable -a your-app-name` and wait for DNS propagation. Check with `heroku domains -a your-app-name`.
