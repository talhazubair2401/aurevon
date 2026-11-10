import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale } from "@aurevon/i18n";
import { PaymentReturn } from "@/components/checkout/PaymentReturn";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/checkout/return">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "checkout" });
  return pageMetadata({ locale, path: "/checkout/return", title: t("confirming"), noindex: true });
}

/** Back from the payment page: the order number arrives in the query string. */
export default async function Page({
  params,
  searchParams,
}: PageProps<"/[locale]/checkout/return">) {
  const { locale } = await params;
  const order = (await searchParams).order;
  if (!isLocale(locale) || typeof order !== "string" || !/^AV\d{6,}$/.test(order)) notFound();
  setRequestLocale(locale);
  return <PaymentReturn number={order} />;
}
