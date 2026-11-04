import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import { GarmentArt, type ArtKind } from "@/components/art/GarmentArt";
import { Newsletter } from "@/components/newsletter/Newsletter";
import { ProductCard } from "@/components/product/ProductCard";
import { FilterForm } from "@/components/shop/FilterForm";
import { MobileFilters, SortSelect } from "@/components/shop/ShopControls";
import styles from "@/components/shop/Shop.module.css";
import { Link } from "@/i18n/navigation";
import { getBanner, getFacets, getProducts } from "@/lib/api";
import { cursorFrom, parseShopState, toSearch, withoutCursor } from "@/lib/shop-query";

export async function generateMetadata({ params }: PageProps<"/[locale]/shop">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "shop" });
  return { title: t("title"), description: t("subtitle") };
}

/** Where the "BEYOND THE ORDINARY" editorial banner sits in the grid: after the second row of four. */
const BANNER_AFTER = 8;

/**
 * Shop All (A-04, refined concept A + C): cinematic gallery of floating hangers, balanced women's and men's
 * presentation, four-column grid, filters, sorting, editorial banner, newsletter, then the site footer.
 */
export default async function ShopPage({ params, searchParams }: PageProps<"/[locale]/shop">) {
  const { locale: raw } = await params;
  // Validate before any API call: unknown paths like /missing.png arrive here as the locale.
  if (!isLocale(raw)) notFound();
  setRequestLocale(raw);
  const locale = raw as Locale;
  const state = parseShopState(await searchParams);
  const t = await getTranslations({ locale, namespace: "shop" });

  const [page, facets, banner] = await Promise.all([
    getProducts(state, locale),
    getFacets(state, locale),
    getBanner("shop_editorial", locale),
  ]);

  const total = state.department
    ? (facets.departments.find((d) => d.value === state.department)?.count ?? 0)
    : facets.departments.reduce((sum, d) => sum + d.count, 0);
  const active =
    (state.category ? 1 : 0) +
    state.size.length +
    state.colour.length +
    (state.price_min || state.price_max ? 1 : 0);
  const base = withoutCursor(state);
  const tabs: Array<{ key: "all" | "women" | "men"; dept?: "women" | "men" }> = [
    { key: "all" },
    { key: "women", dept: "women" },
    { key: "men", dept: "men" },
  ];
  // Gallery: the first pieces in the current view, alternating women's and men's when unfiltered.
  const gallery = page.results.filter((p) => p.image?.demo_art).slice(0, 5);
  const next = cursorFrom(page.next);
  const previous = cursorFrom(page.previous);
  const bannerContent = (banner?.content ?? null) as Record<string, string> | null;

  return (
    <>
      <section className={styles.gallery} aria-labelledby="shop-title">
        <div className={styles.galleryInner}>
          <div className={styles.galleryCopy}>
            <h1 id="shop-title" className={styles.galleryTitle}>
              {t("title")}
            </h1>
            <p className={styles.gallerySubtitle}>{t("subtitle")}</p>
          </div>
          <ul className={styles.hangers} aria-label={t("galleryLabel")}>
            {gallery.map((p) => (
              <li key={p.slug} className={styles.hanger}>
                <Link
                  href={`/products/${p.slug}`}
                  className={styles.hangerLink}
                  aria-label={p.name}
                >
                  <GarmentArt
                    kind={p.image!.demo_art as ArtKind}
                    colour={p.image!.tone}
                    stage="dark"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className={styles.shop}>
        <nav className={styles.departments} aria-label={t("department")}>
          {tabs.map((tab) => {
            const current = state.department === tab.dept;
            const rest = withoutCursor(state, { dropCategory: true });
            if (tab.dept) rest.department = tab.dept;
            else delete rest.department;
            return (
              <Link
                key={tab.key}
                href={`/shop${toSearch(rest)}`}
                className={current ? styles.departmentActive : styles.department}
                aria-current={current ? "page" : undefined}
                scroll={false}
              >
                {t(tab.key)}
              </Link>
            );
          })}
        </nav>

        <div className={styles.toolbar}>
          <p className={styles.resultCount} role="status">
            {t("results", { count: total })}
          </p>
          <div className={styles.toolbarEnd}>
            {active ? (
              <Link
                href={`/shop${toSearch({ sort: state.sort, ...(state.department ? { department: state.department } : {}), ...(state.collection ? { collection: state.collection } : {}) })}`}
                className={styles.clearAll}
                scroll={false}
              >
                {t("clearAll")}
              </Link>
            ) : null}
            <MobileFilters state={state} facets={facets} active={active} />
            <SortSelect state={state} />
          </div>
        </div>

        <div className={styles.layout}>
          <aside className={styles.sidebar} aria-label={t("filters")}>
            <FilterForm state={state} facets={facets} />
          </aside>

          <div className={styles.results}>
            {page.results.length === 0 ? (
              <div className={styles.empty}>
                <h2 className={styles.emptyTitle}>{t("emptyTitle")}</h2>
                <p>{t("emptyBody")}</p>
              </div>
            ) : (
              <ul className={styles.grid}>
                {page.results.map((product, index) => (
                  <ShopItem
                    key={product.slug}
                    showBanner={index === BANNER_AFTER - 1 && !previous && bannerContent !== null}
                    banner={bannerContent}
                  >
                    <ProductCard product={product} locale={locale} />
                  </ShopItem>
                ))}
              </ul>
            )}
            {next || previous ? (
              <nav className={styles.pagination} aria-label={t("pagination")}>
                {previous ? (
                  <Link
                    href={`/shop${toSearch({ ...base, cursor: previous })}`}
                    className={styles.pageLink}
                  >
                    {t("previous")}
                  </Link>
                ) : null}
                {next ? (
                  <Link
                    href={`/shop${toSearch({ ...base, cursor: next })}`}
                    className={styles.pageLink}
                  >
                    {t("loadMore")}
                  </Link>
                ) : null}
              </nav>
            ) : null}
          </div>
        </div>
      </div>

      <Newsletter source="shop_all" />
    </>
  );
}

function ShopItem({
  children,
  showBanner,
  banner,
}: {
  children: React.ReactNode;
  showBanner: boolean;
  banner: Record<string, string> | null;
}) {
  return (
    <>
      <li>{children}</li>
      {showBanner && banner ? (
        <li className={styles.editorialItem}>
          <EditorialBanner content={banner} />
        </li>
      ) : null}
    </>
  );
}

function EditorialBanner({ content }: { content: Record<string, string> }) {
  const href =
    content.link_href?.startsWith("/") && !content.link_href.startsWith("//")
      ? content.link_href
      : "/shop";
  return (
    <section className={styles.editorial} aria-labelledby="editorial-title">
      <div className={styles.editorialArt} aria-hidden="true">
        <GarmentArt kind="kurta" colour="#D8C8AE" stage="dark" />
        <GarmentArt kind="blazer" colour="#151515" stage="dark" />
      </div>
      <div className={styles.editorialCopy}>
        <h2 id="editorial-title" className={styles.editorialTitle} lang="en">
          {content.title}
        </h2>
        {content.body ? <p className={styles.editorialBody}>{content.body}</p> : null}
        {content.link_label ? (
          <Link href={href} className={styles.editorialLink}>
            {content.link_label}
          </Link>
        ) : null}
      </div>
    </section>
  );
}
