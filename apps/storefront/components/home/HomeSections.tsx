import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { colors } from "@aurevon/design-tokens";
import { Link } from "@/i18n/navigation";
import type { CollectionCard, HomeSection, ProductCard as Card } from "@/lib/api";
import { GarmentArt, type ArtKind } from "../art/GarmentArt";
import { ProductCard } from "../product/ProductCard";
import styles from "./HomeSections.module.css";

type Content = Record<string, string | undefined>;

/** Hrefs from the CMS are locale-free paths ("/shop?…"); only same-site paths are accepted. */
function safeHref(href: string | undefined, fallback = "/shop"): string {
  return href && href.startsWith("/") && !href.startsWith("//") ? href : fallback;
}

const HERO_PIECES: Array<{ kind: ArtKind; colour: string; className: string }> = [
  { kind: "coat", colour: "#B08B5E", className: "pieceA" },
  { kind: "dress", colour: "#F2EDE4", className: "pieceB" },
  { kind: "blazer", colour: "#1C2230", className: "pieceC" },
];

export function Hero({ content }: { content: Content }) {
  return (
    <section className={styles.hero} aria-labelledby="hero-title">
      <div className={styles.heroInner}>
        <div className={styles.heroCopy}>
          {content.eyebrow ? <p className={styles.eyebrow}>{content.eyebrow}</p> : null}
          <h1 id="hero-title" className={styles.heroTitle}>
            {content.title}
          </h1>
          {content.subtitle ? <p className={styles.heroSubtitle}>{content.subtitle}</p> : null}
          <div className={styles.heroActions}>
            {content.primary_label ? (
              <Link href={safeHref(content.primary_href)} className={styles.ctaLight}>
                {content.primary_label}
              </Link>
            ) : null}
            {content.secondary_label ? (
              <Link href={safeHref(content.secondary_href)} className={styles.ctaOutline}>
                {content.secondary_label}
              </Link>
            ) : null}
          </div>
        </div>
        <div className={styles.heroStage} aria-hidden="true">
          <div className={styles.spotlight} />
          {HERO_PIECES.map((p) => (
            <div key={p.kind} className={`${styles.piece} ${styles[p.className]}`}>
              <GarmentArt kind={p.kind} colour={p.colour} stage="dark" />
            </div>
          ))}
          <div className={styles.floorLine} />
        </div>
      </div>
    </section>
  );
}

function SectionHeader({
  id,
  title,
  subtitle,
  linkLabel,
  linkHref,
}: {
  id: string;
  title?: string | undefined;
  subtitle?: string | undefined;
  linkLabel?: string | undefined;
  linkHref?: string | undefined;
}) {
  return (
    <div className={styles.sectionHeader}>
      <div>
        <h2 id={id} className={styles.sectionTitle}>
          {title}
        </h2>
        {subtitle ? <p className={styles.sectionSubtitle}>{subtitle}</p> : null}
      </div>
      {linkLabel ? (
        <Link href={safeHref(linkHref)} className={styles.sectionLink}>
          {linkLabel}
        </Link>
      ) : null}
    </div>
  );
}

export async function Collections({
  content,
  collections,
  locale,
}: {
  content: Content;
  collections: CollectionCard[];
  locale: Locale;
}) {
  const t = await getTranslations({ locale, namespace: "home" });
  return (
    <section className={styles.section} aria-labelledby="collections-title">
      <SectionHeader id="collections-title" title={content.title} subtitle={content.subtitle} />
      <ul className={styles.collections}>
        {collections.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/shop?collection=${encodeURIComponent(c.slug)}`}
              className={styles.collection}
            >
              {/* Tone as an SVG fill: no inline styles under the CSP (decision 0005). */}
              <svg
                className={styles.collectionTone}
                preserveAspectRatio="none"
                viewBox="0 0 1 1"
                aria-hidden="true"
              >
                <rect
                  width="1"
                  height="1"
                  fill={/^#[0-9a-fA-F]{6}$/.test(c.tone) ? c.tone : colors.deepBrown}
                />
              </svg>
              {c.demo_art ? (
                <div className={styles.collectionArt} aria-hidden="true">
                  <GarmentArt kind={c.demo_art as ArtKind} colour="#F2EDE4" stage="dark" />
                </div>
              ) : null}
              <div className={styles.collectionText}>
                <h3 className={styles.collectionName}>{c.name}</h3>
                {c.description ? (
                  <p className={styles.collectionDescription}>{c.description}</p>
                ) : null}
                <span className={styles.collectionCta}>{t("explore")}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ProductSection({
  id,
  content,
  products,
  locale,
  layout,
}: {
  id: string;
  content: Content;
  products: Card[];
  locale: Locale;
  layout: "grid" | "row";
}) {
  return (
    <section className={styles.section} aria-labelledby={id}>
      <SectionHeader
        id={id}
        title={content.title}
        linkLabel={content.link_label}
        linkHref={content.link_href}
      />
      <ul className={layout === "grid" ? styles.grid : styles.row}>
        {products.map((p) => (
          <li key={p.slug}>
            <ProductCard product={p} locale={locale} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function BrandStory({ content }: { content: Content }) {
  return (
    <section className={styles.story} aria-labelledby="story-title">
      <div className={styles.storyInner}>
        <div className={styles.storyArt} aria-hidden="true">
          <div className={styles.storyFrame}>
            <GarmentArt kind="kurta" colour="#D8C8AE" stage="dark" />
          </div>
        </div>
        <div className={styles.storyCopy}>
          {content.eyebrow ? <p className={styles.storyEyebrow}>{content.eyebrow}</p> : null}
          <h2 id="story-title" className={styles.storyTitle}>
            {content.title}
          </h2>
          {content.body ? <p className={styles.storyBody}>{content.body}</p> : null}
          {content.link_label ? (
            <Link href={safeHref(content.link_href)} className={styles.sectionLink}>
              {content.link_label}
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export function renderSection(section: HomeSection, locale: Locale) {
  const content = section.content as Content;
  switch (section.key) {
    case "hero":
      return <Hero key={section.key} content={content} />;
    case "collections":
      return (
        <Collections
          key={section.key}
          content={content}
          collections={section.collections ?? []}
          locale={locale}
        />
      );
    case "featured_products":
      return (
        <ProductSection
          key={section.key}
          id="featured-title"
          content={content}
          products={section.products ?? []}
          locale={locale}
          layout="grid"
        />
      );
    case "new_arrivals":
      return (
        <ProductSection
          key={section.key}
          id="new-arrivals-title"
          content={content}
          products={section.products ?? []}
          locale={locale}
          layout="row"
        />
      );
    case "brand_story":
      return <BrandStory key={section.key} content={content} />;
    default:
      return null;
  }
}
