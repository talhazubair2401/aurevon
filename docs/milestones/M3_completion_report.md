# AureVon M3 Completion Report: Design System and Shell

**Date:** 4 November 2026
**Baseline:** MTS v2.1, decision record 0004 (P-19)
**Commit:** `cb613ca` on `main` (plus this report and the V-05 run 2 record)
**CI:** all four jobs passed on the first run
**Status:** M3 is complete within the limits of decision 0004, item 5. This report is awaiting your approval.

## 1. Decisions recorded

**Decision 0004** (`docs/decisions/0004-p19-design-system.md`) closes P-19:

| # | Decision |
| --- | --- |
| 1 | Functional colours approved; the focus ring is now charcoal, not gold |
| 2 | Inter is the interface font |
| 3 | Urdu: Noto Nastaliq Urdu for reading, Noto Naskh Arabic for controls |
| 4 | Burgundy & Blush on the registration page only |
| 5 | A-04 files unavailable: no final page visuals are invented; header, navigation and footer are provisional structure |
| 6 | Interim AUREVON wordmark in Playfair Display capitals |

The type scale, spacing, layout and motion values from the proposal are built as **PROPOSED defaults**, to be confirmed against the A-04 files. MTS v2.1 itself is not edited; the next revision moves P-19 into the approved register.

## 2. What was built

### Design tokens (`packages/design-tokens`)
- Core palette (A-03) unchanged, plus the five functional colours and the registration palette.
- Roles: surface, raised surface, inverse, muted text, field border, focus, error, success.
- Type scale (mobile and desktop), 4px spacing, 1440px maximum width, 44px touch targets, sharp corners, 200–300ms motion that drops to zero with reduced motion.
- Urdu font stacks under `:lang(ur)`: Nastaliq for reading text and headings, Naskh for controls, taller line heights, no letter-spacing (it breaks Arabic-script joining).

### Shared packages
- **`@aurevon/ui`:** Button (primary charcoal, outline secondary, text), ButtonLink, TextField, SelectField, CheckboxField, Alert, Wordmark, SkipLink, Container, TextLink, Price, Icon. Labels, hints and errors are wired with `aria-describedby`; busy buttons stay focusable; icons mirror in right-to-left.
- **`@aurevon/i18n`:** English and Urdu, text direction, money and dates through `Intl` (PKR and Asia/Karachi are settings, not code), interface messages for both languages.

### Storefront shell (`apps/storefront`)
- Locale routes `/en` and `/ur` with next-intl. `/` redirects by browser language. Both locale pages remain **statically generated**, so D-08 stays open.
- `<html lang dir>` set per locale; all four font families self-hosted, and Urdu fonts are not downloaded on English pages.
- Skip link, header, navigation, phone menu (native modal `<dialog>`: focus trapped, Escape closes, focus returns), footer, language switcher that keeps the current page, localised not-found and error pages.
- **Provisional (decision 0004, item 5):** header, navigation and footer placement and styling are neutral defaults; the home page shows only the wordmark, tagline and a note that the approved homepage arrives in M4. Navigation links point at the MTS route names and show the not-found page until those pages exist.

### Staff app
- Moved onto the tokens: charcoal focus ring, approved error and success colours, field borders, no gold.

### Housekeeping
- Removed a Redis snapshot (`dump.rdb`) that had been committed in M2, and ignored it.

## 3. Tests

| Check | Result |
| --- | --- |
| Unit: design tokens (39), UI components (13), i18n (7), API client (4) | 63 passed |
| End-to-end in CI, desktop and phone | **47 passed**, 2 skipped (phone-only tests on desktop) |
| Backend, contract, lint, types, both production builds, `pnpm audit` | Pass |

**What the new tests prove**
- Every approved text pairing meets 4.5:1, borders and focus rings meet 3:1, and gold on light surfaces is confirmed below 3:1.
- No automatically detectable WCAG 2.2 AA violations (axe) on `/en`, `/ur`, both not-found pages and the open phone menu.
- `lang` and `dir` are correct, Urdu uses Nastaliq and Naskh, the wordmark stays Playfair and left-to-right.
- The skip link is first and moves focus to main; the focus ring is charcoal; header controls are at least 44px.
- The language switch keeps the page; the phone menu traps focus, closes on Escape and opens from the right in Urdu.

## 4. V-05 run 2 (CSP)

Unchanged from run 1: only Next.js's own inline scripts (3 per storefront page). The new fonts, styles, icons and Urdu pages caused no violations. Details: `infra/csp/V-05-run-2.md`.

## 5. Limitations and items for you

1. **A-04 reference files.** Needed before M4. Until then, no storefront page has its final appearance.
2. **Urdu copy needs a native-speaker review.** The interface messages were translated by me, including the tagline.
3. **Logo.** The interim wordmark is in place; supply the official file when ready.
4. **Not tested:** physical devices and screen readers (VoiceOver, TalkBack). axe finds only automatically detectable issues; manual checks are planned for M14.

## 6. Next

**M4 Storefront and CMS** needs:
- **D-08:** nonce or hash CSP strategy. Both remain possible.
- **The A-04 homepage and Shop All files,** to finish the header, navigation and footer and build the homepage.

Nothing is started until you approve this report.
