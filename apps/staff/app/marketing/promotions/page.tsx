"use client";

import { useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import {
  describe,
  DiscountFieldsEditor,
  fromFields,
  initialFields,
  STATE,
} from "../../../components/DiscountForm";
import { MARKETING_LINKS, SectionNav } from "../../../components/SectionNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData, type Schemas } from "../../../lib/api";

type Promotion = Schemas["PromotionOut"];
const loadPromotions = () => call(() => api.GET("/api/v1/staff/promotions"));

export default function PromotionsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Marketing</h1>
      <SectionNav label="Marketing" links={MARKETING_LINKS} />
      <Promotions />
    </Shell>
  );
}

function Promotions() {
  const { data, error, reload } = useApiData(loadPromotions);
  const [editing, setEditing] = useState<string | null>(null);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p className={ui.muted}>
        An automatic promotion applies by itself between its start and end, with the label shown in
        the bag. When several are live, each bag gets the largest one.
      </p>
      <section className={ui.panel}>
        <h2 className={ui.subtitle}>Automatic promotions</h2>
        {data.length === 0 ? (
          <p className={ui.muted}>No promotions yet.</p>
        ) : (
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Label in the bag</th>
                <th scope="col">Discount</th>
                <th scope="col">Runs</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className={ui.muted}>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>
                    {p.label_en}
                    {p.label_ur && (
                      <>
                        <br />
                        <span lang="ur" dir="rtl">
                          {p.label_ur}
                        </span>
                      </>
                    )}
                  </td>
                  <td>{describe(p)}</td>
                  <td>
                    {p.starts_at ? formatTime(p.starts_at) : "—"} –{" "}
                    {p.ends_at ? formatTime(p.ends_at) : "—"}
                  </td>
                  <td>
                    <span className={ui.tag}>{STATE[p.state] ?? p.state}</span>
                  </td>
                  <td>
                    <button
                      className={ui.link}
                      onClick={() => setEditing(editing === p.id ? null : p.id)}
                    >
                      {editing === p.id ? "Close" : "Edit"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {editing && (
        <PromotionForm
          key={editing}
          promotion={data.find((x) => x.id === editing) ?? null}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      <PromotionForm promotion={null} onSaved={reload} />
    </>
  );
}

function PromotionForm({
  promotion,
  onSaved,
}: {
  promotion: Promotion | null;
  onSaved: () => void;
}) {
  const [name, setName] = useState(promotion?.name ?? "");
  const [labelEn, setLabelEn] = useState(promotion?.label_en ?? "");
  const [labelUr, setLabelUr] = useState(promotion?.label_ur ?? "");
  const [fields, setFields] = useState(initialFields(promotion ?? undefined));
  const [msg, setMsg] = useState<Msg>(null);
  const id = promotion?.id ?? "new-promotion";
  const save = async () => {
    setMsg(null);
    const body = { ...fromFields(fields), name, label_en: labelEn, label_ur: labelUr };
    try {
      if (promotion)
        await call(() =>
          api.PUT("/api/v1/staff/promotions/{promotion_id}", {
            params: { path: { promotion_id: promotion.id } },
            body,
          }),
        );
      else {
        await call(() => api.POST("/api/v1/staff/promotions", { body }));
        setName("");
        setLabelEn("");
        setLabelUr("");
        setFields(initialFields());
      }
      setMsg({ ok: true, text: "Saved." });
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <section
      className={ui.panel}
      aria-label={promotion ? `Edit ${promotion.name}` : "New promotion"}
    >
      <h2 className={ui.subtitle}>{promotion ? `Edit ${promotion.name}` : "New promotion"}</h2>
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor={`${id}-name`}>Name (staff only)</label>
          <input
            id={`${id}-name`}
            className={ui.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${id}-en`}>Label in the bag (English)</label>
          <input
            id={`${id}-en`}
            className={ui.input}
            value={labelEn}
            onChange={(e) => setLabelEn(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={`${id}-ur`}>Label in the bag (Urdu)</label>
          <input
            id={`${id}-ur`}
            className={ui.input}
            lang="ur"
            dir="rtl"
            value={labelUr}
            onChange={(e) => setLabelUr(e.target.value)}
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
          disabled={
            !name.trim() || !labelEn.trim() || !fields.value || !fields.starts_at || !fields.ends_at
          }
          onClick={() => void save()}
        >
          {promotion ? "Save promotion" : "Create promotion"}
        </button>
      </div>
      <Message message={msg} />
    </section>
  );
}
