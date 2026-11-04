import { defineRouting } from "next-intl/routing";
import { defaultLocale, locales } from "@aurevon/i18n";

// Locale routes /en and /ur (MTS §3). Every storefront URL carries its locale, so pages stay cacheable.
export const routing = defineRouting({
  locales,
  defaultLocale,
  localePrefix: "always",
});
