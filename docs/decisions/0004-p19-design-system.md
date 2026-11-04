# 0004 — P-19 design system: palette, typography, logo

Date: 4 November 2026 · Decided by: Talha (product owner) · Blueprint: MTS v2.1 §1 (A-03, A-04), §3, §16 (M3)
Status: **APPROVED** (items 1–4 and 6) · Item 5 recorded as a constraint, not a design decision

Closes P-19 for palette, typography and logo. A-03 is unchanged; these decisions extend it.

## Approved

| # | Decision |
| --- | --- |
| 1 | **Functional colours approved:** white #FFFFFF (cards, inputs), muted text #6B6461, field border #8C7F78, error #9A2B2B, success #2E5E3A. **The focus ring changes from champagne gold to charcoal #121212.** Gold stays as hairlines, accents on dark surfaces and 3D; never text or focus on light surfaces (2.2:1). |
| 2 | **Interface font: Inter** (not Satoshi). Playfair Display for headings, product names on the product page and brand story; never forms, prices or tables. |
| 3 | **Urdu: Noto Nastaliq Urdu** for reading text (line-height 1.9) and **Noto Naskh Arabic** for interface controls. |
| 4 | **Registration palette "Burgundy & Blush"** (#70263D, #E8C5CC, #FAF7F4, #292629) is used **exclusively on the registration page**; login and forgot-password use the core palette. |
| 6 | **Logo:** the interim **AUREVON** wordmark in Playfair Display capitals until an official logo file is supplied. |

All fonts are OFL-licensed and self-hosted through `@fontsource-variable` / `@fontsource` packages (no third-party font host, MTS §12).

## Item 5 — A-04 design references (constraint)

The previously approved visual direction and page designs (A-04) remain approved, but the original reference
files are not available in the project. Therefore:

- No final storefront page appearance is invented or finalised. Homepage, Shop All, product detail, cart,
  checkout, login, registration and account visuals wait for the A-04 files.
- M3 proceeds with what does not depend on them: tokens, typography, accessibility, shared components,
  right-to-left support and the technical shell (locale routing, landmarks, skip link, language switch).
- The header, navigation and footer are built as **provisional structure**: correct semantics and behaviour,
  neutral token-based styling, clearly marked in code and in the M3 report. Their final layout is fitted to the
  A-04 homepage and Shop All references when supplied, before M4 page work.

## Remaining from the P-19 proposal (PROPOSED defaults, confirm against A-04)

Built as defaults because they follow from approved tokens, and easy to retune once the A-04 files arrive:
type scale (Display 56/38, H1 40/30, H2 30/24, H3 22/20, body 16/1.6, small 14, caption 12; caps labels
12–14 with 0.08–0.12em tracking), 4px spacing grid, 1440px maximum width, 4:5 product crops, sharp corners,
charcoal primary / outline secondary buttons, underlined links, 200–300ms motion with reduced-motion respected,
staff app on the same identity, denser, without gold.

## Consequences

- MTS v2.1 is not edited (it is an approved, preserved document); this record is the register entry for P-19.
  The next MTS revision moves P-19 into the approved register as A-29.
- M3 can start. M4 page visuals need the A-04 files.
