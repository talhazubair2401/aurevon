import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { isLocale } from "@aurevon/i18n";
import { TicketThread } from "@/components/support/TicketThread";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/support/ticket">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = await getTranslations({ locale, namespace: "support" });
  return pageMetadata({ locale, path: "/support/ticket", title: t("ticketTitle"), noindex: true });
}

export default async function Page({ params }: PageProps<"/[locale]/support/ticket">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  return <TicketThread />;
}
