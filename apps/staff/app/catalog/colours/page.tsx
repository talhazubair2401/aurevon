"use client";

import { useState } from "react";
import { CatalogNav, Message, type Msg } from "../../../components/CatalogNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Colour = Schemas["ColourOut"];
const loadColours = () => call(() => api.GET("/api/v1/staff/catalog/colours"));

export default function ColoursPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Catalogue</h1>
      <CatalogNav />
      <Colours />
    </Shell>
  );
}

function Colours() {
  const { can } = useSession();
  const { data: rows, error, reload } = useApiData(loadColours);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!rows) return <p className={ui.muted}>Loading…</p>;
  const canEdit = can("catalog.edit");
  return (
    <>
      <p className={ui.muted}>
        The colours products can come in. The code is part of SKUs and can&apos;t change.
      </p>
      {rows.map((row) => (
        <ColourRow key={row.slug} colour={row} canEdit={canEdit} onSaved={reload} />
      ))}
      {canEdit && <ColourRow colour={null} canEdit onSaved={reload} />}
    </>
  );
}

function ColourRow({
  colour,
  canEdit,
  onSaved,
}: {
  colour: Colour | null;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [v, setV] = useState({
    slug: colour?.slug ?? "",
    code: colour?.code ?? "",
    name_en: colour?.name_en ?? "",
    name_ur: colour?.name_ur ?? "",
    hex: colour?.hex ?? "#",
  });
  const [message, setMessage] = useState<Msg>(null);
  const id = (f: string) => `${colour?.slug ?? "new"}-${f}`;
  const field = (f: keyof typeof v, label: string, extra: Record<string, unknown> = {}) => (
    <div className={ui.field}>
      <label htmlFor={id(f)}>{label}</label>
      <input
        id={id(f)}
        className={ui.input}
        value={v[f]}
        disabled={!canEdit}
        onChange={(e) => setV({ ...v, [f]: e.target.value })}
        {...extra}
      />
    </div>
  );
  const save = async () => {
    setMessage(null);
    try {
      if (colour)
        await call(() =>
          api.PUT("/api/v1/staff/catalog/colours/{slug}", {
            params: { path: { slug: colour.slug } },
            body: { ...v, in_use: colour.in_use },
          }),
        );
      else
        await call(() =>
          api.POST("/api/v1/staff/catalog/colours", { body: { ...v, in_use: false } }),
        );
      setMessage({ ok: true, text: "Saved." });
      onSaved();
      if (!colour) setV({ slug: "", code: "", name_en: "", name_ur: "", hex: "#" });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };
  return (
    <section className={ui.panel} aria-label={colour ? colour.name_en : "New colour"}>
      <div className={c.menuRow}>
        {colour ? (
          <p className={c.mono}>
            {colour.slug} · {colour.code}
          </p>
        ) : (
          field("slug", "Address", { placeholder: "rust" })
        )}
        {!colour && field("code", "Code (3 letters)", { maxLength: 3, placeholder: "RST" })}
        {field("name_en", "English name")}
        {field("name_ur", "Urdu name", { lang: "ur", dir: "rtl" })}
        {field("hex", "Swatch (#RRGGBB)", { className: `${ui.input} ${c.mono}` })}
        {canEdit && (
          <button className={ui.secondary} onClick={() => void save()}>
            {colour ? "Save" : "Add colour"}
          </button>
        )}
      </div>
      <Message message={message} />
    </section>
  );
}
