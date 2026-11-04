# V-05 run 1: CSP baseline against the M1 production builds

Date: 4 November 2026 · Builds: Next.js 16.4.5 production (`next build` + `next start`) behind the M1 Caddy proxy
Policy: the MTS v2.1 §12 baselines in this folder, sent as `Content-Security-Policy-Report-Only`
Method: `e2e/tests/csp.spec.ts` (Playwright, desktop and phone profiles), listening for `securitypolicyviolation`

| Page           | Violations | Directive                  | Cause                                                                                                                       |
| -------------- | ---------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `/` storefront | 3          | `script-src-elem` (inline) | Next.js App Router inline scripts: the bootstrap script and the React Server Components payload (`self.__next_f.push(...)`) |
| `/staff` staff | 6          | `script-src-elem` (inline) | Same cause                                                                                                                  |

No violations for styles, fonts (self-hosted via `next/font/local`), images, connections or workers.

## What this means for D-08 (decide before M4)

- The inline scripts carry per-page data, so their content (and any hash) changes with every page and build.
- **Nonce option:** Next.js can stamp a per-request nonce on these scripts through middleware, but pages then
  render dynamically, giving up static generation for the pages in MTS §3 that were planned as static.
- **Hash option:** keeps static pages, but needs hashes computed per page at build time and delivered with each
  page (headers or a generated manifest); Next.js has no built-in support, so it is custom work.
- Nothing else in the baseline needed loosening. 3D-specific directives (`wasm-unsafe-eval`, `worker-src blob:`)
  are exercised in the M6 run, when the viewer exists.

Policy stays report-only until a run shows zero violations.
