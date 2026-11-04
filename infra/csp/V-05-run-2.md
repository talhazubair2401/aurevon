# V-05 run 2: CSP baseline against the M3 production builds

Date: 4 November 2026 · Builds: Next.js 16.4.5 production, M3 storefront shell (`/en`, `/ur`) and staff app
Policy: the unchanged MTS v2.1 §12 baselines in this folder, report-only
Method: `e2e/tests/csp.spec.ts` in CI (now covering `/en`, `/ur`, `/staff/`), cross-checked locally

| Page                        | Violations | Directive                  | Cause                                                            |
| --------------------------- | ---------- | -------------------------- | ---------------------------------------------------------------- |
| `/en`                       | 3          | `script-src-elem` (inline) | Next.js App Router bootstrap and React Server Components payload |
| `/ur`                       | 3          | `script-src-elem` (inline) | Same                                                             |
| `/en/<unknown>` (not-found) | 3          | `script-src-elem` (inline) | Same                                                             |

No violations from the M3 additions: self-hosted Inter, Playfair Display, Noto Nastaliq Urdu and Noto Naskh Arabic
(`font-src 'self'`), CSS Modules, inline SVG icons, the `<dialog>` menu or next-intl. Nothing needed loosening.

Unchanged conclusion for D-08 (due before M4): only the framework's inline scripts remain, and they need either a
per-request nonce (pages become dynamic) or per-page build-time hashes (custom work, static pages kept).
M3 keeps `/en` and `/ur` statically generated, so either option is still open. Policy stays report-only.
