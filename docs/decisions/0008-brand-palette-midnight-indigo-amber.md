# 0008 — Brand palette: "Midnight Indigo & Amber"

Date: 11 November 2026 · Decided by: Talha (product owner) · Blueprint: MTS v2.1 §1 (A-03), §3; decision 0004
Status: **APPROVED** — supersedes the A-03 core palette and 0004 item 1's colour values

## Decision

The core palette changes from the warm-neutral A-03 palette (off-white, charcoal, stone, deep brown, champagne
gold) to **Midnight Indigo & Amber**. There is one colour system: the tokens were replaced in place in
`packages/design-tokens` (TypeScript and CSS, kept in sync by tests), not duplicated.

| Token | Hex | Role |
| --- | --- | --- |
| Midnight Indigo | #111322 | Primary background; the dominant brand colour; text on light surfaces |
| Deep Indigo | #191D35 | Secondary surfaces, depth, raised panels on dark |
| Amber | #D99A32 | Primary accent, used selectively (hairlines, current page, 3D light). Never text on light surfaces (2.2:1) |
| Soft Amber | #E8B968 | Subtle highlights on dark surfaces |
| Warm Ivory | #F5F3EE | Light surfaces; text on dark |
| Muted Slate | #85879A | Secondary text on dark surfaces only (3.2:1 on ivory) |

Functional colours retuned to the new hues (decision 0004 item 1, values only): muted text on light #5C5F74
(5.7:1 on ivory), field border #7A7D91, ivory shade #E4E1D9 for dividers on light surfaces (a step of Warm Ivory,
not a new hue), error #9A2B2B and success #2E5E3A unchanged, error on dark #E8A3A3. Focus ring: Midnight Indigo
on light, Warm Ivory on dark (0004's charcoal ring, same rule).

## How it is applied

- **Dark surfaces** — header, footer and the homepage bands — set `data-surface="dark"`, which remaps the same
  roles (`--av-surface`, `--av-text`, `--av-divider`, focus, error). Components read roles, so forms and links
  inside turn dark without their own rules.
- **Light surfaces** (shop, product, cart, checkout, account) stay Warm Ivory with Midnight Indigo text, so long
  forms and product browsing keep high contrast. Midnight Indigo dominates through the header, footer, homepage
  and 3D stage.
- Amber appears on dark surfaces only, and sparingly. No gradients on buttons, no glow, no gold borders.

## Unchanged

Playfair Display + Inter, Urdu fonts, the 56 px hero headline and the whole type scale, spacing, motion tokens,
the registration-only "Burgundy & Blush" palette (0004 item 4), the interim wordmark (0004 item 6), 3D release
conditions V-01 to V-03 (0007). MTS v2.1 is a preserved document; its A-03 palette entry is superseded by this
record and the next MTS revision folds it in.
