"use client";

import { useTranslations } from "next-intl";
import { localeNames, locales, type Locale } from "@aurevon/i18n";
import { Link, usePathname } from "@/i18n/navigation";
import styles from "./Shell.module.css";

/** Links to the same page in the other language(s). Each name is shown in its own script and language. */
export function LanguageSwitcher({ locale }: { locale: Locale }) {
  const t = useTranslations("shell");
  const pathname = usePathname();
  const others = locales.filter((l) => l !== locale);

  return (
    <ul className={styles.languages} aria-label={t("language")}>
      {others.map((other) => (
        <li key={other}>
          <Link
            href={pathname}
            locale={other}
            hrefLang={other}
            className={styles.languageLink}
            aria-label={t("switchTo", { language: localeNames[other] })}
          >
            <span lang={other} dir={other === "ur" ? "rtl" : "ltr"}>
              {localeNames[other]}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
