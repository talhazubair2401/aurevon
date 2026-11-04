# AureVon M5 Completion Report: Catalogue and Product Detail

**Date:** 4 November 2026 · **Baseline:** MTS v2.1, decision 0006 (P-12)
**Commits:** `1a2a902` (catalogue rules, stock records, product page, search), `d9a34dc` (staff catalogue and
CSV import), `6245ac4` (product images) · **CI:** all four jobs green on `6245ac4`
**Status:** awaiting your approval before M6.

## Built
- **Catalogue rules (decision 0006):** categories with their own ordered sizes (letters or numbers) and size
  charts in cm; a staff-managed colour list; style numbers; one base price per product with per-variant
  overrides; SKUs `AV-{category}-{style}-{colour}-{size}`, generated once and never changed.
- **Stock records (M14 start):** sellable Main warehouse plus quarantine and damaged locations; one record per
  variant at 0; the database refuses negative stock and over-reservation. Quantities are entered in M9.
- **Product page** `/products/<slug>`: image first, colour and size by link (works without JavaScript), price
  and stock read fresh on every view, size chart, details, Product structured data, swatches under the title
  and price on phones (A-12). "Add to bag" is inactive until M7.
- **Search** `/search`: PostgreSQL full-text in English and Urdu, prefix matching on the last word, sorting,
  paging. The header search icon is active.
- **Staff catalogue:** products (drafts, details in both languages, colour-by-size grid, prices with
  re-confirmation, publish/archive with checks, redirect on renaming a live product), categories and sizes,
  colours, CSV import (template, dry run, all-or-nothing apply, new products as drafts), product images.
- **Images (decision #9):** checked by content, at least 1600 x 2000 and 4:5, re-encoded to WebP without
  metadata, stored once by content hash, served at `/media/` with long-term caching. A photo replaces the
  illustration for its colour.

## Tests
Backend 189 (36 new) · end-to-end 144 on desktop and phone (product page, search, staff catalogue journey with
upload, link crawl) · CSP V-05 run 5: zero violations (`infra/csp/V-05-run-5.md`).

## Choices made in implementation
1. **Uploads go through the API,** not pre-signed direct-to-storage URLs (MTS §8 proposal), so every file is
   checked and re-encoded before it is stored and the staff CSP stays `'self'`.
2. **No MinIO locally:** it no longer publishes official Docker images. Locally images live on a shared
   volume served by the proxy; the S3 adapter for production is unit-tested and verified at P-10.
3. **The migration runs in three steps** (expand, move data, contract), tested against a database from the
   previous release. Your local database upgrades on the next `--build`.
4. Demo trousers now use numeric waist sizes to exercise decision #4.

## Remaining blockers
- **Real catalogue content:** product list, size-chart measurements and photos (decision 0006, before launch).
- **Imagery decision:** photography or approved Flow images.
- **P-11:** whether shown prices include tax.
- **M6 (3D) inputs:** D-01 to D-05; public 3D release still gated by V-01 to V-03.
