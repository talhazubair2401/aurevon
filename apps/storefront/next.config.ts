import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  transpilePackages: ["@aurevon/design-tokens", "@aurevon/api-client"],
  poweredByHeader: false,
  reactStrictMode: true,
};

export default config;
