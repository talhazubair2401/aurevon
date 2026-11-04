import localFont from "next/font/local";

// Self-hosted at build time from npm packages: no third-party font host at runtime (MTS §12).
// Families approved in decision 0004 (P-19).
export const displayFont = localFont({
  src: "../node_modules/@fontsource-variable/playfair-display/files/playfair-display-latin-wght-normal.woff2",
  variable: "--av-font-display-family",
  display: "swap",
});

export const uiFont = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--av-font-ui-family",
  display: "swap",
});

// Urdu: Nastaliq for reading text, Naskh for interface controls. Arabic-script subset only; Latin falls back
// to Inter. Not preloaded, so English pages never download them.
export const urduReadingFont = localFont({
  src: "../node_modules/@fontsource-variable/noto-nastaliq-urdu/files/noto-nastaliq-urdu-arabic-wght-normal.woff2",
  variable: "--av-font-urdu-reading-family",
  display: "swap",
  preload: false,
});

export const urduUiFont = localFont({
  src: "../node_modules/@fontsource-variable/noto-naskh-arabic/files/noto-naskh-arabic-arabic-wght-normal.woff2",
  variable: "--av-font-urdu-ui-family",
  display: "swap",
  preload: false,
});
