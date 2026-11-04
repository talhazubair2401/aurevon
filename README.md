# AureVon

Premium single-brand fashion e-commerce with interactive 3D product presentation. Pakistan first (PKR), global-ready.

The authoritative blueprint is **MTS v2.1** ([`docs/mts/`](docs/mts/)). Decisions are recorded in
[`docs/decisions/`](docs/decisions/) and each milestone's report in [`docs/milestones/`](docs/milestones/).

## Repository layout

| Path                     | What                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------- |
| `apps/storefront`        | Next.js storefront, served at `/`                                                     |
| `apps/staff`             | Next.js staff dashboard, served at `/staff/`                                          |
| `backend`                | Django + Django REST Framework API, served at `/api/v1/`; Celery worker and scheduler |
| `packages/design-tokens` | Approved brand tokens (A-03) as CSS custom properties and TypeScript                  |
| `packages/api-client`    | Typed API client generated from the OpenAPI schema; never edited by hand              |
| `packages/config`        | Shared TypeScript settings                                                            |
| `e2e`                    | Playwright tests against the running stack, including the CSP report (V-05)           |
| `infra`                  | Dockerfiles, Docker Compose, routing proxy, CSP policies                              |
| `prototypes`             | P-09 3D viewer prototypes v1 and v2 (reference only, not built)                       |
| `docs`                   | Specifications, decisions, milestone reports, runbooks                                |

## Run everything locally (Docker)

Prerequisites: Git and Docker Desktop (with WSL 2 on Windows).

```bash
docker compose -f infra/compose.yaml up --build
```

Then open:

- http://localhost:8080/ — storefront
- http://localhost:8080/staff/ — staff dashboard
- http://localhost:8080/api/v1/ — API
- http://localhost:8025/ — Mailpit (all outgoing email lands here locally)

Create the first Owner (the set-up link arrives in Mailpit):

```bash
docker compose -f infra/compose.yaml exec api python manage.py create_owner --email you@example.com --name "Your Name"
```

Staff accounts, recovery and break-glass: `docs/runbooks/staff-accounts.md`.

Stop with `Ctrl+C`; add `-v` to `docker compose ... down -v` to wipe the local database. If you ran the M1 stack
before, wipe it once (`down -v`): M2 introduces the custom account model.

## Develop without Docker

Prerequisites: Node.js 22 LTS, pnpm 10 (`corepack enable`), Python 3.13, PostgreSQL 17 and Redis running locally.

```bash
pnpm install
python -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements-dev.txt
cp .env.example .env   # adjust DATABASE_URL / REDIS_URL, then export the variables

cd backend && python manage.py migrate && python manage.py runserver 8000   # API
pnpm --filter @aurevon/storefront dev                                        # http://localhost:3000
pnpm --filter @aurevon/staff dev                                             # http://localhost:3001/staff
```

## Checks (the same ones CI runs)

```bash
# Backend (from backend/, with DJANGO_SETTINGS_MODULE=config.settings.test and PostgreSQL + Redis running)
ruff format --check . && ruff check . && mypy . && lint-imports
python manage.py makemigrations --check --dry-run && pytest
bandit -q -c pyproject.toml -r . && pip-audit -r requirements.txt --strict

# Frontend (from the repository root)
pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build

# API contract: regenerate the schema and typed client; CI fails if they differ from what is committed
pnpm gen:api

# End-to-end, against a running stack on http://localhost:8080
pnpm test:e2e
```

## Working rules

Follow MTS v2.1. One milestone at a time; each ends with a report and needs product-owner approval before the
next starts. Approved decisions change only with a recorded reason and approval.
