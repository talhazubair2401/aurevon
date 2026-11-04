import { getTranslations, setRequestLocale } from "next-intl/server";
import { Wordmark } from "@aurevon/ui";
import styles from "./page.module.css";

// Shell placeholder. The approved homepage (A-04) is built in M4 from the reference files; nothing here
// stands in for its design (decision 0004, item 5).
export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "meta" });
  const home = await getTranslations({ locale, namespace: "home" });

  return (
    <section className={styles.placeholder} aria-labelledby="home-title">
      <Wordmark as="h1" size="lg" id="home-title" />
      <p className={styles.tagline}>{t("tagline")}</p>
      <hr className={styles.rule} />
      <p className={styles.note}>{home("placeholderNote")}</p>
    </section>
  );
}
