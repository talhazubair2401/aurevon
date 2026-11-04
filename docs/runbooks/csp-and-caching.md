# Runbook: Content Security Policy and caching

Decision 0005 (D-08). Applies to every environment and to whichever CDN P-10 selects.

## The rule

An HTML response carries a nonce that is valid for that one response. If any cache stored it, every later
visitor would receive the same nonce, and an attacker who learns it could run scripts. Therefore:

| Response | Cache-Control | May a CDN or proxy cache it? |
| --- | --- | --- |
| Storefront and staff pages, RSC payloads, redirects | `private, no-store, max-age=0` | **Never** |
| `/api/v1/*` | `no-store` | Never |
| `/_next/static/*` and `/staff/_next/static/*` (content-hashed JS, CSS, fonts) | `public, max-age=31536000, immutable` | Yes, long-term |
| `/media/*`, `/3d/draco/<version>/*` (from M5/M6) | Long-term, versioned paths | Yes |

## Where it is enforced

1. **Apps:** each Next.js `proxy.ts` sets the CSP and the page Cache-Control.
2. **Reverse proxy** (`infra/proxy/Caddyfile`): overrides Cache-Control to `private, no-store, max-age=0` on
   every response except the static asset paths; never changes the apps' CSP; adds a strict script-free fallback
   CSP when a response has none.
3. **CDN (when chosen, P-10):** must
   - honour origin `Cache-Control` and `private`/`no-store` (no "cache everything" or edge HTML caching rules);
   - not strip or rewrite `Content-Security-Policy`, `Reporting-Endpoints` or `Cache-Control`;
   - not inject scripts (analytics, "rocket loader", bot challenges, email obfuscation): they would be blocked;
   - cache only the static asset paths above.

## Verifying an environment

CI (`e2e/tests/csp.spec.ts`) checks all of this through the proxy on every push. Before the first staging and
production release, and after any CDN configuration change, run the same suite against the real hostname:

```bash
E2E_BASE_URL=https://<host> pnpm --filter @aurevon/e2e exec playwright test tests/csp.spec.ts
```

and confirm through the CDN that two requests to the same page return different nonces and a cache status of
MISS/BYPASS/DYNAMIC (the header name varies by CDN, e.g. `cf-cache-status`, `x-cache`).

## When a violation is reported

Reports arrive at `POST /api/v1/csp-reports` and are logged as `csp_violation` (logger `aurevon.csp`). Find the
cause and fix it; never add `'unsafe-inline'`, `'unsafe-eval'` or a broad host allowance to make a report go
away (A-26). A sudden spike usually means a browser extension, an injected CDN feature or an attack.

## Refresh on publish (M4)

CMS reads in the storefront are cached for at most a minute and refreshed as soon as staff publish:

- The API worker calls `POST <STOREFRONT_INTERNAL_URL>/internal/revalidate` with `Authorization: Bearer
  <STOREFRONT_REVALIDATE_SECRET>`; the storefront drops its cached `cms` data (`revalidateTag`, `expire: 0`).
- `/internal/` must **never** be routed publicly by the CDN or proxy (the local Caddyfile returns 404). Use the
  same long random secret (at least 16 characters) on the API, worker and storefront; rotate it on all three.
- If the call fails, the worker retries with back-off; pages still refresh within a minute on their own.
- `/sitemap.xml` and `/robots.txt` are generated per request. `SITE_INDEXABLE=true` only in production; every
  other environment tells search engines not to index it.
