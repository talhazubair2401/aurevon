"use client";

/**
 * Browser-side calls to the same-origin API (/api/v1). The customer session cookie and the guest cart and order
 * cookies are HttpOnly; this module only keeps the CSRF tokens the API hands out:
 * - signed in: the session's token (GET /auth/session), sent on every write;
 * - guest: the cart's own token (GET /cart), sent on cart and checkout writes.
 * Cart changes are broadcast so the header bag count stays current without a page reload.
 */
import type { components } from "@aurevon/api-client";

export type Cart = components["schemas"]["CartOut"];
export type CartLine = components["schemas"]["CartLineOut"];
export type Quote = components["schemas"]["QuoteOut"];
export type Order = components["schemas"]["OrderOut"];
export type OrderSummary = components["schemas"]["OrderSummaryOut"];
export type Address = components["schemas"]["AddressOut"];
export type AddressInput = components["schemas"]["AddressRequest"];
export type Profile = components["schemas"]["ProfileOut"];
export type ShippingOption = components["schemas"]["ShippingOptionOut"];
export type Money = { amount: string; currency: string };
export type Session = {
  account: { email: string; full_name: string; email_verified: boolean };
  csrf_token: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public body: Record<string, unknown>,
  ) {
    super(message);
  }
}

let session: Session | null | undefined;
let cartToken: string | null = null;
const CART_EVENT = "av:cart";

async function parse(response: Response) {
  if (response.status === 204) return null;
  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const type = String(body.type ?? "");
    const code = type.includes("/problems/")
      ? type.split("/problems/")[1]!
      : String(response.status);
    const fieldErrors = body.errors as Record<string, string[]> | undefined;
    const first = fieldErrors ? Object.values(fieldErrors).flat()[0] : undefined;
    throw new ApiError(
      response.status,
      code,
      String(body.detail ?? first ?? "Something went wrong."),
      body,
    );
  }
  return body;
}

export async function getSession(force = false): Promise<Session | null> {
  if (session !== undefined && !force) return session;
  const response = await fetch("/api/v1/auth/session", {
    credentials: "same-origin",
    cache: "no-store",
  });
  session = response.ok ? ((await response.json()) as Session) : null;
  return session;
}

export function forgetSession() {
  session = null;
}

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; idempotencyKey?: string; locale?: string } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const s = await getSession();
    const token = s?.csrf_token ?? cartToken;
    if (token) headers["X-CSRF-Token"] = token;
  }
  if (init.idempotencyKey) headers["Idempotency-Key"] = init.idempotencyKey;
  const url = init.locale ? `${path}${path.includes("?") ? "&" : "?"}locale=${init.locale}` : path;
  const response = await fetch(`/api/v1${url}`, {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
    body: init.body === undefined ? null : JSON.stringify(init.body),
  });
  return (await parse(response)) as T;
}

function remember(cart: Cart) {
  cartToken = cart.csrf_token ?? null;
  window.dispatchEvent(new CustomEvent(CART_EVENT, { detail: cart.count }));
  return cart;
}

export async function getCart(locale: string): Promise<Cart> {
  return remember(await api<Cart>("/cart", { locale }));
}

export async function cartWrite(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  locale: string,
  body?: unknown,
): Promise<Cart> {
  if (!cartToken && !(await getSession())) await getCart(locale);
  return remember(await api<Cart>(path, { method, body, locale }));
}

export function onCartChange(listener: (count: number) => void) {
  const handler = (event: Event) => listener((event as CustomEvent<number>).detail);
  window.addEventListener(CART_EVENT, handler);
  return () => window.removeEventListener(CART_EVENT, handler);
}

export function newIdempotencyKey() {
  return crypto.randomUUID().replace(/-/g, "") + Date.now().toString(36);
}
