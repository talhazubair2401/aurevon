import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import { GarmentArt, type ArtKind } from "@/components/art/GarmentArt";
import styles from "@/components/collections/Collections.module.css";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { CollectionTone } from "@/components/home/HomeSections";
import { ProductCard } from "@/components/product/ProductCard";
import { SortSelect } from "@/components/shop/ShopControls";
import { Link } from "@/i18n/navigation";
import { getCollection, getFacets, getProducts, getSeo, type CollectionCard } from "@/lib/api";
import { redirectOrNotFound } from "@/lib/redirects";
import { pageMetadata } from "@/lib/seo";
import { cursorFrom, parseShopState, toSearch } from "@/lib/shop-query";

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

async function load(locale: string, slug: string): Promise<CollectionCard | null> {
  if (!isLocale(locale) || !SLUG.test(slug)) return null;
  return getCollection(slug, locale);
}

export async function generateMetadata({
  params,
  searchParams,
}: PageProps<"/[locale]/collections/[slug]">): Promise<Metadata> {
  const { locale, slug } = await params;
  const collection = await load(locale, slug);
  if (!collection) return {};
  const seo = await getSeo(`collection:${collection.slug}`, locale as Locale);
  const query = await searchParams;
  return pageMetadata({
    locale: locale as Locale,
    path: `/collections/${collection.slug}`,
    title: seo?.title || collection.name,
    description: seo?.description || collection.description || undefined,
    // Sorted or paged views point at the collection itself and stay out of the index.
    noindex: seo?.noindex || Object.keys(query).length > 0,
  });
}

/**
 * One collection (M01): an introduction band, then its pieces in the Shop All grid with sorting. Filtering a
 * collection hands over to Shop All, which already has every filter.
 */
export default async function CollectionPage({
  params,
  searchParams,
}: PageProps<"/[locale]/collections/[slug]">) {
  const { locale: raw, slug } = await params;
  if (!isLocale(raw)) notFound();
  setRequestLocale(raw);
  const locale = raw as Locale;
  const collection = await load(locale, slug);
  if (!collection) return redirectOrNotFound(locale, `/collections/${slug}`);

  const parsed = parseShopState(await searchParams);
  const view = {
    sort: parsed.sort,
    size: [],
    colour: [],
    ...(parsed.cursor ? { cursor: parsed.cursor } : {}),
  };
  const query = { ...view, collection: collection.slug };
  const t = await getTranslations({ locale, namespace: "collections" });
  const tShop = await getTranslations({ locale, namespace: "shop" });
  const [page, facets] = await Promise.all([getProducts(query, locale), getFacets(query, locale)]);
  const total = facets.departments.reduce((sum, d) => sum + d.count, 0);
  const next = cursorFrom(page.next);
  const previous = cursorFrom(page.previous);
  const base = `/collections/${collection.slug}`;

  return (
    <>
      <section className={styles.band} aria-labelledby="collection-title">
        <CollectionTone tone={collection.tone} className={styles.bandTone} />
        <div className={styles.bandInner}>
          <div>
            <div className={styles.bandCrumbs}>
              <Breadcrumbs
                locale={locale}
                items={[
                  { name: t("title"), path: "/collections" },
                  { name: collection.name, path: base },
                ]}
              />
            </div>
            <p className={styles.bandEyebrow}>{t("title")}</p>
            <h1 id="collection-title" className={styles.bandTitle}>
              {collection.name}
            </h1>
            {collection.description ? (
              <p className={styles.bandDescription}>{collection.description}</p>
            ) : null}
          </div>
          {collection.demo_art ? (
            <div className={styles.bandArt} aria-hidden="true">
              <GarmentArt kind={collection.demo_art as ArtKind} colour="#F2EDE4" stage="dark" />
            </div>
          ) : null}
        </div>
      </section>

      <div className={styles.products}>
        <div className={styles.toolbar}>
          <p className={styles.count} role="status">
            {t("pieces", { count: total })}
          </p>
          <div className={styles.toolbarEnd}>
            <Link
              href={`/shop${toSearch({ collection: collection.slug })}`}
              className={styles.refine}
            >
              {t("refine")}
            </Link>
            <SortSelect state={view} />
          </div>
        </div>

        {page.results.length === 0 ? (
          <p className={styles.empty}>{t("empty")}</p>
        ) : (
          <ul className={styles.grid}>
            {page.results.map((product) => (
              <li key={product.slug}>
                <ProductCard product={product} locale={locale} />
              </li>
            ))}
          </ul>
        )}

        {next || previous ? (
          <nav className={styles.pagination} aria-label={tShop("pagination")}>
            {previous ? (
              <Link
                href={`${base}${toSearch({ ...view, cursor: previous })}`}
                className={styles.pageLink}
              >
                {tShop("previous")}
              </Link>
            ) : null}
            {next ? (
              <Link
                href={`${base}${toSearch({ ...view, cursor: next })}`}
                className={styles.pageLink}
              >
                {tShop("loadMore")}
              </Link>
            ) : null}
          </nav>
        ) : null}
      </div>
    </>
  );
}
