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
        <h2 className={ui.subtitle}>Available now</h2>
        <ul className={ui.muted}>
          {can("staff.view") && (
            <li>
              <Link href="/team">Team</Link>: staff accounts, roles, suspension, sessions and
              recovery.
            </li>
          )}
          {can("audit.view") && (
            <li>
              <Link href="/audit">Audit log</Link>: every sensitive action, who did it and when.
            </li>
          )}
          <li>
            <Link href="/account">My account</Link>: your sessions, password, authenticator and
            recovery codes.
          </li>
        </ul>
        <p className={ui.muted}>
          Catalogue, orders, inventory and finance screens arrive with their milestones.
        </p>
      </div>
    </>
  );
}
