"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { OrdersNav } from "../../../components/OrdersNav";
import { Shell } from "../../../components/Shell";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../../lib/api";
import { useSession } from "../../../lib/session";

export default function AlertsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Orders</h1>
      <OrdersNav />
      <Alerts />
    </Shell>
  );
}

/** Operational alerts (MTS §14): payment conflicts, manual refunds, failed deliveries, COD discrepancies, low stock. */
function Alerts() {
  const { can } = useSession();
  const [resolved, setResolved] = useState(false);
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/alerts", { params: { query: resolved ? { resolved: true } : {} } }),
      ),
    [resolved],
  );
  const { data, error, reload } = useApiData(load);
  const [err, setErr] = useState<string | null>(null);
  const link = (type: string, id: string) =>
    type === "order"
      ? `/orders/view?number=${id}`
      : type === "variant"
        ? `/inventory?q=${id}`
        : null;
  return (
    <>
      <label className={ui.row}>
        <input type="checkbox" checked={resolved} onChange={(e) => setResolved(e.target.checked)} />
        Show resolved alerts
      </label>
      {(error || err) && <p className={ui.error}>{error ?? err}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.length === 0 ? (
        <p className={ui.muted}>{resolved ? "No resolved alerts." : "Nothing needs attention."}</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Alert</th>
              <th scope="col">Severity</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.map((a) => {
              const href = link(a.target_type, a.target_id);
              return (
                <tr key={a.id}>
                  <td>{formatTime(a.created_at)}</td>
                  <td>
                    {a.message}
                    {href && (
                      <>
                        {" "}
                        <Link href={href} className={ui.link}>
                          Open
                        </Link>
                      </>
                    )}
                  </td>
                  <td>
                    <span className={ui.tag}>{a.severity}</span>
                  </td>
                  <td>
                    {a.resolved_at ? (
                      <span className={ui.muted}>Resolved by {a.resolved_by}</span>
                    ) : can("orders.update") ? (
                      <button
                        className={ui.link}
                        onClick={async () => {
                          setErr(null);
                          try {
                            await call(() =>
                              api.POST("/api/v1/staff/alerts/{alert_id}/resolve", {
                                params: { path: { alert_id: a.id } },
                              }),
                            );
                            reload();
                          } catch (e) {
                            setErr(errorMessage(e));
                          }
                        }}
                      >
                        Mark resolved
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
