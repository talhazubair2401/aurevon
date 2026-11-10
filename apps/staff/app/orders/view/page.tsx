"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import {
  money,
  ORDER_STATUS,
  OrdersNav,
  PAYMENT_STATUS,
  REFUND_STATE,
  SHIPMENT_STATUS,
  StatusTag,
} from "../../../components/OrdersNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData, type Schemas } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Detail = Schemas["StaffOrderOut"];
type Money = { amount: string; currency: string };
interface OrderBody {
  number: string;
  status: string;
  payment_status: string;
  payment_method: string;
  placed_at: string;
  email: string;
  phone: string;
  items: Array<{
    name: string;
    sku: string;
    size: string;
    colour: string;
    quantity: number;
    unit_price: Money;
    line_total: Money;
    image_url: string;
  }>;
  subtotal: Money;
  discount: Money;
  discount_label: string;
  shipping_fee: Money;
  cod_fee: Money;
  tax: Money;
  tax_included: boolean;
  total: Money;
  shipping_address: Record<string, string>;
  shipping_method: string;
  delivery_days: string;
}
interface Hist {
  kind: string;
  from: string;
  to: string;
  actor: string;
  reason: string;
  at: string;
}
interface Pay {
  id: string;
  provider: string;
  state: string;
  amount: string;
  provider_ref: string;
  failure_reason: string;
  needs_review: boolean;
  review_note: string;
  created_at: string;
}
interface Ref {
  id: string;
  amount: string;
  reason: string;
  state: string;
  source: string;
  requested_by: string;
  approved_by: string;
  second_approved_by: string;
  decision_note: string;
  last_error: string;
  created_at: string;
}
interface Ship {
  id: string;
  courier: string;
  tracking_number: string;
  tracking_url: string;
  status: string;
  cod_amount: string;
  booked_at: string;
  next: string[];
  events: Array<{
    status: string;
    description: string;
    location: string;
    at: string;
    source: string;
  }>;
}
interface Alert {
  id: string;
  message: string;
  severity: string;
  created_at: string;
}

export default function OrderViewPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Orders</h1>
      <OrdersNav />
      <Suspense fallback={<p className={ui.muted}>Loading…</p>}>
        <Loader />
      </Suspense>
    </Shell>
  );
}

function Loader() {
  const number = useSearchParams().get("number") ?? "";
  const load = useCallback(
    () => call(() => api.GET("/api/v1/staff/orders/{number}", { params: { path: { number } } })),
    [number],
  );
  const { data, error } = useApiData(load);
  const [saved, setSaved] = useState<Detail | null>(null);
  const detail = saved ?? data;
  if (error) return <p className={ui.error}>{error}</p>;
  if (!detail) return <p className={ui.muted}>Loading…</p>;
  return <OrderDetail detail={detail} onChange={setSaved} />;
}

function OrderDetail({ detail, onChange }: { detail: Detail; onChange: (d: Detail) => void }) {
  const { can } = useSession();
  const o = detail.order as OrderBody;
  const history = detail.history as Hist[];
  const pays = detail.payments as Pay[];
  const refunds = detail.refunds as Ref[];
  const shipments = detail.shipments as Ship[];
  const alerts = detail.alerts as Alert[];
  const returns = detail.returns as Array<{
    id: string;
    number: string;
    kind: string;
    status: string;
  }>;
  const [msg, setMsg] = useState<Msg>(null);
  const [busy, setBusy] = useState(false);
  const path = { params: { path: { number: o.number } } };

  const run = async (action: () => Promise<Detail>, done: string) => {
    setBusy(true);
    setMsg(null);
    try {
      onChange(await action());
      setMsg({ ok: true, text: done });
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const a = o.shipping_address;

  return (
    <>
      <p>
        <Link href="/orders" className={ui.link}>
          ← All orders
        </Link>
      </p>
      <section className={ui.panel} aria-labelledby="order-title">
        <div className={c.panelHead}>
          <h2 id="order-title" className={ui.subtitle}>
            <span className={c.mono}>{o.number}</span> · {formatTime(o.placed_at)}
          </h2>
          <span className={ui.row}>
            <StatusTag value={o.status} labels={ORDER_STATUS} />
            <StatusTag value={o.payment_status} labels={PAYMENT_STATUS} />
          </span>
        </div>
        {alerts.map((al) => (
          <p
            key={al.id}
            className={al.severity === "critical" ? ui.bannerUrgent : ui.banner}
            role="alert"
          >
            {al.message}
          </p>
        ))}
        <dl className={c.facts}>
          <dt>Customer</dt>
          <dd>
            {a.name} · {o.email} · {o.phone}
            {detail.account_email ? " (account)" : " (guest)"}
          </dd>
          <dt>Deliver to</dt>
          <dd>
            {[a.line1, a.line2, a.area, a.city, a.province, a.postal_code]
              .filter(Boolean)
              .join(", ")}
          </dd>
          <dt>Delivery</dt>
          <dd>
            {o.shipping_method} {o.delivery_days ? `· ${o.delivery_days} days` : ""}
          </dd>
          <dt>Payment</dt>
          <dd>{o.payment_method === "cod" ? "Cash on delivery" : "Card or wallet"}</dd>
        </dl>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">SKU</th>
              <th scope="col">Qty</th>
              <th scope="col">Price</th>
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {o.items.map((i) => (
              <tr key={i.sku}>
                <td>
                  {i.name}
                  <br />
                  <span className={ui.muted}>
                    {i.colour} · {i.size}
                  </span>
                </td>
                <td className={c.mono}>{i.sku}</td>
                <td>{i.quantity}</td>
                <td>{money(i.unit_price.amount)}</td>
                <td>{money(i.line_total.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <dl className={c.facts}>
          <dt>Subtotal</dt>
          <dd>{money(o.subtotal.amount)}</dd>
          {Number(o.discount.amount) > 0 && (
            <>
              <dt>Discount {o.discount_label && `(${o.discount_label})`}</dt>
              <dd>−{money(o.discount.amount)}</dd>
            </>
          )}
          <dt>Delivery</dt>
          <dd>{money(o.shipping_fee.amount)}</dd>
          {Number(o.cod_fee.amount) > 0 && (
            <>
              <dt>COD fee</dt>
              <dd>{money(o.cod_fee.amount)}</dd>
            </>
          )}
          {Number(o.tax.amount) > 0 && (
            <>
              <dt>Tax {o.tax_included ? "(included)" : ""}</dt>
              <dd>{money(o.tax.amount)}</dd>
            </>
          )}
          <dt>
            <strong>Total</strong>
          </dt>
          <dd>
            <strong>{money(o.total.amount)}</strong>
          </dd>
        </dl>
      </section>

      {can("orders.update") && <Fulfilment detail={detail} busy={busy} run={run} path={path} />}
      <Message message={msg} />

      {shipments.length > 0 && (
        <section className={ui.panel} aria-labelledby="ship-title">
          <h2 id="ship-title" className={ui.subtitle}>
            Shipments
          </h2>
          {shipments.map((s) => (
            <ShipmentCard key={s.id} s={s} canUpdate={can("orders.update")} busy={busy} run={run} />
          ))}
        </section>
      )}

      {o.payment_method === "cod" &&
        detail.cod_actions.length > 0 &&
        can("remittance.reconcile") && (
          <CodPanel
            actions={detail.cod_actions}
            total={o.total.amount}
            busy={busy}
            run={run}
            path={path}
          />
        )}

      <section className={ui.panel} aria-labelledby="pay-title">
        <h2 id="pay-title" className={ui.subtitle}>
          Payments and refunds
        </h2>
        {pays.length === 0 && <p className={ui.muted}>No online payment attempts.</p>}
        {pays.map((p) => (
          <div key={p.id} className={c.shared}>
            <p>
              {p.provider} · {money(p.amount)} · <span className={ui.tag}>{p.state}</span>{" "}
              <span className={c.mono}>{p.provider_ref}</span>
              {p.failure_reason && <span className={ui.muted}> · {p.failure_reason}</span>}
            </p>
            {p.needs_review && <ReviewPanel payment={p} busy={busy} run={run} />}
          </div>
        ))}
        {refunds.length > 0 && (
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Refund</th>
                <th scope="col">Reason</th>
                <th scope="col">State</th>
                <th scope="col">Requested by</th>
                <th scope="col">Approved by</th>
              </tr>
            </thead>
            <tbody>
              {refunds.map((r) => (
                <tr key={r.id}>
                  <td>{money(r.amount)}</td>
                  <td>
                    {r.reason}
                    {r.last_error && <span className={ui.muted}> · {r.last_error}</span>}
                  </td>
                  <td>
                    <StatusTag value={r.state} labels={REFUND_STATE} />
                  </td>
                  <td>{r.requested_by}</td>
                  <td>{[r.approved_by, r.second_approved_by].filter(Boolean).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {can("refunds.request") && Number(detail.refundable) > 0 && (
          <RefundForm refundable={detail.refundable} busy={busy} run={run} path={path} />
        )}
        {refunds.some((r) => r.state === "requested") && (
          <p className={ui.muted}>
            Refunds waiting for approval are on the <Link href="/orders/refunds">Refunds</Link>{" "}
            page.
          </p>
        )}
      </section>

      {returns.length > 0 && (
        <section className={ui.panel} aria-labelledby="ret-title">
          <h2 id="ret-title" className={ui.subtitle}>
            Returns
          </h2>
          <ul>
            {returns.map((r) => (
              <li key={r.id}>
                <Link href={`/support/returns/view?id=${r.id}`} className={c.mono}>
                  {r.number}
                </Link>{" "}
                · {r.kind} · <span className={ui.tag}>{r.status}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={ui.panel} aria-labelledby="hist-title">
        <h2 id="hist-title" className={ui.subtitle}>
          History
        </h2>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Change</th>
              <th scope="col">By</th>
              <th scope="col">Note</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h, i) => (
              <tr key={i}>
                <td>{formatTime(h.at)}</td>
                <td>
                  {h.kind === "payment" ? "Payment: " : ""}
                  {(h.kind === "payment" ? PAYMENT_STATUS : ORDER_STATUS)[h.to] ?? h.to}
                </td>
                <td>{h.actor}</td>
                <td>{h.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

type Run = (action: () => Promise<Detail>, done: string) => Promise<void>;
type NumberPath = { params: { path: { number: string } } };

function Fulfilment({
  detail,
  busy,
  run,
  path,
}: {
  detail: Detail;
  busy: boolean;
  run: Run;
  path: NumberPath;
}) {
  const [reason, setReason] = useState("");
  const [tracking, setTracking] = useState("");
  const [link, setLink] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const labels: Record<string, string> = {
    packing: "Start packing",
    confirmed: "Back to confirmed",
    delivered: "Mark delivered",
    undelivered: "Mark returned undelivered",
    returned: "Mark returned",
  };
  if (detail.next_statuses.length === 0 && !detail.can_dispatch && !detail.can_cancel) return null;
  return (
    <section className={ui.panel} aria-labelledby="ful-title">
      <h2 id="ful-title" className={ui.subtitle}>
        Fulfilment
      </h2>
      {detail.next_statuses.length > 0 && (
        <div className={c.actions}>
          <input
            className={ui.input}
            aria-label="Note for the history (optional)"
            placeholder="Note (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {detail.next_statuses.map((to) => (
            <button
              key={to}
              className={to === "packing" ? ui.button : ui.secondary}
              disabled={busy}
              onClick={() =>
                void run(
                  () =>
                    call(() =>
                      api.POST("/api/v1/staff/orders/{number}/status", {
                        ...path,
                        body: { to, reason } as never,
                      }),
                    ),
                  `Order is now ${ORDER_STATUS[to]?.toLowerCase()}.`,
                )
              }
            >
              {labels[to] ?? to}
            </button>
          ))}
        </div>
      )}
      {detail.can_dispatch && (
        <div className={c.shared}>
          <div className={ui.field}>
            <label htmlFor="trk">Courier tracking number</label>
            <input
              id="trk"
              className={`${ui.input} ${c.mono}`}
              value={tracking}
              onChange={(e) => setTracking(e.target.value)}
            />
          </div>
          <div className={ui.field}>
            <label htmlFor="trk-url">Tracking link (optional, https://)</label>
            <input
              id="trk-url"
              className={ui.input}
              value={link}
              onChange={(e) => setLink(e.target.value)}
            />
          </div>
          <div className={c.actions}>
            <button
              className={ui.button}
              disabled={busy || !tracking.trim()}
              onClick={() =>
                void run(
                  () =>
                    call(() =>
                      api.POST("/api/v1/staff/orders/{number}/dispatch", {
                        ...path,
                        body: {
                          courier: "manual",
                          tracking_number: tracking,
                          tracking_url: link,
                        } as never,
                      }),
                    ),
                  "Dispatched. The customer has been emailed the tracking details.",
                )
              }
            >
              Dispatch
            </button>
          </div>
        </div>
      )}
      {detail.can_cancel && (
        <div className={c.actions}>
          <input
            className={ui.input}
            aria-label="Why is the order cancelled?"
            placeholder="Reason for cancelling"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
          <button
            className={ui.danger}
            disabled={busy || !cancelReason.trim()}
            onClick={() =>
              void run(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/orders/{number}/cancel", {
                      ...path,
                      body: { reason: cancelReason } as never,
                    }),
                  ),
                "Cancelled. Stock is back; a paid order gets a refund request.",
              )
            }
          >
            Cancel order
          </button>
        </div>
      )}
    </section>
  );
}

function ShipmentCard({
  s,
  canUpdate,
  busy,
  run,
}: {
  s: Ship;
  canUpdate: boolean;
  busy: boolean;
  run: Run;
}) {
  const [to, setTo] = useState(s.next[0] ?? "");
  const [desc, setDesc] = useState("");
  const [where, setWhere] = useState("");
  return (
    <div className={c.shared}>
      <p>
        <span className={c.mono}>{s.tracking_number || "—"}</span> ·{" "}
        <StatusTag value={s.status} labels={SHIPMENT_STATUS} />
        {Number(s.cod_amount) > 0 && (
          <span className={ui.muted}> · collect {money(s.cod_amount)}</span>
        )}
        {s.tracking_url && (
          <>
            {" "}
            ·{" "}
            <a className={ui.link} href={s.tracking_url} target="_blank" rel="noreferrer">
              Courier tracking
            </a>
          </>
        )}
      </p>
      <ul>
        {s.events.map((e, i) => (
          <li key={i} className={ui.muted}>
            {formatTime(e.at)} · {SHIPMENT_STATUS[e.status] ?? e.status}
            {e.location && ` · ${e.location}`}
            {e.description && ` · ${e.description}`}
          </li>
        ))}
      </ul>
      {canUpdate && s.next.length > 0 && (
        <div className={c.actions}>
          <select
            className={ui.select}
            aria-label="New tracking status"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          >
            {s.next.map((n) => (
              <option key={n} value={n}>
                {SHIPMENT_STATUS[n] ?? n}
              </option>
            ))}
          </select>
          <input
            className={ui.input}
            aria-label="Location"
            placeholder="Location"
            value={where}
            onChange={(e) => setWhere(e.target.value)}
          />
          <input
            className={ui.input}
            aria-label="Details"
            placeholder="Details"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
          />
          <button
            className={ui.secondary}
            disabled={busy || !to}
            onClick={() =>
              void run(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/shipments/{shipment_id}/events", {
                      params: { path: { shipment_id: s.id } },
                      body: { status: to, description: desc, location: where } as never,
                    }),
                  ),
                "Tracking updated.",
              )
            }
          >
            Add tracking update
          </button>
        </div>
      )}
    </div>
  );
}

function CodPanel({
  actions,
  total,
  busy,
  run,
  path,
}: {
  actions: string[];
  total: string;
  busy: boolean;
  run: Run;
  path: NumberPath;
}) {
  const [amount, setAmount] = useState(total);
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  return (
    <section className={ui.panel} aria-labelledby="cod-title">
      <h2 id="cod-title" className={ui.subtitle}>
        Cash on delivery remittance
      </h2>
      {actions.includes("received") && (
        <div className={c.actions}>
          <input
            className={ui.input}
            aria-label="Amount remitted (PKR)"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
          <input
            className={ui.input}
            aria-label="Courier remittance reference"
            placeholder="Remittance reference"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
          <button
            className={ui.button}
            disabled={busy || !reference.trim()}
            onClick={() =>
              void run(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/orders/{number}/cod", {
                      ...path,
                      body: { action: "received", amount, reference } as never,
                    }),
                  ),
                "Remittance recorded.",
              )
            }
          >
            Record remittance
          </button>
        </div>
      )}
      {actions.includes("reconciled") && (
        <div className={c.actions}>
          <input
            className={ui.input}
            aria-label="Reconciliation note"
            placeholder="Note (required for a discrepancy)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            className={ui.secondary}
            disabled={busy}
            onClick={() =>
              void run(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/orders/{number}/cod", {
                      ...path,
                      body: { action: "reconciled", note } as never,
                    }),
                  ),
                "Reconciled.",
              )
            }
          >
            Mark reconciled
          </button>
        </div>
      )}
    </section>
  );
}

function RefundForm({
  refundable,
  busy,
  run,
  path,
}: {
  refundable: string;
  busy: boolean;
  run: Run;
  path: NumberPath;
}) {
  const [amount, setAmount] = useState(refundable);
  const [reason, setReason] = useState("");
  return (
    <div className={c.actions}>
      <input
        className={ui.input}
        aria-label="Refund amount (PKR)"
        inputMode="decimal"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <input
        className={ui.input}
        aria-label="Reason for the refund"
        placeholder="Reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <button
        className={ui.secondary}
        disabled={busy || !reason.trim()}
        onClick={() =>
          void run(
            () =>
              call(() =>
                api.POST("/api/v1/staff/orders/{number}/refunds", {
                  ...path,
                  body: { amount, reason } as never,
                }),
              ),
            "Refund requested. It needs approval before it is paid.",
          )
        }
      >
        Request refund
      </button>
      <span className={ui.muted}>Up to {money(refundable)}</span>
    </div>
  );
}

function ReviewPanel({ payment, busy, run }: { payment: Pay; busy: boolean; run: Run }) {
  const { can } = useSession();
  const [note, setNote] = useState("");
  return (
    <div className={c.actions}>
      <p className={ui.bannerUrgent}>
        The provider sent conflicting updates for this payment. Check it with the provider.
      </p>
      {can("refunds.approve") && (
        <>
          <input
            className={ui.input}
            aria-label="How was it settled?"
            placeholder="How was it settled?"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            className={ui.secondary}
            disabled={busy || !note.trim()}
            onClick={() =>
              void run(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/payments/{payment_id}/resolve", {
                      params: { path: { payment_id: payment.id } },
                      body: { note } as never,
                    }),
                  ),
                "Payment review settled.",
              )
            }
          >
            Mark settled
          </button>
        </>
      )}
    </div>
  );
}
