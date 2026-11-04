import "server-only";
import { notFound, permanentRedirect, redirect } from "next/navigation";
import type { Locale } from "@aurevon/i18n";
import { resolveRedirect } from "./api";

/**
 * For an address that has no page: follow a staff redirect if one exists (same language), otherwise show the
 * locale's not-found page. Redirect targets are storefront paths, checked when staff save them.
 */
export async function redirectOrNotFound(locale: Locale, path: string): Promise<never> {
  const found = await resolveRedirect(path);
  if (found && found.to.startsWith("/") && !found.to.startsWith("//")) {
    const target = `/${locale}${found.to}`;
    if (found.permanent) permanentRedirect(target);
    redirect(target);
  }
  notFound();
}
