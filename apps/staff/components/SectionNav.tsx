"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "../lib/session";
import c from "./content.module.css";

type Item = { href: string; label: string; permission?: string };

/** Sub-navigation for a section; the first link is the section root and matches only exactly. */
export function SectionNav({ label, links }: { label: string; links: Item[] }) {
  const pathname = usePathname();
  const { can } = useSession();
  return (
    <nav className={c.subnav} aria-label={label}>
      {links
        .filter((l) => !l.permission || can(l.permission))
        .map((link, i) => {
          const active = i === 0 ? pathname === link.href : pathname.startsWith(link.href);
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

export const SETTINGS_LINKS: Item[] = [
  { href: "/settings", label: "General" },
  { href: "/settings/delivery", label: "Delivery zones and rates" },
  { href: "/settings/tax", label: "Tax" },
];

export const MARKETING_LINKS: Item[] = [
  { href: "/marketing", label: "Coupons" },
  { href: "/marketing/promotions", label: "Automatic promotions" },
];

export const SUPPORT_LINKS: Item[] = [
  { href: "/support", label: "Overview" },
  { href: "/support/tickets", label: "Messages", permission: "tickets.view" },
  { href: "/support/returns", label: "Returns", permission: "returns.view" },
];
