"use client";

import { useCallback, useState, type FormEvent } from "react";
import { Shell } from "../../components/Shell";
import ui from "../../components/ui.module.css";
import {
  api,
  call,
  errorMessage,
  formatTime,
  ROLE_OPTIONS,
  useApiData,
  type Schemas,
} from "../../lib/api";
import { useSession } from "../../lib/session";

type Detail = Schemas["StaffAccountDetailOut"];

export default function TeamPage() {
  return (
    <Shell>
      <Team />
    </Shell>
  );
}

const loadAccounts = () => call(() => api.GET("/api/v1/staff/accounts"));

function Team() {
  const { can } = useSession();
  const { data: rows = [], error, reload } = useApiData(loadAccounts);
  const [selected, setSelected] = useState<string | null>(null);
  const load = async () => reload();

  return (
    <>
      <h1 className={ui.title}>Team</h1>
      {can("staff.invite") && <InviteForm onInvited={load} />}
      <section className={ui.panel} aria-labelledby="team-title">
        <h2 id="team-title" className={ui.subtitle}>
          Staff accounts
        </h2>
        {error && <p className={ui.error}>{error}</p>}
        <table className={ui.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-testid={`staff-row-${row.email}`}>
                <td>
                  {row.full_name || "—"}
                  <br />
                  <span className={ui.headerMeta}>{row.email}</span>
                </td>
                <td>{row.role.name}</td>
                <td>
                  <span className={ui.tag}>{row.status}</span>
                </td>
                <td>
                  <button
                    className={ui.link}
                    onClick={() => setSelected(selected === row.id ? null : row.id)}
                  >
                    {selected === row.id ? "Close" : "Manage"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {selected && <AccountPanel key={selected} id={selected} onChanged={load} />}
    </>
  );
}

function InviteForm({ onInvited }: { onInvited: () => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<string>("support");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/accounts", { body: { email, full_name: fullName, role } }),
      );
      setMessage({ ok: true, text: `Invitation sent to ${email}. The link works for 48 hours.` });
      setEmail("");
      setFullName("");
      await onInvited();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="invite-title">
      <h2 id="invite-title" className={ui.subtitle}>
        Invite a staff member
      </h2>
      <form className={ui.form} onSubmit={submit}>
        <div className={ui.row}>
          <label className={ui.field}>
            Full name
            <input
              className={ui.input}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </label>
          <label className={ui.field}>
            Email
            <input
              className={ui.input}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className={ui.field}>
            Role
            <select className={ui.select} value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {message && <p className={message.ok ? ui.success : ui.error}>{message.text}</p>}
        <div className={ui.row}>
          <button className={ui.button}>Send invitation</button>
        </div>
      </form>
    </section>
  );
}

function AccountPanel({ id, onChanged }: { id: string; onChanged: () => Promise<void> }) {
  const { state, can } = useSession();
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const path = { params: { path: { account_id: id } } };
  const self = state.status === "signed-in" && state.info.account.id === id;

  const fetchDetail = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/accounts/{account_id}", { params: { path: { account_id: id } } }),
      ),
    [id],
  );
  const { data: detail, error: loadError, reload } = useApiData<Detail>(fetchDetail);
  const [role, setRole] = useState<string | null>(null);
  const load = async () => reload();

  const act = async (label: string, run: () => Promise<unknown>) => {
    setMessage(null);
    try {
      await run();
      setMessage({ ok: true, text: label });
      await load();
      await onChanged();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  if (!detail) return loadError ? <p className={ui.error}>{loadError}</p> : null;
  const chosenRole = role ?? detail.role.code;
  const recovery = detail.recovery;

  return (
    <section className={ui.panel} aria-labelledby="account-title" data-testid="account-panel">
      <h2 id="account-title" className={ui.subtitle}>
        {detail.full_name || detail.email}
      </h2>
      <p className={ui.muted}>
        {detail.email} · {detail.role.name} · <span className={ui.tag}>{detail.status}</span>
        <br />
        Last sign-in {formatTime(detail.last_login)} · {detail.active_sessions} active session(s) ·
        authenticator {detail.has_authenticator ? "set up" : "not set up"} ·{" "}
        {detail.recovery_codes_remaining} recovery codes left
        {detail.invited_by ? ` · invited by ${detail.invited_by}` : ""}
      </p>

      {recovery && (
        <div className={ui.bannerUrgent}>
          Recovery{" "}
          {recovery.status === "waiting"
            ? `waiting until ${formatTime(recovery.effective_at)}`
            : "released"}{" "}
          (approved by {recovery.approved_by}).{" "}
          <button
            className={ui.link}
            onClick={() =>
              void act("Recovery cancelled.", () =>
                call(() => api.POST("/api/v1/staff/accounts/{account_id}/recovery/cancel", path)),
              )
            }
          >
            Cancel recovery
          </button>
          {recovery.status === "released" && can("staff.recover") && (
            <>
              {" · "}
              <button
                className={ui.link}
                onClick={() =>
                  void act("A new 30-minute recovery link was sent.", () =>
                    call(() =>
                      api.POST("/api/v1/staff/accounts/{account_id}/recovery/resend", path),
                    ),
                  )
                }
              >
                Send a new recovery link
              </button>
            </>
          )}
        </div>
      )}

      {message && (
        <p className={message.ok ? ui.success : ui.error} role="status">
          {message.text}
        </p>
      )}

      {!self && (
        <div className={ui.form}>
          {can("staff.manage_roles") && (
            <div className={ui.row}>
              <select
                className={ui.select}
                value={chosenRole}
                onChange={(e) => setRole(e.target.value)}
                aria-label="Role"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.name}
                  </option>
                ))}
              </select>
              <button
                className={ui.secondary}
                disabled={chosenRole === detail.role.code}
                onClick={() =>
                  void act("Role changed.", () =>
                    call(() =>
                      api.PUT("/api/v1/staff/accounts/{account_id}/role", {
                        ...path,
                        body: { role: chosenRole },
                      }),
                    ),
                  )
                }
              >
                Change role
              </button>
            </div>
          )}

          {(detail.status === "active" || detail.status === "invited") && can("staff.suspend") && (
            <div className={ui.row}>
              <input
                className={ui.input}
                placeholder="Reason for suspension"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                aria-label="Reason for suspension"
              />
              <button
                className={ui.danger}
                disabled={!reason.trim()}
                onClick={() =>
                  void act("Suspended. All sessions ended.", () =>
                    call(() =>
                      api.POST("/api/v1/staff/accounts/{account_id}/suspend", {
                        ...path,
                        body: { reason },
                      }),
                    ),
                  )
                }
              >
                Suspend
              </button>
            </div>
          )}

          <div className={ui.row}>
            {can("staff.suspend") && detail.active_sessions > 0 && (
              <button
                className={ui.secondary}
                onClick={() =>
                  void act("All sessions ended.", () =>
                    call(() =>
                      api.POST("/api/v1/staff/accounts/{account_id}/sessions/revoke", path),
                    ),
                  )
                }
              >
                End all sessions
              </button>
            )}
            {(detail.status === "suspended" || detail.status === "deactivated") &&
              can("staff.reactivate") && (
                <button
                  className={ui.secondary}
                  onClick={() =>
                    void act("Reactivated.", () =>
                      call(() => api.POST("/api/v1/staff/accounts/{account_id}/reactivate", path)),
                    )
                  }
                >
                  Reactivate
                </button>
              )}
            {detail.status !== "deactivated" && can("staff.deactivate") && (
              <button
                className={ui.secondary}
                onClick={() =>
                  void act("Deactivated.", () =>
                    call(() => api.POST("/api/v1/staff/accounts/{account_id}/deactivate", path)),
                  )
                }
              >
                Deactivate (leaver)
              </button>
            )}
            {detail.status === "invited" && can("staff.invite") && (
              <button
                className={ui.secondary}
                onClick={() =>
                  void act("A new invitation was sent.", () =>
                    call(() => api.POST("/api/v1/staff/accounts/{account_id}/invite", path)),
                  )
                }
              >
                Resend invitation
              </button>
            )}
            {detail.status === "active" && !recovery && can("staff.recover") && (
              <button
                className={ui.secondary}
                onClick={() =>
                  void act(
                    detail.role.code === "owner"
                      ? "Recovery approved. It takes effect in 24 hours; the Owner has been notified and can cancel."
                      : "Recovery approved. A 30-minute recovery link was emailed.",
                    () =>
                      call(() => api.POST("/api/v1/staff/accounts/{account_id}/recovery", path)),
                  )
                }
              >
                Approve account recovery
              </button>
            )}
          </div>
          {can("staff.recover") && !recovery && detail.status === "active" && (
            <p className={ui.muted}>
              Approve recovery only after verifying the person outside this system, by voice or in
              person. Their current password and authenticator stop working
              {detail.role.code === "owner" ? " after a 24-hour wait" : ""}.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
