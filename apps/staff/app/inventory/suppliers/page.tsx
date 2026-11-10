"use client";

import { useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import { InventoryNav } from "../../../components/InventoryNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Supplier = Schemas["SupplierOut"];
const loadSuppliers = () => call(() => api.GET("/api/v1/staff/suppliers"));

export default function SuppliersPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Inventory</h1>
      <InventoryNav />
      <Suppliers />
    </Shell>
  );
}

function Suppliers() {
  const { can } = useSession();
  const { data, error, reload } = useApiData(loadSuppliers);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  const canEdit = can("purchase_orders.manage");
  return (
    <>
      {data.length === 0 && <p className={ui.muted}>No suppliers yet.</p>}
      {data.map((s) => (
        <SupplierForm key={s.id} supplier={s} canEdit={canEdit} onSaved={reload} />
      ))}
      {canEdit && <SupplierForm supplier={null} canEdit onSaved={reload} />}
    </>
  );
}

const FIELDS: Array<[keyof Supplier, string]> = [
  ["name", "Name"],
  ["contact_name", "Contact person"],
  ["email", "Email"],
  ["phone", "Phone"],
  ["address", "Address"],
  ["notes", "Notes"],
];

function SupplierForm({
  supplier,
  canEdit,
  onSaved,
}: {
  supplier: Supplier | null;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [v, setV] = useState<Record<string, string>>(
    Object.fromEntries(FIELDS.map(([k]) => [k, String(supplier?.[k] ?? "")])),
  );
  const [active, setActive] = useState(supplier?.is_active ?? true);
  const [msg, setMsg] = useState<Msg>(null);
  const id = (k: string) => `${supplier?.id ?? "new"}-${k}`;
  const save = async () => {
    setMsg(null);
    const body = { ...v, is_active: active } as never;
    try {
      if (supplier)
        await call(() =>
          api.PUT("/api/v1/staff/suppliers/{supplier_id}", {
            params: { path: { supplier_id: supplier.id } },
            body,
          }),
        );
      else await call(() => api.POST("/api/v1/staff/suppliers", { body }));
      setMsg({ ok: true, text: "Saved." });
      if (!supplier) setV(Object.fromEntries(FIELDS.map(([k]) => [k, ""])));
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <section className={ui.panel} aria-label={supplier ? supplier.name : "New supplier"}>
      <div className={c.panelHead}>
        <h2 className={ui.subtitle}>{supplier ? supplier.name : "New supplier"}</h2>
        {supplier && <span className={ui.muted}>{supplier.open_orders} open purchase orders</span>}
      </div>
      <div className={c.shared}>
        {FIELDS.map(([k, label]) => (
          <div key={k} className={ui.field}>
            <label htmlFor={id(k)}>{label}</label>
            <input
              id={id(k)}
              className={ui.input}
              disabled={!canEdit}
              value={v[k]}
              onChange={(e) => setV({ ...v, [k]: e.target.value })}
            />
          </div>
        ))}
      </div>
      {canEdit && (
        <div className={c.actions}>
          <label className={ui.row}>
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            Active
          </label>
          <button className={ui.button} disabled={!v.name?.trim()} onClick={() => void save()}>
            {supplier ? "Save supplier" : "Add supplier"}
          </button>
        </div>
      )}
      <Message message={msg} />
    </section>
  );
}
