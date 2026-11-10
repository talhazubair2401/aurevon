"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { SectionNav, SUPPORT_LINKS } from "../../../components/SectionNav";
import { Shell } from "../../../components/Shell";
import { RETURN_STATUS } from "../../../components/SupportNav";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, formatTime, useApiData } from "../../../lib/api";

export default function ReturnsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Support</h1>
      <SectionNav label="Support" links={SUPPORT_LINKS} />
      <Suspense>
        <Returns />
      </Suspense>
    </Shell>
  );
}

const TABS = ["requested", "approved", "received", "inspected", "completed", "rejected", ""];

function Returns() {
  const [status, setStatus] = useState(useSearchParams().get("status") ?? "requested");
  const load = useCallback(
    () =>
      call(() => api.GET("/api/v1/staff/returns", { params: { query: status ? { status } : {} } })),
    [status],
  );
  const { data, error } = useApiData(load);
  return (
    <>
      <div className={c.subnav} aria-label="Returns by status">
        {TABS.map((s) => (
          <button
            type="button"
            key={s || "all"}
            className={status === s ? c.subnavActive : c.subnavLink}
            onClick={() => setStatus(s)}
          >
            {s ? (RETURN_STATUS[s] ?? s).split(":")[0] : "All"}
            {s && data ? ` (${data.counts[s] ?? 0})` : ""}
          </button>
        ))}
      </div>
      {error && <p className={ui.error}>{error}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.results.length === 0 ? (
        <p className={ui.muted}>No returns here.</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Return</th>
              <th scope="col">Order</th>
              <th scope="col">Customer</th>
              <th scope="col">Type</th>
              <th scope="col">Reason</th>
              <th scope="col">Units</th>
              <th scope="col">Requested</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link href={`/support/returns/view?id=${r.id}`} className={c.mono}>
                    {r.number}
                  </Link>
                </td>
                <td className={c.mono}>{r.order}</td>
                <td>{r.customer}</td>
                <td>{r.kind === "exchange" ? "Exchange" : "Refund"}</td>
                <td>{r.reason_label}</td>
                <td>{r.units}</td>
                <td>{formatTime(r.created_at)}</td>
                <td>
                  <span className={ui.tag}>{RETURN_STATUS[r.status] ?? r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
