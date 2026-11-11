import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { directionOf, type Locale } from "@aurevon/i18n";
import { colors } from "@aurevon/design-tokens";
import "@aurevon/design-tokens/tokens.css";
import "../globals.css";
import { displayFont, uiFont, urduReadingFont, urduUiFont } from "../fonts";
import { routing } from "@/i18n/routing";
import { SiteHeader } from "@/components/shell/SiteHeader";
import { SiteFooter } from "@/components/shell/SiteFooter";
import { SkipLink } from "@aurevon/ui";
import { siteUrl } from "@/lib/seo";

// Every page renders per request so it carries that request's CSP nonce (decision 0005, D-08). Reading the
// request headers opts the whole tree out of static generation; Next.js then stamps the nonce on its scripts.

export const viewport: Viewport = { themeColor: colors.midnightIndigo };

export async function generateMetadata({ params }: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    // Relative canonical and alternate URLs resolve against the public site address (M17).
    metadataBase: new URL(siteUrl()),
    title: { default: t("title"), template: `%s · ${t("title")}` },
    description: t("tagline"),
    applicationName: t("title"),
  };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  await headers();
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "shell" });
  const fontVars = [displayFont, uiFont, urduReadingFont, urduUiFont]
    .map((f) => f.variable)
    .join(" ");

  return (
    <html lang={locale} dir={directionOf(locale as Locale)} className={fontVars}>
      <body>
        <NextIntlClientProvider>
          <SkipLink>{t("skipToContent")}</SkipLink>
          <SiteHeader locale={locale as Locale} />
          <main id="main" tabIndex={-1} className="av-main">
            {children}
          </main>
          <SiteFooter locale={locale as Locale} />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
