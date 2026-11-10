/**
 * Routes that later milestones build (MTS §16). Until a route exists, the storefront doesn't link to it, so
 * no control leads to a "not found" page. Switch each on in the milestone that builds the page.
 */
export const routeReady = {
  products: true, // product detail: M5
  search: true, // search: M5 (R-07)
  account: true, // account pages: M7
  cart: true, // bag and checkout: M7
} as const;
