"use client";

import { useState } from "react";
import { SeoNav, storefrontUrl } from "../../../components/ContentEditor";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../../lib/api";

export default function RedirectsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>SEO</h1>
      <SeoNav />
      <Redirects />
    </Shell>
  );
}

const loadRedirects = () => call(() => api.GET("/api/v1/staff/redirects"));

function Redirects() {
  const { data: rows, error, reload } = useApiData(loadRedirects);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [permanent, setPermanent] = useState(true);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const add = async () => {
    setMessage(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/redirects", {
          body: { from_path: from, to_path: to, is_permanent: permanent },
        }),
      );
      setFrom("");
      setTo("");
      setMessage({ ok: true, text: "Redirect added." });
      reload();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };
  const remove = async (id: string) => {
    setMessage(null);
    try {
      await call(() =>
        api.DELETE("/api/v1/staff/redirects/{redirect_id}", {
          params: { path: { redirect_id: id } },
        }),
      );
      reload();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <>
      <p className={ui.muted}>
        Send an old address to a new one, in both languages. Renaming a live page adds one
        automatically. Redirects apply only to addresses that no longer have a page.
      </p>
      <section className={ui.panel} aria-labelledby="add-redirect">
        <h2 id="add-redirect" className={ui.subtitle}>
          Add a redirect
        </h2>
        <div className={c.shared}>
          <div className={ui.field}>
            <label htmlFor="redirect-from">From (old path)</label>
            <input
              id="redirect-from"
              className={`${ui.input} ${c.mono}`}
              value={from}
              placeholder="/pages/old-name"
              dir="ltr"
              onChange={(e) => setFrom(e.target.value)}
            />
          </div>
          <div className={ui.field}>
            <label htmlFor="redirect-to">To (storefront path)</label>
            <input
              id="redirect-to"
              className={`${ui.input} ${c.mono}`}
              value={to}
              placeholder="/collections/heritage-edit"
              dir="ltr"
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
        </div>
        <div className={c.actions}>
          <label className={ui.row}>
            <input
              type="checkbox"
              checked={permanent}
              onChange={(e) => setPermanent(e.target.checked)}
            />
            Permanent (the old address is gone for good)
          </label>
          <button className={ui.button} disabled={!from || !to} onClick={() => void add()}>
            Add redirect
          </button>
        </div>
        {message && (
          <p className={message.ok ? ui.success : ui.error} role="status">
            {message.text}
          </p>
        )}
      </section>
      {error && <p className={ui.error}>{error}</p>}
      {rows && rows.length === 0 && <p className={ui.muted}>No redirects yet.</p>}
      {rows && rows.length > 0 && (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">From</th>
              <th scope="col">To</th>
              <th scope="col">Type</th>
              <th scope="col">Added</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className={c.mono}>{r.from_path}</td>
                <td className={c.mono}>
                  <a
                    className={ui.link}
                    href={storefrontUrl(r.to_path)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {r.to_path}
                  </a>
                </td>
                <td>
                  {r.is_permanent ? "Permanent" : "Temporary"}
                  {r.source === "slug_change" ? " · page renamed" : ""}
                </td>
                <td>{formatTime(r.created_at)}</td>
                <td>
                  <button
                    className={ui.link}
                    onClick={() => void remove(r.id)}
                    aria-label={`Remove redirect from ${r.from_path}`}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
