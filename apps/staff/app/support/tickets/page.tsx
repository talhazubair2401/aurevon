"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { SectionNav, SUPPORT_LINKS } from "../../../components/SectionNav";
import { Shell } from "../../../components/Shell";
import { TICKET_CATEGORY, TICKET_STATUS } from "../../../components/SupportNav";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, formatTime, useApiData } from "../../../lib/api";

export default function TicketsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Support</h1>
      <SectionNav label="Support" links={SUPPORT_LINKS} />
      <Suspense>
        <Tickets />
      </Suspense>
    </Shell>
  );
}

function Tickets() {
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "open");
  const [mine, setMine] = useState(params.get("mine") === "1");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/tickets", {
          params: {
            query: {
              ...(status ? { status } : {}),
              ...(mine ? { mine: true } : {}),
              ...(q ? { q } : {}),
            },
          },
        }),
      ),
    [status, mine, q],
  );
  const { data, error } = useApiData(load);
  return (
    <>
      <div className={c.subnav} aria-label="Messages by status">
        {["open", "waiting", "closed", ""].map((s) => (
          <button
            type="button"
            key={s || "all"}
            className={status === s ? c.subnavActive : c.subnavLink}
            onClick={() => setStatus(s)}
          >
            {s ? TICKET_STATUS[s] : "All"}
            {s && data ? ` (${data.counts[s] ?? 0})` : ""}
          </button>
        ))}
      </div>
      <form
        className={ui.row}
        onSubmit={(e) => {
          e.preventDefault();
          setQ(draft.trim());
        }}
      >
        <input
          className={ui.input}
          aria-label="Search messages by number, name, email, subject or order"
          placeholder="Number, name, email, subject or order"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button className={ui.secondary} type="submit">
          Search
        </button>
        <label className={ui.row}>
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
          Only mine
        </label>
      </form>
      {error && <p className={ui.error}>{error}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.results.length === 0 ? (
        <p className={ui.muted}>No messages here.</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Number</th>
              <th scope="col">Subject</th>
              <th scope="col">From</th>
              <th scope="col">About</th>
              <th scope="col">Assigned</th>
              <th scope="col">Updated</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((t) => (
              <tr key={t.id}>
                <td>
                  <Link href={`/support/tickets/view?id=${t.id}`} className={c.mono}>
                    {t.number}
                  </Link>
                </td>
                <td>
                  {t.subject}
                  {t.order_number && <span className={ui.muted}> · {t.order_number}</span>}
                </td>
                <td>
                  {t.name}
                  <br />
                  <span className={ui.muted}>{t.email}</span>
                </td>
                <td>{TICKET_CATEGORY[t.category] ?? t.category}</td>
                <td>{t.assigned_to ?? "—"}</td>
                <td>{formatTime(t.updated_at)}</td>
                <td>
                  <span className={ui.tag}>{TICKET_STATUS[t.status] ?? t.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
