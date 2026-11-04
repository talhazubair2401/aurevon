# AureVon M0 — Decision Lock: Completion Report

Date: 4 November 2026 · Blueprint: MTS v2.1 (approved 4 November 2026)

## Result
M0 is complete, pending your answers to the five items under "Decisions to lock". No application code has been written.

## Confirmed
- MTS v2.1 is the authoritative blueprint, marked APPROVED in the document (and in docs/mts, plus the project copy). v1.0 and v2.0 are preserved unchanged.
- Approved design and brand decisions (A-01 to A-04, A-12) carry into development unchanged.
- P-09: technology approved; V-01 to V-03 remain outstanding and gate only the public 3D switch-on.

## Decisions to lock before M1
| # | Item | Recommendation | Blocks |
|---|---|---|---|
| 1 | P-01 Frontend framework and tooling | Approve: Next.js + TypeScript (strict), pnpm workspaces monorepo, React/R3F/Three.js bundled | All of M1 |
| 2 | P-04 Local database and migrations | Approve: PostgreSQL in Docker Compose at production's major version; Django migrations, expand-then-contract | M1 backend skeleton |
| 3 | Code repository | New, genuine blocker: a private GitHub repository (CI uses GitHub Actions per MTS §13). Create it (e.g. `aurevon`) and I'll attach it, or tell me to keep code in the local folder until later | M1 CI slice; everything else can start locally |
| 4 | P-20 Launch scope | Approve MTS §7 priorities (launch-critical / launch / post-launch) as the launch scope baseline | Milestone ordering only; not M1 code |
| 5 | P-10 Hosting | Don't decide now. M1 builds and tests locally and in CI; only the staging-deploy step waits for P-10 | M1 staging step only |

## Not blocking M1 (needed later)
P-05 roles and staff 2FA, D-12 Owner recovery, D-09 staff network restriction (before M2); P-19 final palette and design references (before M3); D-08 CSP strategy (before M4, informed by V-05 in M1).

## Prerequisites
- For you to run AureVon locally: Git, Docker Desktop (with WSL 2 on Windows), Node.js LTS, pnpm, Python 3.12+. Not needed for me to build: I develop and test in my workspace and in CI.
- Exact versions (Django 5.2 LTS, Python, Node, Next.js, React 19, R3F 9, Three.js, PostgreSQL) are pinned at the start of M1 from current stable releases.

## M1 plan (for approval after M0)
Goal: a working, tested foundation; no business features.
1. Repository skeleton: monorepo layout (MTS §15), pnpm workspace, shared lint/format/type configs, `.env.example`, README.
2. Backend skeleton: Django + DRF, split settings, `/api/v1/` routing, health endpoints, OpenAPI schema, JSON logging with request IDs, Celery wiring, pytest on PostgreSQL, Ruff, mypy, import-linter.
3. Frontend skeletons: storefront at `/` and staff app at `/staff/` (basePath), TypeScript strict, AureVon design tokens from A-03, typed API client generated from the OpenAPI schema.
4. Local stack: Docker Compose with PostgreSQL, Redis, MinIO, Mailpit and a routing proxy serving `/`, `/staff/` and `/api/v1/`; Dockerfiles for all services.
5. CI: GitHub Actions running the eight checks in MTS §13.
6. V-05 first run: CSP report-only against the production builds of both apps; results recorded as input to D-08.

Done when: one command starts the stack with all three routes answering; health checks pass; CI is green; the M1 report lists files, setup steps, tests run and known limitations. Staging deployment follows once P-10 is decided.
