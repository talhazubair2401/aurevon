"use client";

import { useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import { SectionNav, SETTINGS_LINKS } from "../../../components/SectionNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData } from "../../../lib/api";

const loadRules = () => call(() => api.GET("/api/v1/staff/tax-rules"));

export default function TaxPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Settings</h1>
      <SectionNav label="Settings" links={SETTINGS_LINKS} />
      <Tax />
    </Shell>
  );
}

function Tax() {
  const { data, error, reload } = useApiData(loadRules);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p className={ui.banner}>
        The tax treatment is still to be confirmed with your accountant (decision P-11). Until a
        rule is in force, checkout charges no tax. Rules can&apos;t be edited or deleted because
        orders were taxed with them; end a rule on a date and add the next one.
      </p>
      <section className={ui.panel}>
        <h2 className={ui.subtitle}>Rules</h2>
        {data.rules.length === 0 ? (
          <p className={ui.muted}>No tax rules. Checkout charges no tax.</p>
        ) : (
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Rate</th>
                <th scope="col">Prices</th>
                <th scope="col">Delivery fee</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col">
                  <span className={ui.muted}>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rules.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.name} {r.in_force && <span className={ui.tag}>In force today</span>}
                  </td>
                  <td>{Number(r.rate_percent)}%</td>
                  <td>{r.prices_include_tax ? "Include tax" : "Tax added at checkout"}</td>
                  <td>{r.applies_to_shipping ? "Taxed" : "Not taxed"}</td>
                  <td>{r.effective_from}</td>
                  <td>{r.effective_to ?? "Open-ended"}</td>
                  <td>
                    <EndRule id={r.id} onSaved={reload} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <NewRule onSaved={reload} />
    </>
  );
}

function EndRule({ id, onSaved }: { id: string; onSaved: () => void }) {
  const [date, setDate] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const end = async () => {
    setMsg(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/tax-rules/{rule_id}/end", {
          params: { path: { rule_id: id } },
          body: { effective_to: date },
        }),
      );
      setDate("");
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <div className={ui.row}>
      <input
        type="date"
        className={ui.input}
        aria-label="Last day of this rule"
        value={date}
        onChange={(e) => setDate(e.target.value)}
      />
      <button className={ui.secondary} disabled={!date} onClick={() => void end()}>
        End on this date
      </button>
      <Message message={msg} />
    </div>
  );
}

function NewRule({ onSaved }: { onSaved: () => void }) {
  const [name, setName] = useState("");
  const [rate, setRate] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [inclusive, setInclusive] = useState(true);
  const [shipping, setShipping] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const save = async () => {
    setMsg(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/tax-rules", {
          body: {
            name,
            rate_percent: rate,
            prices_include_tax: inclusive,
            applies_to_shipping: shipping,
            effective_from: from,
            effective_to: to || null,
          },
        }),
      );
      setName("");
      setRate("");
      setFrom("");
      setTo("");
      setMsg({ ok: true, text: "Rule added." });
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <section className={ui.panel} aria-label="New tax rule">
      <h2 className={ui.subtitle}>Add a rule</h2>
      <p className={ui.muted}>Saving asks for your authenticator code again.</p>
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor="tax-name">Name shown on receipts</label>
          <input
            id="tax-name"
            className={ui.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor="tax-rate">Rate (%)</label>
          <input
            id="tax-rate"
            className={ui.input}
            inputMode="decimal"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor="tax-from">First day</label>
          <input
            id="tax-from"
            type="date"
            className={ui.input}
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor="tax-to">Last day (optional)</label>
          <input
            id="tax-to"
            type="date"
            className={ui.input}
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
      </div>
      <div className={c.actions}>
        <label className={ui.row}>
          <input
            type="checkbox"
            checked={inclusive}
            onChange={(e) => setInclusive(e.target.checked)}
          />
          Shop prices already include this tax
        </label>
        <label className={ui.row}>
          <input
            type="checkbox"
            checked={shipping}
            onChange={(e) => setShipping(e.target.checked)}
          />
          Also tax the delivery fee
        </label>
        <button
          className={ui.button}
          disabled={!name.trim() || !rate || !from}
          onClick={() => void save()}
        >
          Add rule
        </button>
      </div>
      <Message message={msg} />
    </section>
  );
}
