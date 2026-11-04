import { notFound } from "next/navigation";
import { setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import { renderSection } from "@/components/home/HomeSections";
import { getHome } from "@/lib/api";

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
  return <>{home.sections.map((section) => renderSection(section, locale as Locale))}</>;
}
