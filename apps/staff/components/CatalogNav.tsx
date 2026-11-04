"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "../lib/session";
import c from "./content.module.css";
import ui from "./ui.module.css";

export function CatalogNav() {
  const pathname = usePathname();
  const { can } = useSession();
  const links = [
    { href: "/catalog", label: "Products", show: true },
    { href: "/catalog/categories", label: "Categories and sizes", show: true },
    { href: "/catalog/colours", label: "Colours", show: true },
    { href: "/catalog/import", label: "Import", show: can("prices.edit") },
  ];
  return (
    <nav className={c.subnav} aria-label="Catalogue">
      {links
        .filter((l) => l.show)
        .map((link) => {
          const active =
            link.href === "/catalog"
              ? pathname === "/catalog" || pathname.startsWith("/catalog/products")
              : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={active ? c.subnavActive : c.subnavLink}
              aria-current={active ? "page" : undefined}
            >
              {link.label}
            </Link>
          );
        })}
    </nav>
  );
}

export type Msg = { ok: boolean; text: string } | null;
export function Message({ message }: { message: Msg }) {
  if (!message) return null;
  return (
    <p className={message.ok ? ui.success : ui.error} role="status">
      {message.text}
    </p>
  );
}
