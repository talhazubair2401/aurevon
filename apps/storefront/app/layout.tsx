import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@aurevon/design-tokens/tokens.css";
import "./globals.css";
import { displayFont, uiFont } from "./fonts";

export const metadata: Metadata = {
  title: "AureVon",
  description: "Modern Style. Timeless Confidence.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${displayFont.variable} ${uiFont.variable}`}>
      <body>{children}</body>
    </html>
  );
}
