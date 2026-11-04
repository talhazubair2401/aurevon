import { timingSafeEqual } from "node:crypto";
import { revalidateTag } from "next/cache";

/**
 * Called by the API's worker after staff publish (decision 0005: CMS data cached, refreshed on publish).
 * Internal only: the proxy never routes /internal/ publicly, and every call needs the shared secret.
 * `expire: 0` means the next visitor gets the published content, never the stale copy.
 */
const ALLOWED_TAGS = new Set(["cms", "catalogue"]);

function authorised(header: string | null): boolean {
  const secret = process.env.STOREFRONT_REVALIDATE_SECRET ?? "";
  if (secret.length < 16 || !header?.startsWith("Bearer ")) return false;
  const given = Buffer.from(header.slice("Bearer ".length));
  const expected = Buffer.from(secret);
  return given.length === expected.length && timingSafeEqual(given, expected);
}

export async function POST(request: Request): Promise<Response> {
  if (!authorised(request.headers.get("authorization"))) {
    return new Response(null, { status: 401 });
  }
  let tags: unknown;
  try {
    tags = ((await request.json()) as { tags?: unknown }).tags;
  } catch {
    return new Response(null, { status: 400 });
  }
  if (!Array.isArray(tags) || !tags.every((t) => typeof t === "string" && ALLOWED_TAGS.has(t))) {
    return new Response(null, { status: 400 });
  }
  for (const tag of tags as string[]) revalidateTag(tag, { expire: 0 });
  return Response.json({ revalidated: tags });
}
