import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import styles from "@/components/collections/Collections.module.css";
import { ProductCard } from "@/components/product/ProductCard";
import { SortSelect } from "@/components/shop/ShopControls";
import { Link } from "@/i18n/navigation";
import { getFacets, getProducts } from "@/lib/api";
import { pageMetadata } from "@/lib/seo";
import { cursorFrom, parseShopState, toSearch } from "@/lib/shop-query";
import search from "@/components/shop/Search.module.css";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/search">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "search" });
  // Result pages are for shoppers, not search engines.
  return pageMetadata({ locale, path: "/search", title: t("title"), noindex: true });
}

/** Catalogue search (R-07: PostgreSQL full-text, English and Urdu). A plain GET form: works without JavaScript. */
export default async function SearchPage({ params, searchParams }: PageProps<"/[locale]/search">) {
  const { locale: raw } = await params;
  if (!isLocale(raw)) notFound();
  setRequestLocale(raw);
  const locale = raw as Locale;
  const state = parseShopState(await searchParams);
  const t = await getTranslations({ locale, namespace: "search" });
  const tShop = await getTranslations({ locale, namespace: "shop" });
  const q = state.q ?? "";
  const [page, facets] = q
    ? await Promise.all([getProducts(state, locale), getFacets(state, locale)])
    : [null, null];
  const total = facets ? facets.departments.reduce((sum, d) => sum + d.count, 0) : 0;
  const next = cursorFrom(page?.next);
  const previous = cursorFrom(page?.previous);

  return (
    <>
      <div className={styles.intro}>
        <h1 className={styles.introTitle}>{t("title")}</h1>
        <form method="get" role="search" className={search.form}>
          <label htmlFor="search-q" className={search.label}>
            {t("label")}
          </label>
          <div className={search.row}>
            <input
              id="search-q"
              name="q"
              type="search"
              defaultValue={q}
              placeholder={t("placeholder")}
              maxLength={100}
              className={search.input}
              autoComplete="off"
            />
            <button type="submit" className={search.submit}>
              {t("submit")}
            </button>
          </div>
        </form>
      </div>
      <div className={styles.products}>
        {!q ? (
          <p className={styles.count}>{t("prompt")}</p>
        ) : (
          <>
            <div className={styles.toolbar}>
              <p className={styles.count} role="status">
                {page && page.results.length
                  ? t("results", { count: total, q })
                  : t("empty", { q })}
              </p>
              {page && page.results.length ? (
                <div className={styles.toolbarEnd}>
                  <SortSelect state={state} />
                </div>
              ) : null}
            </div>
            {page && page.results.length === 0 ? (
              <p className={styles.empty}>{t("emptyHint")}</p>
            ) : null}
            <ul className={styles.grid}>
              {page?.results.map((product) => (
                <li key={product.slug}>
                  <ProductCard product={product} locale={locale} />
                </li>
              ))}
            </ul>
            {next || previous ? (
              <nav className={styles.pagination} aria-label={tShop("pagination")}>
                {previous ? (
                  <Link
                    href={`/search${toSearch({ ...state, cursor: previous })}`}
                    className={styles.pageLink}
                  >
                    {tShop("previous")}
                  </Link>
                ) : null}
                {next ? (
                  <Link
                    href={`/search${toSearch({ ...state, cursor: next })}`}
                    className={styles.pageLink}
                  >
                    {tShop("loadMore")}
                  </Link>
                ) : null}
              </nav>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}
