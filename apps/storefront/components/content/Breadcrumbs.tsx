import { getTranslations } from "next-intl/server";
import type { Locale } from "@aurevon/i18n";
import { Link } from "@/i18n/navigation";
import { absoluteUrl } from "@/lib/seo";
import { JsonLd, breadcrumbs } from "../seo/JsonLd";
import styles from "./Content.module.css";

interface Crumb {
  name: string;
  path: string;
}

/** Visible breadcrumb trail plus its structured-data twin. The last item is the current page. */
export async function Breadcrumbs({ locale, items }: { locale: Locale; items: Crumb[] }) {
  const t = await getTranslations({ locale, namespace: "collections" });
  const trail = [{ name: t("home"), path: "/" }, ...items];
  return (
    <>
      <nav aria-label={t("breadcrumb")} className={styles.breadcrumbs}>
        <ol className={styles.breadcrumbList}>
          {trail.map((item, index) => (
            <li key={item.path} className={styles.breadcrumbItem}>
              {index === trail.length - 1 ? (
                <span aria-current="page">{item.name}</span>
              ) : (
                <Link href={item.path} className={styles.breadcrumbLink}>
                  {item.name}
                </Link>
              )}
            </li>
          ))}
        </ol>
      </nav>
      <JsonLd
        data={breadcrumbs(trail.map((c) => ({ name: c.name, url: absoluteUrl(locale, c.path) })))}
      />
    </>
  );
}
