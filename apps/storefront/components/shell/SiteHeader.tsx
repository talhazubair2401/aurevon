import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { Icon, Wordmark } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MobileMenu } from "./MobileMenu";
import { primaryNav, utilityLinks } from "./navigation";
import styles from "./Shell.module.css";

/**
 * Site header. PROVISIONAL LAYOUT (decision 0004, item 5): semantics, behaviour and accessibility are final;
 * placement and styling are neutral defaults until the A-04 homepage reference is supplied.
 */
export async function SiteHeader({ locale }: { locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "shell" });
  const nav = await getTranslations({ locale, namespace: "nav" });
  const items = primaryNav.map((item) => ({ href: item.href, label: nav(item.key) }));

  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <div className={styles.headerStart}>
          <MobileMenu
            items={items}
            labels={{
              open: t("openMenu"),
              close: t("closeMenu"),
              title: t("menu"),
              nav: t("primaryNav"),
            }}
            languageSwitcher={<LanguageSwitcher locale={locale} />}
          />
          <Link href="/" className={styles.brand} aria-label={t("home")}>
            <Wordmark size="md" />
          </Link>
        </div>

        <nav aria-label={t("primaryNav")} className={styles.primaryNav}>
          <ul className={styles.navList}>
            {items.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className={styles.navLink}>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className={styles.utilities}>
          <div className={styles.desktopOnly}>
            <LanguageSwitcher locale={locale} />
          </div>
          <Link href={utilityLinks.search} className={styles.iconLink} aria-label={t("search")}>
            <Icon name="search" />
          </Link>
          <Link href={utilityLinks.account} className={styles.iconLink} aria-label={t("account")}>
            <Icon name="account" />
          </Link>
          <Link href={utilityLinks.bag} className={styles.iconLink} aria-label={t("bag")}>
            <Icon name="bag" />
          </Link>
        </div>
      </div>
    </header>
  );
}
