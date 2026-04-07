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

## Font Notice

The GraebenbachTRIAL typeface used in this project is **not included in this repository** — the licence does not permit redistribution. The font files (`frontend/src/fonts/*.otf`) are listed in `.gitignore`.

You have two options before deploying:

**Option A — Use the official trial font**
Download GraebenbachTRIAL directly from the type foundry:
https://camelot-typefaces.com/graebenbach

Place the `.otf` files in `frontend/src/fonts/`. They will be picked up by Vite during the build.

**Option B — Use a different typeface**
Edit `frontend/src/fonts/oiueei-fonts.css` and replace the `@font-face` declarations with your chosen font. Make sure to update the `font-family` name if it differs from `HelsinkiGrotesk`.

> In either case, the app will work without fonts — browsers will fall back to system fonts. Fonts only affect visual appearance.

## Deployment Branch

Because font files must be present for the build but cannot be committed to the public repository, we recommend using a dedicated deployment branch:

```bash
git checkout -b deploy-heroku
# add your font files to frontend/src/fonts/
git add frontend/src/fonts/
git commit -m "Add fonts for deployment"
```

Use this branch exclusively for Heroku deploys. Keep `development` clean for GitHub.

When you have new changes to deploy:

```bash
git checkout deploy-heroku
git merge development
git push heroku deploy-heroku:main
git checkout development
```

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
  DEFAULT_FROM_EMAIL='noreply@your-domain.com' \
  EMAIL_HOST_PASSWORD='<your SMTP API key>' \
  NPM_CONFIG_PRODUCTION=false \
  -a your-app-name
```

> **Note:** Heroku sometimes appends a random suffix to the hostname (e.g. `your-app-name-a1b2c3d4.herokuapp.com`). Check the exact URL after the first deploy and update `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` if needed.

### 5. Deploy

```bash
git push heroku deploy-heroku:main
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

### 8. Open the app

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
  -a your-app-name
```

> **Note:** The root domain (`your-domain.com`) will show "Failing - Incorrect DNS Settings" in `heroku domains` because Heroku verifies via DNS CNAME, which cannot be set on the root. This is expected — your DNS provider's redirect will forward users from `your-domain.com` to `https://www.your-domain.com` transparently.

## Email

OIUEEI requires email to send magic links. Configure your SMTP provider via the following vars (defaults to SendGrid):

| Variable | Description |
|----------|-------------|
| `EMAIL_HOST` | SMTP host (default: `smtp.sendgrid.net`) |
| `EMAIL_PORT` | SMTP port (default: `587`) |
| `EMAIL_HOST_USER` | SMTP username (default: `apikey`) |
| `EMAIL_HOST_PASSWORD` | SMTP password or API key |
| `DEFAULT_FROM_EMAIL` | Sender address |

## Monitoring (New Relic)

OIUEEI uses the New Relic APM add-on for performance and error monitoring. The `Procfile` wraps gunicorn with `newrelic-admin run-program` so every request and background transaction is instrumented automatically.

### Add the add-on

```bash
heroku addons:create newrelic:wayne -a your-app-name
```

This automatically sets `NEW_RELIC_LICENSE_KEY`. Then set the remaining config vars:

```bash
heroku config:set \
  NEW_RELIC_CONFIG_FILE=newrelic.ini \
  NEW_RELIC_LOG=stdout \
  -a your-app-name
```

The `newrelic.ini` file in the repository reads the licence key from `NEW_RELIC_LICENSE_KEY` via `%(NEW_RELIC_LICENSE_KEY)s` — no secrets are hardcoded.

### Scheduler Monitor

The Heroku Scheduler Monitor add-on tracks execution of `expire_bookings`:

```bash
heroku addons:create scheduler-monitor:test -a your-app-name
```

Recommended monitors to activate in the dashboard:
- **Monitor Failed Jobs** — alerts on any job failure
- **Monitor Interrupted Jobs** — alerts if the dyno dies mid-run
- **Monitor Execution Times** — alerts if the job takes longer than expected
- **Scheduler Job Skip Detection (Every Day)** — alerts if the job is skipped entirely

## Booking Expiration

Pending bookings expire after 72 hours. Run the cleanup command periodically using [Heroku Scheduler](https://devcenter.heroku.com/articles/scheduler):

```
python manage.py expire_bookings
```

## Troubleshooting

**Bad Request (400)** — Check `DJANGO_ALLOWED_HOSTS`. The actual Heroku hostname may include a random suffix. Run `heroku open -a your-app-name` to confirm the exact URL.

**Build fails on collectstatic** — Font files may be missing. See the Font Notice section above.

**Release command fails (migrate)** — `DATABASE_URL` may not be set. Verify with `heroku config -a your-app-name` and ensure the Postgres add-on was created.

**App works but fonts look wrong** — Font files were not included in the build. See Option A or Option B in the Font Notice section.

**`ERR_SSL_UNRECOGNIZED_NAME_ALERT` on custom domain** — SSL cert not yet issued. Run `heroku certs:auto:enable -a your-app-name` and wait for DNS propagation. Check with `heroku domains -a your-app-name`.
