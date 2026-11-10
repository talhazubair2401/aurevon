"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import c from "./content.module.css";
import ui from "./ui.module.css";

export function OrdersNav() {
  const pathname = usePathname();
  const links = [
    { href: "/orders", label: "Orders" },
    { href: "/orders/refunds", label: "Refunds" },
    { href: "/orders/alerts", label: "Alerts" },
  ];
  return (
    <nav className={c.subnav} aria-label="Orders">
      {links.map((link) => {
        const active =
          link.href === "/orders"
            ? pathname === "/orders" || pathname.startsWith("/orders/view")
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

export const ORDER_STATUS: Record<string, string> = {
  awaiting_payment: "Awaiting payment",
  confirmed: "Confirmed",
  packing: "Packing",
  dispatched: "Dispatched",
  delivered: "Delivered",
  cancelled: "Cancelled",
  undelivered: "Returned undelivered",
  returned: "Returned",
};

export const PAYMENT_STATUS: Record<string, string> = {
  unpaid: "Unpaid",
  paid: "Paid",
  partly_refunded: "Partly refunded",
  refunded: "Refunded",
  cod_collect: "COD: collect on delivery",
  cod_remittance_pending: "COD: remittance pending",
  cod_remittance_received: "COD: remittance received",
  cod_reconciled: "COD: reconciled",
  cod_discrepancy: "COD: discrepancy",
  cod_cancelled: "COD: nothing to collect",
};

export const PAYMENT_METHOD: Record<string, string> = {
  cod: "Cash on delivery",
  card: "Card",
  exchange: "Exchange (no charge)",
};

export const SHIPMENT_STATUS: Record<string, string> = {
  booked: "Booked with courier",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  failed: "Delivery failed",
  returning: "Returning to AureVon",
  returned: "Returned to AureVon",
};

export const REFUND_STATE: Record<string, string> = {
  requested: "Waiting for approval",
  approved: "Approved",
  processing: "Processing",
  succeeded: "Refunded",
  failed: "Failed",
  manual_required: "Needs manual payment",
  manual_completed: "Paid manually",
  rejected: "Rejected",
};

export function money(amount: string | number): string {
  return `Rs ${Number(amount).toLocaleString("en-PK", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function StatusTag({ value, labels }: { value: string; labels: Record<string, string> }) {
  return <span className={ui.tag}>{labels[value] ?? value}</span>;
}
