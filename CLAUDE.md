# OIUEEI - Development Guide

## Project Conventions

- **Single Django app**: All code lives in `core/`
- **Settings**: Split into `base.py`, `development.py`, `production.py` under `config/settings/`
- **Code style**: black (100-char lines), isort (black profile), flake8
- **Test structure**: `core/tests/unit/`, `core/tests/integration/`, `core/tests/scenarios/`
- **Coverage minimum**: 80% enforced by CI
- **All PKs**: 6-character alphanumeric codes generated via `secrets.choice()` (not auto-increment)
- **Emails**: All user content escaped via `django.utils.html.escape()`

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
