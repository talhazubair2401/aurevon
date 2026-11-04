# D-08 proposal — Content Security Policy strategy — PENDING approval (presented 4 Nov 2026)

Blueprint: MTS v2.1 §3, §12 (A-26), §17 (V-05). Evidence: V-05 runs 1 and 2. M4 does not start until approved.

## Recommendation: per-request nonce with `'strict-dynamic'`, for both apps

| Topic | Proposal |
| --- | --- |
| Strategy | A fresh random nonce (128-bit) on every HTML response; `script-src 'self' 'nonce-…' 'strict-dynamic'` |
| Inline scripts | Next.js reads the nonce from the request's CSP header and stamps it on its own bootstrap and payload scripts and bundles. We add no inline scripts of our own; JSON-LD product data is a data block, not executed |
| Where it is set | `proxy.ts` in each Next.js app generates the nonce and sends the enforcing header. The Caddy report-only header is removed |
| Never in production | `'unsafe-inline'` for scripts, `'unsafe-eval'`. Development keeps its own looser policy |
| 3D (M6) | Add `'wasm-unsafe-eval'` and `worker-src 'self' blob:` only when the viewer lands, proven by the V-05 run with 3D |
| Reporting | Violations reported to a rate-limited Django endpoint, logged, alert on spikes (section 14) |

## Why not hashes

- Next.js has no built-in hash support; the inline payload changes per page and per build, so it needs custom build tooling and per-path headers.
- Hashes only work for static pages. Shop All, search and product detail are server-rendered per request (MTS §3), so they would need nonces anyway: two mechanisms instead of one.
- Fragile tooling tends to end in loosening the policy, which A-26 forbids.
- Next.js's experimental SRI covers external files only, not inline scripts, and doesn't run on Turbopack.

## Cost: what changes

- **Pages:** homepage, collections and content pages render per request instead of being static (MTS §3 row 1, PROPOSED, changes). The highest-traffic pages, Shop All and product detail, were already dynamic.
- **Freshness rule unchanged:** CMS reads use the Next.js data cache, invalidated by tag when staff publish ("rebuilt on publish" becomes "cache refreshed on publish").
- **Caching:** HTML is never cached at the CDN (a cached nonce is a reusable key). Static assets, fonts, images, 3D models and Draco files stay long-term cached; they are most of the bytes.
- **Speed:** a small per-request render cost on a few pages; checked with load tests (k6) and Lighthouse in M14 against P-18 budgets.

## Tests (production builds, every CI run)

1. Enforcing policy, zero violations on every page type, both locales, desktop and phone.
2. Every Next.js script carries the nonce; two requests get different nonces.
3. HTML responses are `private`/`no-store`; static assets keep long-term caching.
4. An injected inline script without the nonce is blocked (proves enforcement, not just absence of errors).
5. Re-run at M5, M6 (with 3D) and M14; on staging, report-only for a period before enforcing in production (P-10).
