# AureVon M4 Completion Report: Storefront and CMS

**Date:** 4 November 2026
**Baseline:** MTS v2.1, decisions 0004 (P-19) and 0005 (D-08), A-04 descriptions (approved 4 Nov as the reference)
**Commits:** `15fc0fd` (slice 1: homepage, Shop All, catalogue reads), `b45575c` (slice 2: this report's scope)
**CI:** all four jobs passed on `6a2252c` (run 41836976186)
**Status:** M4 is complete. This report is awaiting your approval before M5 starts.

## 1. What was built

### Slice 1 (recap)
Homepage (hero, collections, featured, new arrivals, brand story) and Shop All (department tabs, URL filters
that work without JavaScript, sorting, four-column grid, editorial banner, double opt-in newsletter, phone
filter dialog), the public catalogue reads and the demo catalogue.

### Slice 2: storefront

| Page | What it does |
| --- | --- |
| `/collections` | Every published collection, as the homepage cards present them |
| `/collections/<slug>` | Dark introduction band (gold only on dark), the collection's pieces in the Shop All grid, sorting, paging, "Filter this collection" hands over to Shop All with every filter |
| `/pages/<slug>` | CMS content and policy pages: title, summary, headings, paragraphs, lists. Policy pages show "Last updated". An Urdu page not yet translated is shown in English, marked `lang="en"`, with a notice |
| Header and footer | Menus now come from CMS navigation (header, footer "Shop", footer "Help") |
| Homepage cards | Collection cards now open the collection page instead of a filtered Shop All |

### Slice 2: SEO (M17)

- **Canonical and hreflang** on every page: `en`, `ur` and `x-default`, absolute from `SITE_URL`.
- **One indexable URL per view:** Shop All with only a department is indexable; any other filter, sort or page
  points its canonical at the department view and carries `noindex, follow`. Sorted or paged collection views
  do the same.
- **Search titles and descriptions:** staff-editable for the homepage, Shop All, the collections index and each
  collection; content pages carry their own search fields.
- **Open Graph** title, description, URL and locale.
- **Structured data:** Organization and WebSite on the homepage, BreadcrumbList on collection and content
  pages. Each block carries the request's CSP nonce, and `<` is escaped so content can't break out of it.
  Product structured data comes with the product page in M5.
- **`/sitemap.xml`:** home, Shop All, collections, each collection and each published page, in both
  languages with their alternates.
- **`/robots.txt`:** keeps the staff app, the API, cart, checkout and account out. Outside production
  (`SITE_INDEXABLE` not `true`) it asks search engines not to index anything.
- **Redirects on URL changes:** renaming a live page adds a permanent redirect from the old address
  automatically. Staff can add their own. A redirect covers both languages; it is only consulted for an
  address that has no page, so it can never hide one.

### Slice 2: CMS behind it (M07)

**One publishing rule everywhere.** Each editable item has what the store shows and an unpublished draft.
`cms.edit` saves drafts; `cms.publish` makes anything live (publish, unpublish, homepage order and visibility,
navigation, renaming a live page); `seo.edit` covers search settings and redirects. These follow decision
0003's matrix unchanged: Owner, Store Admin and Content/Marketing hold all three.

**Content is plain text.** There is no HTML anywhere in CMS content, so nothing needs sanitising and the store
renders every value as text. Bodies are typed blocks (heading, paragraph, list). Every field has a length
limit; English is required where a field is required, Urdu is optional and falls back field by field.

**Links stay on the store.** Every link is a storefront path such as `/shop?department=women`: other sites,
`//host`, `javascript:`, locale prefixes, `/staff`, `/api` and other internal paths are refused.

**Audit.** Every live change is written to the audit log with before and after values: section and banner
publishing, homepage layout, page create/publish/unpublish/rename, navigation, search settings and redirects.
Draft saves are not audited (they change nothing shoppers see).

**Refresh on publish (decision 0005).** CMS reads are cached for at most a minute. After a publish commits,
the API worker calls the storefront's internal endpoint, which drops the cached data, so the next visitor sees
the change. `/internal/` is never routed by the proxy, and the call needs a shared secret. If the call fails,
the worker retries and pages still refresh within the minute.

**New public API:** `GET /cms/pages`, `/cms/pages/{slug}`, `/cms/navigation`, `/cms/seo/{key}`,
`/cms/redirects/resolve`, `/catalog/collections/{slug}`.
**New staff API:** `/staff/cms/home-sections` (+ layout, draft, publish), `/staff/cms/banners` (+ visibility,
draft, publish), `/staff/cms/pages` (+ settings, draft, publish, unpublish), `/staff/cms/navigation/{menu}`,
`/staff/seo`, `/staff/redirects`.

### Slice 2: staff dashboard

- **Content › Homepage:** order and visibility of the five sections; each section's copy in English and Urdu
  side by side; Save draft, Publish, Discard, View on the store.
- **Content › Banners:** the Shop All editorial banner, with visibility.
- **Content › Pages:** list with status; new page; editor with address, type, bilingual fields and a block
  editor for the body; publish, unpublish, discard. Renaming a live page warns that the old address will
  redirect.
- **Content › Navigation:** the three menus: labels in both languages, links, order.
- **SEO:** search titles, descriptions and "hide from search engines" per page; Redirects with add and remove.
- The staff menu shows Content and SEO only to roles that hold the permissions.

### Demo content
Six pages: Our story, Contact us, and four policy pages (Shipping, Returns and exchanges, Privacy, Terms of
sale). **The policy pages are placeholders on purpose:** they say the policy is being finalised and name the
open decision (P-13, P-14, P-11). No delivery time, fee, return window or legal term has been invented.

## 2. Tests

| Check | Result |
| --- | --- |
| Backend pytest (PostgreSQL) | **162 passed** (30 new) |
| End-to-end, desktop and phone, through the proxy | **116 passed**, 4 skipped (phone-only checks on desktop) |
| ruff, mypy (strict), import boundaries, migrations, deploy check, bandit | Pass |
| Prettier, ESLint, TypeScript, Vitest, both production builds | Pass |
| API contract (schema and typed client regenerated and committed) | Pass |

**What the new tests prove**
- **Permissions:** Support, Accountant and Inventory Manager are refused every content and SEO endpoint;
  Owner, Store Admin and Content/Marketing can edit and publish; a role with edit but not publish can save
  drafts but can't publish or change navigation. Every new staff route is covered by the existing realm test
  (customer sessions get `401`), which now fills every path parameter automatically.
- **Drafts:** a draft never reaches the public API; publishing does, refreshes the storefront once, and is
  audited with before and after values; discarding keeps the live copy.
- **Validation:** off-site, protocol-relative, `javascript:`, locale-prefixed, staff and API links are refused;
  unknown fields, HTML block types, extra block properties, empty bodies and bad addresses are refused.
- **Redirects:** renaming a live page twice leaves no chain; renaming back removes the redirect and leaves no
  loop; duplicates, self-redirects, chains, locale prefixes and reserved paths are refused.
- **End to end, staff:** the Owner creates a page (404 on the store while it is a draft), publishes it, saves a
  change (store unchanged), publishes again and the store shows it within seconds, inside the one-minute cache
  window, so only the refresh on publish can explain it; then renames it and the old Urdu address redirects to
  the new one; the redirect and the audit entries are listed.
- **End to end, store:** collection index and pages, homepage cards, sorting and hand-over to Shop All, 404 for
  unknown collections, content and policy pages, Urdu right-to-left, footer links from the CMS, canonical and
  hreflang tags, noindex on filtered views, sitemap, robots, `/internal/` unreachable, and no detectable
  WCAG 2.2 AA violations (axe) on the new pages.

## 3. V-05 run 4 (CSP)

Zero violations on the four new page types, desktop and phone, with structured data present. No policy change
was needed. Details: `infra/csp/V-05-run-4.md`.

## 4. CI

All four jobs passed on `6a2252c`, including the Docker Compose stack with the full end-to-end suite and the
staff content journey. The first run on `b45575c` failed one formatting check on a Markdown record; fixed in
`6a2252c`, no code change.

## 5. Choices made in implementation (not new architecture)

1. **Draft and live copies on the same record,** not a separate revision table. One draft per item is enough
   at launch; revision history is visible in the audit log.
2. **Plain-text blocks instead of rich text.** MTS §12 allows sanitised rich text; plain blocks remove the
   sanitiser entirely. Inline links and bold inside paragraphs are not possible yet; easy to add as typed
   inline marks if you want them.
3. **Draft saves are not audited;** publishing is.
4. **Navigation, homepage order and banner visibility are live on save** (they need `cms.publish`), rather than
   drafted.
5. **Next.js streams page metadata after the page for ordinary browsers;** search crawlers receive it in
   `<head>` before the page. This is Next.js 16's default and needs no change.

## 6. Limitations and items for you

1. **Visuals stay provisional** (decision 0004, item 5): collection and content pages follow the A-04
   descriptions and the homepage and Shop All patterns, but have no reference of their own.
2. **Product images** are still code-drawn illustrations; your decision on photography or Flow images is open.
3. **Policy texts** wait for P-11, P-13 and P-14. Contact details wait for the support set-up.
4. **Urdu copy** (new pages, menus, search text) needs a native-speaker review, like M3's.
5. **Not built in M4:** scheduled publishing (M07 lists it; it fits with promotions in M11), previewing a draft
   on the storefront before publishing, collection editing (catalogue editing arrives with M5).
6. **Local verification:** Docker is still unavailable in my workspace, so the stack ran as local processes
   behind Caddy and Mailpit, the same way as M1. CI runs the Docker stack.

7. **Routes from later milestones aren't linked yet** (`apps/storefront/lib/features.ts`): the search,
   account and bag icons are shown but inactive ("coming soon"), and product cards aren't links until the
   product page exists (M5; search M5; account and bag M7). An end-to-end check crawls every internal link
   on the main pages and fails on any broken one.

## 7. Next

**M5 Catalogue and product detail** needs **P-12, the launch catalogue** (products, sizes, colours, SKUs,
prices). Nothing is started until you approve this report.
