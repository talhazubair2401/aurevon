import localFont from "next/font/local";

// Self-hosted at build time from npm packages: no third-party font host at runtime (MTS §12, A-03).
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
