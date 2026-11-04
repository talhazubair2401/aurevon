# V-05 run 4: M4 collection, content and policy pages

Date: 4 November 2026 · Builds: Next.js 16.4.5 production, storefront and staff app, behind the routing proxy
Policy: `packages/csp`, enforcing, per-request nonce with `'strict-dynamic'` (decision 0005), unchanged
Method: `e2e/tests/csp.spec.ts`, desktop and phone

| Check                                                                                                             | Result                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Pages from run 3, plus `/en/collections`, `/ur/collections/heritage-edit`, `/en/pages/about`, `/ur/pages/returns` | Enforcing policy, **zero violations**, desktop and phone                                                      |
| Structured data (`application/ld+json` breadcrumbs, Organization, WebSite)                                        | Carries the response's nonce; `<` escaped; no violations                                                      |
| Staff content and SEO screens (signed in, staff journey)                                                          | No console or policy errors                                                                                   |
| `/sitemap.xml`, `/robots.txt`                                                                                     | Served by the storefront without a page policy; the proxy adds the strict script-free fallback; not cacheable |
| `/internal/revalidate` (storefront cache refresh)                                                                 | Not routed by the proxy (404); requires the shared secret when called internally                              |

No policy change was needed: the new pages add no inline scripts or styles of their own (collection tones are
SVG fills, as on the homepage).

Next runs: M5, M6 (with 3D), M14, and against staging/production through the CDN.
