"use client";

import Link from "next/link";
import { Shell } from "../components/Shell";
import ui from "../components/ui.module.css";
import { formatTime } from "../lib/api";
import { useSession } from "../lib/session";

export default function OverviewPage() {
  return (
    <Shell>
      <Overview />
    </Shell>
  );
}

function Overview() {
  const { state, can } = useSession();
  if (state.status !== "signed-in") return null;
  const { account, session } = state.info;
  return (
    <>
      <h1 className={ui.title}>Welcome, {account.full_name || account.email}</h1>
      <p className={ui.muted}>
        Signed in as {account.role.name}. This session ends after 30 minutes without activity, and
        no later than {formatTime(session.expires_at)}.
      </p>
      <div className={ui.panel}>
        <h2 className={ui.subtitle}>Your areas</h2>
        <ul className={ui.muted}>
          {AREAS.filter((a) => can(a.permission)).map((a) => (
            <li key={a.href}>
              <Link href={a.href}>{a.label}</Link>: {a.text}
            </li>
          ))}
          <li>
            <Link href="/account">My account</Link>: your sessions, password, authenticator and
            recovery codes.
          </li>
        </ul>
      </div>
    </>
  );
}

const AREAS = [
  {
    href: "/orders",
    label: "Orders",
    permission: "orders.view",
    text: "packing, dispatch, tracking, cash-on-delivery money, refunds and alerts.",
  },
  {
    href: "/support",
    label: "Support",
    permission: "tickets.view",
    text: "customer messages, returns and exchanges.",
  },
  {
    href: "/catalog",
    label: "Catalogue",
    permission: "catalog.view",
    text: "products, prices, images, sizes and 3D models.",
  },
  {
    href: "/inventory",
    label: "Inventory",
    permission: "inventory.view",
    text: "stock, corrections, reorder alerts, suppliers and purchase orders.",
  },
  {
    href: "/content",
    label: "Content",
    permission: "cms.edit",
    text: "homepage, pages, navigation and banners.",
  },
  {
    href: "/marketing",
    label: "Marketing",
    permission: "promotions.edit",
    text: "coupon codes and scheduled promotions.",
  },
  {
    href: "/reports",
    label: "Reports",
    permission: "reports.aggregate",
    text: "sales, products, customers, returns, stock and CSV downloads.",
  },
  {
    href: "/team",
    label: "Team",
    permission: "staff.view",
    text: "staff accounts, roles, suspension, sessions and recovery.",
  },
  {
    href: "/audit",
    label: "Audit log",
    permission: "audit.view",
    text: "every sensitive action, who did it and when.",
  },
  {
    href: "/settings",
    label: "Settings",
    permission: "settings.store",
    text: "store settings, delivery zones and rates, and tax.",
  },
];
