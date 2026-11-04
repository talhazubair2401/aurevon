"use client";

import { useState } from "react";
import { ContentNav } from "../../../components/ContentEditor";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Menu = Schemas["MenuOut"];
interface Row {
  en: string;
  ur: string;
  href: string;
}

export default function NavigationPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Content</h1>
      <ContentNav />
      <Menus />
    </Shell>
  );
}

const loadMenus = () => call(() => api.GET("/api/v1/staff/cms/navigation"));

function Menus() {
  const { can } = useSession();
  const { data: menus, error } = useApiData(loadMenus);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!menus) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p className={ui.muted}>
        The links in the store&apos;s header and footer. Saving a menu changes the store at once.
      </p>
      {menus.map((menu) => (
        <MenuEditor key={menu.menu} menu={menu} canPublish={can("cms.publish")} />
      ))}
    </>
  );
}

function MenuEditor({ menu, canPublish }: { menu: Menu; canPublish: boolean }) {
  const [rows, setRows] = useState<Row[]>(
    menu.items.map((i) => ({ en: i.label.en ?? "", ur: i.label.ur ?? "", href: i.href })),
  );
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const change = (next: Row[]) => {
    setRows(next);
    setDirty(true);
  };
  const move = (index: number, by: number) => {
    const next = [...rows];
    const [item] = next.splice(index, 1);
    next.splice(index + by, 0, item!);
    change(next);
  };
  const save = async () => {
    setMessage(null);
    try {
      const saved = await call(() =>
        api.PUT("/api/v1/staff/cms/navigation/{menu}", {
          params: { path: { menu: menu.menu } },
          body: {
            items: rows.map((r) => ({
              label: { en: r.en, ...(r.ur ? { ur: r.ur } : {}) },
              href: r.href,
            })),
          },
        }),
      );
      setRows(
        saved.items.map((i) => ({ en: i.label.en ?? "", ur: i.label.ur ?? "", href: i.href })),
      );
      setDirty(false);
      setMessage({ ok: true, text: "Menu saved. The store shows it now." });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };
  const id = (index: number, part: string) => `${menu.menu}-${index}-${part}`;

  return (
    <section className={ui.panel} aria-labelledby={`menu-${menu.menu}`}>
      <h2 id={`menu-${menu.menu}`} className={ui.subtitle}>
        {menu.label}
      </h2>
      <div className={c.column}>
        {rows.map((row, index) => (
          <div key={index} className={c.menuRow}>
            <div className={ui.field}>
              <label htmlFor={id(index, "en")}>Label (English)</label>
              <input
                id={id(index, "en")}
                className={ui.input}
                value={row.en}
                maxLength={40}
                disabled={!canPublish}
                onChange={(e) =>
                  change(rows.map((r, i) => (i === index ? { ...r, en: e.target.value } : r)))
                }
              />
            </div>
            <div className={ui.field}>
              <label htmlFor={id(index, "ur")}>Label (Urdu)</label>
              <input
                id={id(index, "ur")}
                className={`${ui.input} ${c.urdu}`}
                value={row.ur}
                maxLength={40}
                lang="ur"
                dir="rtl"
                disabled={!canPublish}
                onChange={(e) =>
                  change(rows.map((r, i) => (i === index ? { ...r, ur: e.target.value } : r)))
                }
              />
            </div>
            <div className={ui.field}>
              <label htmlFor={id(index, "href")}>Link (storefront path)</label>
              <input
                id={id(index, "href")}
                className={`${ui.input} ${c.mono}`}
                value={row.href}
                dir="ltr"
                disabled={!canPublish}
                onChange={(e) =>
                  change(rows.map((r, i) => (i === index ? { ...r, href: e.target.value } : r)))
                }
              />
            </div>
            {canPublish && (
              <div className={c.blockTools}>
                <button
                  type="button"
                  className={c.small}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                  aria-label={`Move ${row.en || "link"} up`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className={c.small}
                  disabled={index === rows.length - 1}
                  onClick={() => move(index, 1)}
                  aria-label={`Move ${row.en || "link"} down`}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className={c.small}
                  onClick={() => change(rows.filter((_, i) => i !== index))}
                >
                  Remove
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      {canPublish && (
        <div className={c.actions}>
          <button
            type="button"
            className={ui.secondary}
            disabled={rows.length >= 12}
            onClick={() => change([...rows, { en: "", ur: "", href: "/" }])}
          >
            Add link
          </button>
          <button type="button" className={ui.button} disabled={!dirty} onClick={() => void save()}>
            Save menu
          </button>
        </div>
      )}
      {!canPublish && <p className={ui.muted}>Someone with publishing rights changes menus.</p>}
      {message && (
        <p className={message.ok ? ui.success : ui.error} role="status">
          {message.text}
        </p>
      )}
    </section>
  );
}
