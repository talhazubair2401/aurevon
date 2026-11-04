/**
 * Shop All state lives in the URL (MTS §3: filters and sorting in the URL), so every view is linkable and
 * works without JavaScript. Repeated params (size=M&size=L) for multi-select filters.
 */
export const SORTS = ["featured", "newest", "price_asc", "price_desc"] as const;
export type Sort = (typeof SORTS)[number];

export interface ShopState {
  department?: "women" | "men";
  category?: string;
  collection?: string;
  size: string[];
  colour: string[];
  price_min?: string;
  price_max?: string;
  sort: Sort;
  cursor?: string;
}

type Params = Record<string, string | string[] | undefined>;

const SLUG = /^[a-z0-9-]{1,80}$/;
const SIZE = /^[A-Z0-9]{1,6}$/;
const PRICE = /^\d{1,9}(\.\d{1,2})?$/;

function all(value: string | string[] | undefined): string[] {
  const list = Array.isArray(value) ? value : value ? [value] : [];
  return list.flatMap((v) => v.split(",")).filter(Boolean);
}

function one(value: string | string[] | undefined): string | undefined {
  return all(value)[0];
}

export function parseShopState(params: Params): ShopState {
  const department = one(params.department);
  const sort = one(params.sort);
  const category = one(params.category);
  const collection = one(params.collection);
  const priceMin = one(params.price_min);
  const priceMax = one(params.price_max);
  const cursor = one(params.cursor);
  return {
    ...(department === "women" || department === "men" ? { department } : {}),
    ...(category && SLUG.test(category) ? { category } : {}),
    ...(collection && SLUG.test(collection) ? { collection } : {}),
    size: [...new Set(all(params.size).filter((s) => SIZE.test(s)))].slice(0, 10),
    colour: [...new Set(all(params.colour).filter((c) => SLUG.test(c)))].slice(0, 20),
    ...(priceMin && PRICE.test(priceMin) ? { price_min: priceMin } : {}),
    ...(priceMax && PRICE.test(priceMax) ? { price_max: priceMax } : {}),
    sort: (SORTS as readonly string[]).includes(sort ?? "") ? (sort as Sort) : "featured",
    ...(cursor && cursor.length < 400 ? { cursor } : {}),
  };
}

/** Builds the query string for a state, omitting defaults. Changing a filter always drops the cursor. */
export function toSearch(state: Partial<ShopState>): string {
  const q = new URLSearchParams();
  if (state.department) q.set("department", state.department);
  if (state.category) q.set("category", state.category);
  if (state.collection) q.set("collection", state.collection);
  for (const s of state.size ?? []) q.append("size", s);
  for (const c of state.colour ?? []) q.append("colour", c);
  if (state.price_min) q.set("price_min", state.price_min);
  if (state.price_max) q.set("price_max", state.price_max);
  if (state.sort && state.sort !== "featured") q.set("sort", state.sort);
  if (state.cursor) q.set("cursor", state.cursor);
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** The cursor value from the API's absolute `next`/`previous` link. */
export function cursorFrom(link: string | null | undefined): string | undefined {
  if (!link) return undefined;
  try {
    return new URL(link).searchParams.get("cursor") ?? undefined;
  } catch {
    return undefined;
  }
}

/** The same view with a different page: drop the cursor (and optionally the category, which belongs to one department). */
export function withoutCursor(state: ShopState, { dropCategory = false } = {}): Partial<ShopState> {
  const next: Partial<ShopState> = { ...state };
  delete next.cursor;
  if (dropCategory) delete next.category;
  return next;
}
