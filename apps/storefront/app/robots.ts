import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

/**
 * The storefront is public; the staff app, the API and personal pages are not for search engines (MTS §2).
 * Non-production environments (staging, review) ask not to be indexed at all.
 */
export default function robots(): MetadataRoute.Robots {
  const indexable = process.env.SITE_INDEXABLE === "true";
  const disallowPersonal = [
    "/staff",
    "/api/",
    "/en/cart",
    "/ur/cart",
    "/en/checkout",
    "/ur/checkout",
    "/en/account",
    "/ur/account",
  ];
  return {
    rules: indexable
      ? [{ userAgent: "*", allow: "/", disallow: disallowPersonal }]
      : [{ userAgent: "*", disallow: "/" }],
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
