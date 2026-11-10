import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { formatDate, isLocale, type Locale } from "@aurevon/i18n";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { ContactForm } from "@/components/support/ContactForm";
import styles from "@/components/content/Content.module.css";
import { getPage, type CmsPage } from "@/lib/api";
import { redirectOrNotFound } from "@/lib/redirects";
import { pageMetadata } from "@/lib/seo";

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

async function load(locale: string, slug: string): Promise<CmsPage | null> {
  if (!isLocale(locale) || !SLUG.test(slug)) return null;
  return getPage(slug, locale);
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/pages/[slug]">): Promise<Metadata> {
  const { locale, slug } = await params;
  const page = await load(locale, slug);
  if (!page) return {};
  return pageMetadata({
    locale: locale as Locale,
    path: `/pages/${page.slug}`,
    title: page.seo_title || page.title,
    description: page.seo_description || undefined,
  });
}

/**
 * Content and policy pages from the CMS (M07, MTS §6 Page/PolicyPage). The body is plain-text blocks, rendered
 * as text: there is no HTML in CMS content. A page not yet translated is shown in English, marked as such.
 */
export default async function ContentPage({ params }: PageProps<"/[locale]/pages/[slug]">) {
  const { locale: raw, slug } = await params;
  if (!isLocale(raw)) notFound();
  setRequestLocale(raw);
  const locale = raw as Locale;
  const page = await load(locale, slug);
  if (!page) return redirectOrNotFound(locale, `/pages/${slug}`);
  const t = await getTranslations({ locale, namespace: "page" });
  const fallback = locale !== "en" && !page.translated;

  return (
    <div className={styles.page}>
      <div className={styles.article}>
        <Breadcrumbs locale={locale} items={[{ name: page.title, path: `/pages/${page.slug}` }]} />
      </div>
      <article
        className={styles.article}
        aria-labelledby="page-title"
        {...(fallback ? { lang: "en", dir: "ltr" } : {})}
      >
        <header>
          {page.kind === "policy" ? (
            <p className={styles.eyebrow} lang={locale} dir={locale === "ur" ? "rtl" : "ltr"}>
              {t("policy")}
            </p>
          ) : null}
          <h1 id="page-title" className={styles.title}>
            {page.title}
          </h1>
          {page.summary ? <p className={styles.summary}>{page.summary}</p> : null}
          {page.kind === "policy" ? (
            <p className={styles.meta} lang={locale} dir={locale === "ur" ? "rtl" : "ltr"}>
              {t("updated", { date: formatDate(page.updated_at, locale) })}
            </p>
          ) : null}
          {fallback ? (
            <p className={styles.notice} lang={locale} dir="rtl">
              {t("englishOnly")}
            </p>
          ) : null}
        </header>
        <div className={styles.body}>
          {page.body.map((block, index) => {
            if (block.type === "heading") return <h2 key={index}>{block.text}</h2>;
            if (block.type === "list")
              return (
                <ul key={index}>
                  {(block.items ?? []).map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              );
            return <p key={index}>{block.text}</p>;
          })}
        </div>
        {page.slug === "contact" ? <ContactForm /> : null}
      </article>
    </div>
  );
}
