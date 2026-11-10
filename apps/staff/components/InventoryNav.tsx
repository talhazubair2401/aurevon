"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import c from "./content.module.css";

export function InventoryNav() {
  const pathname = usePathname();
  const links = [
    { href: "/inventory", label: "Stock" },
    { href: "/inventory/purchase-orders", label: "Purchase orders" },
    { href: "/inventory/suppliers", label: "Suppliers" },
  ];
  return (
    <nav className={c.subnav} aria-label="Inventory">
      {links.map((link) => {
        const active =
          link.href === "/inventory"
            ? pathname === "/inventory" || pathname.startsWith("/inventory/item")
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

export const MOVEMENT: Record<string, string> = {
  receipt: "Received",
  adjustment: "Count correction",
  demo: "Demo stock",
  sale: "Sold",
  cancellation: "Cancelled order",
  return: "Returned",
  quarantine: "Into quarantine",
  release: "Released from quarantine",
  damaged: "Damaged",
  write_off: "Written off",
  transfer: "Transfer",
};

export const PO_STATUS: Record<string, string> = {
  draft: "Draft",
  sent: "Sent to supplier",
  partly_received: "Partly received",
  received: "Received",
  cancelled: "Cancelled",
};
