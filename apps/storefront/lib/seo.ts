import type { Metadata } from "next";
import { locales, type Locale } from "@aurevon/i18n";

/**
 * Search metadata (M17): one canonical URL per page and language, hreflang alternates for English and Urdu,
 * Open Graph for sharing. Paths are locale-free ("/shop"); the locale prefix is added here.
 */
export function siteUrl(): string {
  return (process.env.SITE_URL ?? "http://localhost:8080").replace(/\/+$/, "");
}

export function localePath(locale: Locale, path: string): string {
  return path === "/" ? `/${locale}` : `/${locale}${path}`;
}

export function alternates(locale: Locale, path: string): Metadata["alternates"] {
  return {
    canonical: localePath(locale, path),
    languages: {
      ...Object.fromEntries(locales.map((l) => [l, localePath(l, path)])),
      "x-default": localePath("en", path),
    },
  };
}

interface PageMeta {
  locale: Locale;
  path: string;
  title?: string | undefined;
  description?: string | undefined;
  noindex?: boolean | undefined;
  /** Use the title as given, without the "· AureVon" suffix (the homepage). */
  absoluteTitle?: boolean | undefined;
}

export function pageMetadata({
  locale,
  path,
  title,
  description,
  noindex,
  absoluteTitle,
}: PageMeta): Metadata {
  return {
    ...(title ? { title: absoluteTitle ? { absolute: title } : title } : {}),
    ...(description ? { description } : {}),
    alternates: alternates(locale, path),
    openGraph: {
      type: "website",
      siteName: "AureVon",
      locale: locale === "ur" ? "ur_PK" : "en_PK",
      url: localePath(locale, path),
      ...(title ? { title } : {}),
      ...(description ? { description } : {}),
    },
    ...(noindex ? { robots: { index: false, follow: true } } : {}),
  };
}

/** Absolute URL for structured data, which search engines require to be absolute. */
export function absoluteUrl(locale: Locale, path: string): string {
  return `${siteUrl()}${localePath(locale, path)}`;
}
