# 0005 — D-08: Content Security Policy with a per-request nonce

Date: 4 November 2026 · Decided by: Talha (product owner) · Blueprint: MTS v2.1 §3, §12 (A-26), §17 (V-05)
Status: **APPROVED**, implemented and verified (V-05 run 3)

## Decision

| Topic | Decision |
| --- | --- |
| Strategy | A fresh 128-bit nonce on every HTML response of the storefront and the staff app; `script-src 'self' 'nonce-…' 'strict-dynamic'`; enforcing, not report-only |
| Inline scripts | Next.js reads the nonce from the request's CSP header and stamps it on its own scripts; AureVon adds no inline scripts of its own |
| Never in production | `'unsafe-inline'` for scripts, `'unsafe-eval'`, third-party script origins. Development gets its own policy (`'unsafe-eval'`, `ws:`) |
| Rendering | All storefront and staff pages render per request. Accepted trade-off: MTS §3 row 1 (homepage, collections, content pages "static, rebuilt on publish") becomes "rendered per request, CMS data cached and refreshed on publish" |
| 3D (M6) | `'wasm-unsafe-eval'` and `worker-src 'self' blob:` are added only when the viewer exists, proven by the V-05 run with 3D |
| Reporting | Violations reported to `POST /api/v1/csp-reports` (rate-limited, size-capped, logged without query strings) |

**Additional requirement (product owner):** no reverse proxy or CDN may ever publicly cache an HTML response
that contains a nonce; static assets keep long-term caching. Implemented in the apps and the proxy, tested in CI,
and written as rules for the production CDN in `docs/runbooks/csp-and-caching.md`.

## Why a nonce rather than hashes

- Next.js supports nonces directly; hashes would need custom build tooling because the inline payload changes per
  page and per build.
- Hashes work only for static pages, while Shop All, search and product detail are rendered per request anyway.
- Fragile tooling invites loosening the policy, which A-26 forbids.
- Next.js's experimental SRI covers external files only and doesn't run on Turbopack.

## Implementation

- `packages/csp`: builds both policies and the nonce; unit-tested (no unsafe keywords, no third-party origins,
  nonce format validated before it reaches a header).
- `apps/storefront/proxy.ts` and `apps/staff/proxy.ts`: nonce, enforcing CSP, `Reporting-Endpoints`,
  `Cache-Control: private, no-store, max-age=0` on every page response.
- `infra/proxy/Caddyfile`: forces the same Cache-Control on everything except `/_next/static/*`, never overrides
  the apps' policy, and adds a strict script-free fallback policy to any response that arrives without one.
- `backend/common/csp_reports.py`: the report endpoint.

## Consequences

- MTS v2.1 is not edited; the register in `docs/decisions/README.md` records D-08 as approved. The next MTS
  revision moves it into §1 as A-30.
- M4 may start: the CMS-driven pages are built as per-request pages with tag-invalidated data caching.
