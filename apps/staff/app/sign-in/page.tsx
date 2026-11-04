"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { CodeField } from "../../components/Authenticator";
import ui from "../../components/ui.module.css";
import { api, call, errorMessage } from "../../lib/api";
import { useSession } from "../../lib/session";

export default function SignInPage() {
  const router = useRouter();
  const { state, signedIn } = useSession();
  const [step, setStep] = useState<"password" | "code">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (state.status === "signed-in") router.replace("/");
  }, [state.status, router]);

  const submitPassword = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await call(() =>
        api.POST("/api/v1/staff/auth/login", { body: { email, password } }),
      );
      setChallenge(data.challenge);
      setPassword("");
      setStep("code");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = useRecovery ? { challenge, recovery_code: recoveryCode } : { challenge, code };
      const info = await call(() => api.POST("/api/v1/staff/auth/mfa/verify", { body }));
      signedIn(info);
      router.replace(info.session.mfa_reenrollment_required ? "/account" : "/");
    } catch (e) {
      setError(errorMessage(e));
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className={ui.narrow}>
      <section className={ui.card} aria-labelledby="sign-in-title">
        <p className={ui.wordmark}>AUREVON</p>
        <h1 id="sign-in-title" className={ui.title}>
          Staff sign-in
        </h1>
        {step === "password" ? (
          <form className={ui.form} onSubmit={submitPassword}>
            <label className={ui.field}>
              Email
              <input
                className={ui.input}
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label className={ui.field}>
              Password
              <input
                className={ui.input}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <p className={ui.error} role="alert">
                {error}
              </p>
            )}
            <button className={ui.button} disabled={busy}>
              Continue
            </button>
            <Link className={ui.link} href="/forgot-password">
              Forgot your password?
            </Link>
          </form>
        ) : (
          <form className={ui.form} onSubmit={submitCode}>
            {useRecovery ? (
              <label className={ui.field}>
                Recovery code
                <input
                  className={ui.input}
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value)}
                  autoComplete="off"
                  required
                />
              </label>
            ) : (
              <CodeField value={code} onChange={setCode} />
            )}
            {error && (
              <p className={ui.error} role="alert">
                {error}
              </p>
            )}
            <button className={ui.button} disabled={busy}>
              Sign in
            </button>
            <button type="button" className={ui.link} onClick={() => setUseRecovery(!useRecovery)}>
              {useRecovery
                ? "Use my authenticator app"
                : "Lost your authenticator? Use a recovery code"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
