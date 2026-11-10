"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import {
  money,
  ORDER_STATUS,
  OrdersNav,
  PAYMENT_METHOD,
  PAYMENT_STATUS,
  StatusTag,
} from "../../components/OrdersNav";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, formatTime, useApiData } from "../../lib/api";

export default function OrdersPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Orders</h1>
      <OrdersNav />
      <Orders />
    </Shell>
  );
}

type Filters = {
  status: string;
  payment_method: string;
  q: string;
  date_from: string;
  date_to: string;
};
const EMPTY: Filters = { status: "", payment_method: "", q: "", date_from: "", date_to: "" };

function Orders() {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => {
    const query = Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as Record<
      string,
      string
    >;
    return call(() =>
      api.GET("/api/v1/staff/orders", {
        params: { query: { ...query, ...(offset ? { offset } : {}) } },
      }),
    );
  }, [filters, offset]);
  const { data, error } = useApiData(load);
  const pick = (status: string) => {
    setDraft({ ...draft, status });
    setFilters({ ...filters, status });
    setOffset(0);
  };

  return (
    <>
      {data && (
        <div className={c.subnav} aria-label="Orders by status">
          <button
            type="button"
            className={filters.status ? c.subnavLink : c.subnavActive}
            onClick={() => pick("")}
          >
            All
          </button>
          {["awaiting_payment", "confirmed", "packing", "dispatched", "delivered"].map((s) => (
            <button
              type="button"
              key={s}
              className={filters.status === s ? c.subnavActive : c.subnavLink}
              onClick={() => pick(s)}
            >
              {ORDER_STATUS[s]} ({data.counts[s] ?? 0})
            </button>
          ))}
        </div>
      )}
      <form
        className={ui.row}
        onSubmit={(e) => {
          e.preventDefault();
          setFilters(draft);
          setOffset(0);
        }}
      >
        <input
          className={ui.input}
          aria-label="Search by order number, name, email, phone or tracking number"
          placeholder="Order, name, email, phone or tracking"
          value={draft.q}
          onChange={(e) => setDraft({ ...draft, q: e.target.value })}
        />
        <select
          className={ui.select}
          aria-label="Payment method"
          value={draft.payment_method}
          onChange={(e) => setDraft({ ...draft, payment_method: e.target.value })}
        >
          <option value="">All payment methods</option>
          <option value="cod">Cash on delivery</option>
          <option value="card">Card or wallet</option>
        </select>
        <label className={ui.row}>
          From
          <input
            type="date"
            className={ui.input}
            value={draft.date_from}
            onChange={(e) => setDraft({ ...draft, date_from: e.target.value })}
          />
        </label>
        <label className={ui.row}>
          To
          <input
            type="date"
            className={ui.input}
            value={draft.date_to}
            onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}
          />
        </label>
        <button className={ui.secondary} type="submit">
          Search
        </button>
      </form>
      {error && <p className={ui.error}>{error}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.results.length === 0 ? (
        <p className={ui.muted}>No orders match.</p>
      ) : (
        <>
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Order</th>
                <th scope="col">Placed</th>
                <th scope="col">Customer</th>
                <th scope="col">City</th>
                <th scope="col">Items</th>
                <th scope="col">Total</th>
                <th scope="col">Status</th>
                <th scope="col">Payment</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((o) => (
                <tr key={o.number}>
                  <td>
                    <Link href={`/orders/view?number=${o.number}`} className={c.mono}>
                      {o.number}
                    </Link>
                  </td>
                  <td>{formatTime(o.placed_at)}</td>
                  <td>
                    {o.customer}
                    <br />
                    <span className={ui.muted}>{o.email}</span>
                  </td>
                  <td>{o.city}</td>
                  <td>{o.items}</td>
                  <td>{money(o.total)}</td>
                  <td>
                    <StatusTag value={o.status} labels={ORDER_STATUS} />
                  </td>
                  <td>
                    <StatusTag value={o.payment_status} labels={PAYMENT_STATUS} />
                    <br />
                    <span className={ui.muted}>
                      {PAYMENT_METHOD[o.payment_method] ?? o.payment_method}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className={c.actions}>
            <span className={ui.muted}>
              {offset + 1}–{offset + data.results.length} of {data.count}
            </span>
            {offset > 0 && (
              <button className={ui.secondary} onClick={() => setOffset(Math.max(offset - 50, 0))}>
                Previous
              </button>
            )}
            {offset + data.results.length < data.count && (
              <button className={ui.secondary} onClick={() => setOffset(offset + 50)}>
                Next
              </button>
            )}
          </div>
        </>
      )}
    </>
  );
}
