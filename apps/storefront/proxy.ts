import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

// Adds the locale prefix (/ -> /en or /ur from Accept-Language or the NEXT_LOCALE cookie).
export default createMiddleware(routing);

export const config = {
  // Storefront pages only: never build assets, Draco files, media, API or staff paths (MTS §2).
  matcher: ["/((?!api|staff|_next|_vercel|3d|media|health|.*\\..*).*)"],
};
