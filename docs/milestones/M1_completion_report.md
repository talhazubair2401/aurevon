# AureVon M1 Completion Report: Technical Foundation

**Date:** 4 November 2026
**Baseline:** MTS v2.1 and the M0 completion report
**Repository:** `talhazubair2401/aurevon` (private), branch `main`
**Commits:** `36ad43c` (M1 foundation) and the `packaging` pin fix
**Status:** All M1 exit criteria are met. CI is green on `main`. This report is awaiting your approval before M2 starts.

## 1. Decisions applied (approved, not reopened)

| ID | Applied as |
| --- | --- |
| P-01 | Next.js 16.4.5 + TypeScript 5.9.3 (strict), React 19.3, pnpm 10.28 monorepo. R3F and Three.js are reserved for the M6 viewer and are not installed yet, because nothing uses them before M6. |
| P-04 | PostgreSQL 17 in Docker Compose and in CI, matching the production major version. |
| Repository | Private GitHub repository `aurevon`, with GitHub Actions as CI. |
| P-20 | MTS §7 launch priorities are the backlog baseline. Nothing in M1 depends on them. |
| P-10 | Deferred. No hosting or staging work has been done. |

Exact versions and the reason for each pin are in `docs/decisions/0002-m1-version-pins.md`.

## 2. What was built

| Area | Functionality |
| --- | --- |
| **API (`backend/`)** | <ul><li>Django 5.2 LTS + DRF under `/api/v1/`.</li><li>Split settings (base, local, test, staging, production), all configured from environment variables.</li><li>Every endpoint denies access unless it explicitly allows it.</li><li>Errors use RFC 9457 problem details, including unknown API paths.</li><li>Each request carries an `X-Request-ID`, which is written into JSON logs.</li><li>Health checks: `health/live` and `health/ready`. The ready check covers the database and Redis, and neither is routed publicly.</li><li>OpenAPI schema, public only in local development.</li><li>Celery worker and scheduler.</li><li>Argon2 password hashing.</li><li>Production security settings: HSTS, secure cookies, SSL redirect.</li><li>Django admin is not installed (R-06).</li></ul> |
| **Storefront (`apps/storefront`)** | <ul><li>Served at `/`.</li><li>A-03 brand tokens and self-hosted fonts.</li><li>Placeholder home page showing only the wordmark. Real storefront pages start in M3, so nothing here poses as working functionality.</li></ul> |
| **Staff app (`apps/staff`)** | <ul><li>Served at `/staff/` (A-27).</li><li>Sends `no-store`, `noindex` and `Referrer-Policy: same-origin`.</li><li>The page says sign-in arrives in M2.</li></ul> |
| **Shared packages** | <ul><li>`design-tokens`: A-03 colours, fonts and CSS variables.</li><li>`api-client`: typed client generated from the OpenAPI schema, with problem-details errors.</li><li>`config`: shared TypeScript settings.</li></ul> |
| **Local stack (`infra/compose.yaml`)** | <ul><li>Services: PostgreSQL 17, Redis 7.4, Mailpit, a one-shot migration, the API, the worker, the scheduler, the storefront and the staff app.</li><li>A Caddy proxy on `:8080` reproduces the production routes: `/`, `/staff/` and `/api/v1/`.</li><li>One command starts it all: `docker compose -f infra/compose.yaml up --build`.</li></ul> |
| **CI (`.github/workflows/ci.yml`)** | Four jobs, listed in section 3. |
| **CSP (`infra/csp/`)** | MTS §12 baselines, served report-only by the proxy, plus the V-05 run 1 record. |

## 3. Tests and checks

**CI run on `main`: all four jobs passed.**

| Job | Checks | Result |
| --- | --- | --- |
| **Backend** | ruff format and lint, mypy (strict), import boundaries (2 contracts), migrations check, pytest on PostgreSQL 17, deploy check (`--fail-level WARNING`), bandit, pip-audit | 23 tests passed; no issues |
| **Frontend** | Prettier, ESLint, TypeScript, Vitest, production builds of both apps, `pnpm audit` | 10 tests passed; no vulnerabilities |
| **API contract** | Regenerates the schema and the typed client, then fails if either differs from what is committed | In sync |
| **Full stack** | Docker images built, all services healthy, Playwright on desktop and phone through the proxy, Celery worker ping | 16/16 passed; worker answered `pong` |

**The end-to-end tests cover:**
- The storefront page.
- The staff app's headers.
- The API: JSON responses, `no-store` caching and request IDs.
- Problem-details 404s.
- `/health/*` and `/admin/` are not reachable through the proxy.

**Found and fixed by CI:**
- The first Docker build showed that the scheduler crashed on start-up. Kombu needs the `packaging` library but does not declare it.
- It is now pinned in `requirements.txt` and was verified in a clean environment that has only the runtime dependencies.

## 4. V-05 run 1 (CSP)

- **Result:** the only violations come from Next.js's own inline scripts:
  - storefront: 3 violations
  - staff: 6 violations
- **No violations for:** styles, fonts, images, connections or workers.
- **Status:** the policy stays report-only.
- **Feeds D-08:** a nonce or a hash for those inline scripts. This decision is due before M4.
- **Details:** `infra/csp/V-05-run-1.md`.

## 5. Deviations and limitations

1. **MinIO is not in the local stack yet.** It was in the M1 plan. Nothing uses object storage until media uploads (M5), so it will be added then, together with its tests.
2. **Docker could not run in my workspace** because Docker Hub is blocked there. Docker is verified only in CI. Locally, I ran the same services as processes behind Caddy, and those checks passed.
3. **`/staff/` redirects to `/staff` (308).** This is how Next.js handles its base path, and the route still works. It is not a defect, but the canonical URL is `/staff`.
4. **CI warnings, not failures:**
   - Some actions still target Node 20; to be updated when new major versions ship.
   - `ubuntu-latest` is moving to Ubuntu 26.
5. **Staging is not set up.** It waits for P-10.
6. **No real-device testing was done.** Phone coverage comes from the Pixel 7 emulation in Playwright only.

## 6. Proposed for M2 (not started)

**M2 Data and identity (MTS §11):**
- The core schema.
- Separate customer and staff sign-in and sessions (A-22, R-05).
- Staff roles and permissions.
- Suspension, revocation and recovery.
- The audit log.

**Decisions needed before or during M2:**
- **P-05:** roles, two-factor, session lengths.
- **D-12:** Owner recovery.
- **D-09:** only if staff routes go on staging.

Nothing is started until you approve this report.
