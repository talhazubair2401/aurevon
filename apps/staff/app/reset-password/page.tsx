"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { CodeField } from "../../components/Authenticator";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage, useHashToken } from "../../lib/api";

export default function ResetPasswordPage() {
  const { token } = useHashToken();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await call(() =>
        api.POST("/api/v1/staff/auth/password-reset/confirm", { body: { token, password, code } }),
      );
      setDone(true);
    } catch (e) {
      setError(errorMessage(e));
      setCode("");
    }
  };

  return (
    <main className={ui.narrow}>
      <section className={ui.card} aria-labelledby="reset-title">
        <p className={ui.wordmark}>AUREVON</p>
        <h1 id="reset-title" className={ui.title}>
          Choose a new password
        </h1>
        {done ? (
          <p className={ui.success} role="status">
            Your password was changed and every session was signed out.{" "}
            <Link href="/sign-in">Sign in</Link>.
          </p>
        ) : (
          <form className={ui.form} onSubmit={submit}>
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
            <CodeField value={code} onChange={setCode} />
            {error && (
              <p className={ui.error} role="alert">
                {error}
              </p>
            )}
            <button className={ui.button} disabled={!token}>
              Change password
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
