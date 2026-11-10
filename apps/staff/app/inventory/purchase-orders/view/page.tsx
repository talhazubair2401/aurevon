"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { Message, type Msg } from "../../../../components/CatalogNav";
import { InventoryNav, PO_STATUS } from "../../../../components/InventoryNav";
import { money, StatusTag } from "../../../../components/OrdersNav";
import { Shell } from "../../../../components/Shell";
import c from "../../../../components/content.module.css";
import ui from "../../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../../../lib/api";
import { useSession } from "../../../../lib/session";

export default function PurchaseOrderPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Inventory</h1>
      <InventoryNav />
      <Suspense fallback={<p className={ui.muted}>Loading…</p>}>
        <PurchaseOrder />
      </Suspense>
    </Shell>
  );
}

function PurchaseOrder() {
  const id = useSearchParams().get("id") ?? "";
  const { can } = useSession();
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/purchase-orders/{po_id}", { params: { path: { po_id: id } } }),
      ),
    [id],
  );
  const { data: po, error, reload } = useApiData(load);
  const [qty, setQty] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<Msg>(null);
  const act = async (action: string, body: unknown, done: string) => {
    setMsg(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/purchase-orders/{po_id}/{action}", {
          params: { path: { po_id: id, action } },
          body: body as never,
        }),
      );
      setMsg({ ok: true, text: done });
      setQty({});
      reload();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  if (error) return <p className={ui.error}>{error}</p>;
  if (!po) return <p className={ui.muted}>Loading…</p>;
  const manage = can("purchase_orders.manage");
  const receiving = po.status === "sent" || po.status === "partly_received";
  return (
    <>
      <p>
        <Link href="/inventory/purchase-orders" className={ui.link}>
          ← All purchase orders
        </Link>
      </p>
      <section className={ui.panel} aria-labelledby="po-title">
        <div className={c.panelHead}>
          <h2 id="po-title" className={ui.subtitle}>
            <span className={c.mono}>{po.number}</span> · {po.supplier.name}
          </h2>
          <StatusTag value={po.status} labels={PO_STATUS} />
        </div>
        <dl className={c.facts}>
          <dt>Created</dt>
          <dd>
            {formatTime(po.created_at)} by {po.created_by}
          </dd>
          {po.sent_at && (
            <>
              <dt>Sent</dt>
              <dd>{formatTime(po.sent_at)}</dd>
            </>
          )}
          <dt>Expected</dt>
          <dd>{po.expected_on ?? "—"}</dd>
          <dt>Supplier contact</dt>
          <dd>
            {[po.supplier.contact_name, po.supplier.email, po.supplier.phone]
              .filter(Boolean)
              .join(" · ") || "—"}
          </dd>
          {po.note && (
            <>
              <dt>Note</dt>
              <dd>{po.note}</dd>
            </>
          )}
          <dt>Total cost</dt>
          <dd>{money(po.total_cost)}</dd>
        </dl>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">Product</th>
              <th scope="col">Ordered</th>
              <th scope="col">Received</th>
              <th scope="col">Unit cost</th>
              {receiving && manage && <th scope="col">Arrived now</th>}
            </tr>
          </thead>
          <tbody>
            {po.lines.map((l) => (
              <tr key={l.id}>
                <td className={c.mono}>
                  <Link href={`/inventory/item?sku=${l.sku}`}>{l.sku}</Link>
                </td>
                <td>{l.product}</td>
                <td>{l.quantity_ordered}</td>
                <td>{l.quantity_received}</td>
                <td>{money(l.unit_cost)}</td>
                {receiving && manage && (
                  <td>
                    <input
                      className={ui.input}
                      aria-label={`Units of ${l.sku} that arrived`}
                      inputMode="numeric"
                      disabled={l.quantity_received >= l.quantity_ordered}
                      value={qty[l.id] ?? ""}
                      onChange={(e) => setQty({ ...qty, [l.id]: e.target.value })}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {manage && (
          <div className={c.actions}>
            {po.status === "draft" && (
              <button
                className={ui.button}
                onClick={() => void act("send", {}, "Marked as sent to the supplier.")}
              >
                Mark as sent
              </button>
            )}
            {receiving && (
              <button
                className={ui.button}
                onClick={() =>
                  void act(
                    "receive",
                    {
                      lines: Object.entries(qty)
                        .filter(([, v]) => v.trim())
                        .map(([line_id, v]) => ({ line_id, quantity: Number(v) })),
                    },
                    "Received. Sellable stock has gone up.",
                  )
                }
              >
                Receive stock
              </button>
            )}
            {(po.status === "draft" || po.status === "sent") && (
              <button className={ui.secondary} onClick={() => void act("cancel", {}, "Cancelled.")}>
                Cancel purchase order
              </button>
            )}
          </div>
        )}
        <Message message={msg} />
      </section>
    </>
  );
}
