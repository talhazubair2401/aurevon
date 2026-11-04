/**
 * Locales and formatting (MTS v2.1 A-18, §3, M15). English and Urdu at launch, Urdu right-to-left.
 * Currency and dates always go through Intl, so PKR and Asia/Karachi are configuration, not code.
 */
import en from "./messages/en.json";
import ur from "./messages/ur.json";

export const locales = ["en", "ur"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

export type Direction = "ltr" | "rtl";
const directions: Record<Locale, Direction> = { en: "ltr", ur: "rtl" };

/** Native names, shown in the language switcher in their own script. */
export const localeNames: Record<Locale, string> = { en: "English", ur: "اردو" };

/** Launch market settings (A-02). Global rollout changes these values, not the code that uses them. */
export const market = { currency: "PKR", timeZone: "Asia/Karachi", country: "PK" } as const;

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (locales as readonly string[]).includes(value);
}

export function directionOf(locale: Locale): Direction {
  return directions[locale];
}

/** Intl locale tags: Urdu in Pakistan uses Latin digits in commerce by default. */
const intlTags: Record<Locale, string> = { en: "en-PK", ur: "ur-PK" };

export function formatMoney(
  amount: string | number,
  locale: Locale,
  currency: string = market.currency,
): string {
  // Money arrives from the API as a decimal string (MTS §8); format only, never calculate here.
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(value)) throw new Error(`Invalid amount: ${String(amount)}`);
  return new Intl.NumberFormat(intlTags[locale], {
    style: "currency",
    currency,
    numberingSystem: "latn",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatDate(
  value: Date | string,
  locale: Locale,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat(intlTags[locale], {
    timeZone: market.timeZone,
    numberingSystem: "latn",
    ...options,
  }).format(date);
}

export type Messages = typeof en;
export const messages: Record<Locale, Messages> = { en, ur };
