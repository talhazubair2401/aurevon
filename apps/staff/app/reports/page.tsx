"use client";

import { useCallback, useState } from "react";
import { money } from "../../components/OrdersNav";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, useApiData, type Schemas } from "../../lib/api";

type Dashboard = Schemas["DashboardOut"];

export default function ReportsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Reports</h1>
      <Reports />
    </Shell>
  );
}

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const EXPORT_LABEL: Record<string, string> = {
  "daily-sales": "Daily sales",
  products: "Products",
  categories: "Categories",
  orders: "Orders with customer details",
};

function Reports() {
  const today = new Date();
  const [range, setRange] = useState({ from: "", to: "" });
  const [draft, setDraft] = useState({
    from: iso(new Date(today.getTime() - 29 * 864e5)),
    to: iso(today),
  });
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/reports/dashboard", {
          params: {
            query: {
              ...(range.from ? { from: range.from } : {}),
              ...(range.to ? { to: range.to } : {}),
            },
          },
        }),
      ),
    [range],
  );
  const { data, error } = useApiData(load);
  const quick = (days: number) => {
    const next = { from: iso(new Date(today.getTime() - (days - 1) * 864e5)), to: iso(today) };
    setDraft(next);
    setRange(next);
  };
  return (
    <>
      <form
        className={ui.row}
        aria-label="Report period"
        onSubmit={(e) => {
          e.preventDefault();
          setRange(draft);
        }}
      >
        {[7, 30, 90].map((d) => (
          <button key={d} type="button" className={ui.secondary} onClick={() => quick(d)}>
            Last {d} days
          </button>
        ))}
        <label className={ui.row}>
          From
          <input
            type="date"
            className={ui.input}
            value={draft.from}
            onChange={(e) => setDraft({ ...draft, from: e.target.value })}
          />
        </label>
        <label className={ui.row}>
          To
          <input
            type="date"
            className={ui.input}
            value={draft.to}
            onChange={(e) => setDraft({ ...draft, to: e.target.value })}
          />
        </label>
        <button className={ui.button} type="submit">
          Show
        </button>
      </form>
      {error && <p className={ui.error}>{error}</p>}
      {!data ? <p className={ui.muted}>Loading…</p> : <Body d={data} />}
    </>
  );
}

function Change({ value }: { value: number | null }) {
  if (value === null) return <span className={c.change}>no earlier sales to compare</span>;
  return (
    <span className={c.change}>
      {value > 0 ? "▲" : value < 0 ? "▼" : "■"} {Math.abs(value)}% vs previous period
    </span>
  );
}

function Tile({ label, value, change }: { label: string; value: string; change?: number | null }) {
  return (
    <div className={c.stat}>
      <strong>{value}</strong>
      {label}
      {change !== undefined && <Change value={change} />}
    </div>
  );
}

function Body({ d }: { d: Dashboard }) {
  const s = d.summary;
  const [showTable, setShowTable] = useState(false);
  const exportUrl = (kind: string) =>
    `/api/v1/staff/reports/export/${kind}?from=${d.start}&to=${d.end}`;
  return (
    <>
      <p className={ui.muted}>
        {d.start} to {d.end} (Pakistan time), compared with {d.previous_start} to {d.previous_end}.
      </p>
      <div className={c.stats}>
        <Tile label="gross sales" value={money(s.gross_sales)} change={d.change.gross_sales} />
        <Tile
          label="net sales (after refunds)"
          value={money(s.net_sales)}
          change={d.change.net_sales}
        />
        <Tile label="orders" value={String(s.orders)} change={d.change.orders} />
        <Tile
          label="average order"
          value={money(s.average_order)}
          change={d.change.average_order}
        />
        <Tile label="pieces sold" value={String(s.units)} />
        <Tile label="refunded" value={money(s.refunds)} />
      </div>

      <section className={ui.panel} aria-labelledby="daily-title">
        <div className={c.panelHead}>
          <h2 className={ui.subtitle} id="daily-title">
            Gross sales by day
          </h2>
          <button className={ui.link} onClick={() => setShowTable(!showTable)}>
            {showTable ? "Show chart" : "Show as table"}
          </button>
        </div>
        {showTable ? <DailyTable d={d} /> : <DailyChart d={d} />}
      </section>

      <div className={c.shared}>
        <section className={ui.panel} aria-labelledby="money-title">
          <h2 className={ui.subtitle} id="money-title">
            Where the money came from
          </h2>
          <dl className={c.facts}>
            <dt>Card and wallet</dt>
            <dd>{money(s.card_sales)}</dd>
            <dt>Cash on delivery</dt>
            <dd>{money(s.cod_sales)}</dd>
            <dt>Discounts given</dt>
            <dd>{money(s.discounts)}</dd>
            <dt>Delivery charged</dt>
            <dd>{money(s.shipping)}</dd>
            <dt>COD fees</dt>
            <dd>{money(s.cod_fees)}</dd>
            <dt>Tax</dt>
            <dd>{money(s.tax)}</dd>
            <dt>COD still with couriers</dt>
            <dd>{money(s.cod_outstanding)} (all time)</dd>
            <dt>Not completed</dt>
            <dd>
              {s.cancelled} cancelled · {s.awaiting_payment} awaiting payment
            </dd>
          </dl>
        </section>
        <section className={ui.panel} aria-labelledby="cust-title">
          <h2 className={ui.subtitle} id="cust-title">
            Customers
          </h2>
          <dl className={c.facts}>
            <dt>New accounts</dt>
            <dd>{d.customers.new_accounts}</dd>
            <dt>Orders by guests</dt>
            <dd>{d.customers.guest_orders}</dd>
            <dt>Orders by account holders</dt>
            <dd>{d.customers.account_orders}</dd>
            <dt>Account holders who bought</dt>
            <dd>{d.customers.buying_accounts}</dd>
            <dt>… of whom had bought before</dt>
            <dd>{d.customers.returning_accounts}</dd>
          </dl>
        </section>
        <section className={ui.panel} aria-labelledby="ret-title">
          <h2 className={ui.subtitle} id="ret-title">
            Returns
          </h2>
          <dl className={c.facts}>
            <dt>Requests</dt>
            <dd>
              {d.returns.requests} ({d.returns.refunds} refund, {d.returns.exchanges} exchange)
            </dd>
            <dt>Pieces returned</dt>
            <dd>
              {d.returns.units_returned} · {d.returns.return_rate_percent}% of pieces sold
            </dd>
            {d.returns.by_reason.map((r) => (
              <div key={r.reason} style={{ display: "contents" }}>
                <dt>{r.reason}</dt>
                <dd>{r.count}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className={ui.panel} aria-labelledby="inv-title">
          <h2 className={ui.subtitle} id="inv-title">
            Stock today
          </h2>
          <dl className={c.facts}>
            <dt>Sellable pieces</dt>
            <dd>
              {d.inventory.sellable_units} ({d.inventory.reserved_units} held by orders)
            </dd>
            <dt>Value at shop prices</dt>
            <dd>{money(d.inventory.retail_value)}</dd>
            <dt>Sold out</dt>
            <dd>{d.inventory.out_of_stock} variants</dd>
            <dt>At or below reorder level</dt>
            <dd>{d.inventory.low_stock} variants</dd>
            <dt>Quarantine · damaged</dt>
            <dd>
              {d.inventory.quarantine_units} · {d.inventory.damaged_units} pieces
            </dd>
          </dl>
        </section>
      </div>

      <Table
        title="Best-selling products"
        head={["Product", "Pieces", "Revenue", "Returned"]}
        rows={d.products.map((p) => [p.name, p.units, money(p.revenue), p.returned_units])}
      />
      <Table
        title="Categories"
        head={["Category", "Pieces", "Revenue"]}
        rows={d.categories.map((x) => [x.category ?? "—", x.units, money(x.revenue)])}
      />
      <Table
        title="Top cities"
        head={["City", "Orders", "Gross sales"]}
        rows={d.cities.map((x) => [x.city, x.orders, money(x.gross_sales)])}
      />
      <Table
        title="Coupons used"
        head={["Code", "Uses", "Discount", "Orders worth"]}
        rows={d.coupons.map((x) => [x.code, x.uses, money(x.discount), money(x.orders_value)])}
      />

      <section className={ui.panel} aria-labelledby="exp-title">
        <h2 className={ui.subtitle} id="exp-title">
          Download (CSV)
        </h2>
        <div className={c.actions}>
          {d.exports.map((k) => (
            <a key={k} className={ui.secondary} href={exportUrl(k)} download>
              {EXPORT_LABEL[k] ?? k}
            </a>
          ))}
        </div>
        {d.exports.includes("orders") && (
          <p className={ui.muted}>
            The order list contains customer names, emails and phone numbers. Each download is
            recorded in the audit log; store it securely.
          </p>
        )}
        <p className={ui.muted}>{d.definitions}</p>
      </section>
    </>
  );
}

function DailyChart({ d }: { d: Dashboard }) {
  const values = d.daily.map((x) => Number(x.gross_sales));
  const max = Math.max(...values, 1);
  const n = d.daily.length;
  const W = 1000;
  const H = 200;
  const gap = n > 60 ? 1 : 2;
  const w = W / n - gap;
  if (values.every((v) => v === 0)) return <p className={ui.muted}>No sales in this period.</p>;
  return (
    <>
      <svg
        className={c.chart}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Gross sales by day, highest ${money(max)}`}
      >
        <line x1={0} x2={W} y1={H - 0.5} y2={H - 0.5} />
        {d.daily.map((x, i) => {
          const v = Number(x.gross_sales);
          const h = v ? Math.max((v / max) * (H - 8), 2) : 0;
          return (
            <rect
              key={x.day}
              x={i * (W / n) + gap / 2}
              y={H - h}
              width={Math.max(w, 1)}
              height={h}
              rx={2}
              tabIndex={0}
            >
              <title>
                {x.day}: {money(x.gross_sales)} from {x.orders} orders
              </title>
            </rect>
          );
        })}
      </svg>
      <p className={ui.muted}>
        {d.daily[0]?.day} → {d.daily[n - 1]?.day} · tallest bar {money(max)}. Hover a bar for the
        day.
      </p>
    </>
  );
}

function DailyTable({ d }: { d: Dashboard }) {
  return (
    <table className={ui.table}>
      <thead>
        <tr>
          <th scope="col">Day</th>
          <th scope="col">Orders</th>
          <th scope="col">Gross sales</th>
        </tr>
      </thead>
      <tbody>
        {d.daily.map((x) => (
          <tr key={x.day}>
            <td>{x.day}</td>
            <td>{x.orders}</td>
            <td>{money(x.gross_sales)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Table({
  title,
  head,
  rows,
}: {
  title: string;
  head: string[];
  rows: Array<Array<string | number>>;
}) {
  return (
    <section className={ui.panel} aria-label={title}>
      <h2 className={ui.subtitle}>{title}</h2>
      {rows.length === 0 ? (
        <p className={ui.muted}>Nothing in this period.</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              {head.map((h) => (
                <th key={h} scope="col">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((cell, j) => (
                  <td key={j}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
