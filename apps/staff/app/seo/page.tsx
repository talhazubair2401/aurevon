"use client";

import { useState } from "react";
import {
  asCopy,
  BilingualFields,
  SeoNav,
  storefrontUrl,
  type Copy,
} from "../../components/ContentEditor";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../lib/api";

type Seo = Schemas["SeoOut"];

export default function SeoPage() {
  return (
    <Shell>
      <h1 className={ui.title}>SEO</h1>
      <SeoNav />
      <SeoList />
    </Shell>
  );
}

const loadSeo = () => call(() => api.GET("/api/v1/staff/seo"));

function SeoList() {
  const { data: rows, error } = useApiData(loadSeo);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!rows) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p className={ui.muted}>
        What search engines show for these pages. Empty fields use the page&apos;s own name and
        description. Content pages have their own search fields in Content › Pages.
      </p>
      {rows.map((row) => (
        <SeoEditor key={row.key} row={row} />
      ))}
    </>
  );
}

function SeoEditor({ row }: { row: Seo }) {
  const [value, setValue] = useState<Copy>(asCopy(row.content));
  const [noindex, setNoindex] = useState(row.noindex);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const save = async () => {
    setMessage(null);
    try {
      await call(() =>
        api.PUT("/api/v1/staff/seo/{key}", {
          params: { path: { key: row.key } },
          body: { content: value, noindex },
        }),
      );
      setDirty(false);
      setMessage({ ok: true, text: "Saved. Search engines see it on their next visit." });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };
  const idPrefix = row.key.replace(/[^a-z0-9-]/g, "-");

  return (
    <section className={ui.panel} aria-labelledby={`seo-${idPrefix}`}>
      <div className={c.panelHead}>
        <h2 id={`seo-${idPrefix}`} className={ui.subtitle}>
          {row.label}
        </h2>
        <a
          className={`${ui.link} ${c.mono}`}
          href={storefrontUrl(row.path)}
          target="_blank"
          rel="noreferrer"
        >
          {row.path}
        </a>
      </div>
      <BilingualFields
        fields={row.fields}
        value={value}
        idPrefix={idPrefix}
        onChange={(next) => {
          setValue(next);
          setDirty(true);
        }}
      />
      <div className={c.actions}>
        <label className={ui.row}>
          <input
            type="checkbox"
            checked={noindex}
            onChange={(e) => {
              setNoindex(e.target.checked);
              setDirty(true);
            }}
          />
          Hide from search engines
        </label>
        <button className={ui.button} disabled={!dirty} onClick={() => void save()}>
          Save
        </button>
      </div>
      {message && (
        <p className={message.ok ? ui.success : ui.error} role="status">
          {message.text}
        </p>
      )}
    </section>
  );
}
