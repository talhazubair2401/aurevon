import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import styles from "@/components/collections/Collections.module.css";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { CollectionCardList } from "@/components/home/HomeSections";
import { getCollections, getSeo } from "@/lib/api";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/collections">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "collections" });
  const seo = await getSeo("collections", locale);
  return pageMetadata({
    locale,
    path: "/collections",
    title: seo?.title || t("title"),
    description: seo?.description || t("subtitle"),
    noindex: seo?.noindex,
  });
}

/** Every published collection (M01 collection browsing), as the homepage presents them. */
export default async function CollectionsPage({ params }: PageProps<"/[locale]/collections">) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  setRequestLocale(raw);
  const locale = raw as Locale;
  const t = await getTranslations({ locale, namespace: "collections" });
  const collections = await getCollections(locale);

  return (
    <>
      <div className={styles.intro}>
        <Breadcrumbs locale={locale} items={[{ name: t("title"), path: "/collections" }]} />
        <h1 className={styles.introTitle}>{t("title")}</h1>
        <p className={styles.introSubtitle}>{t("subtitle")}</p>
      </div>
      <div className={styles.list}>
        <CollectionCardList collections={collections} locale={locale} headingLevel={2} />
      </div>
    </>
  );
}
