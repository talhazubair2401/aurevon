# AureVon Master Technical Specification v2.1

Nov 4, 2026 · @Talha

## Document control

**MTS v2.1 is v2.0 plus seven technical corrections that you approved on 4 November 2026 after reviewing v2.0. Every v2.0 requirement the corrections don't touch is carried over unchanged.** Approved by the product owner on 4 November 2026; this is the authoritative implementation blueprint.

| Item | Value |
| --- | --- |
| Document | AureVon Master Technical Specification (MTS) |
| Version | 2.1 (supersedes v2.0; v2.0 and v1.0 are kept unchanged) |
| Status | APPROVED by the product owner, 4 November 2026 |
| Project | Premium single-brand fashion e-commerce with interactive 3D product presentation |
| Initial market | Pakistan (PKR); global-ready architecture |
| Product owner | Talha: approves decisions, designs and acceptance |
| Implementation | Claude, following this MTS and milestone briefs |
| Architecture review | ChatGPT: specification upkeep, decision tracking, code and design review |
| Visual assets | Flow: generated assets, approved before use |
| Research support | Gemini: independent comparisons when requested |

### Status labels

Every decision in this document carries one of these labels.

| Label | Meaning | Rule for implementation |
| --- | --- | --- |
| **APPROVED** | Explicitly accepted by the product owner | Must be preserved; changes need a recorded reason and approval |
| **PROPOSED** | A recommended implementation detail | May be built as the default, but must be confirmed at the milestone named; it can still change |
| **OUTSTANDING** | A validation or test not yet done | Tracked in section 17; blocks only what it names |
| **PENDING** | A decision not yet made | Tracked in section 18; don't invent a final answer |

In v2.1, **APPROVED (C-n)** marks a requirement from approved correction n. You approved *what* must be defined; the *how* written to meet it is labelled PROPOSED, unless your correction stated it exactly (for example, the cash-on-delivery sequence and the three route prefixes).

### Earlier changes (v1.0 to v2.0, unchanged)

- **Approved since v1.0:** Django and Django REST Framework (P-02); PostgreSQL (P-03); Three.js with React Three Fiber, Draco support required (P-09 technology); production bundling of React, R3F and Three.js; the mobile colour-swatch layout.
- **Modules:** consolidated from 21 to 18. v1.0's Module 16 is now sections 2, 5 and 8; Module 17 is section 16; Module 21 is built into sections 3, 6 and 14. None of their capabilities were removed.
- **P-09:** the v2 viewer is the reference implementation; its physical-device and genuine-garment tests remain OUTSTANDING and don't block other modules.

## Change log: v2.0 to v2.1

**v2.1 incorporates seven approved corrections (C-1 to C-7). It adds one validation (V-05), six open decisions (D-07 to D-12) and one revised proposal (R-06). Nothing approved in v2.0 was removed or weakened.**

| # | Approved correction | What v2.1 adds | Sections |
| --- | --- | --- | --- |
| C-1 | Staff authentication and authorization | Separate customer and staff identities, sign-in endpoints, session cookies and session stores; customer sessions can never reach staff APIs; staff suspension with immediate session revocation; secure staff recovery with no email-only reset; Owner is an AureVon role, independent of Django superuser | 5, 6, 8, 9, 12 |
| C-2 | Payments and refunds | Payment and refund state machines; duplicate, delayed and out-of-order callbacks; payments that succeed after the order expired; provider downtime; failed refunds; idempotency for payment and refund operations; a reconciliation guarantee so no successful payment stays marked unpaid | 6, 8, 10, 11, 13 |
| C-3 | Cash on delivery | Delivery status separated from payment remittance; the approved flow COD order → Shipped → Delivered → Remittance pending → Remittance received → Reconciled; accountant reconciliation per order against courier remittance batches | 6, 8, 10, 11 |
| C-4 | Inventory | Restoration on cancellation before dispatch; stock stays unavailable after dispatch until the return is physically received and inspected; damaged returns go to a non-sellable location; reservation expiry checks the provider first; overselling safeguards | 6, 11 |
| C-5 | Content Security Policy | The policy must be validated against the actual production Next.js build, covering framework scripts, nonces or hashes, Three.js, Draco, Meshopt, WebAssembly and assets, without weakening it unnecessarily. Added as validation V-05 | 3, 12, 16, 17 |
| C-6 | Application routing | `/` storefront, `/staff/` staff dashboard, `/api/v1/` Django API, with staff access restrictions at every layer | 2, 3, 8, 12, 14, 15 |
| C-7 | Monitoring and alerts | Alerts for payment failures, duplicate and conflicting callbacks, late payments, failed refunds, overdue remittances and COD reconciliation mismatches | 14 |

### Other changes that follow from the corrections

| Item | Change | Why |
| --- | --- | --- |
| R-06 (proposal) | Revised: Django admin is not used for any business operation and is switched off in production; emergency operations use audited management commands | C-1: Owner must not depend on Django superuser |
| R-05 (proposal) | Extended: two separate session cookies (customer and staff), each honoured only by its own endpoints | C-1 |
| D-06 (decision) | Proposal updated: the reservation expiry must be longer than the payment provider's own session timeout, plus a margin | C-2, C-4 |
| V-05 (new validation) | CSP validated against the production Next.js build at M1, then again at M3, M5 and M6 | C-5 |
| D-07 to D-12 (new decisions) | Late-payment policy, CSP strategy for Next.js, network restriction for staff routes, alert thresholds and owners, COD remittance terms, Owner account recovery | Items the corrections require but that need your decision; none is assumed approved |
| Order model | Order, payment and shipment states are now three separate fields, so delivery and remittance never share one status | C-3 |
| Diagrams | Architecture diagram updated with routes; new payment and cash-on-delivery state diagram; order diagram updated; ER diagram extended | C-2, C-3, C-6 |

Largely unchanged from v2.0: section 4 (Three.js; only a draft-preview note and V-05) and section 15 (folder structure; only the staff route, finance screens, local proxy and CSP folder). Sections 7 and 16 change only to place the corrections in their modules and milestones.

## 1. Decision register

**Of 42 recorded items, 28 are approved (including the seven v2.1 corrections), 9 are proposed for confirmation at a named milestone, and 5 validations are outstanding.** Proposed items are the default that development builds toward; any one of them can change before its milestone without reworking approved items.

### Approved

| ID | Decision | Source |
| --- | --- | --- |
| A-01 | Brand AureVon, tagline "Modern Style. Timeless Confidence.", Modern Heritage Luxury positioning | MTS v1.0 §3.1 |
| A-02 | Single-brand fashion store; Pakistan first, PKR launch currency; global-ready architecture | MTS v1.0 §1 |
| A-03 | Brand tokens: off-white #F9F8F6, charcoal #121212, stone #E5E0DB, deep brown #3B2F2F, champagne gold #C2A676 (gold mainly in 3D); Playfair Display headings with Inter or Satoshi interface text | MTS v1.0 §3.2 (final palette still P-19) |
| A-04 | Approved page designs are authoritative: homepage hero, Shop All, product detail, cart, checkout, login, registration Direction A, account | MTS v1.0 §3.3 |
| A-05 | Modular monolith: one deployable backend with clear module boundaries | MTS v1.0 §6.1 |
| A-06 | Backend: Django with Django REST Framework (REST API) | P-02, approved 4 Nov 2026 |
| A-07 | Database: PostgreSQL (relational) | P-03 engine, approved 4 Nov 2026; provider still pending |
| A-08 | 3D technology: Three.js with React Three Fiber | P-09, approved 4 Nov 2026 |
| A-09 | Draco-compressed GLB support is required | P-09 Phase 2 |
| A-10 | The v2 viewer is the P-09 reference implementation; the v1 prototype stays preserved | P-09 Phase 2 |
| A-11 | React, R3F and Three.js are bundled and self-hosted in production; no multi-CDN module loading | P-09 Phase 2 |
| A-12 | On phones, colour swatches sit directly under the title and price | P-09 Phase 2 |
| A-13 | No 3D file-size, triangle or texture limit is approved until real-device data exists | P-09 Phase 2 |
| A-14 | 3D is isolated: if it fails, product information, cart and checkout keep working; a static image is always available | MTS v1.0 §3.4, §6.3 |
| A-15 | The server is authoritative for price, discount, tax, shipping and stock | MTS v1.0 §6.3 |
| A-16 | Raw card data is never stored; payments use provider-hosted or tokenized flows | MTS v1.0 Module 05 |
| A-17 | Stock is tracked per variant (size × colour), with each sellable variant identified by its SKU | MTS v1.0 Module 02, 14 |
| A-18 | English and Urdu, including right-to-left layout | MTS v1.0 Module 15 |
| A-19 | Hybrid cloud: separately managed app hosting, relational database, object storage and CDN | MTS v1.0 §14 |
| A-20 | Incremental delivery: one approved design and feature slice at a time, tested before the next | MTS v1.0 Module 17 |
| A-21 | 18 business modules (section 7), with v1.0 Modules 16, 17 and 21 folded into document sections | 4 Nov 2026 |
| A-22 | Strict separation of customer and staff authentication; a customer session never grants access to staff APIs; staff suspension, session revocation and secure staff recovery are defined; the Owner role doesn't depend on Django superuser | C-1, 4 Nov 2026 |
| A-23 | Payment and refund state machines; duplicate, delayed and late callbacks handled; idempotent payment and refund operations; no successful provider payment may stay marked unpaid | C-2, 4 Nov 2026 |
| A-24 | Cash on delivery: delivery status is separate from remittance; flow COD order → Shipped → Delivered → Remittance pending → Remittance received → Reconciled; accountant reconciles each order | C-3, 4 Nov 2026 |
| A-25 | Stock restored on cancellation before dispatch; after dispatch, unavailable until the return is received and inspected; damaged returns never return to sellable stock; reservation expiry, delayed callbacks and overselling addressed | C-4, 4 Nov 2026 |
| A-26 | The CSP is validated against the actual production Next.js build and isn't weakened unnecessarily | C-5, 4 Nov 2026 |
| A-27 | Routing: `/` storefront, `/staff/` staff dashboard, `/api/v1/` Django API, with staff access restrictions enforced | C-6, 4 Nov 2026 |
| A-28 | Monitoring and alerts for payment failures, duplicate callbacks and COD reconciliation mismatches | C-7, 4 Nov 2026 |

### Proposed (confirm at the milestone shown)

| ID | Proposal | Confirm by |
| --- | --- | --- |
| R-01 | Next.js (React, TypeScript) for the storefront and staff dashboard, with server rendering for SEO | P-01, before M1 |
| R-02 | One monorepo: Next.js apps and shared packages managed with pnpm workspaces; Django in the same repository | M1 |
| R-03 | Django 5.2 LTS on Python 3.12 or newer; exact versions pinned at M1 | M1 |
| R-04 | Celery workers with Redis for background jobs; Redis also for caching and rate limits | M1 |
| R-05 | Cookie-based sessions on one site with CSRF protection; separate customer and staff session cookies, each honoured only by its own endpoints (extended in v2.1 for A-22) | M2 |
| R-06 | A purpose-built staff dashboard for all business operations; Django admin switched off in production; emergency operations through audited management commands (revised in v2.1 for A-22) | M2 |
| R-07 | PostgreSQL full-text search for the catalogue at launch | M5 |
| R-08 | Cash on delivery offered alongside online payment, through the same payment architecture. A-24 approves how COD works; whether to offer it is confirmed with P-06 | P-06, before M8 |
| R-09 | WCAG 2.2 AA as the accessibility target | M3 |

### Outstanding validations

| ID | Validation | Blocks |
| --- | --- | --- |
| V-01 | P-09 physical-device tests: iPhone Safari, mid-range Android Chrome, low-end Android Chrome | Production release of the 3D viewer only |
| V-02 | P-09 test with a genuine AureVon garment GLB | Production release of the 3D viewer only |
| V-03 | Re-run the v2 validation suite on the production versions of React, R3F and Three.js | M6 |
| V-04 | KTX2/Basis texture evaluation, which may lower GPU memory use | The asset budget decision only |
| V-05 | CSP validated against the production Next.js build (A-26) | Production release; first run at M1 |

## 2. System architecture and application routing

**AureVon is two Next.js web apps in front of one Django API, which owns every business rule and all data. In v2.1, all three are served from one domain under three approved route prefixes: `/` for the storefront, `/staff/` for the staff dashboard and `/api/v1/` for the API (A-27).** The browser never talks to PostgreSQL, Redis or a provider directly, and providers sit behind adapters.

&#91;embedded content: AureVon system architecture · 3 routes, 1 API, 4 data and job services\]

A request flows top to bottom. The CDN sends each path prefix to its application and serves images and 3D models from the edge. Providers call back into Django through signed webhooks.

| Layer | Responsibility | Status |
| --- | --- | --- |
| Next.js storefront | Server-rendered pages for SEO, client interactivity, the 3D viewer | PROPOSED (P-01) |
| Next.js staff dashboard | Catalogue, orders, inventory, finance, support and CMS screens for staff | PROPOSED |
| Django API | All business rules, validation, permissions, pricing, stock, orders, payments | APPROVED |
| PostgreSQL | The single source of truth for business data | APPROVED (provider pending) |
| Redis | Cache, rate limits, Celery queue | PROPOSED |
| Celery workers | Email, SMS, webhook processing, payment reconciliation, reports, scheduled jobs | PROPOSED |
| Object storage + CDN | Product images, 3D models, documents, static files | APPROVED direction (provider pending) |

### Routing (A-27; details PROPOSED)

| Path | Served by | Caching | Access |
| --- | --- | --- | --- |
| `/`, `/en/…`, `/ur/…` | Next.js storefront | By page type (section 3) | Public |
| `/_next/static/…` | Storefront build assets | Long-term, content-hashed | Public |
| `/3d/draco/<three-version>/…` | Draco decoder files from the storefront build | Long-term, versioned path | Public |
| `/media/…` | Approved images and 3D models from object storage | Long-term, versioned keys | Public; drafts are never served here |
| `/staff/…` | Next.js staff dashboard (`basePath: '/staff'`) | `no-store`, never cached at the CDN | Staff only (below) |
| `/api/v1/…` | Django customer and public API | `no-store` by default; short caching only for named public catalogue reads | Per endpoint (section 8) |
| `/api/v1/staff/…` | Django staff API | `no-store` | Staff session only (section 9) |
| `/api/v1/webhooks/…` | Django webhook receivers | `no-store` | Provider signatures; cookies ignored |
| Django admin, `/health/…` | Not routed publicly in production | — | Internal only (R-06) |

### Staff access restrictions (A-27)

Every layer enforces them, so no single mistake opens the staff area:

1. **Edge:** `/staff/` and `/api/v1/staff/` are never cached, carry `X-Robots-Tag: noindex` and have tighter rate limits. Restricting them further by network (an IP allow-list or a zero-trust access service) is open decision D-09.
2. **Application:** the staff app shows nothing but its sign-in screen without a valid staff session.
3. **API:** every `/api/v1/staff/` endpoint requires a staff session from the staff cookie and the permission it declares. Customer sessions are ignored there (section 9).
4. **Headers:** `frame-ancestors 'none'` and `Referrer-Policy: same-origin` on staff responses.

## 3. Frontend architecture

**PROPOSED (P-01): two Next.js applications in TypeScript, the public storefront at `/` and the staff dashboard at `/staff/` (A-27), sharing design tokens, UI components, the API client and the 3D viewer as packages.** The storefront is server-rendered for SEO and speed; the staff dashboard is client-rendered behind its own sign-in and never indexed.

### Applications

| App | Route | Audience | Rendering | Notes |
| --- | --- | --- | --- | --- |
| `apps/storefront` | `/` | Shoppers | Server-rendered (Next.js App Router) with client components where interaction is needed | Public; SEO, structured product data, Urdu and English |
| `apps/staff` | `/staff/` (Next.js `basePath`) | Staff roles in section 9 | Client-rendered after staff sign-in | Not indexed; separate sign-in and session (section 9); shows only what the role's permissions allow, while the API enforces them |

### Rendering by page type (storefront)

| Page | Strategy | Freshness rule |
| --- | --- | --- |
| Homepage, collections, content and policy pages | Static generation, refreshed when staff publish in the CMS (subject to D-08, below) | Rebuilt on publish |
| Shop All, category, search | Server-rendered; filters and sorting live in the URL | Catalogue cached briefly; never caches price or stock decisions |
| Product detail | Server-rendered with structured product data; 3D viewer loads on the client | Price and stock fetched fresh on every view (A-15) |
| Cart, checkout, payment return | Client-rendered, no caching | Always live from the API |
| Login, registration, password reset | Server-rendered shell, client forms | No caching of personal data |
| Account and order history | Client-rendered after sign-in | Always live |

**CSP and rendering are linked (A-26).** Next.js App Router adds inline scripts to every page. A per-request nonce covers them, but Next.js can then only render those pages dynamically, which rules out the static and cached rendering in the first row. The alternatives keep static pages but need a hash-based or otherwise different policy. V-05 tests both against the real build in M1, and you choose under D-08. Until then, the table above is the proposal.

### Building blocks (all PROPOSED unless marked)

- **Language:** TypeScript in strict mode across apps and packages.
- **Server data:** a typed API client generated from Django's OpenAPI schema (drf-spectacular on the server, openapi-typescript on the client). The frontend never hand-writes request types.
- **Client data:** TanStack Query for cart, account and other live data; a small store (Zustand, already used by R3F) for UI state such as the cart drawer.
- **Forms:** React Hook Form with Zod schemas for instant feedback. The API validates again and is the final authority (A-15).
- **Styling:** AureVon tokens (A-03) as CSS custom properties in `packages/design-tokens`, with CSS Modules for components. CSS logical properties (`margin-inline-start` and similar) throughout, so Urdu right-to-left works without separate styles.
- **Languages:** locale routes `/en` and `/ur` with next-intl; `dir="rtl"` for Urdu (A-18). Currency and dates go through `Intl`, so PKR isn't hard-coded.
- **Images:** Next.js image optimisation through the CDN, serving AVIF or WebP at responsive sizes.
- **Accessibility:** WCAG 2.2 AA target (R-09), with keyboard support, focus states and reduced-motion handling as in the v2 viewer.
- **Analytics:** a consent-aware event layer feeding Module 11; nothing is sent before consent where consent is required.
- **Staff app API calls:** only to `/api/v1/staff/…`, using the staff session; it never calls customer endpoints with a customer session (A-22).

### Version alignment rule

React, React Three Fiber and Three.js must move together. Next.js App Router uses React 19, which pairs with React Three Fiber 9; the v2 viewer was validated on React 18 with R3F 8. V-03 re-runs the v2 validation suite on the exact production versions before M6. All versions are pinned at M1 and updated only deliberately.

No performance budgets are set here. They come from P-18 after real-device data.

## 4. Three.js integration architecture

**APPROVED: Three.js with React Three Fiber, Draco support required, and the v2 viewer as the reference implementation (A-08 to A-14).** Production moves the v2 code into a shared package, bundles it, and feeds it from the catalogue API. The behaviour validated in P-09 Phase 2 carries over unchanged. This section is unchanged from v2.0 apart from the draft-preview note in the pipeline and V-05.

### The `packages/viewer3d` package (PROPOSED structure)

| Part | Responsibility | Carried over from v2 |
| --- | --- | --- |
| `ProductViewer` | The public component: takes the product's 3D asset, poster image and selected variant | Poster-first loading, status messages, Show image / Show 3D |
| `ViewerState` | Loading, ready, failed, unavailable and lost states, outside React, so the page works if 3D never loads | D2 and D4 fixes; no fixed timer; "Try again" |
| `Stage` | Gallery environment, plinth, lights, gold accents (gold mainly in 3D, A-03) | Scene as approved in v1/v2 |
| `Controls` | Rotate, zoom, two-finger tilt, `touch-action: pan-y`, keyboard controls, time-based camera moves | Mobile and keyboard fixes |
| `loadModel` | GLB header inspection, supported-extension check, Draco (WebAssembly, then JavaScript fallback) and Meshopt decoding, time limits, specific error messages | D1 fix and Draco integration |
| `dispose` | Releases geometry, materials, textures and decoded images on every model change | Cleanup verified in Phase 2 |
| Render control | Renders only when 3D is shown, on screen and in a visible tab | D3 fix |

### How the storefront uses it

1. The product page is server-rendered with the product's main image as the poster, so content appears before any 3D code loads (A-14).
2. The viewer is loaded on the client only (`next/dynamic` without server rendering), after the poster is on screen.
3. The API supplies the 3D asset record (below); the viewer never guesses file locations.
4. Variant selection comes from the product page's state; the viewer only shows it. Price, stock and Add to bag never depend on 3D.

### Decoder and library hosting (A-11)

- React, R3F and Three.js are bundled by the Next.js build; nothing loads from a public CDN.
- The Draco decoder files are copied from the installed Three.js version into `public/3d/draco/<three-version>/` at build time. They are served from AureVon's own domain through the CDN, cached long-term, and versioned by path so a Three.js upgrade can't mix decoder versions.

### 3D asset record from the API (PROPOSED)

| Field | Meaning |
| --- | --- |
| `url` | Versioned object-storage URL of the GLB, served through the CDN |
| `poster_image` | The static image used before and instead of 3D |
| `compression` | none, Draco or Meshopt |
| `bytes`, `triangles`, `max_texture_px`, `est_gpu_mb` | Measured at upload, for monitoring and the future asset budget |
| `variant_map` | Which model or material variant shows each colour (method pending, D-03) |
| `status` | draft, approved or retired; only approved assets reach the storefront |
| `checksum` | Integrity check; changes whenever the file changes |

### 3D asset pipeline (PROPOSED)

1. Staff upload a GLB in the staff dashboard (product publishing workflow, section 11).
2. A Celery job validates it: Khronos glTF validator, the same supported-extension list as v2, then measurements.
3. Optimisation with glTF-Transform: Draco or Meshopt, WebP textures. Texture resizing only once an asset budget is approved (A-13).
4. The optimised file is stored under a versioned key. The record stays in draft until a staff member with permission approves it after checking it in the viewer. Drafts are previewed in the staff app through short-lived signed URLs, never through the public `/media/` path.

### Monitoring after launch

The viewer reports, with consent: time to 3D, load failures by reason, fallback use and device class. This gives the field data that the asset budget and any later limits should be based on.

### Outstanding for 3D (section 17)

V-01 (physical devices), V-02 (genuine garment), V-03 (production library versions) and V-04 (KTX2). These gate only the public release of the 3D viewer. Product pages, catalogue and checkout ship with the poster image regardless. V-05 also covers the viewer's needs in the production policy: WebAssembly for Draco and Meshopt, and `blob:` workers.

## 5. Backend architecture

**APPROVED: a Django + Django REST Framework modular monolith on PostgreSQL (A-05 to A-07).** Each business area is a Django app with its own models, rules and API, and apps talk to each other only through each other's published service functions. That keeps one deployment simple, while letting a module be split out later if measured load ever justifies it.

### Django apps and the modules they serve

| App | Owns | Module (section 7) |
| --- | --- | --- |
| `accounts` | Customer and staff identities, kept separate (A-22); customer sign-in and staff sign-in; the two session stores; roles, permissions, staff suspension, revocation and recovery | M03, M06 |
| `customers` | Customer profiles, addresses, preferences, wishlist | M03, M01 |
| `catalog` | Products, variants, SKUs, categories, collections, images, 3D assets | M02 |
| `inventory` | Stock levels per location, movements, reservations, adjustments, quarantine and damaged stock | M14 |
| `suppliers` | Suppliers, supplier products, purchase orders, supplier payments | M14 |
| `cart` | Carts and cart items for guests and customers | M04 |
| `checkout` | Price quotes, the order-placement transaction | M04 |
| `orders` | Orders, order items with purchase-time snapshots, order states | M05 |
| `payments` | Payments, payment attempts and provider events, refunds, cash-on-delivery remittance batches and per-order reconciliation | M05 |
| `shipping` | Shipping zones, rates, shipments, tracking events | M04, M15 |
| `promotions` | Coupons, promotion rules, usage records | M16 |
| `returns` | Return and exchange requests, inspection outcomes | M13 |
| `support` | Tickets, messages, assignment, priorities | M13 |
| `cms` | Pages, banners, navigation, homepage sections, policy pages, SEO records | M07, M17 |
| `notifications` | Templates, preferences, consent, delivery attempts | M12 |
| `analytics` | Commerce events, daily metrics, report definitions, exports | M11 |
| `localization` | Locales, currencies, exchange rates, tax rules, country rules | M15 |
| `reviews` | Product reviews (FUTURE: the model is reserved, the feature comes later) | M01 |
| `audit` | Audit log of sensitive actions | M06, M08 |
| `integrations` | Provider adapters: payment, courier, email, SMS, storage | M05, M10, M12 |
| `common` | Base models, money type, state-machine helper, errors, pagination, utilities | All |

### Inside each app (PROPOSED convention)

| File or folder | Rule |
| --- | --- |
| `models.py` | Data and database constraints only |
| `selectors.py` | Read queries other code may call |
| `services.py` | Every write and business rule, in database transactions where needed. Other apps call these, never another app's models directly for writes |
| `api/` | DRF serializers, views and URLs. Views stay thin: validate, call a service, return |
| `tasks.py` | Celery tasks for this app |
| `events.py` | Domain events this app publishes (for example `order.paid`) |
| `tests/` | Unit, service and API tests for this app |

Boundary rules are checked automatically in CI with import-linter (PROPOSED), so an app can't quietly reach into another app's internals.

### Cross-cutting patterns

- **Money:** `NUMERIC(12,2)` with a currency code on every amount; never floating point (MTS v1.0 §7.1). Amounts are calculated with Python `Decimal`.
- **Time:** stored in UTC, shown in local time (Asia/Karachi at launch).
- **Identifiers:** UUID primary keys on public-facing records; human-readable order numbers (for example `AV-2026-000123`) for customers and staff.
- **State machines (new in v2.1):** order, payment, refund, shipment, remittance and return states change only through a service that checks an explicit table of allowed transitions, locks the row and writes a history record. Status columns also carry database `CHECK` constraints listing their valid values. An event that would move a record backwards (for example "pending" arriving after "succeeded") is recorded and ignored, never applied.
- **Reliable side effects (transactional outbox):** a service writes the business change and an outbox event in the same transaction. Workers send emails, SMS and webhooks from the outbox, so a crash never sends a message for an order that didn't commit, or loses one that did.
- **Idempotency:** order placement, payment start, refunds and every provider callback carry an idempotency key or provider event ID, stored with a unique constraint; a repeat returns the first result (A-23).
- **Background jobs:** Celery workers with Redis (R-04), and Celery Beat for schedules: payment status checks and reconciliation, reservation expiry (which checks the provider first, section 10), refund retries, overdue-remittance checks, abandoned-cart reminders, daily metrics and scheduled reports.
- **Settings:** split into base, development, staging and production; secrets come only from environment variables, with a committed `.env.example` (MTS v1.0 §17.1).
- **API schema:** drf-spectacular generates the OpenAPI schema that the frontend's typed client is built from.
- **Observability:** structured JSON logs with a request ID on every line; error tracking, uptime monitoring and the business alerts in section 14, through a provider chosen under P-10.
- **Django admin (R-06, revised in v2.1):** not used for any business operation, and switched off in production. The Owner role works entirely through the staff dashboard (A-22). Rare emergency operations use Django management commands run by a named operator, which go through services and write to the audit log.

## 6. PostgreSQL database architecture

**APPROVED: PostgreSQL as the single source of truth for business data (A-07). PROPOSED: a currently supported PostgreSQL major version (17 or newer) on a managed service chosen under P-10, with the same major version in local development.** v2.1 adds separate customer and staff identities, payment attempts and events, refund attempts, cash-on-delivery remittance records and stock locations.

&#91;embedded content: Core entity relationships · 16 entities, 15 relationships\]

Order and ProductVariant remain the two hubs. In v2.1 an order carries its order status and its payment status separately, delivery status lives on the shipment (A-24), and stock is held per location, so quarantined or damaged units are never counted as sellable (A-25).

### Entities by domain

| Domain (Django app) | Entities | Key rules |
| --- | --- | --- |
| Identity (`accounts`, `customers`) | Account (type: customer or staff), CustomerProfile, Address, Wishlist, WishlistItem, StaffProfile, Role, Permission, StaffSession, StaffMFADevice, StaffRecoveryCode, StaffAccountEvent | Account type is set at creation and never changes; the same email may hold one customer and one staff account, which never share sessions (A-22) |
| Catalogue (`catalog`) | Product, ProductVariant, Category, Collection, CollectionItem, ProductImage, Product3DAsset, ProductTranslation | Unique SKU per variant; unique (product, size, colour); price lives on the variant |
| Inventory (`inventory`, `suppliers`) | StockLocation (sellable, quarantine, damaged), InventoryItem (per variant and location), StockMovement, StockReservation, Supplier, SupplierProduct, PurchaseOrder, PurchaseOrderLine, SupplierPayment | Only sellable locations count towards availability; every change is an immutable movement; supplier edits never rewrite past purchase records |
| Commerce (`cart`, `checkout`, `orders`) | Cart, CartItem, Order, OrderItem, OrderStatusHistory, IdempotencyKey | OrderItem snapshots name, SKU, options and price at purchase; order status and payment status are separate columns |
| Payments (`payments`) | Payment, PaymentAttempt, PaymentEvent, PaymentStatusHistory, Refund, RefundAttempt, RemittanceBatch, RemittanceLine | Every provider callback is stored before it is applied; each provider event is stored once; each COD order is reconciled against exactly one remittance line |
| Fulfilment (`shipping`, `returns`) | ShippingZone, ShippingRate, Shipment, ShipmentItem, TrackingEvent, ReturnRequest, ReturnItem, ExchangeRequest | States are traceable; courier callbacks are validated |
| Promotions (`promotions`) | Coupon, PromotionRule, CouponRedemption | Validated on the server and recorded against the order |
| CMS and SEO (`cms`) | Page, Banner, NavigationItem, HomepageSection, PolicyPage, SEORecord, Redirect, StoreSetting | Content is data; design system and code stay with developers |
| Support (`support`) | SupportTicket, TicketMessage, TicketAssignment | Timestamped, permission-controlled |
| Communication (`notifications`) | NotificationTemplate, NotificationPreference, ConsentRecord, OutboxEvent, DeliveryAttempt | Marketing respects consent and unsubscribe |
| Analytics (`analytics`) | CommerceEvent, DailyMetric, ReportDefinition, ReportRun | Aggregated wherever possible |
| Localization (`localization`) | Locale, Currency, ExchangeRate, CountryRule, TaxRule | Explicit precision and effective dates |
| Governance (`audit`) | AuditLog | Actor, action, before and after, IP address, time |

### Database rules (PROPOSED unless they repeat an approved requirement)

- **Keys:** UUID primary keys; human-readable order numbers as a separate unique column.
- **Money:** `NUMERIC(12,2)` plus a 3-letter currency code (approved in v1.0 §7.1: never floating point).
- **Constraints in the database, not only in code:** `CHECK (on_hand >= 0)`, `CHECK (reserved >= 0 AND reserved <= on_hand)`, `CHECK (quantity > 0)` on lines, unique SKU, unique coupon codes, and one default address per customer (partial unique index).
- **Constraints added in v2.1:** `CHECK` on every status column listing its valid values; unique (provider, provider event ID) on PaymentEvent; unique idempotency key on PaymentAttempt and RefundAttempt; at most one succeeded payment per order (partial unique index), so a double charge is caught and refunded rather than silently accepted; unique order per RemittanceLine; unique (email, account type) on Account; reservations may only reference sellable locations.
- **Deletes:** financial and order records use `ON DELETE PROTECT`. Products are archived, not deleted, so past orders stay intact. Staff accounts are deactivated, never deleted, so audit history keeps its actor.
- **Stock changes:** only through inventory services, which lock the inventory row (`SELECT … FOR UPDATE`) and write a StockMovement in the same transaction. Available stock = sellable on hand − reserved.
- **Flexible data:** JSONB only for genuinely variable data (product attributes, audit before/after, provider payloads), never for fields the business queries routinely.
- **Search:** PostgreSQL full-text search on product name and description per language, with GIN indexes (R-07).
- **Indexes:** added from observed query patterns, with the obvious ones from day one: order number, order status and date, payment status and age (for reconciliation), customer, SKU, product slug.
- **Migrations:** Django migrations, reviewed like code. Schema changes that could break a running release use expand-then-contract (add the new column, deploy, migrate data, then remove the old one). Every migration notes how to roll it back.
- **Local development:** PostgreSQL in Docker Compose at the same major version as production (proposed answer to P-04).
- **Retention and anonymisation** of personal data: PENDING (P-11 and P-17), and must be decided before production.

## 7. The 18 business modules

**All 18 modules and their capabilities are APPROVED scope (A-21); what changes between them is when they are built.** Priority follows v1.0's release principle: first a complete, trustworthy shopping journey; advanced analytics, forecasting and international rollout later, without architecture that blocks them. In v2.1, M05, M06 and M14 gain the capabilities from corrections C-1 to C-4.

Priority key: **Launch-critical** = the shopping journey can't work without it. **Launch** = needed at launch, possibly in a simpler first version. **Post-launch** = later releases, with the data model and boundaries prepared from the start.

| # | Module | Scope (capabilities kept from v1.0, plus v2.1 additions) | Django apps | Priority | Phase (section 16) | v1.0 # |
| --- | --- | --- | --- | --- | --- | --- |
| M01 | Storefront & Shopping Experience | Homepage sections, Shop All, category and collection browsing, filters, product detail, cart and account pages, responsive layouts | Frontend + `catalog`, `cms` | Launch-critical | 3–5 | 01 |
| M02 | Product Catalogue & 3D | Products, variants with their own SKU and stock, categories, collections, images, 3D assets, lazy loading, static fallback | `catalog` | Launch-critical (3D: release gated by V-01/V-02) | 5, 6 | 02 |
| M03 | Authentication & Customer Accounts | Registration, login, logout, verification, password reset, profile, addresses, order history, preferences | `accounts`, `customers` | Launch-critical | 2, 7 | 03 |
| M04 | Cart & Checkout | Cart add/update/remove, variant and stock validation, server-side totals, stock reservation, confirmation and retry states | `cart`, `checkout`, `shipping` | Launch-critical | 7 | 04 |
| M05 | Payments & Order Management | Payment adapter, payment and refund state machines, idempotent payment and refund operations, duplicate and late callback handling, reconciliation, cash-on-delivery remittance reconciliation per order (v2.1), order lifecycle, cancellation, refunds, staff order search | `orders`, `payments` | Launch-critical | 8 (remittance with 10) | 05 |
| M06 | Administration & Role Permissions | Staff dashboard, separate staff authentication, role-based access, granular permissions, staff suspension, session revocation and recovery (v2.1), audit of sensitive actions, confirmation for high-risk actions | `accounts`, `audit` + staff app | Launch-critical | 2, then every phase | 06 |
| M07 | Store Configuration & CMS | Homepage sections, banners, navigation, collections, content and policy pages, store settings, scheduled publishing | `cms`, `localization` | Launch | 4 | 07 |
| M08 | Security & Performance | Authentication security, CSRF/XSS protection, validation, rate limits, secrets, backups, caching, CDN, graceful degradation, CSP validated against the real build (v2.1) | Cross-cutting | Launch-critical | 1, 14 | 08 |
| M09 | Testing & Quality Assurance | Unit, integration, API, end-to-end, 3D, security, performance, accessibility, UAT | Cross-cutting | Launch-critical | Every phase | 09 |
| M10 | Deployment & Hosting | Hybrid cloud, domain, SSL, routing under `/`, `/staff/` and `/api/v1/` (v2.1), automated deployment, monitoring, backups | Infrastructure | Launch-critical | 1, 15 | 10 |
| M11 | Analytics & Business Intelligence | Sales, AOV, customers, products, conversion, campaigns, finance summaries, PDF/Excel exports, scheduled reports | `analytics` | Launch: core sales reporting. Post-launch: segmentation, lifetime value, forecasting | 13 | 11 |
| M12 | Notifications & Communication | Order, payment, shipping, refund, verification and reset messages; staff alerts; email and SMS; preferences; templates; delivery monitoring | `notifications`, `integrations` | Launch: transactional. Post-launch: campaigns | 8, 11 | 12 |
| M13 | Customer Support & Returns | Contact form, tickets, assignment, priorities, return and exchange requests, refunds, issue categories | `support`, `returns` | Launch: contact form and returns. Post-launch: full ticket analytics | 12 | 13 |
| M14 | Inventory & Supplier Management | Stock per variant and location, quarantine and damaged stock kept out of sellable stock (v2.1), adjustments, reservations, low-stock alerts, history, suppliers, purchase orders, receiving, valuation, reorder suggestions | `inventory`, `suppliers` | Launch-critical: stock and reservations. Post-launch: forecasting | 9 | 14 |
| M15 | Internationalization, Localization & Global Readiness | English and Urdu with right-to-left, PKR, address and date formats; later currencies, countries, tax and shipping rules, with no hard-coded country assumptions (absorbs v1.0 Module 21) | `localization`, `shipping` | Launch: English, Urdu, PKR, Pakistan. Post-launch: other markets | 3, 10 | 15, 21 |
| M16 | Promotions & Marketing Operations | Coupons, scheduled promotions, usage reporting, consented marketing and abandoned-cart flows | `promotions`, `notifications` | Launch: basic coupons. Post-launch: campaigns | 11 | 18 |
| M17 | SEO & Content Publishing | SEO titles, descriptions and slugs, canonical tags, sitemap, robots, structured product data, redirects on URL changes | `cms` + storefront | Launch | 4, 5 | 19 |
| M18 | Operational Reliability & Recovery | Automated backups with restore tests, error and job monitoring, payment and COD reconciliation alerts (v2.1), payment and notification recovery, disaster recovery, runbooks | Cross-cutting | Launch-critical | 14 | 20 |

### Where v1.0's other three modules went

| v1.0 module | Now covered by |
| --- | --- |
| 16 Final Technical Architecture & Integration | Sections 2 (system), 5 (backend) and 8 (API and integration layers) |
| 17 Development Roadmap & Implementation | Section 16 (phases), with the working rules of v1.0 §17 unchanged |
| 21 Global Readiness & Scalability | M15 above, plus sections 3, 6 and 14 (configuration, data rules, scaling) |

## 8. API architecture and endpoint responsibilities

**APPROVED: a REST API built with Django REST Framework (A-06), served under `/api/v1/` (A-27). PROPOSED: the conventions and endpoint map below, with every endpoint enforcing permissions on the server.** The API is the only way into business data, for both web apps. v2.1 gives staff their own authentication endpoints and adds refund and remittance operations.

### Conventions (PROPOSED)

| Topic | Rule |
| --- | --- |
| Base path and versioning | `/api/v1/…`; breaking changes go to `/api/v2/` with a deprecation period |
| Format | JSON; snake\_case fields; ISO 8601 times in UTC; money as a decimal string plus currency (`{"amount": "48500.00", "currency": "PKR"}`) |
| Schema | OpenAPI 3 generated by drf-spectacular; the frontend's typed client is built from it, and CI fails if they drift |
| Errors | One shape everywhere (RFC 9457 problem details): `type`, `title`, `status`, `detail`, plus per-field `errors` for validation |
| Lists | Cursor pagination; filters and sorting as query parameters |
| Retries | Order placement, payment start, refunds and remittance reconciliation require an `Idempotency-Key` header; a repeat returns the first result (A-23) |
| Authentication | Customer endpoints accept only the customer session cookie; `/api/v1/staff/` accepts only the staff session cookie; each ignores the other's cookie (A-22, section 9). Webhooks authenticate with provider signatures and ignore all cookies |
| CSRF | Separate CSRF cookies and tokens for the customer and staff realms |
| Rate limits | Per IP and per account on sign-in, password reset, registration, checkout and public search; tighter limits on all staff authentication endpoints (Redis-backed) |
| Staff endpoints | Under `/api/v1/staff/`, with separate authentication and permission classes; never reachable with a customer session |
| File uploads | Direct to object storage with short-lived pre-signed URLs; the API records the upload and starts validation |
| Webhook responses | A duplicate event returns success without being applied again, so providers stop retrying (A-23) |

### Endpoint map

| Area | Endpoints (method and path under `/api/v1`) | Responsibility | Access |
| --- | --- | --- | --- |
| Catalogue | `GET /catalog/products`, `GET /catalog/products/{slug}`, `GET /catalog/categories`, `GET /catalog/collections/{slug}` | Browse, filter and search; product detail with variants, images and approved 3D asset | Public |
| Availability | `GET /catalog/products/{slug}/availability` | Fresh price and stock per variant, never cached long | Public |
| Content | `GET /cms/home`, `GET /cms/navigation`, `GET /cms/pages/{slug}` | Published CMS content in the requested language | Public |
| Customer sign-in | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/password-reset`, `POST /auth/password-reset/confirm`, `POST /auth/verify`, `GET /auth/session` | Customer accounts, sessions, CSRF token. Staff accounts can't sign in here | Public / customer |
| My account | `GET PATCH /me`, `GET POST PATCH DELETE /me/addresses`, `GET /me/orders`, `GET /me/orders/{number}`, `GET POST DELETE /me/wishlist` | Profile, addresses, history, wishlist | Customer (own data only) |
| Cart | `GET /cart`, `POST /cart/items`, `PATCH DELETE /cart/items/{id}`, `POST DELETE /cart/coupon` | Cart for guests (cookie) and customers; validates variant, quantity and stock | Public / customer |
| Checkout | `GET /shipping/options`, `POST /checkout/quote`, `POST /checkout/orders` | Server-calculated totals; places the order, reserves stock and returns the payment next step | Customer or guest (per P-15) |
| Payment | `POST /orders/{number}/payment-attempts`, `GET /orders/{number}/payment-status` | Start or retry payment within the reservation window; read status after returning from the provider. Reading status also triggers a direct provider check if the payment is still pending | Order owner |
| Support and returns | `POST /support/tickets`, `POST /returns/requests`, `GET /me/returns` | Contact, return and exchange requests | Public / customer |
| Webhooks | `POST /webhooks/payments/{provider}`, `POST /webhooks/shipping/{provider}`, `POST /webhooks/messaging/{provider}` | Signature check, store the event once, acknowledge, process in a worker | Provider signature |
| Staff sign-in | `POST /staff/auth/login`, `POST /staff/auth/mfa/verify`, `POST /staff/auth/logout`, `GET /staff/auth/session`, `POST /staff/auth/recovery/start`, `POST /staff/auth/recovery/complete` | Staff password plus second factor; staff session; recovery flow in section 9. Customer accounts can't sign in here | Public, rate-limited |
| Staff: my sessions | `GET /staff/me/sessions`, `DELETE /staff/me/sessions/{id}`, `POST /staff/me/password`, `POST /staff/me/mfa` | See and end one's own sessions; change password; replace the second factor (re-authentication required) | Signed-in staff |
| Staff: catalogue | `/staff/products`, `/staff/variants`, `/staff/categories`, `/staff/collections`, `/staff/media/uploads`, `/staff/3d-assets/{id}/approve` | Create, edit, publish, archive; image and 3D upload and approval | Catalogue permissions |
| Staff: inventory | `/staff/inventory`, `/staff/inventory/adjustments`, `/staff/inventory/inspections`, `/staff/suppliers`, `/staff/purchase-orders`, `/staff/purchase-orders/{id}/receive` | Stock per location, adjustments with reasons, return inspections (sellable, quarantine, damaged), suppliers, receiving | Inventory permissions |
| Staff: orders | `/staff/orders`, `/staff/orders/{number}/status`, `/staff/orders/{number}/cancel`, `/staff/shipments` | Search, update, cancel, create shipments | Operations permissions |
| Staff: payments and refunds | `/staff/payments`, `/staff/payments/{id}/check`, `/staff/refunds`, `/staff/refunds/{id}/approve`, `/staff/refunds/{id}/retry`, `/staff/refunds/{id}/mark-manual` | Payment history and on-demand provider check; refund approval, retry and manual completion | Accountant / operations permissions |
| Staff: COD remittance | `/staff/remittances`, `/staff/remittances/{id}/lines`, `/staff/remittances/{id}/lines/{line}/reconcile`, `/staff/remittances/{id}/lines/{line}/discrepancy` | Record courier remittance batches; reconcile each order; resolve mismatches | Accountant permissions |
| Staff: customer care | `/staff/tickets`, `/staff/returns`, `/staff/returns/{id}/decision` | Ticket handling, return approval with a recorded reason | Support permissions |
| Staff: content and marketing | `/staff/cms/*`, `/staff/seo`, `/staff/redirects`, `/staff/promotions`, `/staff/coupons` | Content, SEO, promotions | Content / marketing permissions |
| Staff: reports | `/staff/reports/{name}`, `/staff/exports` | Dashboards and PDF/Excel exports (exports run in workers) | Report permissions; personal data restricted |
| Staff: administration | `/staff/accounts`, `/staff/accounts/{id}/suspend`, `/staff/accounts/{id}/reactivate`, `/staff/accounts/{id}/sessions` (list, revoke all), `/staff/accounts/{id}/recovery`, `/staff/roles`, `/staff/settings`, `/staff/audit-log` | Staff accounts, suspension and session revocation, assisted recovery, roles, store settings, audit reading | Owner / admin permissions |
| Operations | `GET /health/live`, `GET /health/ready` | Liveness and readiness for the platform | Internal only (not routed publicly) |

Each module's milestone brief turns its rows into a detailed contract: request and response fields, errors, permissions and tests.

## 9. Authentication and authorization

**APPROVED (A-22, from C-1): strict separation between customer and staff authentication; a customer session never grants access to staff APIs; staff suspension, session revocation and secure staff recovery are defined; the Owner role doesn't depend on Django superuser. Also approved since v1.0: every permission is enforced on the server.** PROPOSED: the mechanisms below. PENDING: the final role list, permission matrix, two-factor policy, session lengths and dual-approval rules (P-05), Owner recovery arrangements (D-12) and network restriction (D-09).

### Two separate realms (PROPOSED design for A-22)

| Layer | Customer realm | Staff realm |
| --- | --- | --- |
| Identity | Account of type `customer` | Account of type `staff`. A separate record even when the email matches a customer account; the type never changes |
| Sign-in endpoint | `/api/v1/auth/login`; refuses staff accounts | `/api/v1/staff/auth/login` plus second factor; refuses customer accounts |
| Authentication backend | Customer backend only | Staff backend only |
| Session store | Customer session table, cached in Redis | `StaffSession` table, one revocable row per session, cached in Redis |
| Cookie | `__Host-av_session`: `Path=/`, `Secure`, `HttpOnly`, `SameSite=Lax` | `__Secure-av_staff`: `Path=/api/v1/staff/`, `Secure`, `HttpOnly`, `SameSite=Strict`. The browser never sends it to the storefront or to customer endpoints |
| CSRF | Customer CSRF cookie and header | Separate staff CSRF token, delivered in the staff session response |
| Which requests it can authenticate | Customer and public endpoints only | `/api/v1/staff/…` only |
| Session length | Rolling, longer ("remember me") | Short idle timeout and absolute maximum (values: P-05) |

**How the separation is enforced:** a middleware picks the realm from the URL prefix before any view runs. On `/api/v1/staff/`, only the staff authentication class is installed, so a valid customer cookie is simply ignored and the request gets `401`. An automated test lists every staff route from the URL configuration and checks that a customer session is refused on each one, so a new endpoint can't miss the rule.

### Staff account lifecycle

| State | How it's entered | Effect |
| --- | --- | --- |
| Invited | An authorised staff member creates the account | A single-use, expiring enrollment link: set password, enrol second factor, receive recovery codes |
| Active | Enrollment completed, or reactivation | Can sign in |
| Suspended | Suspended by an authorised staff member | **All sessions revoked in the same transaction**; sign-in refused; the account and its audit history are kept |
| Deactivated | A leaver | As suspended, and only an Owner can reverse it |

- **Immediate effect:** every staff request re-checks the account's status and the session's revocation flag. Suspension takes effect on the very next request, with no cache delay.
- **Session revocation:** happens automatically on suspension, deactivation, password change (all other sessions), second-factor reset and assisted recovery. Owners can also revoke all of an account's sessions, and each staff member can see and end their own sessions.
- **Role changes:** take effect on the next request, because permissions are read per request.
- **Notifications:** suspension, revocation and every recovery event are emailed to the account and recorded in the audit log.

### Staff account recovery (no email-only reset)

| Situation | Recovery path | Controls |
| --- | --- | --- |
| Forgot password, still has the second factor | Single-use email link, **and** the second factor must be passed before the new password is accepted | All other sessions revoked; notification sent |
| Lost the second factor, has a recovery code | Password plus one recovery code, then immediate enrolment of a new second factor | Code consumed; new codes issued; notification sent |
| Lost both, or no recovery codes left | Assisted recovery: an Owner verifies the person outside the system, then issues a single-use recovery enrollment link. The old password and second factor stop working at once | All sessions revoked; audited with the approving Owner; nobody can approve their own recovery |
| An Owner loses access | Assisted recovery by another Owner. With only one Owner, a documented break-glass procedure is needed: D-12 decides how (for example, always keeping two Owner accounts) | Never through Django superuser |

Recovery endpoints are tightly rate-limited and always respond the same way, whether or not an account exists.

### The Owner role without Django superuser

- Owner is an AureVon role whose permissions are granted explicitly in the permission tables, like every other role.
- No staff account has Django's `is_superuser` flag, and AureVon's permission checks ignore it entirely. A test confirms that the flag grants nothing.
- Django admin is switched off in production (R-06), so no business function depends on it.
- The system refuses to suspend, deactivate or demote the last active Owner.

### Customers (PROPOSED)

- Django's authentication with email as the sign-in name; passwords hashed with Argon2.
- The customer session cookie described above. The session ID changes at sign-in; sign-out ends the session on the server.
- Email verification and password reset use single-use, time-limited links. (For customers, an email link alone is acceptable; the stricter rule above is for staff.)
- Rate limits on sign-in, registration and password reset, with a generic response that doesn't reveal whether an email is registered.
- Phone OTP is possible later through the SMS adapter, once P-08 selects a provider.
- **Guest checkout (P-15 pending):** the architecture supports both answers. A guest order links to an email address and a private order-access link; if guest checkout is refused, checkout simply requires sign-in.

### Authorization model (PROPOSED)

- **Role-based:** roles are groups of named permissions such as `orders.refund`, `refunds.approve`, `inventory.adjust`, `remittance.reconcile`, `catalog.publish`, `cms.publish`, `reports.export_personal`, `staff.suspend`, `staff.recover`, `staff.manage_roles`.
- **Default deny:** every endpoint declares the permission it needs; anything undeclared is refused.
- **Ownership:** customer endpoints filter every query by the signed-in customer, so one customer can never read another's orders or addresses, even by guessing an ID.
- **Two layers:** DRF permission classes check the request, and services check again for high-risk actions, so a future endpoint can't skip the rule.
- **Re-authentication:** refunds, permission changes, price changes, suspension and recovery approvals ask for the second factor again.
- **Audit:** permission changes, price changes, stock adjustments, refunds, remittance reconciliation, order overrides, CMS publishing, setting changes and every staff-account event are written to the audit log with actor, before and after values, IP address and time.

### Candidate role matrix (PENDING approval under P-05)

| Capability | Owner | Store Admin | Accountant | Inventory Manager | Support | Content / Marketing |
| --- | --- | --- | --- | --- | --- | --- |
| Manage staff and roles | Yes | — | — | — | — | — |
| Suspend staff, revoke sessions | Yes | Limited | — | — | — | — |
| Approve assisted staff recovery | Yes | — | — | — | — | — |
| Store and security settings | Yes | Limited | — | — | — | — |
| Catalogue and 3D assets: edit, publish | Yes | Yes | — | Read | Read | Edit, no publish |
| Prices | Yes | Yes | Read | — | — | — |
| Stock adjustments, return inspections, purchase orders | Yes | Read | Read | Yes | — | — |
| Orders: view, update status | Yes | Yes | Read | Read | Yes | — |
| Refunds | Yes | Request | Approve | — | Request | — |
| COD remittance reconciliation | Yes | Read | Yes | — | — | — |
| Returns decisions, tickets | Yes | Yes | Read | — | Yes | — |
| CMS, SEO, promotions | Yes | Yes | — | — | — | Yes |
| Financial reports and exports with personal data | Yes | Limited | Yes | — | — | — |
| Audit log | Yes | Read | Read | — | — | — |

"Limited" and "Request" are placeholders for decisions in P-05, such as which settings a Store Admin may change and whether refunds above an amount need a second approver.

## 10. Payments, refunds and cash on delivery

**APPROVED (A-23, A-24 from C-2 and C-3): payment and refund state machines; duplicate, delayed and late callbacks handled; idempotent payment and refund operations; no successful provider payment left marked unpaid; COD delivery status kept separate from remittance, following COD order → Shipped → Delivered → Remittance pending → Remittance received → Reconciled, with accountant reconciliation per order. Also approved since v1.0: provider-hosted or tokenized payments only, signature-checked callbacks, reconciliation, a manual courier fallback.** PENDING: providers (P-06), couriers (P-07), shipping rules (P-13), tax (P-11), late-payment policy (D-07) and COD remittance terms (D-11).

&#91;embedded content: Payment states · online and cash on delivery\]

An order now carries two independent statuses: its order status (section 11) and its payment status, shown here. For cash on delivery, the first three steps come from the shipment and the last three from finance, so a delivered parcel is never mistaken for money received.

### Payment states (PROPOSED)

Each attempt to pay is its own Payment record; an order may have several attempts but at most one success.

| State | Meaning | Can move to |
| --- | --- | --- |
| Created | Attempt recorded, idempotency key stored, before contacting the provider | Pending, Not paid (provider refused to start) |
| Pending | Shopper sent to the provider; result not yet confirmed | Succeeded, Not paid |
| Succeeded | Provider confirmed payment, by verified callback or by a direct status check | Partly refunded, Refunded |
| Not paid | Failed, cancelled at the provider, or expired | Succeeded, only on provider confirmation (a late success, below) |
| Partly refunded / Refunded | Refunds have succeeded against this payment | Refunded (from partly refunded) |

The order's payment status is derived from its payments: unpaid, paid, partly refunded or refunded. For COD: collect on delivery, remittance pending, remittance received, reconciled, or discrepancy.

### Callback handling (A-23)

- **Duplicates:** each provider event is stored once, keyed on (provider, event ID). A repeat is acknowledged as success and not applied again.
- **Delayed or out-of-order events:** transitions only move forward through the table above. An event that would move a payment backwards (for example "pending" after "succeeded") is stored and ignored.
- **Conflicts:** an event that contradicts a final state (for example "failed" after "succeeded") is never applied automatically. The payment is flagged for review and an alert fires (section 14).
- **Verification:** the signature is checked before anything is treated as trusted. Where the provider supports it, the worker also confirms the result with a direct status check before applying a success.
- **Never trusted alone:** return-URL parameters from the shopper's browser never change a payment's state.

### No successful payment left unpaid (A-23)

Three independent paths confirm every payment, so a lost callback can't leave a paid order marked unpaid:

1. **Callbacks**, processed as above.
2. **Active status checks:** a scheduled job asks the provider about every payment still pending, on a backing-off schedule, until it reaches a final state or the provider's own window closes. The shopper's return page also triggers an immediate check.
3. **Settlement reconciliation:** a daily job matches the provider's settlement report against every payment. A success found only in the settlement report is applied, and an alert records the missed callback.

Before any reservation expires, or any unpaid order is cancelled, the provider is checked one last time (section 11).

### Payment succeeds after the order expired (D-07 pending)

The provider's confirmation always wins: the payment is recorded as Succeeded. What happens to the order is open decision D-07. The proposal:

- If the items are still available, re-reserve them, restore the order to Confirmed and notify the customer and staff.
- If they aren't, start a full refund automatically, tell the customer, and alert staff.

Either way, a staff alert fires (section 14).

### Idempotency (A-23)

| Operation | Key | Guarantee |
| --- | --- | --- |
| Start payment | Idempotency key per attempt; the provider's idempotency key where supported | A double click or retry never opens two payments |
| Callback | Provider event ID | Applied at most once |
| Refund | Idempotency key per refund request, passed to the provider | A retry never refunds twice |
| Remittance reconciliation | Remittance line, unique per order | An order is reconciled once |

### Provider downtime (PROPOSED)

- **Starting payments:** if the provider is failing, a circuit breaker stops new attempts and checkout says online payment is temporarily unavailable. Other approved methods, such as COD if confirmed under R-08, stay available. Already-placed orders keep their reservation and can retry payment until it expires.
- **Callbacks during an outage:** providers retry; nothing is lost on AureVon's side because callbacks are stored before processing.
- **Status checks and refunds:** retried with back-off; an alert fires if the outage continues (section 14).

### Refund states (PROPOSED)

| State | Meaning | Next |
| --- | --- | --- |
| Requested | Raised by staff or a return decision | Approved, Rejected |
| Approved | Approved by someone with `refunds.approve` (dual approval rules: P-05) | Processing |
| Processing | Sent to the provider with its idempotency key | Succeeded, Failed |
| Failed | Provider refused or timed out | Processing (automatic retry with back-off), Manual required |
| Manual required | Retries exhausted, provider can't refund, or a COD refund | Manual completed |
| Manual completed | Paid by bank transfer or wallet, with the reference recorded | — |
| Rejected | Not approved, with a reason | — |

Failed refunds are never silently dropped: every one ends in Succeeded, Manual completed or Rejected, and an alert fires when a refund reaches Manual required.

### Cash on delivery and remittance reconciliation (A-24)

1. **COD order:** placed and confirmed; stock is committed (section 11); payment status is "collect on delivery".
2. **Shipped and Delivered** come from the shipment and courier tracking. Delivery moves the payment to **Remittance pending**; it doesn't mark the order paid.
3. **Remittance received:** the accountant records the courier's remittance batch (reference, date, total, courier fees) with one line per order, imported from the courier's statement or API.
4. **Reconciled:** the accountant reconciles each order individually against its line. Expected amount, collected amount and fees must match; then the payment is final.
5. **Mismatch:** a line that doesn't match, or a delivered order with no line, becomes a **discrepancy** and raises an alert. It stays open until the accountant resolves it with a recorded reason.
6. **Undelivered COD:** the COD payment is cancelled; there's nothing to remit; stock follows the return rules in section 11.

The expected remittance window, fee handling and discrepancy tolerance are open decision D-11, and depend on the chosen couriers (P-07).

### Payment adapter (PROPOSED, unchanged from v2.0)

Every payment method implements one interface in `integrations/payments/`:

| Operation | Purpose |
| --- | --- |
| `start_payment(order, amount, return_url, idempotency_key)` | Returns the next step: redirect to a hosted page, show a provider form, or nothing (cash on delivery) |
| `verify_callback(request)` | Checks the provider's signature and returns a normalised, verified event, or rejects it |
| `get_status(reference)` | Asks the provider directly; used for return pages, status checks and reconciliation |
| `refund(payment, amount, reason, idempotency_key)` | Full or partial refund where the provider supports it; otherwise the refund goes to Manual required |
| `settlement_report(date)` | Fetches the provider's settlement data, where offered |
| `capabilities` | What this provider can do: partial refunds, idempotency keys, settlement reports |

A fake provider with the same interface is used in development and tests, including simulated duplicate, delayed, conflicting and missing callbacks.

**Candidate payment methods to research under P-06 (not decided):** card payments through a Pakistani bank or payment aggregator, mobile wallets such as JazzCash and Easypaisa, and cash on delivery (R-08).

### Shipping adapter (PROPOSED, unchanged from v2.0)

| Operation | Purpose |
| --- | --- |
| `quote(address, parcel)` | Live rates where the courier offers them |
| `book(shipment)` | Creates the consignment and label, including any cash-on-delivery amount |
| `track(tracking_number)` and `verify_webhook(request)` | Tracking updates by polling or by courier callback |
| `cancel(shipment)` | Cancels a booking that hasn't been collected |
| `remittance_statement(period)` | Fetches COD remittance data, where the courier offers it (new in v2.1) |

- **Rates at launch:** zone-based table rates kept by staff, so checkout doesn't depend on a courier being online. Zones, fees and thresholds are PENDING (P-13).
- **Manual fallback (approved):** staff can book with the courier outside the system and enter the tracking number by hand; the order flow continues normally.
- **Couriers to evaluate under P-07 (not decided):** established Pakistani couriers such as TCS, Leopards, M&P, Trax and PostEx, judged on API quality, COD remittance reporting, return logistics and coverage.

### Tax (PENDING P-11)

Tax is calculated on the server from configurable `TaxRule` records with effective dates. Whether prices are shown tax-inclusive, and the applicable rates, need local professional advice before M8.

## 11. Inventory and order workflows

**APPROVED (A-25, from C-4): stock is restored on cancellation before dispatch; after dispatch it stays unavailable until the return is physically received and inspected; damaged returns never go back to sellable stock; reservation expiry, delayed payment callbacks and overselling risks are addressed. Also approved since v1.0: stock per variant, reservations against overselling, every adjustment a movement record, purchase-time snapshots on order lines.** PROPOSED: the states and rules below.

&#91;embedded content: Order states and stock · 5 forward states, 3 exits, 1 inspection step\]

"Awaiting" is skipped for cash on delivery: a COD order goes straight to Confirmed once accepted. "Dispatched" is the point where the parcel leaves AureVon's hands. Every state change is written to `OrderStatusHistory` with the actor and reason; the payment side lives in section 10.

### Stock locations (PROPOSED)

| Location type | Counts as available to sell? | Used for |
| --- | --- | --- |
| Sellable | Yes | Normal stock |
| Quarantine | No | Returns that need cleaning, repair or a second check before a decision |
| Damaged | No, ever | Unsellable returns and damaged receipts, held for write-off |

Available to sell = sellable on hand − reserved. Reservations may only point at sellable stock (database constraint).

### Stock rules (PROPOSED)

| Event | Stock effect | Movement recorded |
| --- | --- | --- |
| Item added to cart | None; availability is checked only | — |
| Order placed | `reserved` += quantity, inside the order transaction with the inventory rows locked; if any line is short, the whole order is refused with the exact item named | Reservation |
| Payment confirmed or COD accepted | Sellable `on_hand` −= quantity and `reserved` −= quantity | Sale |
| Reservation reaches its expiry | Only after a final provider check: success → confirm; still pending at the provider → hold until the provider's result or the end of its window; failed or expired → release | Reservation released (when released) |
| **Cancelled before dispatch** (Awaiting, Confirmed or Packing) | Back to sellable immediately: the reservation is released, or committed stock is restored; refund started if paid (A-25) | Reservation released, or Cancellation |
| Dispatched | None; the units have already left sellable stock | — |
| **Cancelled after dispatch, undelivered, or returned** | No change until the parcel is physically received; the units stay unavailable while in transit (A-25) | — |
| Return received and inspected: sellable | Into sellable stock | Return to stock |
| Inspected: needs work or a second check | Into quarantine; later moved to sellable or damaged by an inventory permission holder | Quarantine, then Release or Damaged |
| **Inspected: damaged** | Into damaged stock; never sellable; written off by an authorised person (A-25) | Damaged |
| Purchase order received | Sellable `on_hand` += received quantity (damaged units go to damaged) | Receipt |
| Staff adjustment | Change with a mandatory reason; audited | Adjustment |

### Overselling safeguards (A-25)

- **Locking:** order placement locks the inventory rows of every line, in a consistent order to avoid deadlocks, before checking and reserving.
- **Database backstops:** `CHECK` constraints stop `on_hand` going negative and `reserved` exceeding `on_hand`, even if code is wrong.
- **No early reservations:** carts don't hold stock, so abandoned carts can't block sales; availability is rechecked at placement.
- **Expiry never races a payment:** the expiry job processes reservations one at a time with row locks (`SKIP LOCKED`), and always asks the provider before releasing (above).
- **Expiry is longer than the provider's window:** the reservation lifetime must exceed the payment provider's own session timeout, plus a margin, so a shopper still on the payment page can't lose their item (D-06).
- **Late payments:** if a payment succeeds after the reservation was released, stock is re-checked and re-reserved under D-07; it is never assumed.
- **COD:** stock is committed as soon as a COD order is confirmed.
- **Proof:** a concurrency test runs parallel orders for the last unit; exactly one may succeed (section 13). Any constraint violation raises an alert (section 14).

Low-stock alerts fire when available stock drops to a per-variant threshold that staff set.

### Order placement transaction (unchanged from v2.0)

1. Validate the cart: product published, variant active, quantity allowed.
2. Recalculate prices, promotion, shipping and tax on the server (A-15).
3. Lock the variants' inventory rows in a consistent order and reserve stock.
4. Create the order and order items with snapshots, the status history row and the first payment attempt.
5. Write outbox events. Commit. Only then call the payment provider.

If any step fails, the whole transaction rolls back. The `Idempotency-Key` guarantees that a double click or a network retry can't create two orders.

### Other workflows

- **Product publishing:** as in MTS v1.0 §8.1, with 3D assets adding a validation job and an approval step (section 4).
- **Returns and refunds:** a return request is checked against the return window (P-14), approved or rejected with a reason, received, inspected into sellable, quarantine or damaged stock (above), and refunded through the refund states in section 10.
- **Purchase orders:** draft → sent → partly received → received, or cancelled. Receiving creates stock movements; supplier records never rewrite past purchases.

## 12. Security requirements

**APPROVED baseline (MTS v1.0 §9 and Module 08), unchanged: server-side authorization on every endpoint, CSRF and XSS protection, validated input, rate limits, HTTPS, secrets out of source control, validated uploads, least-privilege credentials, audit logging, no raw card data, minimal personal data. Added in v2.1: the CSP is validated against the actual production Next.js build and not weakened unnecessarily (A-26), and staff routes are restricted at every layer (A-27).** No critical or high-severity issue may remain at launch without a documented risk decision approved by the product owner.

### Content Security Policy (A-26)

**Correction to v2.0:** v2.0 assumed a bundled Next.js app has no inline scripts. That's not true: Next.js App Router writes inline scripts into every page to start the app. The policy therefore needs nonces or hashes, and the choice affects rendering (section 3). v2.1 sets the requirements, proposes a baseline, and makes the real-build test a tracked validation (V-05).

**Requirements (approved, from C-5):** the policy must be tested against the production build and account for framework-generated scripts, nonce or hash requirements, Three.js, Draco and Meshopt, WebAssembly, and production assets. Nothing is loosened beyond what that test shows is needed.

**Baseline to validate (PROPOSED):**

| Directive | Storefront | Why |
| --- | --- | --- |
| `script-src` | `'self'`, plus a per-request nonce with `'strict-dynamic'` **or** hashes of the framework's inline scripts (D-08); `'wasm-unsafe-eval'` | Next.js inline scripts; bundled code; Draco and Meshopt WebAssembly |
| Never in production | `'unsafe-inline'` for scripts, `'unsafe-eval'` | Development builds may need `'unsafe-eval'`, so development gets its own looser policy that never ships |
| `style-src` | `'self'`, plus a nonce or hashes only for any style blocks the build injects | Fonts are self-hosted through Next.js at build time, so no Google Fonts host is needed |
| `font-src`, `img-src` | `'self'`; images also `data:` and `blob:` | `blob:` for textures decoded from GLB files |
| `worker-src` | `'self' blob:` | Three.js DRACOLoader runs its decoder in a `blob:` worker |
| `connect-src` | `'self'`, `blob:`, plus only the approved analytics and error-monitoring endpoints | GLB texture decoding fetches `blob:` URLs |
| `form-action` | `'self'`, plus the payment provider's domain if its hosted page is reached by form post (P-06) | Hosted payment redirects |
| `frame-ancestors`, `object-src`, `base-uri` | `'none'` | Clickjacking and injection |

The staff app gets its own, stricter policy: no third-party origins at all, and `'wasm-unsafe-eval'` only if 3D preview is enabled there.

**How V-05 is run:** build both apps in production mode; deploy the policy to staging in report-only mode with a violation-report endpoint; run every page type plus the end-to-end and 3D suites; fix causes rather than adding allowances; switch to enforcing mode once there are zero violations. The final headers are recorded in the M1 report, and the test is repeated at M3, M5, M6 and before launch.

### Implementation requirements (PROPOSED)

| Area | Requirement |
| --- | --- |
| Transport | HTTPS everywhere; HSTS with preload once the domain is stable; TLS 1.2 or newer |
| Other headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` (staff: `same-origin`), a restrictive `Permissions-Policy` |
| Cookies and sessions | Two realms (section 9): customer cookie `__Host-` prefixed, `SameSite=Lax`; staff cookie scoped to `/api/v1/staff/`, `SameSite=Strict`; both `HttpOnly` and `Secure`; session ID rotated at sign-in; server-side revocation |
| Staff routes | Never cached; `X-Robots-Tag: noindex`; tighter rate limits; staff session plus second factor; network restriction per D-09 (section 2) |
| Passwords | Argon2 hashing; checks against common and breached passwords; no maximum below 64 characters |
| Input and output | DRF serializers validate every field; the Django ORM only (raw SQL only by reviewed exception); React escapes output by default, and any CMS rich text is sanitised on the server against an allow-list |
| Uploads | Pre-signed, time-limited upload URLs; type checked by content, not extension; size checked; images re-encoded; GLBs pass the validator job before approval; storage buckets private, served only through the CDN |
| Webhooks | Signature verified before anything is treated as trusted; each event stored once; replay protection by event ID and timestamp; conflicting events flagged, not applied; unknown events logged and ignored |
| Secrets | Environment variables or the hosting platform's secret store; separate secrets per environment; `.env.example` only in the repository; rotation documented |
| Access | Least-privilege database users (the app can't alter the schema in production; migrations run with a separate role); no Django superuser in business use (A-22); production access limited and logged |
| Dependencies | Lock files committed; automated vulnerability alerts; pinned versions upgraded deliberately (also V-03 for the 3D libraries) |
| Privacy | Collect only what's needed; consent for marketing and analytics; privacy notice, retention and deletion rules decided before launch (P-11, P-17) |
| Abuse | Rate limits (section 8); bot protection on registration and checkout if abuse appears; alerts on unusual refund, adjustment and staff-recovery activity |

### Security testing (see section 13)

Automated dependency and static checks on every pull request; permission tests for allowed and denied access on every protected endpoint, including a customer session against every staff endpoint; CSP validation (V-05); an external penetration test before launch (M14).

## 13. Testing and quality assurance

**APPROVED: the v1.0 test layers and Definition of Done (§13, §16). A feature is done only when its design matches the approved reference, server rules and permissions are tested (including denied access), all states are handled, tests pass, and nothing approved regresses.** PROPOSED: the tools and pipeline below. v2.1 adds the tests that prove corrections C-1 to C-7.

### Test layers and tools (PROPOSED tools)

| Layer | What it proves | Tools |
| --- | --- | --- |
| Unit | Pricing, promotions, tax, stock arithmetic, every state machine's allowed and refused transitions, validation | pytest, pytest-django, factory\_boy; Vitest for frontend logic |
| Service and database | Transactions, locking, constraints, idempotency, outbox | pytest against a real PostgreSQL (never SQLite) |
| API | Every endpoint: allowed and denied roles, validation errors, rate limits, the error format | DRF test client; Schemathesis fuzzing from the OpenAPI schema |
| Contract | Frontend and API agree | Generated client compiles in CI; schema drift fails the build |
| Integration | Payment, courier, email and SMS adapters | Fake providers in CI; provider sandboxes in staging |
| Component | UI components and states (loading, empty, error, disabled) | React Testing Library |
| End-to-end | Register, sign in, browse, product detail, cart, checkout, payment return, order history, returns; staff sign-in and core staff tasks | Playwright on staging, desktop and phone viewports |
| 3D | Framing, touch, keyboard, loading strategy, failure paths, Draco and Meshopt, cleanup | The P-09 Playwright suite, ported to the production viewer; plus the section 17 device procedure |
| Concurrency | Two shoppers buying the last item: only one succeeds, with no negative stock; expiry racing a late payment | Parallel tests against PostgreSQL |
| Accessibility | WCAG 2.2 AA target (R-09) | axe-core in Playwright; manual keyboard, VoiceOver and TalkBack checks |
| Performance | Page speed, API response times, load on checkout and catalogue | Lighthouse CI, k6; targets from P-18 |
| Security | Dependencies, static analysis, permissions, external penetration test | pip-audit, npm audit, Bandit, Semgrep; permission tests; external test at M14 |
| CSP | Zero violations under the enforced policy across every page type and the 3D suite (V-05) | Report-only then enforced policy on staging, Playwright |
| UAT | Representative customers and store staff | Scripted sessions on staging; documented sign-off |

### Tests required by the v2.1 corrections

| Correction | Tests that must pass |
| --- | --- |
| C-1 Staff separation | A customer session gets `401` on every staff route (route list generated from the URL configuration); a staff account can't sign in through the customer endpoint and vice versa; suspension revokes every session before the next request; email-only staff reset is refused; recovery codes work once; the last Owner can't be suspended; `is_superuser` grants nothing |
| C-2 Payments and refunds | With the fake provider: duplicate callbacks applied once; out-of-order callbacks never move a payment backwards; conflicting callbacks flagged; a missing callback is recovered by the status check and by settlement reconciliation; success after expiry follows D-07; payment and refund retries never double-charge or double-refund; a failed refund ends in Manual required with an alert |
| C-3 Cash on delivery | Delivery doesn't mark the order paid; each COD order reconciles once against its remittance line; mismatches and missing lines become discrepancies with alerts; undelivered COD cancels the payment |
| C-4 Inventory | Cancellation before dispatch restores sellable stock at once; after dispatch, nothing returns until inspection; damaged units never become sellable; reservations never reference non-sellable stock; expiry checks the provider first |
| C-5 CSP | V-05 passes on the production build |
| C-6 Routing | `/staff/` and `/api/v1/staff/` responses are `no-store` and `noindex`; Django admin and health routes aren't publicly reachable in the production configuration |
| C-7 Monitoring | Each alert in section 14 fires in staging when its condition is simulated |

### Continuous integration (PROPOSED)

Every pull request runs, and must pass:

1. Formatting and linting: Ruff for Python, ESLint and Prettier for TypeScript.
2. Type checks: mypy (with django-stubs) and `tsc --noEmit`.
3. Boundary check: import-linter for the backend's app boundaries.
4. Unit, service and API tests with a PostgreSQL service container.
5. Migration check: no missing migrations; migrations apply cleanly to an empty database and to a copy of the previous release's schema.
6. OpenAPI schema generation and client build.
7. Frontend tests and a production build of both apps.
8. Dependency and static security scans.

Merges to the main branch deploy to staging automatically, where the end-to-end, 3D, CSP and accessibility suites run. Production releases need those to pass, plus your approval (MTS v1.0 §14).

## 14. Deployment, infrastructure, monitoring and alerts

**APPROVED: hybrid cloud with separately managed application hosting, PostgreSQL, object storage and CDN; local, staging and production environments; automated deployment, monitoring and independent backups; start small and scale on measured demand (MTS v1.0 Module 10, §14). Added in v2.1: the three routes (A-27) and business alerts for payments and COD (A-28). PENDING: provider, region, sizes, tooling and budget (P-10); alert thresholds, channels and owners (D-10).** The design is provider-neutral.

### Runtime services (PROPOSED)

| Service | What runs | Route | Scaling |
| --- | --- | --- | --- |
| `storefront` | Next.js storefront server (Node.js) | `/` | Horizontal, stateless |
| `staff` | Next.js staff dashboard | `/staff/` | One small instance |
| `api` | Django + DRF under Gunicorn | `/api/v1/` | Horizontal, stateless |
| `worker` | Celery workers (notifications, webhooks, status checks, reconciliation, reports, 3D validation) | — | Horizontal, by queue |
| `scheduler` | Celery Beat, exactly one instance | — | Single |
| PostgreSQL | Managed service with automated backups and point-in-time recovery | — | Vertical first; read replica for reports later |
| Redis | Managed service | — | Vertical |
| Object storage | Private buckets for media, 3D assets and exports | `/media/` (approved files only) | Managed |
| CDN and reverse proxy | Routing by prefix, caching rules and staff restrictions from section 2; TLS | All | Managed |

All application services ship as Docker images built once in CI and promoted unchanged from staging to production.

### Environments

| Environment | Purpose | Rules |
| --- | --- | --- |
| Local | Development | Docker Compose with PostgreSQL, Redis and S3-compatible storage (MinIO); a local proxy reproducing the three routes; fake payment and courier providers; seeded demo data |
| Staging | Integration, end-to-end tests, UAT, CSP report-only runs | Production-like configuration and routes; provider sandboxes; anonymised or synthetic data only |
| Production | Live store | HTTPS; restricted, logged access; monitoring and alerts; backups; release approval |

### Release process (PROPOSED)

1. Merge to main: CI builds images and deploys to staging automatically.
2. Staging suites pass (section 13).
3. You approve the release.
4. Database migrations run first, written expand-then-contract so the previous release keeps working.
5. New images roll out with health checks. Rollback means redeploying the previous image, and is documented in the runbook.
6. Larger features, including the public 3D viewer, ship behind feature flags.

### Hosting considerations for the Pakistan launch

- Choose a region with low latency to Pakistan, and a CDN with points of presence in or near Pakistan. Confirm any data-residency obligations under P-11.
- Start with the smallest sizes that pass load testing, and scale from monitoring data, not guesses (A-19).

### Monitoring and alerts (A-28; thresholds PENDING D-10)

No numeric thresholds are set here. Each alert has a severity: **critical** (someone acts now), **high** (same working day) or **digest** (daily summary). Where an alert says "each", every single occurrence alerts, because it should never happen.

| Area | Alert | Severity |
| --- | --- | --- |
| Payments | Payment failure rate above threshold, per provider and method | High |
| Payments | Provider unavailable (circuit breaker open) | Critical |
| Payments | Webhook signature failures above threshold | High |
| Payments | Duplicate callbacks above their normal level (each duplicate is also counted) | Digest; High on a spike |
| Payments | Conflicting callback, such as "failed" after "succeeded" (each) | High |
| Payments | Payment still pending after the provider's window has closed (each) | High |
| Payments | Success found only by reconciliation, meaning a callback was missed (each) | High |
| Payments | Success after the order expired, handled under D-07 (each) | High |
| Payments | A second successful payment on one order, a double charge (each) | Critical |
| Refunds | Refund reaches Manual required, or stays Processing beyond threshold (each) | High |
| COD | Delivered order with no remittance after the expected window (D-11) | High |
| COD | Reconciliation mismatch or discrepancy (each) | High |
| COD | Remittance batch total doesn't equal the sum of its lines (each) | High |
| Inventory | Database blocked an oversell, or a stock constraint failed (each) | Critical |
| Inventory | Unusual volume of reservation expiries | Digest |
| Staff security | Staff sign-in failures above threshold; any staff recovery, suspension or revocation | High; recovery and suspension also notify Owners |
| Platform | Errors, uptime, worker queue depth, outbox backlog, failed notifications | Per P-10 tooling |

### Operations (Module M18)

- **Monitoring:** error tracking, uptime checks, structured logs, and the alerts above, each with a named owner (D-10).
- **Backups:** managed daily backups plus point-in-time recovery, and a separate copy outside the primary provider. Restore tested on a schedule. Frequency, retention, RTO and RPO are PENDING (P-17).
- **Runbooks:** deployment, rollback, incident response, payment-provider outage (pause online payment, keep COD if approved), missed-callback recovery, refund failure, COD discrepancy, courier outage (manual booking), staff account compromise (suspend, revoke, recover), database restore.

## 15. Project folder structure

**PROPOSED (R-02): one repository holding both Next.js apps, the shared packages, the Django backend, infrastructure, end-to-end tests and documentation.** The P-09 prototypes are kept in the repository for reference but are not part of any build (A-10). v2.1 changes only the staff app's route, adds finance and staff-account screens, a local routing proxy and the CSP configuration.

```
aurevon/
├─ apps/
│  ├─ storefront/                 Next.js storefront, served at /
│  │  ├─ app/[locale]/            routes: home, shop, products/[slug], cart, checkout, account, auth, pages/[slug]
│  │  ├─ features/                feature folders: catalog, product, cart, checkout, account, cms
│  │  ├─ components/              storefront-only components
│  │  ├─ lib/                     API calls, formatting, analytics
│  │  ├─ public/3d/draco/<three-version>/   Draco decoder, copied from three.js at build time
│  │  └─ tests/
│  └─ staff/                      Next.js staff dashboard, served at /staff/ (basePath); private, not indexed
│     ├─ app/                     routes: sign-in, catalog, inventory, orders, finance (payments, refunds,
│     │                           remittances), customers, support, cms, promotions, reports, staff, settings
│     ├─ features/
│     └─ tests/
├─ packages/
│  ├─ design-tokens/              AureVon colours, type, spacing as CSS custom properties
│  ├─ ui/                         shared accessible components
│  ├─ api-client/                 typed client generated from the OpenAPI schema
│  ├─ viewer3d/                   React Three Fiber viewer, from the P-09 v2 reference
│  ├─ i18n/                       English and Urdu messages, locale helpers
│  └─ config/                     shared TypeScript, ESLint and Prettier settings
├─ backend/
│  ├─ config/                     settings/ (base, local, staging, production), urls, celery, asgi, wsgi
│  ├─ apps/                       accounts, customers, catalog, inventory, suppliers, cart, checkout,
│  │                              orders, payments, shipping, promotions, returns, support, cms,
│  │                              notifications, analytics, localization, reviews, audit
│  ├─ integrations/               payments/, shipping/, messaging/, storage/ (base, fake, one file per provider)
│  ├─ common/                     base models, money, state-machine helper, errors, pagination
│  ├─ templates/                  email templates
│  ├─ tests/                      cross-module, realm-separation and concurrency tests
│  ├─ manage.py
│  └─ pyproject.toml
├─ e2e/                           Playwright: shopping journey, staff journey, csp/, 3d/ (ported P-09 suite)
├─ infra/
│  ├─ docker/                     Dockerfiles for storefront, staff, api, worker
│  ├─ compose.yaml                local stack: PostgreSQL, Redis, MinIO, Mailpit, routing proxy
│  ├─ proxy/                      local reverse proxy reproducing /, /staff/ and /api/v1/
│  ├─ csp/                        storefront and staff policies, and the V-05 results
│  └─ deploy/                     provider-specific files, added after P-10
├─ docs/
│  ├─ mts/                        MTS v1.0 and v2.0 (preserved), v2.1
│  ├─ decisions/                  one short record per approved decision
│  ├─ milestones/                 milestone briefs and completion reports
│  └─ runbooks/                   deploy, rollback, incidents, payments, COD, staff compromise, restore
├─ prototypes/
│  ├─ v1/                         P-09 v1 prototype, preserved unchanged
│  └─ v2/                         P-09 v2 reference viewer, serve_v2.py, Draco files
├─ .github/workflows/             CI and deployment pipelines
├─ .env.example                   every setting, no real secrets
├─ package.json, pnpm-workspace.yaml
└─ README.md                      setup in under 15 minutes
```

| Rule | Why |
| --- | --- |
| Apps may import packages; packages never import apps | Keeps shared code reusable and testable |
| `api-client` is generated, never edited by hand | The API schema stays the single contract |
| Each backend app follows the layout in section 5 | Predictable code, enforceable boundaries |
| Provider code lives only in `backend/integrations/` | Changing a provider never touches business logic |
| The staff app calls only `/api/v1/staff/` | Keeps the two authentication realms apart (A-22) |
| Prototypes are reference only | Production code is rebuilt cleanly in `packages/viewer3d` |

## 16. Development phases and implementation priorities

**APPROVED: incremental delivery, one approved design and feature slice at a time, each tested and reviewed before the next (A-20). PROPOSED: the phase order below, keeping v1.0's milestone numbers.** After the foundation, the four tracks can run in parallel where people allow. Only the public switch-on of 3D waits on the outstanding P-09 validations. v2.1 places each correction in the milestone that builds it.

&#91;embedded content: Development tracks · foundation, 4 tracks, 1 gate, launch\]

Commerce core is the critical path to launch. The 3D viewer is built in M6 like any other feature, but stays switched off for shoppers until V-01, V-02 and V-03 pass. If the gate isn't passed by launch, the store launches with product images and switches 3D on later.

| Phase | Delivers | Needs first | Decisions needed before it starts |
| --- | --- | --- | --- |
| M0 Decision lock | Approval of this MTS v2.1; the M0 report | — | P-01 (confirm Next.js), P-20 (launch scope) |
| M1 Project foundation | Monorepo, Docker Compose stack with the local routing proxy for `/`, `/staff/` and `/api/v1/`, CI pipeline, Django and Next.js skeletons, settings, health checks, staging environment; first CSP run (V-05) | M0 | P-04 (local database), P-10 for staging hosting |
| M2 Data and identity | Core schema and migrations; customer and staff realms with separate sign-in and sessions; staff roles and permissions; suspension, revocation and recovery; audit log | M1 | P-05 (roles, two-factor, session lengths), D-12 (Owner recovery), D-09 before staff routes are exposed on staging |
| M3 Design system and shell | Tokens, shared components, layout, navigation, footer, Urdu right-to-left, accessibility baseline; CSP re-run | M1 | P-19 (final palette and design references) |
| M4 Storefront and CMS | Homepage sections, collections, content and policy pages, CMS screens, SEO basics | M2, M3 | D-08 (CSP strategy, which affects static pages) |
| M5 Catalogue and product detail | Products, variants, SKUs, per-variant stock records and stock locations, images, search and filters, product page with poster image; CSP re-run | M2, M3 | P-12 (launch catalogue) |
| M6 3D product experience | `viewer3d` package, asset pipeline and approval, feature flag, ported test suite; CSP re-run with 3D | M5 | D-01 to D-05 are inputs; public release gated by V-01 to V-03 |
| M7 Customer journey | Registration and login screens, account, addresses, wishlist, cart, checkout, stock reservation | M5 | P-15 (guest checkout), D-06 (reservation expiry) |
| M8 Orders and payments | Order and payment state machines, payment adapter with fake and sandbox providers, callback handling, status checks, settlement reconciliation, refund states and retries, payment alerts, transactional email | M7 | P-06 (providers), P-11 (tax), P-08 for email, D-07 (late payments), D-10 (alert thresholds) |
| M9 Inventory and suppliers | Adjustments, return inspection into sellable, quarantine and damaged stock, low-stock alerts, suppliers, purchase orders, receiving, valuation | M5 | — |
| M10 Shipping, tax and localization | Zones and rates, courier adapter, tracking, COD remittance batches and per-order reconciliation, tax rules, Pakistan formats | M8 | P-07, P-13, P-11, D-11 (COD remittance terms) |
| M11 Marketing and communication | Coupons, scheduled promotions, SMS, abandoned-cart flows with consent, preferences | M8 | P-08 |
| M12 Support and returns | Contact and tickets, returns and exchanges, refund workflow | M8, M9 | P-14 |
| M13 Analytics and reports | Event definitions, dashboards, exports, scheduled reports | M8 | P-16 |
| M14 Hardening | Security review and penetration test, performance and load tests, accessibility audit, backup restore test, every alert tested, runbooks, final CSP run | All launch features | P-17, P-18 |
| M15 UAT and launch | Full regression, staff training, launch checklist, production release, post-launch monitoring | M14 | Release approval |

Each phase is split into small vertical slices. Each slice goes through acceptance criteria, implementation, tests, review and approval, then merge, with a completion report listing changed files, setup steps, tests run and known limitations (MTS v1.0 §17.1).

## 17. Outstanding validations

**Five validations are outstanding: four for the 3D experience and, new in v2.1, the CSP test against the real Next.js build (V-05). None blocks unrelated development.** The catalogue, product pages, checkout, payments, inventory and every other track proceed regardless, and product pages always work with images alone (A-14).

| ID | Validation | How | Blocks | Does not block |
| --- | --- | --- | --- | --- |
| V-01 | Physical-device testing: an iPhone with Safari, a mid-range Android with Chrome, a low-end Android with Chrome | The 14-case procedure and exit criteria in the P-09 Production Readiness Report, section 7, using `serve_v2.py --lan` | Switching the 3D viewer on for shoppers | All other development, including M6 build work |
| V-02 | A genuine AureVon garment GLB | Same procedure, with the real model and its Draco and Meshopt copies | Switching 3D on; the asset budget (D-01); the colour-variant method (D-03) | All other development |
| V-03 | The v2 validation suite re-run on the production versions of React, React Three Fiber and Three.js (expected React 19 with R3F 9) | Port the P-09 Playwright suite into `e2e/3d/` during M6 | Switching 3D on | M1–M5 and all non-3D work |
| V-04 | KTX2/Basis texture evaluation | Compare GPU memory and quality on the V-01 devices | The asset budget decision (D-01) only | Switching 3D on |
| V-05 | CSP validated against the production Next.js build (A-26) | Report-only, then enforced, on staging, across every page type and the end-to-end and 3D suites (section 12); first at M1, again at M3, M5, M6 and before launch | Production release; also informs D-08 before M4 | All development; each run records its results |

P-09 is closed only when you accept the V-01 to V-03 results. Until then its technology decision (A-08) stands, but it is not marked production-ready.

### P-09 defect record (unchanged from v2.0)

All six defects found during P-09 are fixed in the v2 reference viewer, and their fixes are requirements for `packages/viewer3d`.

| ID | Defect | Fix (now a requirement) |
| --- | --- | --- |
| D1 | Endless spinner on corrupt, unsupported or Draco files | Read the GLB header first; check required extensions; catch errors that GLTFLoader throws as well as those it reports; time limits on decoding; a specific message for every failure |
| D2 | 3D that arrived late stayed hidden behind the fallback | No fixed switch-over; 3D takes over whenever it is ready, and "Show 3D" appears once it is |
| D3 | 3D kept rendering behind the image | Render only when 3D is showing, on screen, in a visible tab |
| D4 | A rigid 10-second loading timeout | Image first; loading continues; messages change with time, but failure is declared only for real errors, with "Try again" |
| D5 | "Try again" didn't recover after a network failure, because the browser caches failed module downloads | "Try again" reloads the page and keeps the shopper's selections. In production, a bundled build should make retries of individual chunks possible, which V-03 re-tests |
| D6 | Meshopt models showed a raw error, and logged a console error, where WebAssembly is blocked | A plain message; the Meshopt decoder loads only where WebAssembly is allowed; the production policy allows `'wasm-unsafe-eval'` (section 12) |

## 18. Open decisions register

**29 decisions remain open: 17 carried from v1.0, 6 from P-09, and 6 new in v2.1 (D-07 to D-12), which the approved corrections require but which need your decision.** None is assumed approved. Each blocks only the milestone named beside it. Closed since v1.0: P-02 (Django with DRF), P-03 (PostgreSQL; provider moves into P-10) and the P-09 technology choice (its validations stay open in section 17).

| ID | Decision | Current proposal | Needed before | Status |
| --- | --- | --- | --- | --- |
| P-01 | Frontend framework and build tooling | Next.js with TypeScript in a pnpm monorepo, bundling React, R3F and Three.js | M1 | Proposed |
| P-04 | Local development database and migration strategy | PostgreSQL in Docker Compose, same major version as production; Django migrations, expand-then-contract | M1 | Proposed |
| P-05 | Role names, permission matrix, staff two-factor policy, staff session lengths, dual approval | The candidate matrix and realm design in section 9 (session lengths added in v2.1) | M2 | Proposed |
| P-06 | Payment providers and methods, including cash on delivery | Research candidates in section 10 | M8 | Pending |
| P-07 | Couriers and return logistics | Research candidates in section 10 | M10 | Pending |
| P-08 | Email and SMS/OTP providers | — | M8 (email), M11 (SMS) | Pending |
| P-10 | Cloud provider, region, sizes, budget, deployment tooling, monitoring; final security policy | Provider-neutral design in section 14 | M1 (staging) | Pending |
| P-11 | Tax, invoicing, privacy and consumer law, data residency | Needs local professional advice | M8 | Pending |
| P-12 | Launch catalogue: products, sizes, colours, SKUs, prices | — | M5 | Pending |
| P-13 | Shipping zones, fees, free-shipping thresholds, delivery promises | Table rates by zone (section 10) | M10 | Pending |
| P-14 | Return window, eligibility, exchange and refund policies | — | M12 | Pending |
| P-15 | Guest checkout | The architecture supports both answers | M7 | Pending |
| P-16 | Analytics definitions, consent model, report schedule | — | M13 | Pending |
| P-17 | Backup frequency, retention, RTO and RPO | — | M14 | Pending |
| P-18 | Supported browsers and devices; performance budgets | Set from V-01 device data | M14 | Pending |
| P-19 | Final global palette and page design references | — | M3 | Pending |
| P-20 | Launch scope versus post-launch | The priorities in section 7 | M0 | Proposed |
| D-01 | 3D asset budget: file size, triangles, textures, GPU memory | None until V-01 and V-02 report (A-13) | 3D switch-on | Pending |
| D-02 | Standard 3D compression | Draco, Meshopt or both, after V-02 | M6 | Pending |
| D-03 | Colour-variant method for real garments | Per-colour models, glTF material variants, or recolour in code | M5–M6 | Pending |
| D-04 | Who produces garment 3D models, and with what tools | — | M6 | Pending |
| D-05 | Desktop mouse-wheel zoom over the viewer | Keep, require a modifier key, or click to activate | M6 | Pending |
| D-06 | Reservation expiry for unpaid online orders | Longer than the payment provider's own session timeout plus a margin; at least 30 minutes; a store setting (updated in v2.1) | M7 | Proposed |
| D-07 | What happens when a payment succeeds after the order expired | Re-reserve and restore the order if stock allows; otherwise refund automatically; alert staff either way (section 10) | M8 | Proposed |
| D-08 | CSP strategy for the Next.js storefront | Nonce-based (all pages render dynamically) or hash-based (static pages kept); chosen from the V-05 results | M4 | Pending |
| D-09 | Network restriction for `/staff/` and `/api/v1/staff/` | None beyond authentication, an IP allow-list, or a zero-trust access service | Exposing staff routes on staging (M2) | Pending |
| D-10 | Alert thresholds, channels and owners | The alert list in section 14, without numbers | M8 | Pending |
| D-11 | COD remittance terms: expected remittance window, fee handling, discrepancy tolerance | Depends on the couriers chosen (P-07) | M10 | Pending |
| D-12 | Owner account recovery arrangements | For example, always keep at least two active Owner accounts, plus a documented break-glass procedure | M2 | Pending |

When a decision is made, its status changes here and it moves to the approved register in section 1, with the date and reason.
