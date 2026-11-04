/**
 * AureVon brand tokens. Values are APPROVED in MTS v2.1 (A-03, from MTS v1.0 §3.2).
 * Change them only with product-owner approval; the final palette is still open under P-19.
 */
export const colors = {
  offWhite: "#F9F8F6",
  charcoal: "#121212",
  stone: "#E5E0DB",
  deepBrown: "#3B2F2F",
  champagneGold: "#C2A676",
} as const;

export const fonts = {
  display: "Playfair Display",
  ui: "Inter",
} as const;

/** CSS custom property name for each colour, as declared in tokens.css. */
export const colorVariables: Record<keyof typeof colors, string> = {
  offWhite: "--av-color-off-white",
  charcoal: "--av-color-charcoal",
  stone: "--av-color-stone",
  deepBrown: "--av-color-deep-brown",
  champagneGold: "--av-color-champagne-gold",
};
