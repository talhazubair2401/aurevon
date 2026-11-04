"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Shell } from "../../components/Shell";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, formatTime, type Schemas } from "../../lib/api";

type Row = Schemas["AuditLogOut"];

export default function AuditPage() {
  return (
    <Shell>
      <Audit />
    </Shell>
  );
}

function cursorOf(next: string | null | undefined): string | undefined {
  if (!next) return undefined;
  return new URL(next, window.location.origin).searchParams.get("cursor") ?? undefined;
}

function Audit() {
  const [rows, setRows] = useState<Row[]>([]);
  const [next, setNext] = useState<string | undefined>();
  const [action, setAction] = useState("");
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback((filter: string, cursor?: string) => {
    const query: { action?: string; cursor?: string } = {};
    if (filter) query.action = filter;
    if (cursor) query.cursor = cursor;
    return call(() => api.GET("/api/v1/staff/audit-log", { params: { query } }));
  }, []);

  const load = useCallback(
    (filter: string, cursor?: string) => {
      setError(null);
      fetchPage(filter, cursor)
        .then((page) => {
          setRows((previous) => (cursor ? [...previous, ...page.results] : page.results));
          setNext(cursorOf(page.next));
        })
        .catch((e: unknown) => setError(errorMessage(e)));
    },
    [fetchPage],
  );

  useEffect(() => {
    let current = true;
    fetchPage("")
      .then((page) => {
        if (!current) return;
        setRows(page.results);
        setNext(cursorOf(page.next));
      })
      .catch((e: unknown) => current && setError(errorMessage(e)));
    return () => {
      current = false;
    };
  }, [fetchPage]);

  const filter = (event: FormEvent) => {
    event.preventDefault();
    load(action.trim());
  };

  return (
    <>
      <h1 className={ui.title}>Audit log</h1>
      <p className={ui.muted}>
        Append-only: entries can&apos;t be edited or deleted, even by the application.
      </p>
      <form className={ui.row} onSubmit={filter}>
        <input
          className={ui.input}
          placeholder="Action, e.g. staff.suspended"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          aria-label="Filter by action"
        />
        <button className={ui.secondary}>Filter</button>
      </form>
      {error && <p className={ui.error}>{error}</p>}
      <section className={ui.panel}>
        <table className={ui.table}>
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Action</th>
              <th className={ui.hideSmall}>Details</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{formatTime(row.at)}</td>
                <td>{row.actor_label}</td>
                <td>{row.action}</td>
                <td className={ui.hideSmall}>
                  <pre className={ui.pre}>
                    {[
                      row.before ? `before: ${JSON.stringify(row.before)}` : "",
                      row.after ? `after: ${JSON.stringify(row.after)}` : "",
                      row.ip ? `from ${row.ip}` : "",
                    ]
                      .filter(Boolean)
                      .join("\n")}
                  </pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {next && (
          <button className={ui.secondary} onClick={() => load(action.trim(), next)}>
            Load older entries
          </button>
        )}
      </section>
    </>
  );
}
