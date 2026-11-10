import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale } from "@aurevon/i18n";
import { VerifyEmail } from "@/components/account/AuthForms";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/account/verify">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "auth" });
  // Personal pages: never indexed.
  return pageMetadata({ locale, path: "/account/verify", title: t("verifyKicker"), noindex: true });
}

export default async function Page({ params }: PageProps<"/[locale]/account/verify">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
