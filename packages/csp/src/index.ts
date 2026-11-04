/**
 * Content Security Policy (MTS v2.1 §12, A-26; decision 0005 approves D-08).
 *
 * Every HTML response gets a fresh nonce. Next.js reads it from the request's CSP header and stamps it on its
 * own inline bootstrap and payload scripts and on its bundles; 'strict-dynamic' extends trust to scripts those
 * load. Production never allows 'unsafe-inline' scripts or 'unsafe-eval'.
 */

export type App = "storefront" | "staff";

export interface PolicyOptions {
  app: App;
  nonce: string;
  /** next dev needs eval for React's debugging; development builds never ship. */
  development?: boolean;
  /**
   * 3D viewer (M6): WebAssembly for Draco/Meshopt and blob: workers. Off until the viewer exists and
   * V-05 proves it (decision 0005).
   */
  webAssembly?: boolean;
}

/** Same-origin endpoint that receives violation reports (rate-limited, logged; MTS §14). */
export const REPORT_PATH = "/api/v1/csp-reports";
export const REPORT_GROUP = "csp";

/** 128 random bits, base64. Uses Web Crypto, which the Next.js proxy runtime provides. */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

const NONCE_PATTERN = /^[A-Za-z0-9+/]{22}==$/;

export function buildPolicy({
  app,
  nonce,
  development = false,
  webAssembly = false,
}: PolicyOptions): string {
  if (!NONCE_PATTERN.test(nonce)) throw new Error("Invalid CSP nonce");

  const script = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"];
  if (webAssembly) script.push("'wasm-unsafe-eval'");
  if (development) script.push("'unsafe-eval'");

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": script,
    "style-src": ["'self'", `'nonce-${nonce}'`],
    "img-src": app === "storefront" ? ["'self'", "data:", "blob:"] : ["'self'", "data:"],
    "font-src": ["'self'"],
    "connect-src": app === "storefront" ? ["'self'", "blob:"] : ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'none'"],
    "report-uri": [REPORT_PATH],
    "report-to": [REPORT_GROUP],
  };
  if (app === "storefront" && webAssembly) directives["worker-src"] = ["'self'", "blob:"];
  if (development) {
    // Hot reload uses a websocket on the dev server.
    directives["connect-src"] = [...directives["connect-src"]!, "ws:"];
  }
  // No upgrade-insecure-requests: it would break the local http proxy; HSTS covers production (MTS §12).

  return Object.entries(directives)
    .map(([name, values]) => [name, ...values].join(" "))
    .join("; ");
}

/** Value for the Reporting-Endpoints response header that `report-to csp` refers to. */
export const reportingEndpoints = `${REPORT_GROUP}="${REPORT_PATH}"`;

/**
 * Cache-Control for every HTML (and RSC payload) response. A cached nonce would be a reusable key, so these
 * responses must never be stored by a CDN, proxy or browser cache.
 */
export const HTML_CACHE_CONTROL = "private, no-store, max-age=0";
