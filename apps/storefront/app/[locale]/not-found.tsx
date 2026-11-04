import { ButtonLink } from "@aurevon/ui";
import { getPathname } from "@/i18n/navigation";
import { getLocale, getTranslations } from "next-intl/server";

export default async function NotFound() {
  const locale = await getLocale();
  const t = await getTranslations({ locale, namespace: "notFound" });
  return (
    <div className="av-centred">
      <h1 className="av-heading">{t("title")}</h1>
      <p>{t("body")}</p>
      <p>
        <ButtonLink href={getPathname({ href: "/", locale })} variant="secondary">
          {t("back")}
        </ButtonLink>
      </p>
    </div>
  );
}
