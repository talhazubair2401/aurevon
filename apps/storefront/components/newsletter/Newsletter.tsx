"use client";

import { useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Alert, Button, CheckboxField, TextField } from "@aurevon/ui";
import styles from "./Newsletter.module.css";

type State = "idle" | "sending" | "sent" | "error";

/** Newsletter sign-up: double opt-in through POST /api/v1/newsletter/subscribe (same origin). */
export function Newsletter({
  source,
  headingId = "newsletter-title",
  compact = false,
}: {
  source: string;
  /** Unique per page: the footer carries its own form on pages that also have one in the body. */
  headingId?: string;
  /** Footer form: smaller heading, no section padding. */
  compact?: boolean;
}) {
  const t = useTranslations("newsletter");
  const locale = useLocale();
  const [state, setState] = useState<State>("idle");
  const [errors, setErrors] = useState<{ email?: string; consent?: string }>({});

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const consent = form.get("consent") === "on";
    const next: typeof errors = {};
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = t("invalidEmail");
    if (!consent) next.consent = t("consentRequired");
    setErrors(next);
    if (next.email || next.consent) return;

    setState("sending");
    try {
      const response = await fetch("/api/v1/newsletter/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email, consent, locale, source }),
      });
      setState(response.status === 202 ? "sent" : "error");
    } catch {
      setState("error");
    }
  }

  return (
    <section
      className={compact ? styles.compact : styles.newsletter}
      aria-labelledby={headingId}
      data-newsletter={source}
    >
      <div className={styles.inner}>
        <div className={styles.copy}>
          <h2 id={headingId} className={styles.title}>
            {t("title")}
          </h2>
          <p className={styles.body}>{t("body")}</p>
        </div>
        {state === "sent" ? (
          <Alert tone="success" title={t("sent")} />
        ) : (
          <form className={styles.form} onSubmit={onSubmit} noValidate>
            <div className={styles.row}>
              <TextField
                className={styles.email}
                label={t("email")}
                name="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                error={errors.email}
              />
              <Button type="submit" busy={state === "sending"} className={styles.submit}>
                {state === "sending" ? t("sending") : t("submit")}
              </Button>
            </div>
            <CheckboxField name="consent" label={t("consent")} error={errors.consent} />
            {state === "error" ? <Alert tone="error" title={t("error")} /> : null}
          </form>
        )}
      </div>
    </section>
  );
}
