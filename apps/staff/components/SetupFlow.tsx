"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, call, errorMessage, useHashToken } from "../lib/api";
import { useSession } from "../lib/session";
import { AuthenticatorQr, CodeField, RecoveryCodes, type PendingDevice } from "./Authenticator";
import ui from "./ui.module.css";

/** Invite enrolment and account recovery: set a password and connect a new authenticator app. */
export function SetupFlow({ kind }: { kind: "enroll" | "recovery" }) {
  const router = useRouter();
  const { signedIn } = useSession();
  const { token, checked } = useHashToken();
  const [device, setDevice] = useState<PendingDevice | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!checked || !token) return;
    let current = true;
    call(() =>
      kind === "enroll"
        ? api.POST("/api/v1/staff/auth/enroll/start", { body: { token } })
        : api.POST("/api/v1/staff/auth/recovery/start", { body: { token } }),
    )
      .then((pending) => current && setDevice(pending))
      .catch((e: unknown) => current && setError(errorMessage(e)));
    return () => {
      current = false;
    };
  }, [kind, token, checked]);

  const linkError =
    checked && !token ? "This link is incomplete. Open the link from your email again." : null;
  const shownError = error ?? linkError;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = { token, password, code };
      const result = await call(() =>
        kind === "enroll"
          ? api.POST("/api/v1/staff/auth/enroll/complete", { body })
          : api.POST("/api/v1/staff/auth/recovery/complete", { body }),
      );
      signedIn(result.session);
      setCodes(result.recovery_codes);
    } catch (e) {
      setError(errorMessage(e));
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className={ui.narrow}>
      <section className={`${ui.card} ${ui.wide}`} aria-labelledby="setup-title">
        <p className={ui.wordmark}>AUREVON</p>
        {codes ? (
          <RecoveryCodes codes={codes} onDone={() => router.replace("/")} />
        ) : (
          <>
            <h1 id="setup-title" className={ui.title}>
              {kind === "enroll" ? "Set up your staff account" : "Recover your staff account"}
            </h1>
            {device && (
              <form className={ui.form} onSubmit={submit}>
                <p className={ui.muted}>{device.email}</p>
                <label className={ui.field}>
                  New password (at least 12 characters)
                  <input
                    className={ui.input}
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </label>
                <label className={ui.field}>
                  Repeat the password
                  <input
                    className={ui.input}
                    type="password"
                    autoComplete="new-password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                  />
                </label>
                <AuthenticatorQr device={device} />
                <CodeField
                  value={code}
                  onChange={setCode}
                  label="Code shown in your authenticator app"
                />
                {error && (
                  <p className={ui.error} role="alert">
                    {error}
                  </p>
                )}
                <button className={ui.button} disabled={busy}>
                  Finish set-up
                </button>
              </form>
            )}
            {!device && shownError && (
              <p className={ui.error} role="alert">
                {shownError}
              </p>
            )}
            {!device && !shownError && <p className={ui.muted}>Checking your link…</p>}
          </>
        )}
      </section>
    </main>
  );
}
