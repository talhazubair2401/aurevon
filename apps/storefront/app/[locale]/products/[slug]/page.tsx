import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale, type Locale } from "@aurevon/i18n";
import { Price } from "@aurevon/ui";
import { decoderPath, ProductViewer, VIEWER_ENGLISH, type ViewerLabels } from "@aurevon/viewer3d";
import { GarmentArt, type ArtKind } from "@/components/art/GarmentArt";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import styles from "@/components/product/ProductPage.module.css";
import { CollectionTone } from "@/components/home/HomeSections";
import { JsonLd } from "@/components/seo/JsonLd";
import { Link } from "@/i18n/navigation";
import { getAvailability, getProduct, type ProductDetail } from "@/lib/api";
import { routeReady } from "@/lib/features";
import { redirectOrNotFound } from "@/lib/redirects";
import { absoluteUrl, pageMetadata } from "@/lib/seo";

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

async function load(locale: string, slug: string): Promise<ProductDetail | null> {
  if (!isLocale(locale) || !SLUG.test(slug)) return null;
  return getProduct(slug, locale);
}

export async function generateMetadata({
  params,
  searchParams,
}: PageProps<"/[locale]/products/[slug]">): Promise<Metadata> {
  const { locale, slug } = await params;
  const product = await load(locale, slug);
  if (!product) return {};
  return pageMetadata({
    locale: locale as Locale,
    path: `/products/${product.slug}`,
    title: product.name,
    description: product.description || undefined,
    // A colour or size choice is the same page for search engines.
    noindex: Object.keys(await searchParams).length > 0,
  });
}

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * Product page (M01, M02): server-rendered with the product's image first (A-14), structured product data, and
 * price and stock read fresh on every view (A-15). Colour and size are chosen with links (?colour=&size=), so the
 * page works without JavaScript. Adding to the bag arrives with the cart in M7.
 */
export default async function ProductPage({
  params,
  searchParams,
}: PageProps<"/[locale]/products/[slug]">) {
  const { locale: raw, slug } = await params;
  if (!isLocale(raw)) notFound();
  setRequestLocale(raw);
  const locale = raw as Locale;
  const product = await load(locale, slug);
  if (!product) return redirectOrNotFound(locale, `/products/${slug}`);
  const [availability, t, t3d, query] = await Promise.all([
    getAvailability(product.slug),
    getTranslations({ locale, namespace: "product" }),
    getTranslations({ locale, namespace: "viewer3d" }),
    searchParams,
  ]);

  const colours = product.colours;
  const colour = colours.find((c) => c.slug === one(query.colour)) ?? colours[0]!;
  const fresh = new Map((availability?.variants ?? []).map((v) => [`${v.colour}|${v.size}`, v]));
  const sizeChoice = one(query.size);
  const size = product.sizes.includes(sizeChoice ?? "") ? sizeChoice : undefined;
  const selected = size ? fresh.get(`${colour.slug}|${size}`) : undefined;
  const colourVariants = product.sizes
    .map((s) => fresh.get(`${colour.slug}|${s}`))
    .filter((v): v is NonNullable<typeof v> => Boolean(v));
  const prices = colourVariants.map((v) => Number(v.price.amount));
  const low = colourVariants.find((v) => Number(v.price.amount) === Math.min(...prices));
  const high = colourVariants.find((v) => Number(v.price.amount) === Math.max(...prices));
  // This colour's images, photographs first; images without a colour belong to every colour.
  const images = product.images
    .filter((i) => i.colour === colour.slug || !i.colour)
    .sort((a, b) => Number(Boolean(b.url)) - Number(Boolean(a.url)));
  const shown = images[0] ?? product.images[0];
  const base = `/products/${product.slug}`;
  const href = (c: string, s?: string) =>
    `${base}?colour=${encodeURIComponent(c)}${s ? `&size=${encodeURIComponent(s)}` : ""}`;
  const anyAvailable = colourVariants.some((v) => v.available);
  // 3D only where the API sends it (approved, and on for shoppers after V-01 to V-03); a colour without it keeps
  // its photos (decision 0007, D-03). The image is the poster and always renders first.
  const model = product.model3d?.by_colour[colour.slug];
  // Raw strings: the viewer fills its own {key} and {colour} placeholders.
  const viewerLabels = Object.fromEntries(
    Object.keys(VIEWER_ENGLISH).map((k) => [k, String(t3d.raw(k))]),
  ) as unknown as ViewerLabels;
  const poster = shown?.url ? (
    // eslint-disable-next-line @next/next/no-img-element -- served pre-sized from object storage (M5)
    <img
      src={shown.url}
      alt={shown.alt}
      className={styles.photo}
      width={1600}
      height={2000}
      fetchPriority="high"
    />
  ) : shown?.demo_art ? (
    <div className={styles.stageArt} role="img" aria-label={shown.alt}>
      <GarmentArt kind={shown.demo_art as ArtKind} colour={shown.tone} />
    </div>
  ) : null;

  return (
    <div className={styles.page}>
      <Breadcrumbs
        locale={locale}
        items={[
          { name: t("breadcrumbShop"), path: "/shop" },
          {
            name: product.category.name,
            path: `/shop?department=${product.department}&category=${product.category.slug}`,
          },
          { name: product.name, path: base },
        ]}
      />
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Product",
          name: product.name,
          description: product.description,
          sku: product.variants[0]?.sku,
          brand: { "@type": "Brand", name: "AureVon" },
          category: product.category.name,
          url: absoluteUrl(locale, base),
          offers: (availability?.variants ?? []).map((v) => ({
            "@type": "Offer",
            sku: v.sku,
            price: v.price.amount,
            priceCurrency: v.price.currency,
            availability: v.available
              ? "https://schema.org/InStock"
              : "https://schema.org/OutOfStock",
            url: absoluteUrl(locale, href(v.colour, v.size)),
          })),
        }}
      />
      <div className={styles.layout}>
        <section className={styles.gallery} aria-label={t("gallery")}>
          <div className={styles.stage}>
            {model ? (
              <ProductViewer
                src={model.url}
                variant={model.variant}
                decoderPath={decoderPath()}
                colourName={colour.name}
                labels={viewerLabels}
              >
                {poster}
              </ProductViewer>
            ) : (
              poster
            )}
          </div>
          {colours.length > 1 ? (
            <ul className={styles.thumbs}>
              {colours.map((c) => {
                const image =
                  product.images.find((i) => i.colour === c.slug && i.url) ??
                  product.images.find((i) => i.colour === c.slug);
                return (
                  <li key={c.slug}>
                    <Link
                      href={href(c.slug, size)}
                      scroll={false}
                      className={c.slug === colour.slug ? styles.thumbActive : styles.thumb}
                      aria-label={image?.alt ?? c.name}
                      aria-current={c.slug === colour.slug ? "true" : undefined}
                    >
                      {image?.url ? (
                        // eslint-disable-next-line @next/next/no-img-element -- pre-sized thumbnail
                        <img
                          src={image.url}
                          alt=""
                          className={styles.photo}
                          loading="lazy"
                          width={160}
                          height={200}
                        />
                      ) : image?.demo_art ? (
                        <span className={styles.stageArt} aria-hidden="true">
                          <GarmentArt kind={image.demo_art as ArtKind} colour={image.tone} />
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </section>

        <div className={styles.info}>
          <div>
            <p className={styles.category}>{product.category.name}</p>
            <h1 className={styles.name}>{product.name}</h1>
            <p className={styles.price}>
              {selected ? (
                <Price
                  amount={selected.price.amount}
                  currency={selected.price.currency}
                  locale={locale}
                />
              ) : low && high ? (
                <>
                  <Price amount={low.price.amount} currency={low.price.currency} locale={locale} />
                  {low.price.amount !== high.price.amount ? (
                    <>
                      {" – "}
                      <Price
                        amount={high.price.amount}
                        currency={high.price.currency}
                        locale={locale}
                      />
                    </>
                  ) : null}
                </>
              ) : null}
            </p>
          </div>

          <fieldset className={styles.group}>
            <legend className={styles.legend}>{t("colour", { name: colour.name })}</legend>
            <ul className={styles.options}>
              {colours.map((c) => (
                <li key={c.slug}>
                  <Link
                    href={href(c.slug, size)}
                    scroll={false}
                    className={c.slug === colour.slug ? styles.swatchActive : styles.swatch}
                    aria-label={t("colourOption", { name: c.name })}
                    aria-current={c.slug === colour.slug ? "true" : undefined}
                  >
                    <CollectionTone tone={c.hex} className={styles.swatchDot} />
                  </Link>
                </li>
              ))}
            </ul>
          </fieldset>

          <fieldset className={styles.group}>
            <legend className={styles.legend}>{t("size")}</legend>
            <ul className={styles.options}>
              {product.sizes.map((s) => {
                const variant = fresh.get(`${colour.slug}|${s}`);
                if (!variant) return null;
                const active = s === size;
                return (
                  <li key={s}>
                    <Link
                      href={href(colour.slug, s)}
                      scroll={false}
                      className={
                        active
                          ? styles.sizeActive
                          : variant.available
                            ? styles.size
                            : styles.sizeSoldOut
                      }
                      aria-label={
                        variant.available
                          ? t("sizeOption", { size: s })
                          : t("unavailableSize", { size: s })
                      }
                      aria-current={active ? "true" : undefined}
                      dir="ltr"
                    >
                      {s}
                    </Link>
                  </li>
                );
              })}
            </ul>
            <p
              role="status"
              className={
                selected
                  ? selected.available
                    ? styles.inStock
                    : styles.soldOut
                  : anyAvailable
                    ? styles.note
                    : styles.soldOut
              }
            >
              {selected
                ? selected.available
                  ? t("inStock")
                  : t("soldOut")
                : anyAvailable
                  ? t("chooseSize")
                  : t("soldOut")}
            </p>
          </fieldset>

          <div className={styles.group}>
            {/* Inert until the bag exists (M7); a server-rendered page needs no click handler for it. */}
            <button type="button" className={styles.bag} disabled aria-describedby="bag-note">
              {t("addToBag")}
            </button>
            {!routeReady.cart ? (
              <p id="bag-note" className={styles.note}>
                {t("bagSoon")}
              </p>
            ) : null}
          </div>

          {product.size_chart.length > 0 ? (
            <details className={styles.disclosure}>
              <summary>{t("sizeChart")}</summary>
              <div className={styles.chartWrap}>
                <table className={styles.chart}>
                  <thead>
                    <tr>
                      <th scope="col">{t("measurement")}</th>
                      {product.sizes.map((s) => (
                        <th key={s} scope="col" dir="ltr">
                          {s}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {product.size_chart.map((row) => (
                      <tr key={row.name}>
                        <th scope="row">{row.name}</th>
                        {product.sizes.map((s) => (
                          <td key={s} dir="ltr">
                            {row.values[s] ?? "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}

          <details className={styles.disclosure} open>
            <summary>{t("details")}</summary>
            {product.description ? <p className={styles.details}>{product.description}</p> : null}
            <dl className={styles.details}>
              {product.fabric ? (
                <>
                  <dt>{t("fabric")}</dt>
                  <dd>{product.fabric}</dd>
                </>
              ) : null}
              {product.care ? (
                <>
                  <dt>{t("care")}</dt>
                  <dd>{product.care}</dd>
                </>
              ) : null}
              {product.fit_note ? (
                <>
                  <dt>{t("fit")}</dt>
                  <dd>{product.fit_note}</dd>
                </>
              ) : null}
            </dl>
            <p className={styles.note} dir="ltr">
              {t("styleNumber", { number: product.style_number })}
            </p>
            {product.collections.length > 0 ? (
              <p className={styles.note}>
                {t("inCollections")}{" "}
                {product.collections.map((c, i) => (
                  <span key={c.slug}>
                    {i > 0 ? ", " : ""}
                    <Link href={`/collections/${c.slug}`}>{c.name}</Link>
                  </span>
                ))}
              </p>
            ) : null}
          </details>
        </div>
      </div>
    </div>
  );
}
