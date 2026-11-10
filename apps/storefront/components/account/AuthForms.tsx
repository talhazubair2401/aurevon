"use client";

import { useEffect, useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError, api, forgetSession, getSession } from "@/lib/client";
import styles from "./Account.module.css";

const noop = () => () => {};
/** False during server render and hydration: submit buttons wait for it so an early click never posts natively. */
function useHydrated() {
  return useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
}

/** Only same-site paths are honoured as "next" after sign-in (no open redirects). */
function safeNext(raw: string | null) {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/account";
}

function Panel({
  theme,
  kicker,
  title,
  intro,
  children,
}: {
  theme?: "registration";
  kicker: string;
  title: string;
  intro?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div
      className={
        theme === "registration" ? `${styles.authPage} ${styles.registration}` : styles.authPage
      }
    >
      <div className={styles.authPanel}>
        <p className={styles.kicker}>{kicker}</p>
        <h1 className={styles.authTitle}>{title}</h1>
        {intro ? <p className={styles.intro}>{intro}</p> : null}
        {children}
      </div>
    </div>
  );
}

function Input({
  label,
  error,
  ...props
}: { label: string; error?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className={styles.field} data-invalid={error ? "true" : undefined}>
      <span className={styles.fieldLabel}>{label}</span>
      <input {...props} aria-invalid={error ? true : undefined} />
      {error ? <span className={styles.error}>{error}</span> : null}
    </label>
  );
}

export function SignInForm() {
  const t = useTranslations("auth");
  const hydrated = useHydrated();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        body: {
          email: form.get("email"),
          password: form.get("password"),
          remember: form.get("remember") === "on",
        },
      });
      forgetSession();
      await getSession(true);
      router.replace(safeNext(params.get("next")));
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
      setBusy(false);
    }
  }

  return (
    <Panel kicker={t("welcomeBack")} title={t("signInTitle")}>
      <form className={styles.form} onSubmit={submit} method="post">
        <Input label={t("email")} name="email" type="email" autoComplete="email" required />
        <Input
          label={t("password")}
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <div className={styles.row}>
          <label className={styles.check}>
            <input type="checkbox" name="remember" /> {t("remember")}
          </label>
          <Link href="/account/forgot-password" className={styles.link}>
            {t("forgot")}
          </Link>
        </div>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        <button className={styles.primary} disabled={busy || !hydrated} data-testid="sign-in">
          {busy ? t("signingIn") : t("signIn")}
        </button>
      </form>
      <p className={styles.switch}>
        {t("newHere")}{" "}
        <Link href="/account/register" className={styles.link}>
          {t("createAccount")}
        </Link>
      </p>
    </Panel>
  );
}

export function RegisterForm() {
  const t = useTranslations("auth");
  const hydrated = useHydrated();
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api("/auth/register", {
        method: "POST",
        body: {
          full_name: form.get("full_name"),
          email: form.get("email"),
          password: form.get("password"),
        },
      });
      setSent(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  if (sent)
    return (
      <Panel
        theme="registration"
        kicker={t("almostThere")}
        title={t("checkEmail")}
        intro={t("checkEmailBody")}
      >
        <Link href="/account/sign-in" className={styles.primaryLink}>
          {t("signIn")}
        </Link>
      </Panel>
    );

  return (
    <Panel
      theme="registration"
      kicker={t("joinKicker")}
      title={t("registerTitle")}
      intro={t("registerIntro")}
    >
      <form className={styles.form} onSubmit={submit} method="post">
        <Input
          label={t("fullName")}
          name="full_name"
          autoComplete="name"
          required
          maxLength={150}
        />
        <Input label={t("email")} name="email" type="email" autoComplete="email" required />
        <Input
          label={t("password")}
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
        />
        <p className={styles.hint}>{t("passwordHint")}</p>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        <button className={styles.primary} disabled={busy || !hydrated} data-testid="register">
          {busy ? t("creating") : t("createAccount")}
        </button>
      </form>
      <p className={styles.switch}>
        {t("haveAccount")}{" "}
        <Link href="/account/sign-in" className={styles.link}>
          {t("signIn")}
        </Link>
      </p>
    </Panel>
  );
}

/** Links in emails carry the token in the URL fragment, which never reaches any server log. */
function useHashToken() {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (value) history.replaceState(null, "", window.location.pathname);
    // Read once after hydration (the server never sees the fragment).
    void Promise.resolve().then(() => setToken(value ?? ""));
  }, []);
  return token;
}

export function VerifyEmail() {
  const t = useTranslations("auth");
  const token = useHashToken();
  const [result, setState] = useState<"working" | "done" | "failed">("working");
  const state = token === "" ? "failed" : result;
  useEffect(() => {
    if (!token) return;
    api("/auth/verify", { method: "POST", body: { token } }).then(
      () => setState("done"),
      () => setState("failed"),
    );
  }, [token]);
  return (
    <Panel
      theme="registration"
      kicker={t("verifyKicker")}
      title={
        state === "done" ? t("verified") : state === "failed" ? t("verifyFailed") : t("verifying")
      }
      intro={
        state === "done"
          ? t("verifiedBody")
          : state === "failed"
            ? t("verifyFailedBody")
            : undefined
      }
    >
      {state !== "working" ? (
        <Link href="/account/sign-in" className={styles.primaryLink}>
          {t("signIn")}
        </Link>
      ) : null}
    </Panel>
  );
}

export function ForgotPassword() {
  const t = useTranslations("auth");
  const hydrated = useHydrated();
  const [sent, setSent] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = new FormData(event.currentTarget).get("email");
    await api("/auth/password-reset", { method: "POST", body: { email } }).catch(() => undefined);
    setSent(true);
  }
  return (
    <Panel
      kicker={t("account")}
      title={t("forgotTitle")}
      intro={sent ? t("resetSent") : t("forgotIntro")}
    >
      {sent ? null : (
        <form className={styles.form} onSubmit={submit} method="post">
          <Input label={t("email")} name="email" type="email" autoComplete="email" required />
          <button className={styles.primary} disabled={!hydrated}>
            {t("sendLink")}
          </button>
        </form>
      )}
      <p className={styles.switch}>
        <Link href="/account/sign-in" className={styles.link}>
          {t("backToSignIn")}
        </Link>
      </p>
    </Panel>
  );
}

export function ResetPassword() {
  const t = useTranslations("auth");
  const hydrated = useHydrated();
  const token = useHashToken();
  const [state, setState] = useState<"form" | "done">("form");
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const password = new FormData(event.currentTarget).get("password");
    try {
      await api("/auth/password-reset/confirm", { method: "POST", body: { token, password } });
      setState("done");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    }
  }
  return (
    <Panel kicker={t("account")} title={state === "done" ? t("passwordChanged") : t("resetTitle")}>
      {state === "done" ? (
        <Link href="/account/sign-in" className={styles.primaryLink}>
          {t("signIn")}
        </Link>
      ) : token === "" ? (
        <p className={styles.error}>{t("linkInvalid")}</p>
      ) : (
        <form className={styles.form} onSubmit={submit} method="post">
          <Input
            label={t("newPassword")}
            name="password"
            type="password"
            autoComplete="new-password"
            required
          />
          <p className={styles.hint}>{t("passwordHint")}</p>
          {error ? <p className={styles.error}>{error}</p> : null}
          <button className={styles.primary} disabled={!hydrated}>
            {t("savePassword")}
          </button>
        </form>
      )}
    </Panel>
  );
}
