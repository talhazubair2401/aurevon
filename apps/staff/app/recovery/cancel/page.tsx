"use client";

import { useState } from "react";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useHashToken } from "../../../lib/api";

/** The immediate cancellation link from an Owner-recovery notice (decision 0003, clarification 3). No sign-in. */
export default function CancelRecoveryPage() {
  const { token } = useHashToken();
  const [state, setState] = useState<"ready" | "busy" | "done">("ready");
  const [error, setError] = useState<string | null>(null);

  const cancel = async () => {
    setState("busy");
    setError(null);
    try {
      await call(() => api.POST("/api/v1/staff/auth/recovery/cancel", { body: { token } }));
      setState("done");
    } catch (e) {
      setError(errorMessage(e));
      setState("ready");
    }
  };

  return (
    <main className={ui.narrow}>
      <section className={ui.card} aria-labelledby="cancel-title">
        <p className={ui.wordmark}>AUREVON</p>
        <h1 id="cancel-title" className={ui.title}>
          Cancel account recovery
        </h1>
        {state === "done" ? (
          <p className={ui.success} role="status">
            The recovery is cancelled. Nothing on your account has changed, and every Owner has been
            told.
          </p>
        ) : (
          <>
            <p className={ui.muted}>
              Someone started recovery of your Owner account. If you didn&apos;t ask for it, cancel
              it now. This takes effect immediately.
            </p>
            {error && (
              <p className={ui.error} role="alert">
                {error}
              </p>
            )}
            <button
              className={ui.danger}
              onClick={() => void cancel()}
              disabled={!token || state === "busy"}
            >
              Cancel the recovery
            </button>
          </>
        )}
      </section>
    </main>
  );
}
