/**
 * AureVon design tokens.
 * - Core colours: "Midnight Indigo & Amber", APPROVED 11 Nov 2026 (decision 0008), replacing the A-03 palette.
 * - Functional colours, indigo focus ring, Inter, Urdu fonts, registration palette, interim wordmark:
 *   APPROVED in decision 0004 (P-19).
 * - Type scale, spacing, layout and motion: PROPOSED defaults from the P-19 proposal, to be confirmed against
 *   the A-04 references when supplied (decision 0004).
 * Keep in sync with tokens.css; tests enforce it. Change values only with product-owner approval.
 */
export const colors = {
  midnightIndigo: "#111322", // primary background and the brand's dominant colour
  deepIndigo: "#191D35", // secondary surfaces, depth
  amber: "#D99A32", // primary accent, used selectively; never text on light surfaces (2.2:1)
  softAmber: "#E8B968", // subtle highlights on dark surfaces
  warmIvory: "#F5F3EE", // light surfaces and text on dark
  mutedSlate: "#85879A", // secondary text on dark surfaces only (3.2:1 on ivory)
} as const;

/** Functional colours (decision 0004, item 1; retuned to the indigo palette in decision 0008). */
export const functionalColors = {
  white: "#FFFFFF",
  mutedText: "#5C5F74", // secondary text on light surfaces (5.7:1 on ivory)
  fieldBorder: "#7A7D91", // form borders on light surfaces (3.7:1)
  ivoryShade: "#E4E1D9", // dividers and quiet fills on light surfaces: a step of Warm Ivory, not a new hue
  error: "#9A2B2B",
  success: "#2E5E3A",
  errorOnDark: "#E8A3A3", // error text on indigo surfaces (8:1 on Deep Indigo)
} as const;

/** "Burgundy & Blush": the registration page only (decision 0004, item 4). */
export const registrationColors = {
  burgundy: "#70263D",
  blush: "#E8C5CC",
  ivory: "#FAF7F4",
  ink: "#292629",
} as const;

export const fonts = {
  display: "Playfair Display",
  ui: "Inter",
  urduReading: "Noto Nastaliq Urdu",
  urduUi: "Noto Naskh Arabic",
} as const;

/** CSS custom property name for each colour, as declared in tokens.css. */
export const colorVariables: Record<keyof typeof colors, string> = {
  midnightIndigo: "--av-color-midnight-indigo",
  deepIndigo: "--av-color-deep-indigo",
  amber: "--av-color-amber",
  softAmber: "--av-color-soft-amber",
  warmIvory: "--av-color-warm-ivory",
  mutedSlate: "--av-color-muted-slate",
};

export const functionalColorVariables: Record<keyof typeof functionalColors, string> = {
  white: "--av-color-white",
  mutedText: "--av-color-muted-text",
  fieldBorder: "--av-color-field-border",
  ivoryShade: "--av-color-ivory-shade",
  errorOnDark: "--av-color-error-on-dark",
  error: "--av-color-error",
  success: "--av-color-success",
};

export const registrationColorVariables: Record<keyof typeof registrationColors, string> = {
  burgundy: "--av-reg-burgundy",
  blush: "--av-reg-blush",
  ivory: "--av-reg-ivory",
  ink: "--av-reg-ink",
};

/** Type scale in px: [desktop, mobile] (PROPOSED, P-19). */
export const typeScale = {
  display: [56, 38],
  h1: [40, 30],
  h2: [30, 24],
  h3: [22, 20],
  body: [16, 16],
  small: [14, 14],
  caption: [12, 12],
} as const;

/** Spacing on a 4px grid (PROPOSED, P-19). */
export const spacingUnitPx = 4;
export const maxContentWidthPx = 1440;

/** The wordmark text used until an official logo is supplied (decision 0004, item 6). */
export const interimWordmark = "AUREVON";
export { contrastRatio, relativeLuminance } from "./contrast";
