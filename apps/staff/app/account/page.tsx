"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  AuthenticatorQr,
  CodeField,
  RecoveryCodes,
  type PendingDevice,
} from "../../components/Authenticator";
import { Shell } from "../../components/Shell";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, formatTime, useApiData } from "../../lib/api";
import { useSession } from "../../lib/session";

export default function AccountPage() {
  return (
    <Shell>
      <Account />
    </Shell>
  );
}

function Account() {
  const { state } = useSession();
  if (state.status !== "signed-in") return null;
  const mustReenroll = state.info.session.mfa_reenrollment_required;
  return (
    <>
      <h1 className={ui.title}>My account</h1>
      {mustReenroll ? (
        <div className={ui.bannerUrgent} role="alert">
          You signed in with a recovery code, so your old authenticator no longer works. Set up a
          new one to continue.
        </div>
      ) : (
        <p className={ui.muted}>{state.info.account.email}</p>
      )}
      <NewAuthenticator forced={mustReenroll} />
      {!mustReenroll && (
        <>
          <MySessions />
          <ChangePassword />
          <RecoveryEmail />
          <NewRecoveryCodes />
        </>
      )}
    </>
  );
}

const loadMySessions = () => call(() => api.GET("/api/v1/staff/me/sessions"));

function MySessions() {
  const { data: rows = [], error: loadError, reload } = useApiData(loadMySessions);
  const [error, setError] = useState<string | null>(null);

  const revoke = async (id: string) => {
    try {
      await call(() =>
        api.DELETE("/api/v1/staff/me/sessions/{session_id}", {
          params: { path: { session_id: id } },
        }),
      );
      reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="sessions-title">
      <h2 id="sessions-title" className={ui.subtitle}>
        Where you&apos;re signed in
      </h2>
      {(error ?? loadError) && <p className={ui.error}>{error ?? loadError}</p>}
      <table className={ui.table}>
        <thead>
          <tr>
            <th>Device</th>
            <th className={ui.hideSmall}>Address</th>
            <th>Last active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.user_agent || "Unknown browser"}</td>
              <td className={ui.hideSmall}>{row.ip ?? "—"}</td>
              <td>{formatTime(row.last_seen_at)}</td>
              <td>
                {row.current ? (
                  <span className={ui.tag}>This session</span>
                ) : (
                  <button className={ui.link} onClick={() => void revoke(row.id)}>
                    Sign out
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/me/password", {
          body: { current_password: current, new_password: next },
        }),
      );
      setCurrent("");
      setNext("");
      setMessage({ ok: true, text: "Password changed. Your other sessions were signed out." });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="password-title">
      <h2 id="password-title" className={ui.subtitle}>
        Change password
      </h2>
      <form className={ui.form} onSubmit={submit}>
        <label className={ui.field}>
          Current password
          <input
            className={ui.input}
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
        </label>
        <label className={ui.field}>
          New password (at least 12 characters)
          <input
            className={ui.input}
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
          />
        </label>
        {message && <p className={message.ok ? ui.success : ui.error}>{message.text}</p>}
        <div className={ui.row}>
          <button className={ui.button}>Change password</button>
        </div>
      </form>
    </section>
  );
}

function RecoveryEmail() {
  const [value, setValue] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    call(() => api.GET("/api/v1/staff/me/recovery-email"))
      .then((data) => setValue(data.recovery_email))
      .catch(() => undefined);
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const data = await call(() =>
        api.PUT("/api/v1/staff/me/recovery-email", { body: { recovery_email: value } }),
      );
      setValue(data.recovery_email);
      setMessage({
        ok: true,
        text: data.recovery_email ? "Recovery email saved." : "Recovery email removed.",
      });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="recovery-email-title">
      <h2 id="recovery-email-title" className={ui.subtitle}>
        Recovery email
      </h2>
      <p className={ui.muted}>
        A second address, different from your sign-in email. If anyone starts a recovery of your
        account, notices with a cancellation link go to every registered address.
      </p>
      <form className={ui.form} onSubmit={submit}>
        <input
          className={ui.input}
          type="email"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label="Recovery email"
        />
        {message && <p className={message.ok ? ui.success : ui.error}>{message.text}</p>}
        <div className={ui.row}>
          <button className={ui.secondary}>Save</button>
        </div>
      </form>
    </section>
  );
}

function NewAuthenticator({ forced }: { forced: boolean }) {
  const { refresh } = useSession();
  const [device, setDevice] = useState<PendingDevice | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    setError(null);
    try {
      setDevice(await call(() => api.POST("/api/v1/staff/me/mfa/start")));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const confirm = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const data = await call(() => api.POST("/api/v1/staff/me/mfa/confirm", { body: { code } }));
      setCodes(data.recovery_codes);
      setDevice(null);
    } catch (e) {
      setError(errorMessage(e));
      setCode("");
    }
  };

  if (codes) {
    return (
      <section className={ui.panel}>
        <RecoveryCodes
          codes={codes}
          onDone={() => {
            setCodes(null);
            void refresh();
          }}
        />
      </section>
    );
  }

  return (
    <section className={ui.panel} aria-labelledby="authenticator-title">
      <h2 id="authenticator-title" className={ui.subtitle}>
        Authenticator app
      </h2>
      {device ? (
        <form className={ui.form} onSubmit={confirm}>
          <AuthenticatorQr device={device} />
          <CodeField value={code} onChange={setCode} label="Code from the new authenticator" />
          {error && <p className={ui.error}>{error}</p>}
          <div className={ui.row}>
            <button className={ui.button}>Use this authenticator</button>
          </div>
        </form>
      ) : (
        <>
          <p className={ui.muted}>
            Replacing your authenticator signs out your other sessions and issues new recovery
            codes.
          </p>
          {error && <p className={ui.error}>{error}</p>}
          <button className={forced ? ui.button : ui.secondary} onClick={() => void start()}>
            Set up a new authenticator
          </button>
        </>
      )}
    </section>
  );
}

function NewRecoveryCodes() {
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { refresh } = useSession();
  const generate = async () => {
    setError(null);
    try {
      setCodes((await call(() => api.POST("/api/v1/staff/me/recovery-codes"))).recovery_codes);
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  return (
    <section className={ui.panel} aria-labelledby="codes-title">
      {codes ? (
        <RecoveryCodes
          codes={codes}
          onDone={() => {
            setCodes(null);
            void refresh();
          }}
        />
      ) : (
        <>
          <h2 id="codes-title" className={ui.subtitle}>
            Recovery codes
          </h2>
          <p className={ui.muted}>Generating a new set cancels every earlier code.</p>
          {error && <p className={ui.error}>{error}</p>}
          <button className={ui.secondary} onClick={() => void generate()}>
            Generate new recovery codes
          </button>
        </>
      )}
    </section>
  );
}
