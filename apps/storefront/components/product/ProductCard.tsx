import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { Price } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import type { ProductCard as Card } from "@/lib/api";
import { GarmentArt, type ArtKind } from "../art/GarmentArt";
import styles from "./ProductCard.module.css";

/** A product in a grid or row: 4:5 image, name, category, price, colours. Links to its product page (M5). */
export async function ProductCard({ product, locale }: { product: Card; locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "product" });
  const image = product.image;
  const priceRange = product.price_min.amount !== product.price_max.amount;

  return (
    <article className={styles.card}>
      <Link href={`/products/${product.slug}`} className={styles.link}>
        <div className={styles.media}>
          {image?.demo_art ? (
            <div className={styles.art}>
              <GarmentArt kind={image.demo_art as ArtKind} colour={image.tone} />
            </div>
          ) : null}
          {product.is_new ? <span className={styles.badge}>{t("new")}</span> : null}
        </div>
        <div className={styles.body}>
          <p className={styles.category}>{product.category.name}</p>
          <h3 className={styles.name}>{product.name}</h3>
          <p className={styles.price}>
            <Price
              amount={product.price_min.amount}
              currency={product.price_min.currency}
              locale={locale}
            />
            {priceRange ? (
              <>
                {" – "}
                <Price
                  amount={product.price_max.amount}
                  currency={product.price_max.currency}
                  locale={locale}
                />
              </>
            ) : null}
          </p>
        </div>
      </Link>
      <ul className={styles.swatches} aria-label={t("colours", { count: product.colours.length })}>
        {product.colours.map((c) => (
          <li key={c.slug} title={c.name}>
            {/* SVG fill, not an inline style: the CSP allows no style attributes (decision 0005). */}
            <svg className={styles.swatch} viewBox="0 0 12 12" aria-hidden="true" focusable="false">
              <circle cx="6" cy="6" r="5.5" fill={c.hex} />
            </svg>
            <span className={styles.srOnly}>{c.name}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}
