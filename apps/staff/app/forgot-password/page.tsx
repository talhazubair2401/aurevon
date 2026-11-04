"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage } from "../../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await call(() => api.POST("/api/v1/staff/auth/password-reset", { body: { email } }));
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <main className={ui.narrow}>
      <section className={ui.card} aria-labelledby="forgot-title">
        <p className={ui.wordmark}>AUREVON</p>
        <h1 id="forgot-title" className={ui.title}>
          Reset your password
        </h1>
        {sent ? (
          <p className={ui.muted} role="status">
            If that is an active staff account, a reset link is on its way. It works for 30 minutes,
            and you&apos;ll also need your authenticator app. If you&apos;ve lost your authenticator
            too, ask an Owner for an account recovery.
          </p>
        ) : (
          <form className={ui.form} onSubmit={submit}>
            <p className={ui.muted}>You&apos;ll need your authenticator app to finish the reset.</p>
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
            {error && (
              <p className={ui.error} role="alert">
                {error}
              </p>
            )}
            <button className={ui.button}>Send reset link</button>
          </form>
        )}
        <p className={ui.muted}>
          <Link className={ui.link} href="/sign-in">
            Back to sign-in
          </Link>
        </p>
      </section>
    </main>
  );
}
