"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, call, errorMessage, formatTime } from "../lib/api";
import { useSession } from "../lib/session";
import ui from "./ui.module.css";

const NAV = [
  { href: "/", label: "Overview", permission: null },
  { href: "/orders", label: "Orders", permission: "orders.view" },
  { href: "/catalog", label: "Catalogue", permission: "catalog.view" },
  { href: "/inventory", label: "Inventory", permission: "inventory.view" },
  { href: "/content", label: "Content", permission: "cms.edit" },
  { href: "/seo", label: "SEO", permission: "seo.edit" },
  { href: "/team", label: "Team", permission: "staff.view" },
  { href: "/audit", label: "Audit log", permission: "audit.view" },
  { href: "/settings", label: "Settings", permission: "settings.store" },
  { href: "/account", label: "My account", permission: null },
] as const;

/** Signed-in frame: shows nothing but sign-in without a valid staff session (MTS §2 staff restrictions). */
export function Shell({ children }: { children: ReactNode }) {
  const { state, can, signOut, refresh } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [cancelError, setCancelError] = useState<string | null>(null);

  const mustReenroll = state.status === "signed-in" && state.info.session.mfa_reenrollment_required;

  useEffect(() => {
    if (state.status === "signed-out") router.replace("/sign-in");
    if (mustReenroll && pathname !== "/account") router.replace("/account");
  }, [state.status, mustReenroll, pathname, router]);

  if (state.status !== "signed-in") {
    return (
      <main className={ui.narrow}>
        <p className={ui.muted}>Loading…</p>
      </main>
    );
  }
  const { info } = state;

  const cancelOwnRecovery = async () => {
    setCancelError(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/accounts/{account_id}/recovery/cancel", {
          params: { path: { account_id: info.account.id } },
        }),
      );
      await refresh();
    } catch (e) {
      setCancelError(errorMessage(e));
    }
  };

  return (
    <>
      <header className={ui.header}>
        <div className={ui.headerInner}>
          <span className={ui.brand}>AUREVON · STAFF</span>
          <nav className={ui.nav} aria-label="Staff">
            {!mustReenroll &&
              NAV.filter((item) => item.permission === null || can(item.permission)).map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    pathname === item.href ||
                    (item.href !== "/" && pathname.startsWith(`${item.href}/`))
                      ? ui.navLinkActive
                      : ui.navLink
                  }
                >
                  {item.label}
                </Link>
              ))}
          </nav>
          <span className={`${ui.headerMeta} ${ui.hideSmall}`}>
            {info.account.email} · {info.account.role.name}
          </span>
          <button className={ui.link} onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </header>
      <main className={ui.page}>
        {info.recovery_in_progress && (
          <div className={ui.bannerUrgent} role="alert" data-testid="own-recovery-banner">
            <strong>Recovery of your account is in progress</strong> (approved by{" "}
            {info.recovery_in_progress.approved_by}). It takes effect{" "}
            {formatTime(info.recovery_in_progress.effective_at)}. If you didn&apos;t ask for this,{" "}
            <button className={ui.link} onClick={() => void cancelOwnRecovery()}>
              cancel it now
            </button>
            .{cancelError && <span className={ui.error}> {cancelError}</span>}
          </div>
        )}
        {info.security_warnings.includes("single_owner") && (
          <div className={ui.banner} role="status" data-testid="single-owner-warning">
            <strong>Security warning: only one Owner account.</strong> If it is lost, the store can
            only be recovered with the break-glass procedure. Add a second, independent Owner before
            launch.
          </div>
        )}
        {info.security_warnings.includes("few_recovery_codes") && (
          <div className={ui.banner} role="status">
            You have few recovery codes left. Generate a new set in{" "}
            <Link href="/account">My account</Link>.
          </div>
        )}
        {children}
      </main>
    </>
  );
}
