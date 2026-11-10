import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale } from "@aurevon/i18n";
import { EmailLink } from "@/components/newsletter/EmailLink";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/newsletter/confirm">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "newsletter" });
  return pageMetadata({
    locale,
    path: "/newsletter/confirm",
    title: t("confirmTitle"),
    noindex: true,
  });
}

export default async function Page({ params }: PageProps<"/[locale]/newsletter/confirm">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  return <EmailLink kind="confirm" />;
}
