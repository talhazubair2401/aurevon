import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale } from "@aurevon/i18n";
import { AccountDashboard } from "@/components/account/AccountDashboard";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/account">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "account" });
  // Personal pages: never indexed.
  return pageMetadata({ locale, path: "/account", title: t("kicker"), noindex: true });
}

export default async function Page({ params }: PageProps<"/[locale]/account">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  return (
    <Suspense>
      <AccountDashboard />
    </Suspense>
  );
}
