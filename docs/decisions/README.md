# Decision register (since MTS v2.1)

MTS v2.1 §1 and §18 are the register as approved on 4 November 2026. MTS v2.1 is a preserved document, so
decisions made since then are recorded here and in the numbered records; the next MTS revision folds them in.

## Decided since MTS v2.1

| ID | Decision | Record | Date | Status |
| --- | --- | --- | --- | --- |
| P-01 | Next.js + TypeScript, pnpm monorepo, React/R3F/Three.js bundled | 0001 | 4 Nov 2026 | APPROVED |
| P-04 | PostgreSQL in Docker Compose at production's major version; expand-then-contract migrations | 0001 | 4 Nov 2026 | APPROVED |
| P-20 | MTS §7 priorities are the launch-scope baseline | 0001 | 4 Nov 2026 | APPROVED |
| R-03 | Toolchain and version pins | 0002 | 4 Nov 2026 | In effect |
| P-05 | Six staff roles, permission matrix, TOTP for staff, session lengths, dual refund approval | 0003 | 4 Nov 2026 | APPROVED |
| D-12 | Owner recovery: two Owners before launch, 24-hour assisted recovery, sealed break-glass | 0003 | 4 Nov 2026 | APPROVED |
| P-19 | Functional colours (values retuned in 0008), focus ring, Inter, Nastaliq + Naskh for Urdu, registration palette, interim wordmark | 0004 | 4 Nov 2026 | APPROVED (A-04 files still to supply) |
| D-08 | CSP with a per-request nonce and `'strict-dynamic'`, both apps; HTML never publicly cached | 0005 | 4 Nov 2026 | APPROVED, implemented |
| D-01–D-05 | 3D: provisional warnings only (no final budget), Draco, material variants per colour, external CLO 3D / Marvelous Designer specialist, Ctrl/⌘ + wheel zoom | 0007 | 5 Nov 2026 | APPROVED |
| A-03 | Core palette replaced by "Midnight Indigo & Amber" (#111322, #191D35, #D99A32, #E8B968, #F5F3EE, #85879A); functional neutrals retuned; typography unchanged | 0008 | 11 Nov 2026 | APPROVED, implemented |
| P-12 | Launch catalogue rules: departments, categories, letter and numeric sizes per category, colours, SKUs, prices, product fields, images, CSV import, stock | 0006 | 4 Nov 2026 | APPROVED |

## Still open (unchanged from MTS v2.1 §18 unless noted)

| ID | Decision | Needed before |
| --- | --- | --- |
| P-06 | Payment providers and methods, including cash on delivery | M8 |
| P-07 | Couriers and return logistics | M10 |
| P-08 | Email and SMS/OTP providers | M8 (email), M11 (SMS) |
| P-10 | Cloud provider, region, CDN, budget, monitoring | Staging |
| P-11 | Tax, invoicing, privacy, data residency | M8 |
| P-13 | Shipping zones and fees | M10 |
| P-14 | Returns policy | M12 |
| P-15 | Guest checkout | M7 |
| P-16 | Analytics definitions and consent | M13 |
| P-17 | Backups, RTO, RPO | M14 |
| P-18 | Supported browsers and devices; performance budgets | M14 |
| D-06 | Reservation expiry | M7 |
| D-07 | Late payment after expiry | M8 |
| D-09 | Network restriction for staff routes | Staff routes on staging |
| D-10 | Alert thresholds, channels, owners | M8 |
| D-11 | COD remittance terms | M10 |

Outstanding validations V-01 to V-05 are tracked in MTS §17; V-05 records are in `infra/csp/`.
