/**
 * Shell navigation. Menu links (header, footer "Shop" and "Help") come from the CMS (GET /cms/navigation,
 * managed in the staff dashboard under Content › Navigation). Only the utility icons are fixed here.
 * PROVISIONAL placement and grouping until the A-04 references are supplied (decision 0004, item 5).
 */
export const utilityLinks = {
  search: "/search",
  account: "/account",
  bag: "/cart",
} as const;

/** CMS hrefs are storefront paths; anything else falls back to Shop All. */
export function safeHref(href: string | undefined, fallback = "/shop"): string {
  return href && href.startsWith("/") && !href.startsWith("//") ? href : fallback;
}
