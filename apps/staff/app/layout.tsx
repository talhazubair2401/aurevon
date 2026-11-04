import type { Metadata } from "next";
import type { ReactNode } from "react";
import { headers } from "next/headers";
import "@aurevon/design-tokens/tokens.css";
import "./globals.css";
import { Providers } from "../components/Providers";
import { displayFont, uiFont } from "./fonts";

export const metadata: Metadata = {
  title: "AureVon Staff",
  robots: { index: false, follow: false },
};

// Rendered per request so every page carries that request's CSP nonce (decision 0005, D-08).
export default async function StaffLayout({ children }: { children: ReactNode }) {
  await headers();
  return (
    <html lang="en" className={`${displayFont.variable} ${uiFont.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
