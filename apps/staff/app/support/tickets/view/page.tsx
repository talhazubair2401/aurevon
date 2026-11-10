"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { Message, type Msg } from "../../../../components/CatalogNav";
import { SectionNav, SUPPORT_LINKS } from "../../../../components/SectionNav";
import { Shell } from "../../../../components/Shell";
import { TICKET_CATEGORY, TICKET_STATUS } from "../../../../components/SupportNav";
import c from "../../../../components/content.module.css";
import ui from "../../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../../../lib/api";
import { useSession } from "../../../../lib/session";

export default function TicketPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Support</h1>
      <SectionNav label="Support" links={SUPPORT_LINKS} />
      <Suspense>
        <Ticket />
      </Suspense>
    </Shell>
  );
}

function Ticket() {
  const id = useSearchParams().get("id") ?? "";
  const { can } = useSession();
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/tickets/{ticket_id}", { params: { path: { ticket_id: id } } }),
      ),
    [id],
  );
  const { data: t, error, reload } = useApiData(load);
  const [body, setBody] = useState("");
  const [kind, setKind] = useState<"staff" | "note">("staff");
  const [close, setClose] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!t) return <p className={ui.muted}>Loading…</p>;
  const handle = can("tickets.handle");

  const send = async () => {
    setMsg(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/tickets/{ticket_id}/messages", {
          params: { path: { ticket_id: id } },
          body: { kind, body, close: kind === "staff" && close },
        }),
      );
      setBody("");
      setClose(false);
      setMsg({
        ok: true,
        text: kind === "staff" ? "Reply emailed to the customer." : "Note added.",
      });
      reload();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  const update = async (patch: {
    status?: "open" | "waiting" | "closed";
    assign?: "me" | "nobody";
  }) => {
    setMsg(null);
    try {
      await call(() =>
        api.PATCH("/api/v1/staff/tickets/{ticket_id}", {
          params: { path: { ticket_id: id } },
          body: patch,
        }),
      );
      reload();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <>
      <section className={ui.panel} aria-label="Message details">
        <div className={c.panelHead}>
          <h2 className={ui.subtitle}>
            <span className={c.mono}>{t.number}</span> · {t.subject}
          </h2>
          <span className={ui.tag}>{TICKET_STATUS[t.status] ?? t.status}</span>
        </div>
        <dl className={c.facts}>
          <dt>From</dt>
          <dd>
            {t.name} · {t.email}
            {t.phone && ` · ${t.phone}`}
            {t.has_account && <span className={ui.muted}> (has an account)</span>}
          </dd>
          <dt>About</dt>
          <dd>{TICKET_CATEGORY[t.category] ?? t.category}</dd>
          {t.order_number && (
            <>
              <dt>Order</dt>
              <dd>
                {can("orders.view") ? (
                  <Link href={`/orders/view?number=${t.order_number}`} className={c.mono}>
                    {t.order_number}
                  </Link>
                ) : (
                  t.order_number
                )}
              </dd>
            </>
          )}
          <dt>Language</dt>
          <dd>{t.locale === "ur" ? "Urdu" : "English"}</dd>
          <dt>Assigned</dt>
          <dd>{t.assigned_to ?? "Nobody yet"}</dd>
        </dl>
        {handle && (
          <div className={c.actions}>
            {t.assigned_to_me ? (
              <button className={ui.secondary} onClick={() => void update({ assign: "nobody" })}>
                Unassign me
              </button>
            ) : (
              <button className={ui.secondary} onClick={() => void update({ assign: "me" })}>
                Assign to me
              </button>
            )}
            {t.status === "closed" ? (
              <button className={ui.secondary} onClick={() => void update({ status: "open" })}>
                Reopen
              </button>
            ) : (
              <button className={ui.secondary} onClick={() => void update({ status: "closed" })}>
                Close without replying
              </button>
            )}
          </div>
        )}
      </section>
      <section className={ui.panel} aria-label="Conversation">
        <h2 className={ui.subtitle}>Conversation</h2>
        <ol className={c.thread}>
          {t.messages.map((m) => (
            <li key={m.id} className={m.kind === "note" ? c.note : undefined}>
              <p className={ui.muted}>
                {m.kind === "customer" ? t.name : m.author}
                {m.kind === "note"
                  ? " · internal note"
                  : m.kind === "staff"
                    ? " · reply"
                    : ""} · {formatTime(m.created_at)}
              </p>
              {m.body}
            </li>
          ))}
        </ol>
        {handle && (
          <>
            <fieldset className={ui.row}>
              <legend>Write</legend>
              <label className={ui.row}>
                <input type="radio" checked={kind === "staff"} onChange={() => setKind("staff")} />
                Reply to the customer (emailed)
              </label>
              <label className={ui.row}>
                <input type="radio" checked={kind === "note"} onChange={() => setKind("note")} />
                Internal note (staff only)
              </label>
            </fieldset>
            <div className={ui.field}>
              <label htmlFor="ticket-body">{kind === "staff" ? "Reply" : "Note"}</label>
              <textarea
                id="ticket-body"
                className={ui.input}
                rows={6}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </div>
            <div className={c.actions}>
              {kind === "staff" && (
                <label className={ui.row}>
                  <input
                    type="checkbox"
                    checked={close}
                    onChange={(e) => setClose(e.target.checked)}
                  />
                  Mark as resolved
                </label>
              )}
              <button className={ui.button} disabled={!body.trim()} onClick={() => void send()}>
                {kind === "staff" ? "Send reply" : "Add note"}
              </button>
            </div>
          </>
        )}
        <Message message={msg} />
      </section>
    </>
  );
}
