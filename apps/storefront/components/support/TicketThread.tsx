"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { formatDate, type Locale } from "@aurevon/i18n";
import type { components } from "@aurevon/api-client";
import { ApiError, api } from "@/lib/client";
import styles from "@/components/account/Account.module.css";

type Ticket = components["schemas"]["TicketOut"];

/** A support conversation opened from the private link in our email (#token=...). */
export function TicketThread() {
  const t = useTranslations("support");
  const locale = useLocale() as Locale;
  const [token, setToken] = useState<string | null>(null);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (!value) {
      void Promise.resolve().then(() => setFailed(true));
      return;
    }
    void Promise.resolve().then(() => setToken(value));
    api<Ticket>("/support/ticket", { method: "POST", body: { token: value } }).then(setTicket, () =>
      setFailed(true),
    );
  }, []);

  async function reply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("message") ?? "");
    try {
      setTicket(
        await api<Ticket>("/support/ticket/reply", {
          method: "POST",
          body: { token, message: body },
        }),
      );
      form.reset();
      setMessage(t("replySent"));
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : t("error"));
    }
  }

  if (failed)
    return (
      <div className={styles.orderPage}>
        <h1 className={styles.dashTitle}>{t("linkInvalid")}</h1>
        <p className={styles.muted}>{t("linkInvalidBody")}</p>
      </div>
    );
  if (!ticket) return <p className={styles.loading}>{t("loading")}</p>;

  return (
    <div className={styles.orderPage}>
      <p className={styles.kicker} dir="ltr">
        {ticket.number}
      </p>
      <h1 className={styles.dashTitle}>{ticket.subject}</h1>
      <p className={styles.muted}>{t(`status.${ticket.status}`)}</p>
      <ol className={styles.thread}>
        {ticket.messages.map((m) => (
          <li key={m.id} data-kind={m.kind}>
            <p className={styles.muted}>
              {m.kind === "customer" ? t("you") : "AureVon"} · {formatDate(m.created_at, locale)}
            </p>
            <p className={styles.threadBody}>{m.body}</p>
          </li>
        ))}
      </ol>
      <form className={styles.form} onSubmit={reply}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{t("reply")}</span>
          <textarea name="message" required maxLength={4000} rows={5} />
        </label>
        <button className={styles.primary}>{t("sendReply")}</button>
        {message ? (
          <p className={styles.muted} role="status">
            {message}
          </p>
        ) : null}
      </form>
    </div>
  );
}
