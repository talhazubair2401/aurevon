import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { Icon, Wordmark } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MobileMenu } from "./MobileMenu";
import { ScrollState } from "./ScrollState";
import { getNavigation } from "@/lib/api";
import { BagLink } from "@/components/cart/BagLink";
import { routeReady } from "@/lib/features";
import { safeHref, utilityLinks } from "./navigation";
import styles from "./Shell.module.css";

/**
 * Site header, "Midnight Indigo & Amber" (decision 0008): a Midnight Indigo bar with Warm Ivory type; amber
 * marks hover and the current page. It tightens and gains a hairline once the page scrolls (ScrollState).
 */
export async function SiteHeader({ locale }: { locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "shell" });
  const menus = await getNavigation(locale);
  const items = menus.header.map((item) => ({ href: safeHref(item.href), label: item.label }));

  return (
    <header className={styles.header} data-surface="dark">
      <ScrollState />
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
          {(
            [
              ["search", "search", routeReady.search],
              ["account", "account", routeReady.account],
              ["bag", "bag", routeReady.cart],
            ] as const
          ).map(([key, icon, ready]) =>
            ready && key === "bag" ? (
              <BagLink
                key={key}
                label={t(key)}
                className={styles.iconLink ?? ""}
                countClass={styles.bagCount ?? ""}
                hiddenClass={styles.srOnly ?? ""}
              />
            ) : ready ? (
              <Link
                key={key}
                href={utilityLinks[key]}
                className={styles.iconLink}
                aria-label={t(key)}
              >
                <Icon name={icon} />
              </Link>
            ) : (
              // Not built yet (lib/features.ts): shown, but leads nowhere rather than to "not found".
              <span
                key={key}
                className={`${styles.iconLink} ${styles.iconSoon}`}
                role="img"
                aria-label={t("comingSoon", { label: t(key) })}
                title={t("comingSoon", { label: t(key) })}
              >
                <Icon name={icon} />
              </span>
            ),
          )}
        </div>
      </div>
    </header>
  );
}
