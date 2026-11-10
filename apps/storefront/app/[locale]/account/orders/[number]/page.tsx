import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale } from "@aurevon/i18n";
import { OrderDetail } from "@/components/account/OrderDetail";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/account/orders/[number]">): Promise<Metadata> {
  const { locale, number } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "orders" });
  return pageMetadata({
    locale,
    path: `/account/orders/${number}`,
    title: `${t("order")} ${number}`,
    noindex: true,
  });
}

export default async function Page({ params }: PageProps<"/[locale]/account/orders/[number]">) {
  const { locale, number } = await params;
  if (!isLocale(locale) || !/^AV\d{6,}$/.test(number)) notFound();
  setRequestLocale(locale);
  return (
    <Suspense>
      <OrderDetail number={number} />
    </Suspense>
  );
}
