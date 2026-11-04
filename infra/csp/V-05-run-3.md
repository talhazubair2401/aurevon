# V-05 run 3: enforcing nonce policy (D-08) against the production builds

Date: 4 November 2026 · Builds: Next.js 16.4.5 production, storefront and staff app, behind the routing proxy
Policy: `packages/csp`, enforcing, per-request nonce with `'strict-dynamic'` (decision 0005)
Method: `e2e/tests/csp.spec.ts`, desktop and phone, in CI and locally

| Check                                                                                                                              | Result                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Pages: `/en`, `/ur`, both not-found pages, `/staff`, `/staff/sign-in`, `/staff/forgot-password`, `/staff/enroll`, `/staff/recover` | Enforcing policy present, no report-only header, **zero violations**      |
| Every `<script>` in the server HTML carries the response's nonce                                                                   | Pass                                                                      |
| Nonce rotation: 5 requests each to `/en` and `/staff/sign-in`                                                                      | 5 different nonces each                                                   |
| Injected markup (reflected-XSS simulation): inline script, external script, `onerror` handler, `javascript:` link                  | All blocked, violations reported                                          |
| `eval` from a script that carries the nonce                                                                                        | Blocked (no `'unsafe-eval'`)                                              |
| Pages, redirects and RSC payloads                                                                                                  | `private, no-store, max-age=0`; never `public`, `s-maxage` or `immutable` |
| `/_next/static` JS and fonts, both apps                                                                                            | `public, max-age=31536000, immutable`                                     |
| Response that bypasses the apps (`/no-such-file.txt`)                                                                              | Strict script-free fallback policy, not cacheable                         |
| Pages still hydrate and navigate client-side                                                                                       | Pass                                                                      |

Found and fixed while testing: with a `basePath`, the staff app's request proxy did not run on the bare `/staff`
path, so that page had no nonce. The proxy's fallback policy blocked its scripts (failing closed, as designed).
The matcher now lists `/` explicitly and `/staff` is in the tested pages.

Next runs: M5, M6 (with 3D), M14, and against staging/production through the CDN (runbook `csp-and-caching.md`).
