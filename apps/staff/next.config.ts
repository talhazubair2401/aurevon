import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  // Served under /staff/ on the same domain as the storefront (MTS v2.1 A-27).
  basePath: "/staff",
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  transpilePackages: [
    "@aurevon/design-tokens",
    "@aurevon/api-client",
    "@aurevon/csp",
    "@aurevon/viewer3d",
  ],
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    // Staff pages are never cached or indexed; the proxy enforces the same (MTS v2.1 §2). Content-hashed build
    // assets under /_next/static keep Next.js's long-term immutable caching (decision 0005).
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
      {
        source: "/((?!_next/static).*)",
        headers: [{ key: "Cache-Control", value: "no-store" }],
      },
    ];
  },
};

export default config;
