"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, call, errorMessage, setStepUpHandler } from "../lib/api";
import ui from "./ui.module.css";

/** Asks for the authenticator code again when an action needs a fresh confirmation (decision 0003, 2.5). */
export function StepUpProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const resolver = useRef<((ok: boolean) => void) | null>(null);

  const ask = useCallback(
    () =>
      new Promise<boolean>((resolve) => {
        resolver.current = resolve;
        setCode("");
        setError(null);
        setOpen(true);
      }),
    [],
  );

  useEffect(() => {
    setStepUpHandler(ask);
    return () => setStepUpHandler(null);
  }, [ask]);

  const finish = (ok: boolean) => {
    setOpen(false);
    resolver.current?.(ok);
    resolver.current = null;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await call(() => api.POST("/api/v1/staff/auth/step-up", { body: { code } }));
      finish(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {children}
      {open && (
        <div
          className={ui.dialogBackdrop}
          role="dialog"
          aria-modal="true"
          aria-labelledby="step-up-title"
        >
          <form className={ui.card} onSubmit={submit}>
            <h2 id="step-up-title" className={ui.subtitle}>
              Confirm it&apos;s you
            </h2>
            <p className={ui.muted}>This action needs a fresh code from your authenticator app.</p>
            <div className={ui.form}>
              <label className={ui.field}>
                Authenticator code
                <input
                  className={ui.codeInput}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  autoFocus
                  required
                />
              </label>
              {error && (
                <p className={ui.error} role="alert">
                  {error}
                </p>
              )}
              <div className={ui.row}>
                <button className={ui.button} disabled={busy || code.length !== 6}>
                  Confirm
                </button>
                <button type="button" className={ui.secondary} onClick={() => finish(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
