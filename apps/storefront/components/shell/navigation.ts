/**
 * Shell navigation (M3). Labels are message keys; hrefs are the route names in MTS §15.
 * PROVISIONAL: the final items and grouping come from the A-04 homepage and Shop All references and, from
 * M4, from CMS navigation (GET /cms/navigation). Routes not yet built show the locale's not-found page.
 */
export interface NavItem {
  key: string;
  href: string;
}

export const primaryNav: NavItem[] = [
  { key: "shopAll", href: "/shop" },
  { key: "collections", href: "/collections" },
];

export const footerNav: Array<{ key: string; items: NavItem[] }> = [
  { key: "shop", items: primaryNav },
  {
    key: "help",
    items: [
      { key: "contact", href: "/pages/contact" },
      { key: "shipping", href: "/pages/shipping" },
      { key: "returns", href: "/pages/returns" },
      { key: "privacy", href: "/pages/privacy" },
      { key: "terms", href: "/pages/terms" },
    ],
  },
];

export const utilityLinks = {
  search: "/search",
  account: "/account",
  bag: "/cart",
} as const;
