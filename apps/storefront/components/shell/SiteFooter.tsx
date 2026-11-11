import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { Wordmark } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import { Newsletter } from "@/components/newsletter/Newsletter";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { getNavigation } from "@/lib/api";
import { safeHref } from "./navigation";
import styles from "./Shell.module.css";

type Item = { href: string; label: string };

// Policies are the legal pages; "About" gathers the brand's own pages. Everything else stays where staff put it
// in the CMS menus (Content › Navigation).
const POLICY = /^\/pages\/(privacy|terms|cookies)\b/;
const ABOUT = /^\/pages\/(about|atelier|story)\b/;

/**
 * Site footer, "Midnight Indigo & Amber" (decision 0008): brand and newsletter, then Shop, Customer care, About
 * and Policies from the CMS menus, then language and copyright. No payment or courier marks until P-06 and
 * P-07 are decided.
 */
export async function SiteFooter({ locale }: { locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "shell" });
  const nav = await getTranslations({ locale, namespace: "nav" });
  const meta = await getTranslations({ locale, namespace: "meta" });
  const menus = await getNavigation(locale);
  const all: Item[] = [...menus.footer_shop, ...menus.footer_help].map((i) => ({
    href: safeHref(i.href),
    label: i.label,
  }));
  const shop = menus.footer_shop
    .map((i) => ({ href: safeHref(i.href), label: i.label }))
    .filter((i) => !ABOUT.test(i.href) && !POLICY.test(i.href));
  const care = menus.footer_help
    .map((i) => ({ href: safeHref(i.href), label: i.label }))
    .filter((i) => !ABOUT.test(i.href) && !POLICY.test(i.href));
  const about = all.filter((i) => ABOUT.test(i.href));
  const policies = all.filter((i) => POLICY.test(i.href));
  const groups = [
    { key: "shop", items: shop },
    { key: "help", items: care },
    { key: "about", items: about },
    { key: "policies", items: policies },
  ].filter((group) => group.items.length > 0);
  // Pages render per request (decision 0005), so this is the current year.
  const year = new Date().getFullYear();

  return (
    <footer className={styles.footer} data-surface="dark">
      <div className={styles.footerInner}>
        <div className={styles.footerTop}>
          <div className={styles.footerBrand}>
            <Wordmark size="md" />
            <p className={styles.footerTagline}>{meta("tagline")}</p>
          </div>
          <div className={styles.footerNewsletter}>
            <Newsletter source="footer" headingId="footer-newsletter-title" compact />
          </div>
        </div>
        <nav aria-label={t("footerNav")} className={styles.footerNav}>
          {groups.map((group) => (
            <div key={group.key} className={styles.footerGroup}>
              <h2 className={styles.footerHeading}>{nav(group.key)}</h2>
              <ul className={styles.footerList}>
                {group.items.map((item) => (
                  <li key={item.href}>
                    <Link href={item.href} className={styles.footerLink}>
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className={styles.footerBottom}>
          <LanguageSwitcher locale={locale} />
          <p className={styles.copyright}>{t("copyright", { year })}</p>
        </div>
      </div>
    </footer>
  );
}
