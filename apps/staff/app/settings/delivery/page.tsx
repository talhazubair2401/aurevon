"use client";

import { useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import { money } from "../../../components/OrdersNav";
import { SectionNav, SETTINGS_LINKS } from "../../../components/SectionNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../../lib/api";

type Zone = Schemas["ZoneOut"];
type Rate = Schemas["RateOut"];

const PROVINCES: Record<string, string> = {
  punjab: "Punjab",
  sindh: "Sindh",
  kp: "Khyber Pakhtunkhwa",
  balochistan: "Balochistan",
  ict: "Islamabad Capital Territory",
  gb: "Gilgit-Baltistan",
  ajk: "Azad Jammu and Kashmir",
};
const METHOD: Record<string, string> = { standard: "Standard", express: "Express" };
const loadZones = () => call(() => api.GET("/api/v1/staff/shipping-zones"));

export default function DeliveryPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Settings</h1>
      <SectionNav label="Settings" links={SETTINGS_LINKS} />
      <Zones />
    </Shell>
  );
}

function Zones() {
  const { data, error, reload } = useApiData(loadZones);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p className={ui.muted}>
        Checkout matches an address to a zone by city first, then province, then the catch-all zone.
        Orders keep the fee they were charged, so changes here only affect new orders. The real
        zones, fees and delivery promises are still to be confirmed (decision P-13).
      </p>
      {data.length === 0 && (
        <p className={ui.bannerUrgent}>
          No delivery zones yet: checkout can&apos;t offer delivery until at least one exists.
        </p>
      )}
      {data.map((z) => (
        <ZoneCard key={z.code} zone={z} onSaved={reload} />
      ))}
      <ZoneForm zone={null} onSaved={reload} />
    </>
  );
}

function ZoneCard({ zone, onSaved }: { zone: Zone; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const remove = async () => {
    if (!window.confirm(`Delete the ${zone.name} zone and its rates?`)) return;
    try {
      await call(() =>
        api.DELETE("/api/v1/staff/shipping-zones/{code}", {
          params: { path: { code: zone.code } },
        }),
      );
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  const where = [
    ...zone.cities,
    ...zone.provinces.map((p) => PROVINCES[p] ?? p),
    ...(zone.is_fallback ? ["Everywhere else (catch-all)"] : []),
  ].join(", ");
  return (
    <section className={ui.panel} aria-label={zone.name}>
      <div className={c.panelHead}>
        <h2 className={ui.subtitle}>
          {zone.name} <span className={c.mono}>{zone.code}</span>
        </h2>
        <div className={c.actions}>
          <button className={ui.secondary} onClick={() => setEditing(!editing)}>
            {editing ? "Close" : "Edit zone"}
          </button>
          <button className={ui.danger} onClick={() => void remove()}>
            Delete
          </button>
        </div>
      </div>
      <p className={ui.muted}>{where}</p>
      {editing && (
        <ZoneForm
          zone={zone}
          onSaved={() => {
            setEditing(false);
            onSaved();
          }}
        />
      )}
      {zone.rates.length === 0 ? (
        <p className={ui.error}>No rates: addresses in this zone can&apos;t check out.</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Method</th>
              <th scope="col">Fee</th>
              <th scope="col">Free over</th>
              <th scope="col">Days</th>
              <th scope="col">Cash on delivery</th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className={ui.muted}>Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {zone.rates.map((r) => (
              <RateRow key={r.id} rate={r} onSaved={onSaved} />
            ))}
          </tbody>
        </table>
      )}
      {zone.rates.length < 2 && <RateForm zone={zone.code} rate={null} onSaved={onSaved} />}
      <Message message={msg} />
    </section>
  );
}

function ZoneForm({ zone, onSaved }: { zone: Zone | null; onSaved: () => void }) {
  const [code, setCode] = useState(zone?.code ?? "");
  const [name, setName] = useState(zone?.name ?? "");
  const [cities, setCities] = useState(zone?.cities.join(", ") ?? "");
  const [provinces, setProvinces] = useState<string[]>(zone?.provinces ?? []);
  const [fallback, setFallback] = useState(zone?.is_fallback ?? false);
  const [position, setPosition] = useState(String(zone?.position ?? 0));
  const [msg, setMsg] = useState<Msg>(null);
  const key = zone?.code ?? "new-zone";
  const save = async () => {
    setMsg(null);
    const body = {
      code,
      name,
      cities: cities
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      provinces: provinces as never,
      is_fallback: fallback,
      position: Number(position) || 0,
    };
    try {
      if (zone)
        await call(() =>
          api.PUT("/api/v1/staff/shipping-zones/{code}", {
            params: { path: { code: zone.code } },
            body,
          }),
        );
      else await call(() => api.POST("/api/v1/staff/shipping-zones", { body }));
      if (!zone) {
        setCode("");
        setName("");
        setCities("");
        setProvinces([]);
        setFallback(false);
      }
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  const Wrapper = zone ? "div" : "section";
  return (
    <Wrapper className={zone ? undefined : ui.panel} aria-label={zone ? undefined : "New zone"}>
      {!zone && <h2 className={ui.subtitle}>New delivery zone</h2>}
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor={`${key}-code`}>Code</label>
          <input
            id={`${key}-code`}
            className={ui.input}
            value={code}
            disabled={!!zone}
            placeholder="e.g. karachi"
            onChange={(e) => setCode(e.target.value.toLowerCase())}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${key}-name`}>Name</label>
          <input
            id={`${key}-name`}
            className={ui.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${key}-cities`}>Cities (comma separated)</label>
          <input
            id={`${key}-cities`}
            className={ui.input}
            value={cities}
            onChange={(e) => setCities(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${key}-position`}>Order in lists</label>
          <input
            id={`${key}-position`}
            className={ui.input}
            inputMode="numeric"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>
      </div>
      <fieldset className={ui.row}>
        <legend>Whole provinces</legend>
        {Object.entries(PROVINCES).map(([value, label]) => (
          <label key={value} className={ui.row}>
            <input
              type="checkbox"
              checked={provinces.includes(value)}
              onChange={(e) =>
                setProvinces(
                  e.target.checked ? [...provinces, value] : provinces.filter((p) => p !== value),
                )
              }
            />
            {label}
          </label>
        ))}
      </fieldset>
      <div className={c.actions}>
        <label className={ui.row}>
          <input
            type="checkbox"
            checked={fallback}
            onChange={(e) => setFallback(e.target.checked)}
          />
          Catch-all for every address no other zone matches
        </label>
        <button className={ui.button} disabled={!code || !name.trim()} onClick={() => void save()}>
          {zone ? "Save zone" : "Add zone"}
        </button>
      </div>
      <Message message={msg} />
    </Wrapper>
  );
}

function RateRow({ rate, onSaved }: { rate: Rate; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const remove = async () => {
    if (!window.confirm(`Delete the ${METHOD[rate.method]} rate?`)) return;
    try {
      await call(() =>
        api.DELETE("/api/v1/staff/shipping-rates/{rate_id}", {
          params: { path: { rate_id: rate.id } },
        }),
      );
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  if (editing)
    return (
      <tr>
        <td colSpan={7}>
          <RateForm
            zone={rate.zone}
            rate={rate}
            onSaved={() => {
              setEditing(false);
              onSaved();
            }}
          />
        </td>
      </tr>
    );
  return (
    <tr>
      <td>{METHOD[rate.method] ?? rate.method}</td>
      <td>{money(rate.fee)}</td>
      <td>{rate.free_over ? money(rate.free_over) : "—"}</td>
      <td>
        {rate.days_min === rate.days_max ? rate.days_min : `${rate.days_min}–${rate.days_max}`}
      </td>
      <td>
        {rate.cod_allowed
          ? `Yes${Number(rate.cod_fee) ? `, fee ${money(rate.cod_fee)}` : ""}`
          : "No"}
      </td>
      <td>
        <span className={ui.tag}>{rate.is_active ? "Offered" : "Hidden"}</span>
      </td>
      <td>
        <button className={ui.link} onClick={() => setEditing(true)}>
          Edit
        </button>{" "}
        <button className={ui.link} onClick={() => void remove()}>
          Delete
        </button>
        <Message message={msg} />
      </td>
    </tr>
  );
}

function RateForm({
  zone,
  rate,
  onSaved,
}: {
  zone: string;
  rate: Rate | null;
  onSaved: () => void;
}) {
  const [v, setV] = useState({
    method: rate?.method ?? "standard",
    fee: rate?.fee ?? "",
    free_over: rate?.free_over ?? "",
    days_min: String(rate?.days_min ?? 1),
    days_max: String(rate?.days_max ?? 3),
    cod_fee: rate?.cod_fee ?? "0",
  });
  const [cod, setCod] = useState(rate?.cod_allowed ?? true);
  const [active, setActive] = useState(rate?.is_active ?? true);
  const [msg, setMsg] = useState<Msg>(null);
  const key = rate?.id ?? `new-rate-${zone}`;
  const save = async () => {
    setMsg(null);
    const body = {
      zone,
      method: v.method as Rate["method"] as never,
      fee: v.fee,
      free_over: v.free_over.trim() ? v.free_over.trim() : null,
      days_min: Number(v.days_min),
      days_max: Number(v.days_max),
      cod_allowed: cod,
      cod_fee: cod ? v.cod_fee || "0" : "0",
      is_active: active,
    };
    try {
      if (rate)
        await call(() =>
          api.PUT("/api/v1/staff/shipping-rates/{rate_id}", {
            params: { path: { rate_id: rate.id } },
            body,
          }),
        );
      else await call(() => api.POST("/api/v1/staff/shipping-rates", { body }));
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  const input = (k: keyof typeof v, label: string, mode: "decimal" | "numeric") => (
    <div className={ui.field}>
      <label htmlFor={`${key}-${k}`}>{label}</label>
      <input
        id={`${key}-${k}`}
        className={ui.input}
        inputMode={mode}
        value={v[k]}
        onChange={(e) => setV({ ...v, [k]: e.target.value })}
      />
    </div>
  );
  return (
    <div aria-label={rate ? `Edit ${METHOD[rate.method]} rate` : "New rate"}>
      {!rate && <h3 className={c.small}>Add a rate</h3>}
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor={`${key}-method`}>Method</label>
          <select
            id={`${key}-method`}
            className={ui.select}
            value={v.method}
            disabled={!!rate}
            onChange={(e) => setV({ ...v, method: e.target.value as Rate["method"] })}
          >
            <option value="standard">Standard</option>
            <option value="express">Express</option>
          </select>
        </div>
        {input("fee", "Fee (Rs)", "decimal")}
        {input("free_over", "Free over (Rs, optional)", "decimal")}
        {input("days_min", "Fastest (days)", "numeric")}
        {input("days_max", "Slowest (days)", "numeric")}
        {cod && input("cod_fee", "Cash on delivery fee (Rs)", "decimal")}
      </div>
      <div className={c.actions}>
        <label className={ui.row}>
          <input type="checkbox" checked={cod} onChange={(e) => setCod(e.target.checked)} />
          Cash on delivery allowed
        </label>
        <label className={ui.row}>
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          Offered at checkout
        </label>
        <button className={ui.button} disabled={!v.fee} onClick={() => void save()}>
          {rate ? "Save rate" : "Add rate"}
        </button>
      </div>
      <Message message={msg} />
    </div>
  );
}
