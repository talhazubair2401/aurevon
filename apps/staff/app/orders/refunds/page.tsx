"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Message, type Msg } from "../../../components/CatalogNav";
import { money, OrdersNav, REFUND_STATE, StatusTag } from "../../../components/OrdersNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData, type Schemas } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Refund = Schemas["RefundRowOut"];

export default function RefundsPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Orders</h1>
      <OrdersNav />
      <Refunds />
    </Shell>
  );
}

/**
 * Refund approvals (decision 0003, 1.5): the person who asked can't approve; with no threshold set, every refund
 * needs two approvers. Approving asks for the authenticator code again.
 */
function Refunds() {
  const [state, setState] = useState("requested");
  const load = useCallback(
    () =>
      call(() => api.GET("/api/v1/staff/refunds", { params: { query: state ? { state } : {} } })),
    [state],
  );
  const { data, error, reload } = useApiData(load);
  return (
    <>
      <div className={ui.row}>
        <label className={ui.row}>
          Show
          <select className={ui.select} value={state} onChange={(e) => setState(e.target.value)}>
            <option value="requested">Waiting for approval</option>
            <option value="manual_required">Needs manual payment</option>
            <option value="failed">Failed (retrying)</option>
            <option value="succeeded">Refunded</option>
            <option value="rejected">Rejected</option>
            <option value="">All</option>
          </select>
        </label>
      </div>
      {error && <p className={ui.error}>{error}</p>}
      {!data ? (
        <p className={ui.muted}>Loading…</p>
      ) : data.length === 0 ? (
        <p className={ui.muted}>Nothing here.</p>
      ) : (
        data.map((r) => <RefundCard key={r.id} r={r} onDone={reload} />)
      )}
    </>
  );
}

function RefundCard({ r, onDone }: { r: Refund; onDone: () => void }) {
  const { can, state } = useSession();
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const me = state.status === "signed-in" ? state.info.account.email : null;
  const act = async (fn: () => Promise<unknown>, done: string) => {
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: done });
      onDone();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  };
  const path = { params: { path: { refund_id: r.id } } };
  const mine = me === r.requested_by || me === r.approved_by;
  return (
    <section className={ui.panel} aria-label={`Refund for ${r.order}`}>
      <div className={c.panelHead}>
        <h2 className={ui.subtitle}>
          {money(r.amount)} ·{" "}
          <Link href={`/orders/view?number=${r.order}`} className={c.mono}>
            {r.order}
          </Link>
        </h2>
        <StatusTag value={r.state} labels={REFUND_STATE} />
      </div>
      <dl className={c.facts}>
        <dt>Reason</dt>
        <dd>{r.reason}</dd>
        <dt>Requested</dt>
        <dd>
          {r.requested_by} · {formatTime(r.created_at)} ({r.source})
        </dd>
        {r.approved_by && (
          <>
            <dt>Approved by</dt>
            <dd>{[r.approved_by, r.second_approved_by].filter(Boolean).join(", ")}</dd>
          </>
        )}
        {r.last_error && (
          <>
            <dt>Last error</dt>
            <dd>{r.last_error}</dd>
          </>
        )}
        {r.decision_note && (
          <>
            <dt>Note</dt>
            <dd>{r.decision_note}</dd>
          </>
        )}
      </dl>
      {can("refunds.approve") && r.state === "requested" && (
        <div className={c.actions}>
          <button
            className={ui.button}
            disabled={mine}
            title={mine ? "Someone else needs to approve this refund." : undefined}
            onClick={() =>
              void act(
                () => call(() => api.POST("/api/v1/staff/refunds/{refund_id}/approve", path)),
                "Approved.",
              )
            }
          >
            Approve
          </button>
          <input
            className={ui.input}
            aria-label="Reason for rejecting"
            placeholder="Reason for rejecting"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            className={ui.secondary}
            disabled={!note.trim()}
            onClick={() =>
              void act(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/refunds/{refund_id}/reject", {
                      ...path,
                      body: { note } as never,
                    }),
                  ),
                "Rejected.",
              )
            }
          >
            Reject
          </button>
          {mine && <span className={ui.muted}>You asked for or already approved this one.</span>}
        </div>
      )}
      {can("refunds.approve") && r.state === "manual_required" && (
        <div className={c.actions}>
          <input
            className={ui.input}
            aria-label="Bank transfer reference"
            placeholder="Bank transfer reference"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            className={ui.button}
            disabled={!note.trim()}
            onClick={() =>
              void act(
                () =>
                  call(() =>
                    api.POST("/api/v1/staff/refunds/{refund_id}/manual", {
                      ...path,
                      body: { reference: note } as never,
                    }),
                  ),
                "Recorded as paid manually.",
              )
            }
          >
            Record manual payment
          </button>
        </div>
      )}
      <Message message={msg} />
    </section>
  );
}
