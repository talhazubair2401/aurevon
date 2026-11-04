"use client";

import { useState } from "react";
import { BlockPanel } from "../../components/BlockPanel";
import { ContentNav, storefrontUrl } from "../../components/ContentEditor";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../lib/api";
import { useSession } from "../../lib/session";

type Section = Schemas["EditableBlockOut"];

export default function HomepageContentPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Content</h1>
      <ContentNav />
      <Homepage />
    </Shell>
  );
}

const loadSections = () => call(() => api.GET("/api/v1/staff/cms/home-sections"));

function Homepage() {
  const { can } = useSession();
  const { data: sections, error, reload } = useApiData(loadSections);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!sections) return <p className={ui.muted}>Loading…</p>;
  const canEdit = can("cms.edit");
  const canPublish = can("cms.publish");

  return (
    <>
      <p className={ui.muted}>
        The homepage shows these sections in this order. Product and collection lists fill
        themselves from the catalogue; here you edit their headings and links.
      </p>
      <Layout
        key={sections.map((s) => `${s.key}:${s.is_enabled}`).join()}
        sections={sections}
        canPublish={canPublish}
        onSaved={reload}
      />
      {sections.map((section) => (
        <BlockPanel
          key={section.key}
          item={section}
          canEdit={canEdit}
          canPublish={canPublish}
          viewHref={storefrontUrl("/")}
          onSaveDraft={(content) =>
            call(() =>
              api.PUT("/api/v1/staff/cms/home-sections/{key}/draft", {
                params: { path: { key: section.key } },
                body: { content },
              }),
            )
          }
          onPublish={() =>
            call(() =>
              api.POST("/api/v1/staff/cms/home-sections/{key}/publish", {
                params: { path: { key: section.key } },
              }),
            )
          }
          onDiscard={() =>
            call(() =>
              api.DELETE("/api/v1/staff/cms/home-sections/{key}/draft", {
                params: { path: { key: section.key } },
              }),
            )
          }
        />
      ))}
    </>
  );
}

function Layout({
  sections,
  canPublish,
  onSaved,
}: {
  sections: Section[];
  canPublish: boolean;
  onSaved: () => void;
}) {
  const [rows, setRows] = useState(
    sections.map((s) => ({ key: s.key, label: s.label, is_enabled: s.is_enabled })),
  );
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const move = (index: number, by: number) => {
    const next = [...rows];
    const [item] = next.splice(index, 1);
    next.splice(index + by, 0, item!);
    setRows(next);
    setDirty(true);
  };
  const save = async () => {
    setMessage(null);
    try {
      await call(() =>
        api.PUT("/api/v1/staff/cms/home-sections/layout", {
          body: { sections: rows.map(({ key, is_enabled }) => ({ key, is_enabled })) },
        }),
      );
      setDirty(false);
      setMessage({ ok: true, text: "Homepage order saved. The store shows it now." });
      onSaved();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="layout-title">
      <h2 id="layout-title" className={ui.subtitle}>
        Order and visibility
      </h2>
      <ol className={c.layoutList}>
        {rows.map((row, index) => (
          <li key={row.key} className={c.layoutRow}>
            <span className={c.layoutName}>
              {index + 1}. {row.label}
            </span>
            <label className={ui.row}>
              <input
                type="checkbox"
                checked={row.is_enabled}
                disabled={!canPublish}
                onChange={(e) => {
                  setRows(
                    rows.map((r) =>
                      r.key === row.key ? { ...r, is_enabled: e.target.checked } : r,
                    ),
                  );
                  setDirty(true);
                }}
              />
              Shown
            </label>
            <button
              type="button"
              className={c.small}
              disabled={!canPublish || index === 0}
              onClick={() => move(index, -1)}
              aria-label={`Move ${row.label} up`}
            >
              ↑
            </button>
            <button
              type="button"
              className={c.small}
              disabled={!canPublish || index === rows.length - 1}
              onClick={() => move(index, 1)}
              aria-label={`Move ${row.label} down`}
            >
              ↓
            </button>
          </li>
        ))}
      </ol>
      {canPublish && (
        <div className={c.actions}>
          <button className={ui.button} disabled={!dirty} onClick={() => void save()}>
            Save order and visibility
          </button>
        </div>
      )}
      {message && (
        <p className={message.ok ? ui.success : ui.error} role="status">
          {message.text}
        </p>
      )}
    </section>
  );
}
