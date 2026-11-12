import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { colors } from "@aurevon/design-tokens";
import { decoderPath, HeroViewer } from "@aurevon/viewer3d";
import { HeroVideo } from "./HeroVideo";
import { MotionToggle } from "./MotionToggle";
import { Link } from "@/i18n/navigation";
import {
  getProduct,
  type CollectionCard,
  type HomeSection,
  type ProductCard as Card,
} from "@/lib/api";
import { ProductCard } from "../product/ProductCard";
import { safeHref } from "../shell/navigation";
import { Reveal } from "./Reveal";
import styles from "./HomeSections.module.css";

type Content = Record<string, string | undefined>;

/**
 * Homepage, "Midnight Indigo & Amber" (decision 0008; layout from the AureVon Homepage Redesign Plan, 11 Nov
 * 2026). Every section's copy and order come from the CMS. Imagery is real or clearly marked as pending: no
 * illustration stands in for a photograph here.
 */

/** A frame where a photograph will go, labelled so nobody mistakes it for finished imagery. */
async function PendingImage({
  locale,
  what,
  className,
  hanger = false,
}: {
  locale: Locale;
  what: "hero" | "collection" | "story";
  className?: string | undefined;
  hanger?: boolean;
}) {
  const t = await getTranslations({ locale, namespace: "home" });
  return (
    <div
      className={[styles.pending, className ?? ""].filter(Boolean).join(" ")}
      data-placeholder={what}
    >
      <div className={styles.pendingLight} aria-hidden="true" />
      {hanger ? (
        <svg
          className={styles.pendingHanger}
          viewBox="0 0 240 120"
          aria-hidden="true"
          focusable="false"
        >
          {/* Brass rail, hook and walnut hanger: where the hero garment will hang. */}
          <line x1="0" y1="10" x2="240" y2="10" className={styles.rail} />
          <path d="M120 10 L120 30 Q120 42 130 42 Q140 42 140 34" className={styles.hook} />
          <path
            d="M120 44 L40 92 Q36 96 42 98 L198 98 Q204 96 200 92 Z"
            className={styles.hangerBody}
          />
        </svg>
      ) : null}
      <p className={styles.pendingLabel}>{t(`pending.${what}`)}</p>
    </div>
  );
}

/** The hero garment: a CMS-chosen product. Its photograph is the poster; its approved model, when the catalogue
 * returns one (3D on for shoppers after V-01 to V-03), replaces the poster once loaded. */
async function heroGarment(slug: string | undefined, locale: Locale) {
  if (!slug) return null;
  const product = await getProduct(slug, locale).catch(() => null);
  if (!product) return null;
  const photo = product.images.find((i) => i.url);
  const colour = photo?.colour || product.colours[0]?.slug || "";
  const model =
    product.model3d?.by_colour[colour] ?? Object.values(product.model3d?.by_colour ?? {})[0];
  return {
    href: `/products/${product.slug}`,
    name: product.name,
    poster: photo?.url ? { url: photo.url, alt: photo.alt || product.name } : null,
    model: model ? { url: model.url, variant: model.variant ?? "" } : null,
  };
}

export async function Hero({ content, locale }: { content: Content; locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "home" });
  const garment = await heroGarment(content.feature_product, locale);
  const poster = garment?.poster ? (
    // eslint-disable-next-line @next/next/no-img-element -- served pre-sized from object storage (M5)
    <img
      src={garment.poster.url}
      alt={garment.poster.alt}
      className={styles.heroPhoto}
      width={1600}
      height={2000}
      fetchPriority="high"
    />
  ) : null;

  // A background video sets the cinematic layout; an approved 3D model still takes precedence over it.
  const video = !garment?.model && content.video?.startsWith("/media/") ? content.video : undefined;
  const videoPoster = content.video_poster?.startsWith("/media/")
    ? content.video_poster
    : undefined;

  return (
    <section
      className={styles.hero}
      aria-labelledby="hero-title"
      data-video={video ? "" : undefined}
    >
      {video ? (
        <div className={styles.heroBackdrop}>
          <HeroVideo src={video} poster={videoPoster ?? garment?.poster?.url} />
          <div className={styles.heroScrim} aria-hidden="true" />
        </div>
      ) : null}
      <div className={styles.heroInner}>
        <div className={styles.heroCopy}>
          {content.eyebrow ? (
            <p className={`${styles.eyebrow} ${styles.enter1}`}>{content.eyebrow}</p>
          ) : null}
          <h1 id="hero-title" className={styles.heroTitle}>
            <SplitLines text={content.title ?? ""} />
          </h1>
          {content.subtitle ? (
            <p className={`${styles.heroSubtitle} ${styles.enter3}`}>{content.subtitle}</p>
          ) : null}
          <div className={`${styles.heroActions} ${styles.enter4}`}>
            {content.primary_label ? (
              <Link href={safeHref(content.primary_href)} className={styles.ctaPrimary}>
                {content.primary_label}
              </Link>
            ) : null}
            {content.secondary_label ? (
              <Link href={safeHref(content.secondary_href)} className={styles.ctaQuiet}>
                {content.secondary_label}
              </Link>
            ) : null}
          </div>
        </div>

        {video ? (
          garment ? (
            <Link
              href={garment.href}
              className={`${styles.heroCaption} ${styles.heroCaptionFloat}`}
            >
              <span>{garment.name}</span>
            </Link>
          ) : null
        ) : (
          <div className={`${styles.heroStage} ${styles.enterStage}`}>
            <div className={styles.heroLight} aria-hidden="true" />
            {poster && garment?.model ? (
              <HeroViewer
                src={garment.model.url}
                variant={garment.model.variant}
                decoderPath={decoderPath()}
                loadingLabel={t("loading3d")}
                className={styles.heroViewer}
              >
                {poster}
              </HeroViewer>
            ) : poster ? (
              <div className={styles.heroViewer}>{poster}</div>
            ) : (
              <PendingImage locale={locale} what="hero" hanger className={styles.heroViewer} />
            )}
            {garment ? (
              <Link href={garment.href} className={styles.heroCaption}>
                <span>{garment.name}</span>
                {/* Only a real, approved model earns the 3D label (never a photograph or placeholder). */}
                {garment.model && poster ? (
                  <span className={styles.badge3d}>{t("view3d")}</span>
                ) : null}
              </Link>
            ) : null}
          </div>
        )}
      </div>
      <Marquee text={t("marquee")} />
      <MotionToggle pause={t("pauseMotion")} play={t("playMotion")} />
    </section>
  );
}

/** A slow band of brand words under the hero. Decorative (the words repeat), so hidden from screen readers. */
function Marquee({ text }: { text: string }) {
  const run = Array.from({ length: 4 }, () => text).join(" · ");
  return (
    <div className={styles.marquee} aria-hidden="true">
      <div className={styles.marqueeTrack}>
        <span>{run} · </span>
        <span>{run} · </span>
      </div>
    </div>
  );
}

/** The headline rises line by line (each sentence is a line); screen readers read it as one heading. */
function SplitLines({ text }: { text: string }) {
  const lines = text
    .match(/[^.!?]+[.!?]*/g)
    ?.map((l) => l.trim())
    .filter(Boolean) ?? [text];
  return (
    <>
      {lines.map((line, i) => (
        <span key={i} className={styles.titleLine}>
          <span className={styles.titleLineInner}>{line}</span>{" "}
        </span>
      ))}
    </>
  );
}

function SectionHeader({
  id,
  eyebrow,
  title,
  subtitle,
  linkLabel,
  linkHref,
  tone = "light",
}: {
  id: string;
  eyebrow?: string | undefined;
  title?: string | undefined;
  subtitle?: string | undefined;
  linkLabel?: string | undefined;
  linkHref?: string | undefined;
  tone?: "light" | "dark";
}) {
  return (
    <div className={`${styles.sectionHeader} ${tone === "dark" ? styles.onDark : ""}`}>
      <div className={styles.sectionHeading}>
        {eyebrow ? <p className={styles.sectionEyebrow}>{eyebrow}</p> : null}
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
    <section className={styles.collectionsBand} aria-labelledby="collections-title">
      <Reveal className={styles.sectionWide}>
        <SectionHeader
          id="collections-title"
          eyebrow={t("collectionsEyebrow")}
          title={content.title}
          subtitle={content.subtitle}
          tone="dark"
        />
        <EditorialCollections collections={collections.slice(0, 3)} locale={locale} />
      </Reveal>
    </section>
  );
}

/** One large collection and two supporting ones; each opens /collections/<slug>. */
async function EditorialCollections({
  collections,
  locale,
}: {
  collections: CollectionCard[];
  locale: Locale;
}) {
  const t = await getTranslations({ locale, namespace: "home" });
  return (
    <ul className={styles.editorial}>
      {collections.map((c, index) => (
        <li key={c.slug} className={index === 0 ? styles.editorialLead : styles.editorialSide}>
          <Link
            href={`/collections/${encodeURIComponent(c.slug)}`}
            className={styles.editorialCard}
          >
            <div className={styles.editorialMedia}>
              {c.image?.url ? (
                // eslint-disable-next-line @next/next/no-img-element -- served pre-sized from object storage (M5)
                <img src={c.image.url} alt="" className={styles.editorialPhoto} loading="lazy" />
              ) : (
                <PendingImage locale={locale} what="collection" />
              )}
            </div>
            <div className={styles.editorialText}>
              <h3 className={styles.editorialName}>{c.name}</h3>
              {c.description && index === 0 ? (
                <p className={styles.editorialDescription}>{c.description}</p>
              ) : null}
              <span className={styles.editorialCta}>{t("explore")}</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Collection cards for the collections index (unchanged layout, new palette). */
export async function CollectionCardList({
  collections,
  locale,
  headingLevel = 3,
}: {
  collections: CollectionCard[];
  locale: Locale;
  headingLevel?: 2 | 3;
}) {
  const t = await getTranslations({ locale, namespace: "home" });
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <ul className={styles.collections}>
      {collections.map((c) => (
        <li key={c.slug}>
          <Link href={`/collections/${encodeURIComponent(c.slug)}`} className={styles.collection}>
            {/* Tone as an SVG fill: no inline styles under the CSP (decision 0005). */}
            <CollectionTone tone={c.tone} className={styles.collectionTone} />
            {c.image?.url ? (
              // eslint-disable-next-line @next/next/no-img-element -- served pre-sized from object storage (M5)
              <img src={c.image.url} alt="" className={styles.editorialPhoto} loading="lazy" />
            ) : null}
            <div className={styles.collectionText}>
              <Heading className={styles.collectionName}>{c.name}</Heading>
              {c.description ? (
                <p className={styles.collectionDescription}>{c.description}</p>
              ) : null}
              <span className={styles.collectionCta}>{t("explore")}</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A collection's background tone as an SVG fill (no inline styles under the CSP, decision 0005). */
export function CollectionTone({
  tone,
  className,
}: {
  tone: string;
  className?: string | undefined;
}) {
  return (
    <svg className={className} preserveAspectRatio="none" viewBox="0 0 1 1" aria-hidden="true">
      <rect width="1" height="1" fill={/^#[0-9a-fA-F]{6}$/.test(tone) ? tone : colors.deepIndigo} />
    </svg>
  );
}

export async function ProductSection({
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
  const t = await getTranslations({ locale, namespace: "home" });
  return (
    <section className={styles.section} aria-labelledby={id}>
      <Reveal>
        <SectionHeader
          id={id}
          eyebrow={layout === "row" ? t("newEyebrow") : t("featuredEyebrow")}
          title={content.title}
          linkLabel={content.link_label}
          linkHref={content.link_href}
        />
        {/* A sideways-scrolling row must be reachable by keyboard (WCAG 2.1.1). No automatic movement. */}
        <ul
          className={layout === "grid" ? styles.grid : styles.row}
          {...(layout === "row" ? { tabIndex: 0, "aria-labelledby": id } : {})}
        >
          {products.map((p) => (
            <li key={p.slug}>
              <ProductCard product={p} locale={locale} />
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}

export async function BrandStory({ content, locale }: { content: Content; locale: Locale }) {
  return (
    <section className={styles.story} aria-labelledby="story-title">
      <Reveal className={styles.storyInner}>
        <div className={styles.storyMedia}>
          {content.image?.startsWith("/media/") ? (
            // eslint-disable-next-line @next/next/no-img-element -- served pre-sized from the media library
            <img src={content.image} alt="" className={styles.editorialPhoto} loading="lazy" />
          ) : (
            <PendingImage locale={locale} what="story" />
          )}
        </div>
        <div className={styles.storyCopy}>
          {content.eyebrow ? <p className={styles.eyebrow}>{content.eyebrow}</p> : null}
          <h2 id="story-title" className={styles.storyTitle}>
            {content.title}
          </h2>
          <span className={styles.storyRule} aria-hidden="true" />
          {content.body ? <p className={styles.storyBody}>{content.body}</p> : null}
          {content.link_label ? (
            <Link href={safeHref(content.link_href)} className={styles.ctaQuiet}>
              {content.link_label}
            </Link>
          ) : null}
        </div>
      </Reveal>
    </section>
  );
}

export function renderSection(section: HomeSection, locale: Locale) {
  const content = section.content as Content;
  switch (section.key) {
    case "hero":
      return <Hero key={section.key} content={content} locale={locale} />;
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
      return <BrandStory key={section.key} content={content} locale={locale} />;
    default:
      return null;
  }
}
