import { NextResponse, type NextRequest } from "next/server";
import { HTML_CACHE_CONTROL, buildPolicy, generateNonce, reportingEndpoints } from "@aurevon/csp";

/**
 * Every staff page request gets a fresh nonce and the enforcing staff CSP (decision 0005, D-08): no
 * third-party origins; WebAssembly only for the 3D model preview (M6). Next.js reads the nonce from the request header and stamps its scripts.
 */
export default function proxy(request: NextRequest) {
  const nonce = generateNonce();
  const policy = buildPolicy({
    app: "staff",
    nonce,
    development: process.env.NODE_ENV === "development",
    webAssembly: true, // 3D viewer (M6)
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Reporting-Endpoints", reportingEndpoints);
  response.headers.set("Cache-Control", HTML_CACHE_CONTROL);
  return response;
}

export const config = {
  // Pages only (paths are relative to basePath /staff); build assets keep long-term caching. The bare root
  // needs its own entry: with a basePath, "/staff" does not match the general pattern.
  matcher: ["/", "/((?!_next|.*\\..*).*)"],
};
