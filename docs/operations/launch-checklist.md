# Launch checklist

Tick each item with the date and who checked it. Items marked **decision** need the Owner.

## Decisions still open (block launch)

- [ ] **decision** P-06 payment provider chosen; adapter added; credentials in the secret store; refunds tested in
      the provider sandbox
- [ ] **decision** P-07 courier(s); until then dispatch is manual (tracking entered by staff)
- [ ] **decision** P-08 email provider (SPF, DKIM, DMARC on the sending domain) and SMS provider (optional)
- [ ] **decision** P-10 hosting; domain; TLS
- [ ] **decision** P-11 tax treatment confirmed by the accountant and entered (Settings › Tax)
- [ ] **decision** P-13 delivery zones, fees and promises entered (Settings › Delivery); demo zones removed
- [ ] **decision** P-14 return window and instructions; returns/refund/privacy/terms pages written
- [ ] **decision** P-16 analytics definitions and consent (behavioural analytics is not built until then)
- [ ] **decision** P-17 backup frequency, retention, RTO/RPO
- [ ] **decision** P-18 supported browsers/devices and performance budgets
- [ ] **decision** refund dual-approval threshold (Settings), COD order limit
- [ ] 3D: V-01, V-02, V-03 passed before shopper 3D is switched on (decision 0007); it stays off otherwise

## Content

- [ ] Real catalogue, prices, size charts and photography (demo data cleared)
- [ ] Urdu copy reviewed by a native speaker
- [ ] Contact page text, support hours; homepage and collections

## Technical

- [ ] CI green on the release commit, including full-stack e2e and the CSP run
- [ ] CSP switched from report-only to enforced after a clean V-05 period (decision 0005)
- [ ] Production settings: `SITE_URL`, `SITE_INDEXABLE=true`, HSTS, `DJANGO_ALLOWED_HOSTS`, CSRF origins
- [ ] Two Owners with authenticators and recovery codes stored offline; staff invited with least-privilege roles
- [ ] Backup taken and a restore rehearsed (`docs/operations/backup-restore.md`)
- [ ] Load test run on staging with the agreed P-18 budgets (`scripts/load/checkout.js`)
- [ ] Accessibility: automated axe checks green; a manual keyboard and screen-reader pass of checkout
- [ ] Monitoring: error alerts, uptime check on the storefront and `/health/ready`, critical staff alerts emailed
- [ ] Payment webhook URL registered with the provider; signature secret set
- [ ] A test order end to end in production with a real card, then refunded
