"use client";

import { useState } from "react";
import { CatalogNav, Message, type Msg } from "../../../components/CatalogNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, type Schemas } from "../../../lib/api";

type Report = Schemas["ImportOut"];

export default function ImportPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Catalogue</h1>
      <CatalogNav />
      <Import />
    </Shell>
  );
}

/** Bulk loading (decision 0006, #10): check the file first, then apply. One bad row and nothing changes. */
function Import() {
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [message, setMessage] = useState<Msg>(null);
  const [busy, setBusy] = useState(false);

  const send = async (apply: boolean) => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await call(() =>
        api.POST("/api/v1/staff/catalog/import", { body: { csv, apply } }),
      );
      setReport(result);
      if (result.applied)
        setMessage({
          ok: true,
          text: "Imported. New products are drafts: publish them when ready.",
        });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="import-title">
      <h2 id="import-title" className={ui.subtitle}>
        Import products from a spreadsheet
      </h2>
      <p className={ui.muted}>
        One row per product, saved from your spreadsheet as CSV UTF-8. Colours and sizes are
        separated by |. A row whose address already exists updates that product; others become
        drafts.
      </p>
      <p>
        <a className={ui.link} href="/api/v1/staff/catalog/import/template" download>
          Download the template
        </a>
      </p>
      <div className={ui.field}>
        <label htmlFor="csv-file">CSV file</label>
        <input
          id="csv-file"
          type="file"
          accept=".csv,text/csv"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            setReport(null);
            setMessage(null);
            if (!file) return;
            if (file.size > 2 * 1024 * 1024) {
              setMessage({
                ok: false,
                text: "The file is larger than 2 MB. Split it into smaller files.",
              });
              return;
            }
            setFileName(file.name);
            setCsv(await file.text());
          }}
        />
      </div>
      <div className={c.actions}>
        <button className={ui.secondary} disabled={!csv || busy} onClick={() => void send(false)}>
          Check {fileName || "file"}
        </button>
        <button
          className={ui.button}
          disabled={!report || report.errors.length > 0 || report.applied || busy}
          onClick={() => void send(true)}
        >
          Import
        </button>
      </div>
      {report && (
        <div role="status">
          <p>
            {report.rows} rows: {report.created.length} new, {report.updated.length} updated
            {report.errors.length ? `, ${report.errors.length} with problems` : ""}.
          </p>
          {report.errors.length > 0 && (
            <table className={ui.table}>
              <thead>
                <tr>
                  <th scope="col">Row</th>
                  <th scope="col">Problem</th>
                </tr>
              </thead>
              <tbody>
                {report.errors.map((e, i) => (
                  <tr key={i}>
                    <td>{e.row}</td>
                    <td>{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      <Message message={message} />
    </section>
  );
}
