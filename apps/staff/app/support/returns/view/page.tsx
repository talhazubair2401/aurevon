"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { Message, type Msg } from "../../../../components/CatalogNav";
import { money } from "../../../../components/OrdersNav";
import { SectionNav, SUPPORT_LINKS } from "../../../../components/SectionNav";
import { Shell } from "../../../../components/Shell";
import { OUTCOME, RETURN_STATUS } from "../../../../components/SupportNav";
import c from "../../../../components/content.module.css";
import ui from "../../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData, type Schemas } from "../../../../lib/api";
import { useSession } from "../../../../lib/session";

type Return = Schemas["StaffReturnOut"];

export default function ReturnPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Support</h1>
      <SectionNav label="Support" links={SUPPORT_LINKS} />
      <Suspense>
        <ReturnDetail />
      </Suspense>
    </Shell>
  );
}

function ReturnDetail() {
  const id = useSearchParams().get("id") ?? "";
  const { can } = useSession();
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/returns/{return_id}", { params: { path: { return_id: id } } }),
      ),
    [id],
  );
  const { data: r, error, reload } = useApiData(load);
  const [msg, setMsg] = useState<Msg>(null);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!r) return <p className={ui.muted}>Loading…</p>;
  const decide = can("returns.decide");

  const act = async (
    action: string,
    body: Record<string, unknown> = {},
    done = "Saved.",
  ): Promise<boolean> => {
    setMsg(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/returns/{return_id}/{action}", {
          params: { path: { return_id: id, action } },
          body: body as never,
        }),
      );
      setMsg({ ok: true, text: done });
      reload();
      return true;
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
      return false;
    }
  };

  return (
    <>
      <section className={ui.panel} aria-label="Return details">
        <div className={c.panelHead}>
          <h2 className={ui.subtitle}>
            <span className={c.mono}>{r.number}</span> ·{" "}
            {r.kind === "exchange" ? "Exchange" : "Refund"}
          </h2>
          <span className={ui.tag}>{RETURN_STATUS[r.status] ?? r.status}</span>
        </div>
        <dl className={c.facts}>
          <dt>Order</dt>
          <dd>
            <Link href={`/orders/view?number=${r.order}`} className={c.mono}>
              {r.order}
            </Link>
          </dd>
          <dt>Customer</dt>
          <dd>
            {r.customer_name} · {r.customer_email}
          </dd>
          <dt>Reason</dt>
          <dd>{r.reason_label}</dd>
          {r.details && (
            <>
              <dt>Customer&apos;s note</dt>
              <dd>{r.details}</dd>
            </>
          )}
          <dt>Requested</dt>
          <dd>{formatTime(r.created_at)}</dd>
          {r.decision_note && (
            <>
              <dt>Our note</dt>
              <dd>{r.decision_note}</dd>
            </>
          )}
          {r.refund_amount && r.status === "completed" && (
            <>
              <dt>Refund raised</dt>
              <dd>
                {money(r.refund_amount)} · <Link href="/orders/refunds">waiting for approval</Link>
              </dd>
            </>
          )}
          {r.exchange_order && (
            <>
              <dt>Replacement order</dt>
              <dd>
                <Link href={`/orders/view?number=${r.exchange_order}`} className={c.mono}>
                  {r.exchange_order}
                </Link>
              </dd>
            </>
          )}
        </dl>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">SKU</th>
              <th scope="col">Units</th>
              {r.kind === "exchange" && <th scope="col">Wants instead</th>}
              <th scope="col">Inspection</th>
            </tr>
          </thead>
          <tbody>
            {r.items.map((i) => (
              <tr key={i.id}>
                <td>
                  {i.name}
                  <br />
                  <span className={ui.muted}>
                    {i.size} · {i.colour}
                  </span>
                </td>
                <td className={c.mono}>{i.sku}</td>
                <td>{i.quantity}</td>
                {r.kind === "exchange" && (
                  <td>
                    {i.exchange_label} <span className={c.mono}>{i.exchange_sku}</span>
                  </td>
                )}
                <td>
                  {i.outcome ? OUTCOME[i.outcome] : "—"}
                  {i.inspection_note && <span className={ui.muted}> · {i.inspection_note}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {decide && r.status === "requested" && <Decide act={act} />}
      {decide && r.status === "approved" && (
        <section className={ui.panel} aria-label="Receive">
          <h2 className={ui.subtitle}>When the parcel arrives</h2>
          <button
            className={ui.button}
            onClick={() => void act("receive", {}, "Marked as received.")}
          >
            Mark as received
          </button>
        </section>
      )}
      {decide && r.status === "received" && <Inspect ret={r} act={act} />}
      {decide && r.status === "inspected" && <Complete ret={r} act={act} />}
      <Message message={msg} />
    </>
  );
}

type Act = (action: string, body?: Record<string, unknown>, done?: string) => Promise<boolean>;

function Decide({ act }: { act: Act }) {
  const [note, setNote] = useState("");
  return (
    <section className={ui.panel} aria-label="Decide">
      <h2 className={ui.subtitle}>Decide</h2>
      <p className={ui.muted}>
        Approving emails the customer the return instructions from Settings. Rejecting needs a
        reason, which is emailed to them.
      </p>
      <div className={ui.field}>
        <label htmlFor="return-note">Note to the customer</label>
        <input
          id="return-note"
          className={ui.input}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div className={c.actions}>
        <button
          className={ui.button}
          onClick={() => void act("approve", { note }, "Approved; the customer has been emailed.")}
        >
          Approve return
        </button>
        <button
          className={ui.danger}
          disabled={!note.trim()}
          onClick={() => void act("reject", { note }, "Rejected; the customer has been emailed.")}
        >
          Reject
        </button>
      </div>
    </section>
  );
}

function Inspect({ ret, act }: { ret: Return; act: Act }) {
  const [v, setV] = useState<Record<string, { outcome: string; note: string }>>(
    Object.fromEntries(ret.items.map((i) => [i.id, { outcome: "sellable", note: "" }])),
  );
  return (
    <section className={ui.panel} aria-label="Inspect">
      <h2 className={ui.subtitle}>Inspect</h2>
      <p className={ui.muted}>
        Each item goes into the stock location you choose. Items not going back on sale need a note.
      </p>
      {ret.items.map((i) => {
        const row = v[i.id] ?? { outcome: "sellable", note: "" };
        return (
          <div key={i.id} className={c.shared}>
            <div className={ui.field}>
              <label htmlFor={`outcome-${i.id}`}>
                {i.name} ({i.size}, {i.colour}) × {i.quantity}
              </label>
              <select
                id={`outcome-${i.id}`}
                className={ui.select}
                value={row.outcome}
                onChange={(e) => setV({ ...v, [i.id]: { ...row, outcome: e.target.value } })}
              >
                {Object.entries(OUTCOME).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className={ui.field}>
              <label htmlFor={`note-${i.id}`}>Note for {i.sku}</label>
              <input
                id={`note-${i.id}`}
                className={ui.input}
                value={row.note}
                onChange={(e) => setV({ ...v, [i.id]: { ...row, note: e.target.value } })}
              />
            </div>
          </div>
        );
      })}
      <button
        className={ui.button}
        onClick={() => void act("inspect", { outcomes: v }, "Inspection saved; stock updated.")}
      >
        Save inspection
      </button>
    </section>
  );
}

function Complete({ ret, act }: { ret: Return; act: Act }) {
  const [amount, setAmount] = useState(
    ret.suggested_refund ? String(Number(ret.suggested_refund)) : "",
  );
  if (ret.kind === "exchange")
    return (
      <section className={ui.panel} aria-label="Complete">
        <h2 className={ui.subtitle}>Send the replacement</h2>
        <p className={ui.muted}>
          Creates a no-charge order for the replacement, takes it out of stock, and emails the
          customer. Pack and dispatch it from Orders like any other order.
        </p>
        <button
          className={ui.button}
          onClick={() => void act("complete", {}, "Replacement order created.")}
        >
          Create replacement order
        </button>
      </section>
    );
  return (
    <section className={ui.panel} aria-label="Complete">
      <h2 className={ui.subtitle}>Refund</h2>
      {!ret.can_complete_refund ? (
        <p className={ui.muted}>Your role can&apos;t request refunds. Ask a colleague who can.</p>
      ) : (
        <>
          <p className={ui.muted}>
            Suggested: what the returned items cost, less their share of any discount (delivery
            isn&apos;t refunded). The refund then needs approval like any other, and asks for your
            authenticator code.
          </p>
          <div className={ui.field}>
            <label htmlFor="refund-amount">Refund amount (Rs)</label>
            <input
              id="refund-amount"
              className={ui.input}
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <button
            className={ui.button}
            disabled={!Number(amount)}
            onClick={() => void act("complete", { refund_amount: amount }, "Refund requested.")}
          >
            Request refund
          </button>
        </>
      )}
    </section>
  );
}
