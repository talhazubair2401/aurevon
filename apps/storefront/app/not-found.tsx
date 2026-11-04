import Link from "next/link";
import "@aurevon/design-tokens/tokens.css";
import "./globals.css";
import { displayFont, uiFont } from "./fonts";

// Only reached for paths outside the locale routes; every locale page has its own not-found.
export default function GlobalNotFound() {
  return (
    <html lang="en" dir="ltr" className={`${displayFont.variable} ${uiFont.variable}`}>
      <body>
        <main className="av-centred">
          <h1 className="av-heading">Page not found</h1>
          <p>
            <Link href="/en">Back to the homepage</Link>
          </p>
        </main>
      </body>
    </html>
  );
}
