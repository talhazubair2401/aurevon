# Deploying AureVon

Status: **ready for staging**; production deployment waits on P-10 (hosting), P-06 (payment provider), P-08 (email/SMS
providers) and the other open decisions in `docs/decisions/README.md`.

## What runs

| Service | Image / command | Notes |
|---|---|---|
| api | `infra/docker/api.Dockerfile` → gunicorn `config.wsgi` | Django/DRF, `/api/v1/` behind the proxy |
| worker | same image → `celery -A config worker` | email, SMS, refunds, cache refresh |
| scheduler | same image → `celery -A config beat` | payment checks, reservation expiry, refund retries, owner recovery release, bag reminders |
| migrate | same image → `python manage.py migrate` | one-shot, before api/worker start |
| storefront | `infra/docker/web.Dockerfile` (storefront) | Next.js, nonce CSP (decision 0005) |
| staff | `infra/docker/web.Dockerfile` (staff) | Next.js under `/staff` |
| proxy | Caddy (`infra/proxy`) | TLS, routing, fallback CSP, security headers |
| postgres 17, redis 7.4 | managed services in production | daily backups + PITR at the provider (P-17) |

The local `infra/compose.yaml` is the reference topology; staging/production use the same images with managed
PostgreSQL, Redis, object storage and SMTP.

## Release steps

1. CI green on `main` (backend, frontend, API contract, full-stack e2e + CSP).
2. Build and tag images from the commit (`aurevon-backend`, `aurevon-web`).
3. **Back up the database** (`scripts/ops/backup.sh`) and confirm the checksum file exists.
4. Run `migrate` once with the new image. Migrations are additive in every release so far; a migration that
   drops or rewrites data must be called out in the release notes and rehearsed on a restored copy first.
5. Roll api, worker, scheduler, storefront and staff. Only one scheduler may run.
6. Smoke test: `/health/ready` (internal), storefront home, a product page, add to bag, quote, staff sign-in,
   Orders list. Check the error rate and CSP reports for 15 minutes.
7. Rollback: redeploy the previous images. If a migration must be undone, restore the pre-release backup next to
   the live database (`scripts/ops/restore.sh`) and switch over; never restore over the live database.

## Environment

Every variable is listed with its purpose in `.env.example`. Production refuses to start without
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `MFA_ENCRYPTION_KEY`, and refuses `PAYMENTS_SANDBOX_ENABLED`.
Secrets come from the host's secret store, never from the repository or the frontend bundles (only `NEXT_PUBLIC_*`
values reach browsers, and none are secrets).

## After the first production deploy

- `python manage.py create_owner` (the first Owner; see `docs/runbooks/staff-accounts.md`), then a second Owner.
- Enter real delivery zones and rates (Settings › Delivery), the tax rule (Settings › Tax) once P-11 is
  decided, store settings (return window, refund threshold, COD limits), and policy pages.
- Never run `seed_demo_catalog` (it refuses unless `ALLOW_DEMO_DATA=true`).
