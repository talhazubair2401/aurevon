"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import { InventoryNav, PO_STATUS } from "../../../components/InventoryNav";
import { money, StatusTag } from "../../../components/OrdersNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../../lib/api";
import { useSession } from "../../../lib/session";

const loadPos = () => call(() => api.GET("/api/v1/staff/purchase-orders"));
const loadSuppliers = () => call(() => api.GET("/api/v1/staff/suppliers"));

export default function PurchaseOrdersPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Inventory</h1>
      <InventoryNav />
      <PurchaseOrders />
    </Shell>
  );
}

function PurchaseOrders() {
  const { can } = useSession();
  const { data, error } = useApiData(loadPos);
  return (
    <>
      {can("purchase_orders.manage") && <NewPurchaseOrder />}
      {error && <p className={ui.error}>{error}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.length === 0 ? (
        <p className={ui.muted}>No purchase orders yet.</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Number</th>
              <th scope="col">Supplier</th>
              <th scope="col">Units</th>
              <th scope="col">Cost</th>
              <th scope="col">Expected</th>
              <th scope="col">Status</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.map((po) => (
              <tr key={po.id}>
                <td>
                  <Link href={`/inventory/purchase-orders/view?id=${po.id}`} className={c.mono}>
                    {po.number}
                  </Link>
                </td>
                <td>{po.supplier.name}</td>
                <td>
                  {po.units_received} / {po.units_ordered}
                </td>
                <td>{money(po.total_cost)}</td>
                <td>{po.expected_on ?? "—"}</td>
                <td>
                  <StatusTag value={po.status} labels={PO_STATUS} />
                </td>
                <td>{formatTime(po.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

export interface Line {
  sku: string;
  quantity: string;
  unit_cost: string;
}

export function LinesEditor({ lines, onChange }: { lines: Line[]; onChange: (l: Line[]) => void }) {
  const set = (i: number, k: keyof Line, value: string) =>
    onChange(lines.map((l, j) => (j === i ? { ...l, [k]: value } : l)));
  return (
    <>
      {lines.map((l, i) => (
        <div key={i} className={c.actions}>
          <input
            className={`${ui.input} ${c.mono}`}
            aria-label={`Line ${i + 1} SKU`}
            placeholder="SKU"
            value={l.sku}
            onChange={(e) => set(i, "sku", e.target.value.toUpperCase())}
          />
          <input
            className={ui.input}
            aria-label={`Line ${i + 1} quantity`}
            placeholder="Quantity"
            inputMode="numeric"
            value={l.quantity}
            onChange={(e) => set(i, "quantity", e.target.value)}
          />
          <input
            className={ui.input}
            aria-label={`Line ${i + 1} unit cost (PKR)`}
            placeholder="Unit cost (PKR)"
            inputMode="decimal"
            value={l.unit_cost}
            onChange={(e) => set(i, "unit_cost", e.target.value)}
          />
          <button
            type="button"
            className={c.small}
            onClick={() => onChange(lines.filter((_, j) => j !== i))}
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        className={ui.secondary}
        onClick={() => onChange([...lines, { sku: "", quantity: "", unit_cost: "" }])}
      >
        Add line
      </button>
    </>
  );
}

function NewPurchaseOrder() {
  const router = useRouter();
  const { data: suppliers } = useApiData(loadSuppliers);
  const [supplier, setSupplier] = useState("");
  const [expected, setExpected] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ sku: "", quantity: "", unit_cost: "" }]);
  const [msg, setMsg] = useState<Msg>(null);
  const active = (suppliers ?? []).filter((s) => s.is_active);
  const create = async () => {
    setMsg(null);
    try {
      const po = await call(() =>
        api.POST("/api/v1/staff/purchase-orders", {
          body: {
            supplier: supplier || active[0]?.id,
            expected_on: expected || null,
            note,
            lines,
          } as never,
        }),
      );
      router.push(`/inventory/purchase-orders/view?id=${po.id}`);
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <section className={ui.panel} aria-labelledby="new-po">
      <h2 id="new-po" className={ui.subtitle}>
        New purchase order
      </h2>
      {active.length === 0 ? (
        <p className={ui.muted}>
          Add a supplier first on the <Link href="/inventory/suppliers">Suppliers</Link> page.
        </p>
      ) : (
        <>
          <div className={c.shared}>
            <div className={ui.field}>
              <label htmlFor="po-supplier">Supplier</label>
              <select
                id="po-supplier"
                className={ui.select}
                value={supplier}
                onChange={(e) => setSupplier(e.target.value)}
              >
                {active.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div className={ui.field}>
              <label htmlFor="po-expected">Expected on</label>
              <input
                id="po-expected"
                type="date"
                className={ui.input}
                value={expected}
                onChange={(e) => setExpected(e.target.value)}
              />
            </div>
            <div className={ui.field}>
              <label htmlFor="po-note">Note</label>
              <input
                id="po-note"
                className={ui.input}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          </div>
          <LinesEditor lines={lines} onChange={setLines} />
          <div className={c.actions}>
            <button className={ui.button} onClick={() => void create()}>
              Create draft
            </button>
          </div>
        </>
      )}
      <Message message={msg} />
    </section>
  );
}
