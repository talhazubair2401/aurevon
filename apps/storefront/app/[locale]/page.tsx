import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import { renderSection } from "@/components/home/HomeSections";
import { JsonLd } from "@/components/seo/JsonLd";
import { getHome, getSeo } from "@/lib/api";
import { absoluteUrl, pageMetadata, siteUrl } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "meta" });
  const seo = await getSeo("home", locale);
  return pageMetadata({
    locale,
    path: "/",
    title: seo?.title || `${t("title")} · ${t("tagline")}`,
    description: seo?.description || t("tagline"),
    noindex: seo?.noindex,
    absoluteTitle: true,
  });
}

/**
 * Homepage (A-04, Modern Heritage Luxury): Hero, Collections, Featured Products, New Arrivals, Brand Story,
 * then the site footer. Sections, their order and copy come from the CMS (GET /cms/home).
 */
export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  // Validate before any API call: unknown paths like /missing.png arrive here as the locale.
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  const home = await getHome(locale as Locale);
  const t = await getTranslations({ locale, namespace: "meta" });
  return (
    <>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@graph": [
            { "@type": "Organization", name: t("title"), url: siteUrl(), slogan: t("tagline") },
            {
              "@type": "WebSite",
              name: t("title"),
              url: absoluteUrl(locale as Locale, "/"),
              inLanguage: locale === "ur" ? "ur-PK" : "en-PK",
            },
          ],
        }}
      />
      {home.sections.map((section) => renderSection(section, locale as Locale))}
    </>
  );
}
