import "server-only";
import { createApiClient, unwrap, type components } from "@aurevon/api-client";
import type { Locale } from "@aurevon/i18n";

/**
 * Server-side reads from the Django API. Inside Docker the storefront reaches the API directly
 * (API_INTERNAL_URL=http://api:8000); the browser never needs these calls.
 * Freshness (MTS §3, decision 0005): content and catalogue are cached briefly in the Next.js data cache and
 * tagged, so publishing can refresh them; price and stock decisions are never made from this cache (A-15).
 */
const api = createApiClient({
  baseUrl: process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000",
});

export type ProductCard = components["schemas"]["ProductCard"];
export type CollectionCard = components["schemas"]["CollectionCard"];
export type Facets = components["schemas"]["Facets"];
export type HomeSection = components["schemas"]["HomeSection"];
export type ProductPage = components["schemas"]["ProductPage"];

const CONTENT_SECONDS = 60;
const CATALOGUE_SECONDS = 30;

export async function getHome(locale: Locale) {
  return unwrap(
    await api.GET("/api/v1/cms/home", {
      params: { query: { locale } },
      next: { revalidate: CONTENT_SECONDS, tags: ["cms", "catalogue"] },
    }),
  );
}

export async function getBanner(key: string, locale: Locale) {
  const result = await api.GET("/api/v1/cms/banners/{key}", {
    params: { path: { key }, query: { locale } },
    next: { revalidate: CONTENT_SECONDS, tags: ["cms"] },
  });
  return result.response.ok ? (result.data ?? null) : null;
}

export interface ShopQuery {
  department?: "women" | "men";
  category?: string;
  collection?: string;
  size?: string[];
  colour?: string[];
  price_min?: string;
  price_max?: string;
  sort?: "featured" | "newest" | "price_asc" | "price_desc";
  cursor?: string;
  q?: string;
}

/** Query parameters without the unset ones (the generated types forbid explicit undefined). */
function compact<T extends Record<string, unknown>>(
  obj: T,
): { [K in keyof T]?: Exclude<T[K], undefined> } {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined && v !== "")) as {
    [K in keyof T]?: Exclude<T[K], undefined>;
  };
}

function number(value: string | undefined): number | undefined {
  if (value === undefined || value === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

function filterParams(q: ShopQuery) {
  return {
    department: q.department,
    category: q.category,
    collection: q.collection,
    size: q.size?.length ? q.size.join(",") : undefined,
    colour: q.colour?.length ? q.colour.join(",") : undefined,
    price_min: number(q.price_min),
    price_max: number(q.price_max),
    q: q.q,
  };
}

export async function getProducts(q: ShopQuery, locale: Locale): Promise<ProductPage> {
  return unwrap(
    await api.GET("/api/v1/catalog/products", {
      params: {
        query: compact({ ...filterParams(q), locale, sort: q.sort, cursor: q.cursor, limit: 24 }),
      },
      next: { revalidate: CATALOGUE_SECONDS, tags: ["catalogue"] },
    }),
  );
}

export async function getFacets(q: ShopQuery, locale: Locale): Promise<Facets> {
  return unwrap(
    await api.GET("/api/v1/catalog/facets", {
      params: { query: compact({ ...filterParams(q), locale }) },
      next: { revalidate: CATALOGUE_SECONDS, tags: ["catalogue"] },
    }),
  );
}

export type CmsPage = components["schemas"]["Page"];
export type Navigation = components["schemas"]["Navigation"];
export type Seo = components["schemas"]["Seo"];

export async function getNavigation(locale: Locale): Promise<Navigation> {
  const result = await api.GET("/api/v1/cms/navigation", {
    params: { query: { locale } },
    next: { revalidate: CONTENT_SECONDS, tags: ["cms"] },
  });
  // The shell must render even if the API is briefly unavailable: no menus rather than an error page.
  return result.data ?? { header: [], footer_shop: [], footer_help: [] };
}

export async function getPage(slug: string, locale: Locale): Promise<CmsPage | null> {
  const result = await api.GET("/api/v1/cms/pages/{slug}", {
    params: { path: { slug }, query: { locale } },
    next: { revalidate: CONTENT_SECONDS, tags: ["cms"] },
  });
  if (result.response.status === 404) return null;
  return unwrap(result);
}

export async function getPages(locale: Locale) {
  return unwrap(
    await api.GET("/api/v1/cms/pages", {
      params: { query: { locale } },
      next: { revalidate: CONTENT_SECONDS, tags: ["cms"] },
    }),
  );
}

/** Search title and description staff set for a page; null when none is set (page defaults apply). */
export async function getSeo(key: string, locale: Locale): Promise<Seo | null> {
  const result = await api.GET("/api/v1/cms/seo/{key}", {
    params: { path: { key }, query: { locale } },
    next: { revalidate: CONTENT_SECONDS, tags: ["cms"] },
  });
  return result.response.ok ? (result.data ?? null) : null;
}

/** Asked only for addresses that would otherwise be "not found" (M17: redirects on URL changes). */
export async function resolveRedirect(path: string) {
  const result = await api.GET("/api/v1/cms/redirects/resolve", {
    params: { query: { path } },
    next: { revalidate: CONTENT_SECONDS, tags: ["cms"] },
  });
  return result.response.ok ? (result.data ?? null) : null;
}

export async function getCollections(locale: Locale): Promise<CollectionCard[]> {
  return unwrap(
    await api.GET("/api/v1/catalog/collections", {
      params: { query: { locale } },
      next: { revalidate: CATALOGUE_SECONDS, tags: ["catalogue"] },
    }),
  );
}

export async function getCollection(slug: string, locale: Locale): Promise<CollectionCard | null> {
  const result = await api.GET("/api/v1/catalog/collections/{slug}", {
    params: { path: { slug }, query: { locale } },
    next: { revalidate: CATALOGUE_SECONDS, tags: ["catalogue"] },
  });
  if (result.response.status === 404) return null;
  return unwrap(result);
}

export type ProductDetail = components["schemas"]["ProductDetail"];
export type Availability = components["schemas"]["Availability"];

export async function getProduct(slug: string, locale: Locale): Promise<ProductDetail | null> {
  const result = await api.GET("/api/v1/catalog/products/{slug}", {
    params: { path: { slug }, query: { locale } },
    next: { revalidate: CATALOGUE_SECONDS, tags: ["catalogue"] },
  });
  if (result.response.status === 404) return null;
  return unwrap(result);
}

/** Price and stock per variant, read fresh on every view (MTS §3, A-15): never from a cache. */
export async function getAvailability(slug: string): Promise<Availability | null> {
  const result = await api.GET("/api/v1/catalog/products/{slug}/availability", {
    params: { path: { slug } },
    cache: "no-store",
  });
  if (result.response.status === 404) return null;
  return unwrap(result);
}
