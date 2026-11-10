# M7–M14 progress report (10 Nov 2026)

Commits on `main`: `80aa793` (staff orders), `d9e295e` (M9 inventory), `7273432` (M10–M14), plus e2e fixes.

## Built, integrated and tested

| Milestone | What works end to end |
|---|---|
| M7 Customer journey | Accounts, bag, guest/account checkout, order pages (earlier session); message preferences, newsletter confirm and unsubscribe pages, contact page form |
| M8 Orders and payments | Staff orders list/detail, packing, dispatch with tracking, delivered/undelivered (undelivered restocks), COD remittance and discrepancies, refund requests with dual approval, manual refunds, payment reviews, alerts; sandbox card payments, retries, late payments |
| M9 Inventory and suppliers | Stock by SKU and location, corrections that respect reserved stock, quarantine/damaged transfers, reorder levels with self-resolving low-stock alerts, suppliers, purchase orders with partial receiving |
| M10 Shipping and tax | Staff-managed zones (city → province → catch-all) and rates that checkout quotes from; effective-dated tax rules (step-up; ended, never edited); manual courier adapter; Pakistani addresses and phone normalisation; SMS adapter interface |
| M11 Marketing | Coupons and scheduled promotions with usage totals; no stacking; consented abandoned-bag reminders (once per bag change, 24 h, 7-day window, verified email, one-click unsubscribe); opt-in order-update SMS |
| M12 Support, returns | Return/exchange requests within the window; staff decide → receive → inspect into stock locations → refund (normal approvals) or no-charge exchange order; contact form (honeypot, rate limit), tickets with private rotating reply links, internal notes, assignment; support dashboard |
| M13 Analytics | Reports dashboard: gross/net sales, period comparison, daily chart with table view, products, categories, cities, customers, returns, coupons, stock; CSV exports; customer-detail export restricted, audited, formula-injection safe |
| M14 Hardening (part) | Route-level security test over every staff endpoint; backup/restore scripts with a verified round trip; k6 load script; deployment, backup, launch checklist and operations docs |

Tests: backend 256 + 107 route-security cases; frontend unit tests, types, lint, production builds; Playwright
journeys for COD fulfilment, purchase orders, delivery zone + coupon, contact → staff reply → customer reply,
reports and CSV download, with axe checks on the new storefront pages.

## Not done, and why

- Real payment provider, couriers, email/SMS providers, hosting: P-06, P-07, P-08, P-10 (adapters ready).
- Storefront behavioural analytics and scheduled report emails: P-16 (definitions and consent).
- Load test executed against staging with budgets: needs hosting (P-10) and budgets (P-18).
- Manual accessibility and cross-browser/device pass: needs P-18 device list and real devices.
- Shopper 3D: stays off until V-01..V-03 (decision 0007).
- M15 final regression on staging and the launch itself: after the decisions above.
