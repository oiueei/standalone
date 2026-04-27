# OIUEEI - Development Guide

## Project Conventions

- **Single Django app**: All code lives in `core/`
- **Settings**: Split into `base.py`, `development.py`, `production.py` under `config/settings/`
- **Code style**: black (100-char lines), isort (black profile), flake8
- **Test structure**: `core/tests/unit/`, `core/tests/integration/`, `core/tests/scenarios/`
- **Coverage minimum**: 80% enforced by CI
- **All PKs**: 6-character alphanumeric codes generated via `secrets.choice()` (not auto-increment)
- **Emails**: All user content escaped via `django.utils.html.escape()`
- **String length in migrations**: SQLite (local) does NOT enforce `CharField(max_length=N)` at the DB level — PostgreSQL (Heroku/production) does. Always verify that seed data fits within the model's `max_length` before committing. Key limits: `headline` = 64, `description` = 256, `name` = 32, `email` = 64, `question` = 64, `answer` = 256, `location` = 32.
- **Demo data lives in a command, not migrations**: `python manage.py seed_demo` populates Lala/Lele/Lili/Lolo/Lulu and their collections. Idempotent (`update_or_create`). Fresh DBs start empty; run the command explicitly (also on Heroku: `heroku run --app <app> "python manage.py seed_demo"` — quote the inner command, otherwise the Heroku CLI intercepts inner flags like `--lang`/`--reset` as its own). Supports multiple languages via `--lang=en|es` and `--reset` to wipe demos before re-seeding; text content lives in `core/management/commands/seed_data/{lang}.py`. Don't add new demo data to migrations — edit the relevant `seed_data/*.py` and re-run. To add a new language, copy `en.py` → `{lang}.py`, translate text fields (respecting model max_length), add the code to `SUPPORTED_LANGS` in `seed_demo.py`.

## Project Documentation

For complete information about OIUEEI — project structure, tech stack, API endpoints, development setup, environment variables, security measures, and roadmap — see [`README.md`](README.md).

## Detailed Models Documentation

For complete field-by-field documentation, business rules, methods, and reverse relations for each model, see [`core/models/CLAUDE.md`](core/models/CLAUDE.md).

## Detailed Views Documentation

For endpoint definitions, permissions, request/response formats, and business logic for each Django view, see [`core/views/CLAUDE.md`](core/views/CLAUDE.md).

## Detailed Serializers Documentation

For serializer patterns (security fields, prefetch-aware computed fields, Cloudinary URLs), naming conventions, and field-by-field documentation for each serializer, see [`core/serializers/CLAUDE.md`](core/serializers/CLAUDE.md).

## Detailed Services Documentation

For booking business logic (atomic transactions, row-level locking) and centralised email service (XSS prevention, dual format, action links), see [`core/services/CLAUDE.md`](core/services/CLAUDE.md).

## Frontend Documentation

For React routes, pages, tech stack, Vite configuration, and authentication flow, see [`frontend/CLAUDE.md`](frontend/CLAUDE.md).

## Design Guidelines

When designing or reviewing any frontend view, component, or copy, consult [`DESIGN.md`](DESIGN.md) and apply all nine principles. Use the checklist at the end of that document before considering any view complete.
