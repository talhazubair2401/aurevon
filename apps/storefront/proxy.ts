import { NextResponse, type NextRequest } from "next/server";
import createMiddleware from "next-intl/middleware";
import { HTML_CACHE_CONTROL, buildPolicy, generateNonce, reportingEndpoints } from "@aurevon/csp";
import { routing } from "./i18n/routing";

const intl = createMiddleware(routing);

/**
 * Every storefront page request (decision 0005, D-08):
 * 1. a fresh nonce and the enforcing CSP, passed to Next.js on the request so it stamps its own scripts;
 * 2. locale routing (/ -> /en or /ur);
 * 3. the same CSP on the response, and Cache-Control that forbids any shared or browser cache from storing
 *    the HTML, because a cached nonce would be a reusable key.
 */
export default function proxy(request: NextRequest) {
  const nonce = generateNonce();
  const policy = buildPolicy({
    app: "storefront",
    nonce,
    development: process.env.NODE_ENV === "development",
    webAssembly: true, // 3D viewer (M6)
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", policy);

  const response = intl(request);

  // Forward the modified request headers through next-intl's response (next or rewrite).
  const forward = NextResponse.next({ request: { headers: requestHeaders } });
  forward.headers.forEach((value, key) => {
    if (key === "x-middleware-override-headers" || key.startsWith("x-middleware-request-")) {
      response.headers.set(key, value);
    }
  });

  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Reporting-Endpoints", reportingEndpoints);
  response.headers.set("Cache-Control", HTML_CACHE_CONTROL);
  return response;
}

export const config = {
  // Pages only. Build assets, fonts, Draco files, media, API and staff paths never pass through here, so
  // they keep their own long-term caching (MTS §2).
  matcher: ["/((?!api|staff|internal|_next|_vercel|3d|media|health|.*\\..*).*)"],
};
