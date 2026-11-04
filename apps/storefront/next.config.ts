import path from "node:path";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  transpilePackages: [
    "@aurevon/design-tokens",
    "@aurevon/api-client",
    "@aurevon/i18n",
    "@aurevon/ui",
  ],
  poweredByHeader: false,
  reactStrictMode: true,
};

export default withNextIntl(config);
