# 0001 — M0 decision lock

Date: 4 November 2026 · Decided by: Talha (product owner) · Blueprint: MTS v2.1

| ID | Decision | Status |
| --- | --- | --- |
| P-01 | Next.js + TypeScript in a pnpm monorepo; React, React Three Fiber and Three.js bundled (no CDN loading) | APPROVED |
| P-04 | PostgreSQL in Docker Compose for local development, same major version as production; Django migrations, expand-then-contract | APPROVED |
| Repository | Private GitHub repository `aurevon`, used for version control and GitHub Actions | APPROVED |
| P-20 | MTS v2.1 §7 launch priorities are the launch-scope baseline | APPROVED |
| P-10 | Hosting deferred until the staging deployment phase | DEFERRED |

Consequences: M1 builds and verifies everything locally and in CI; the staging deployment step of M1 waits for P-10.
