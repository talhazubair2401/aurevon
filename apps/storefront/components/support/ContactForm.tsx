"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ApiError, api, getSession } from "@/lib/client";
import styles from "@/components/account/Account.module.css";

const CATEGORIES = ["order", "delivery", "return", "payment", "product", "other"] as const;

/** The contact form (M12): opens a support ticket; the reply comes by email with a private link. */
export function ContactForm() {
  const t = useTranslations("support");
  const locale = useLocale();
  const [defaults, setDefaults] = useState({ name: "", email: "" });
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSession().then((s) => {
      if (s) setDefaults({ name: s.account.full_name ?? "", email: s.account.email });
    });
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(event.currentTarget);
    try {
      const r = await api<{ number: string }>("/contact", {
        method: "POST",
        body: {
          name: f.get("name"),
          email: f.get("email"),
          phone: f.get("phone"),
          category: f.get("category"),
          subject: f.get("subject"),
          message: f.get("message"),
          order_number: String(f.get("order_number") ?? "")
            .trim()
            .toUpperCase(),
          website: f.get("website"),
          locale,
        },
      });
      setSent(r.number);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  if (sent)
    return (
      <div className={styles.notice} role="status" data-testid="contact-sent">
        {t("sent", { number: sent })}
      </div>
    );

  return (
    <form
      className={styles.form}
      onSubmit={submit}
      aria-labelledby="contact-title"
      key={defaults.email}
    >
      <h2 className={styles.panelTitle} id="contact-title">
        {t("title")}
      </h2>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("name")}</span>
        <input
          name="name"
          required
          maxLength={120}
          autoComplete="name"
          defaultValue={defaults.name}
        />
      </label>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("email")}</span>
        <input
          name="email"
          type="email"
          required
          autoComplete="email"
          dir="ltr"
          defaultValue={defaults.email}
        />
      </label>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("phone")}</span>
        <input name="phone" type="tel" autoComplete="tel" dir="ltr" />
      </label>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("category")}</span>
        <select name="category" required defaultValue="">
          <option value="" disabled>
            {t("choose")}
          </option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`categories.${c}`)}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("order")}</span>
        <input name="order_number" dir="ltr" placeholder="AV100001" pattern="[Aa][Vv][0-9]{6,}" />
      </label>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("subject")}</span>
        <input name="subject" required maxLength={150} />
      </label>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>{t("message")}</span>
        <textarea name="message" required minLength={10} maxLength={4000} rows={6} />
      </label>
      {/* Hidden from people; bots that fill every field are quietly ignored. */}
      <div aria-hidden="true" style={{ position: "absolute", insetInlineStart: "-10000px" }}>
        <label>
          Website
          <input name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>
      <p className={styles.muted}>{t("privacy")}</p>
      <button className={styles.primary} disabled={busy}>
        {busy ? t("sending") : t("send")}
      </button>
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}
