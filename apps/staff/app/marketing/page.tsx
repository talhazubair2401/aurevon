"use client";

import { useState } from "react";
import { Message, type Msg } from "../../components/CatalogNav";
import {
  describe,
  DiscountFieldsEditor,
  fromFields,
  initialFields,
  STATE,
} from "../../components/DiscountForm";
import { money } from "../../components/OrdersNav";
import { MARKETING_LINKS, SectionNav } from "../../components/SectionNav";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData, type Schemas } from "../../lib/api";

type Coupon = Schemas["CouponOut"];
const loadCoupons = () => call(() => api.GET("/api/v1/staff/coupons"));

export default function CouponsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Marketing</h1>
      <SectionNav label="Marketing" links={MARKETING_LINKS} />
      <Coupons />
    </Shell>
  );
}

function Coupons() {
  const { data, error, reload } = useApiData(loadCoupons);
  const [editing, setEditing] = useState<string | null>(null);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p className={ui.muted}>
        Customers type a coupon code in their bag. Coupons and automatic promotions don&apos;t
        stack: the larger discount applies.
      </p>
      <section className={ui.panel}>
        <h2 className={ui.subtitle}>Coupons</h2>
        {data.length === 0 ? (
          <p className={ui.muted}>No coupons yet.</p>
        ) : (
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Discount</th>
                <th scope="col">Runs</th>
                <th scope="col">Used</th>
                <th scope="col">Discount given</th>
                <th scope="col">Orders worth</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className={ui.muted}>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((cp) => (
                <tr key={cp.id}>
                  <td>
                    <span className={c.mono}>{cp.code}</span>
                    {cp.description && (
                      <>
                        <br />
                        <span className={ui.muted}>{cp.description}</span>
                      </>
                    )}
                  </td>
                  <td>{describe(cp)}</td>
                  <td>
                    {cp.starts_at ? formatTime(cp.starts_at) : "Now"} –{" "}
                    {cp.ends_at ? formatTime(cp.ends_at) : "no end"}
                  </td>
                  <td>
                    {cp.times_used}
                    {cp.usage_limit ? ` of ${cp.usage_limit}` : ""}
                  </td>
                  <td>{money(cp.discount_given)}</td>
                  <td>{money(cp.order_value)}</td>
                  <td>
                    <span className={ui.tag}>{STATE[cp.state] ?? cp.state}</span>
                  </td>
                  <td>
                    <button
                      className={ui.link}
                      onClick={() => setEditing(editing === cp.id ? null : cp.id)}
                    >
                      {editing === cp.id ? "Close" : "Edit"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {editing && (
        <CouponForm
          key={editing}
          coupon={data.find((x) => x.id === editing) ?? null}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      <CouponForm coupon={null} onSaved={reload} />
    </>
  );
}

function CouponForm({ coupon, onSaved }: { coupon: Coupon | null; onSaved: () => void }) {
  const [code, setCode] = useState(coupon?.code ?? "");
  const [description, setDescription] = useState(coupon?.description ?? "");
  const [limit, setLimit] = useState(coupon?.usage_limit ? String(coupon.usage_limit) : "");
  const [perCustomer, setPerCustomer] = useState(String(coupon?.per_customer_limit ?? 1));
  const [fields, setFields] = useState(initialFields(coupon ?? undefined));
  const [msg, setMsg] = useState<Msg>(null);
  const id = coupon?.id ?? "new-coupon";
  const save = async () => {
    setMsg(null);
    const body = {
      ...fromFields(fields),
      code,
      description,
      usage_limit: limit.trim() ? Number(limit) : null,
      per_customer_limit: Number(perCustomer) || 1,
    };
    try {
      if (coupon)
        await call(() =>
          api.PUT("/api/v1/staff/coupons/{coupon_id}", {
            params: { path: { coupon_id: coupon.id } },
            body,
          }),
        );
      else {
        await call(() => api.POST("/api/v1/staff/coupons", { body }));
        setCode("");
        setDescription("");
        setLimit("");
        setFields(initialFields());
      }
      setMsg({ ok: true, text: "Saved." });
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <section className={ui.panel} aria-label={coupon ? `Edit ${coupon.code}` : "New coupon"}>
      <h2 className={ui.subtitle}>{coupon ? `Edit ${coupon.code}` : "New coupon"}</h2>
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor={`${id}-code`}>Code</label>
          <input
            id={`${id}-code`}
            className={ui.input}
            value={code}
            disabled={!!coupon && coupon.times_used > 0}
            placeholder="e.g. EID15"
            onChange={(e) => setCode(e.target.value.toUpperCase())}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${id}-description`}>Internal note</label>
          <input
            id={`${id}-description`}
            className={ui.input}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${id}-limit`}>Total uses allowed (optional)</label>
          <input
            id={`${id}-limit`}
            className={ui.input}
            inputMode="numeric"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${id}-per`}>Uses per customer</label>
          <input
            id={`${id}-per`}
            className={ui.input}
            inputMode="numeric"
            value={perCustomer}
            onChange={(e) => setPerCustomer(e.target.value)}
          />
        </div>
      </div>
      <DiscountFieldsEditor id={id} value={fields} onChange={setFields} />
      <div className={c.actions}>
        <label className={ui.row}>
          <input
            type="checkbox"
            checked={fields.is_active}
            onChange={(e) => setFields({ ...fields, is_active: e.target.checked })}
          />
          Switched on
        </label>
        <button
          className={ui.button}
          disabled={code.length < 3 || !fields.value}
          onClick={() => void save()}
        >
          {coupon ? "Save coupon" : "Create coupon"}
        </button>
      </div>
      <Message message={msg} />
    </section>
  );
}
