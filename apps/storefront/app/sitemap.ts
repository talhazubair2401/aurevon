import type { MetadataRoute } from "next";
import { locales } from "@aurevon/i18n";
import { getCollections, getPages } from "@/lib/api";
import { siteUrl } from "@/lib/seo";

// Built per request from published content (M17), like every page under the nonce CSP (decision 0005).
export const dynamic = "force-dynamic";

/** Every public page in both languages, each entry listing its other-language alternate. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const [pages, collections] = await Promise.all([getPages("en"), getCollections("en")]);
  const paths: Array<{ path: string; lastModified?: string }> = [
    { path: "" },
    { path: "/shop" },
    { path: "/collections" },
    ...collections.map((c) => ({ path: `/collections/${c.slug}` })),
    ...pages.map((p) => ({ path: `/pages/${p.slug}`, lastModified: p.updated_at })),
  ];
  return paths.flatMap(({ path, lastModified }) =>
    locales.map((locale) => ({
      url: `${base}/${locale}${path}`,
      ...(lastModified ? { lastModified } : {}),
      alternates: {
        languages: Object.fromEntries(locales.map((l) => [l, `${base}/${l}${path}`])),
      },
    })),
  );
}
