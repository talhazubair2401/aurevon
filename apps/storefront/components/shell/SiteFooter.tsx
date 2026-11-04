import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { Wordmark } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { getNavigation } from "@/lib/api";
import { safeHref } from "./navigation";
import styles from "./Shell.module.css";

/**
 * Site footer. PROVISIONAL LAYOUT (decision 0004, item 5): link groups and styling are neutral defaults until
 * the A-04 references are supplied. The links come from CMS navigation (M4).
 */
export async function SiteFooter({ locale }: { locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "shell" });
  const nav = await getTranslations({ locale, namespace: "nav" });
  const meta = await getTranslations({ locale, namespace: "meta" });
  const menus = await getNavigation(locale);
  const groups = [
    { key: "shop", items: menus.footer_shop },
    { key: "help", items: menus.footer_help },
  ].filter((group) => group.items.length > 0);
  // Pages render per request (decision 0005), so this is the current year.
  const year = new Date().getFullYear();

  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <div className={styles.footerBrand}>
          <Wordmark size="sm" />
          <p className={styles.footerTagline}>{meta("tagline")}</p>
        </div>
        <nav aria-label={t("footerNav")} className={styles.footerNav}>
          {groups.map((group) => (
            <div key={group.key} className={styles.footerGroup}>
              <h2 className={styles.footerHeading}>{nav(group.key)}</h2>
              <ul className={styles.footerList}>
                {group.items.map((item) => (
                  <li key={item.href}>
                    <Link href={safeHref(item.href)} className={styles.footerLink}>
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
