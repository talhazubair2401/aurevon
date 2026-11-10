"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { InventoryNav } from "../../components/InventoryNav";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, useApiData } from "../../lib/api";

export default function InventoryPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Inventory</h1>
      <InventoryNav />
      <Suspense fallback={<p className={ui.muted}>Loading…</p>}>
        <Stock />
      </Suspense>
    </Shell>
  );
}

function Stock() {
  const initial = useSearchParams().get("q") ?? "";
  const [q, setQ] = useState(initial);
  const [query, setQuery] = useState(initial);
  const [low, setLow] = useState(false);
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/inventory", {
          params: { query: { ...(query ? { q: query } : {}), ...(low ? { low: true } : {}) } },
        }),
      ),
    [query, low],
  );
  const { data, error } = useApiData(load);
  return (
    <>
      <form
        className={ui.row}
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(q.trim());
        }}
      >
        <input
          className={ui.input}
          aria-label="Search by SKU or product"
          placeholder="SKU or product"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button className={ui.secondary} type="submit">
          Search
        </button>
        <label className={ui.row}>
          <input type="checkbox" checked={low} onChange={(e) => setLow(e.target.checked)} />
          Low stock only
        </label>
      </form>
      {error && <p className={ui.error}>{error}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.length === 0 ? (
        <p className={ui.muted}>
          {low ? "Nothing is at or below its reorder level." : "No variants match."}
        </p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">Product</th>
              <th scope="col">On hand</th>
              <th scope="col">Held for orders</th>
              <th scope="col">Available</th>
              <th scope="col">Quarantine</th>
              <th scope="col">Damaged</th>
              <th scope="col">Reorder at</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.sku}>
                <td>
                  <Link href={`/inventory/item?sku=${r.sku}`} className={c.mono}>
                    {r.sku}
                  </Link>
                </td>
                <td>
                  {r.product}
                  <br />
                  <span className={ui.muted}>
                    {r.colour} · {r.size}
                    {!r.is_active && " · not sold"}
                  </span>
                </td>
                <td>{r.on_hand}</td>
                <td>{r.reserved}</td>
                <td>
                  {r.available} {r.low && <span className={ui.tag}>Low</span>}
                </td>
                <td>{r.quarantine}</td>
                <td>{r.damaged}</td>
                <td>{r.reorder_level || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
