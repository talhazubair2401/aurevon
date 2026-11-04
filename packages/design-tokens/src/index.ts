/**
 * AureVon design tokens.
 * - Core colours: APPROVED, MTS v2.1 A-03 (unchanged).
 * - Functional colours, charcoal focus ring, Inter, Urdu fonts, registration palette, interim wordmark:
 *   APPROVED in decision 0004 (P-19).
 * - Type scale, spacing, layout and motion: PROPOSED defaults from the P-19 proposal, to be confirmed against
 *   the A-04 references when supplied (decision 0004).
 * Keep in sync with tokens.css; tests enforce it. Change values only with product-owner approval.
 */
export const colors = {
  offWhite: "#F9F8F6",
  charcoal: "#121212",
  stone: "#E5E0DB",
  deepBrown: "#3B2F2F",
  champagneGold: "#C2A676",
} as const;

/** Functional colours (decision 0004, item 1). */
export const functionalColors = {
  white: "#FFFFFF",
  mutedText: "#6B6461",
  fieldBorder: "#8C7F78",
  error: "#9A2B2B",
  success: "#2E5E3A",
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
  offWhite: "--av-color-off-white",
  charcoal: "--av-color-charcoal",
  stone: "--av-color-stone",
  deepBrown: "--av-color-deep-brown",
  champagneGold: "--av-color-champagne-gold",
};

export const functionalColorVariables: Record<keyof typeof functionalColors, string> = {
  white: "--av-color-white",
  mutedText: "--av-color-muted-text",
  fieldBorder: "--av-color-field-border",
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
