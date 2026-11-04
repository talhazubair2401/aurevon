import { notFound } from "next/navigation";
import { isLocale } from "@aurevon/i18n";
import { redirectOrNotFound } from "@/lib/redirects";

const PATH = /^[a-z0-9\-_/]{1,200}$/;

// Unknown paths under a locale: follow a staff redirect if one exists (M17), otherwise the locale's not-found
// page, inside the shell.
export default async function CatchAll({ params }: PageProps<"/[locale]/[...rest]">) {
  const { locale, rest } = await params;
  const path = `/${rest.join("/")}`;
  if (!isLocale(locale) || !PATH.test(path)) notFound();
  return redirectOrNotFound(locale, path);
}
