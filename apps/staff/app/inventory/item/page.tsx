"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import { InventoryNav, MOVEMENT } from "../../../components/InventoryNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../../lib/api";
import { useSession } from "../../../lib/session";

export default function StockItemPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Inventory</h1>
      <InventoryNav />
      <Suspense fallback={<p className={ui.muted}>Loading…</p>}>
        <Item />
      </Suspense>
    </Shell>
  );
}

const LOCATIONS: Record<string, string> = {
  main: "Sellable",
  quarantine: "Quarantine",
  damaged: "Damaged",
};

function Item() {
  const sku = useSearchParams().get("sku") ?? "";
  const { can } = useSession();
  const load = useCallback(
    () => call(() => api.GET("/api/v1/staff/inventory/{sku}", { params: { path: { sku } } })),
    [sku],
  );
  const { data, error, reload } = useApiData(load);
  const [msg, setMsg] = useState<Msg>(null);
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("adjustment");
  const [note, setNote] = useState("");
  const [level, setLevel] = useState<string | null>(null);
  const [move, setMove] = useState("main>quarantine");
  const [moveQty, setMoveQty] = useState("1");
  const [moveNote, setMoveNote] = useState("");
  const path = { params: { path: { sku } } };
  const act = async (fn: () => Promise<unknown>, done: string) => {
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: done });
      reload();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p>
        <Link href="/inventory" className={ui.link}>
          ← All stock
        </Link>
      </p>
      <section className={ui.panel} aria-labelledby="item-title">
        <div className={c.panelHead}>
          <h2 id="item-title" className={ui.subtitle}>
            {data.product} · <span className={c.mono}>{data.sku}</span>
          </h2>
          {data.low && <span className={ui.tag}>Low stock</span>}
        </div>
        <dl className={c.facts}>
          <dt>Colour and size</dt>
          <dd>
            {data.colour} · {data.size}
          </dd>
          <dt>Sellable on hand</dt>
          <dd>{data.on_hand}</dd>
          <dt>Held for orders</dt>
          <dd>{data.reserved}</dd>
          <dt>Available to sell</dt>
          <dd>{data.available}</dd>
          <dt>Quarantine</dt>
          <dd>{data.quarantine}</dd>
          <dt>Damaged</dt>
          <dd>{data.damaged}</dd>
        </dl>
      </section>

      {can("inventory.adjust") && (
        <section className={ui.panel} aria-labelledby="adj-title">
          <h2 id="adj-title" className={ui.subtitle}>
            Correct stock
          </h2>
          <div className={c.actions}>
            <input
              className={ui.input}
              aria-label="Units to add (use a minus sign to remove)"
              placeholder="+5 or -2"
              inputMode="numeric"
              value={delta}
              onChange={(e) => setDelta(e.target.value)}
            />
            <select
              className={ui.select}
              aria-label="Reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            >
              <option value="adjustment">Count correction</option>
              <option value="receipt">Received (no purchase order)</option>
              <option value="damaged">Damaged</option>
              <option value="write_off">Written off</option>
            </select>
            <input
              className={ui.input}
              aria-label="Note"
              placeholder="Note (required)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <button
              className={ui.button}
              disabled={!delta.trim() || !note.trim()}
              onClick={() =>
                void act(
                  () =>
                    call(() =>
                      api.POST("/api/v1/staff/inventory/{sku}/adjust", {
                        ...path,
                        body: { location: "main", delta: Number(delta), reason, note } as never,
                      }),
                    ),
                  "Stock corrected.",
                )
              }
            >
              Save correction
            </button>
          </div>
          <div className={c.actions}>
            <label htmlFor="reorder">Alert when available stock falls to</label>
            <input
              id="reorder"
              className={ui.input}
              inputMode="numeric"
              value={level ?? String(data.reorder_level)}
              onChange={(e) => setLevel(e.target.value)}
            />
            <button
              className={ui.secondary}
              onClick={() =>
                void act(
                  () =>
                    call(() =>
                      api.PUT("/api/v1/staff/inventory/{sku}/reorder-level", {
                        ...path,
                        body: { level: Number(level ?? data.reorder_level) } as never,
                      }),
                    ),
                  "Reorder level saved.",
                )
              }
            >
              Save reorder level
            </button>
            <span className={ui.muted}>0 turns the alert off.</span>
          </div>
        </section>
      )}

      {can("inventory.inspect") && (
        <section className={ui.panel} aria-labelledby="mv-title">
          <h2 id="mv-title" className={ui.subtitle}>
            Move between sellable, quarantine and damaged
          </h2>
          <div className={c.actions}>
            <select
              className={ui.select}
              aria-label="Move"
              value={move}
              onChange={(e) => setMove(e.target.value)}
            >
              <option value="main>quarantine">Sellable → quarantine</option>
              <option value="quarantine>main">Quarantine → sellable (passed a second check)</option>
              <option value="quarantine>damaged">Quarantine → damaged</option>
              <option value="main>damaged">Sellable → damaged</option>
            </select>
            <input
              className={ui.input}
              aria-label="Units to move"
              inputMode="numeric"
              value={moveQty}
              onChange={(e) => setMoveQty(e.target.value)}
            />
            <input
              className={ui.input}
              aria-label="Note for the move"
              placeholder="Note"
              value={moveNote}
              onChange={(e) => setMoveNote(e.target.value)}
            />
            <button
              className={ui.secondary}
              onClick={() => {
                const [from, to] = move.split(">");
                void act(
                  () =>
                    call(() =>
                      api.POST("/api/v1/staff/inventory/{sku}/transfer", {
                        ...path,
                        body: { from, to, quantity: Number(moveQty), note: moveNote } as never,
                      }),
                    ),
                  "Stock moved.",
                );
              }}
            >
              Move stock
            </button>
          </div>
        </section>
      )}
      <Message message={msg} />

      <section className={ui.panel} aria-labelledby="hist-title">
        <h2 id="hist-title" className={ui.subtitle}>
          Movements
        </h2>
        {data.movements.length === 0 ? (
          <p className={ui.muted}>No movements yet.</p>
        ) : (
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Where</th>
                <th scope="col">Change</th>
                <th scope="col">Why</th>
                <th scope="col">Reference</th>
                <th scope="col">By</th>
              </tr>
            </thead>
            <tbody>
              {data.movements.map((m, i) => (
                <tr key={i}>
                  <td>{formatTime(m.at)}</td>
                  <td>{LOCATIONS[m.location] ?? m.location}</td>
                  <td>{m.quantity > 0 ? `+${m.quantity}` : m.quantity}</td>
                  <td>
                    {MOVEMENT[m.reason] ?? m.reason}
                    {m.note && <span className={ui.muted}> · {m.note}</span>}
                  </td>
                  <td className={c.mono}>
                    {m.reference.startsWith("AV") ? (
                      <Link href={`/orders/view?number=${m.reference}`}>{m.reference}</Link>
                    ) : (
                      m.reference
                    )}
                  </td>
                  <td>{m.actor || "system"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
