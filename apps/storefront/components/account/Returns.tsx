"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { formatDate, type Locale } from "@aurevon/i18n";
import type { components } from "@aurevon/api-client";
import { ApiError, api } from "@/lib/client";
import styles from "./Account.module.css";

type Info = components["schemas"]["OrderReturnsOut"];
type Line = { qty: number; exchange: string };

/** Return or exchange request for a delivered order (M12), for whoever can open the order. */
export function Returns({ number }: { number: string }) {
  const t = useTranslations("returns");
  const locale = useLocale() as Locale;
  const [info, setInfo] = useState<Info | null>(null);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"refund" | "exchange">("refund");
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [lines, setLines] = useState<Record<string, Line>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<Info>(`/orders/${number}/returns`).then(setInfo, () => setInfo(null));
  }, [number]);
  useEffect(load, [load]);
  if (!info || (!info.can_return && info.requests.length === 0)) return null;

  const chosen = Object.entries(lines).filter(([, l]) => l.qty > 0);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const next = await api<Info>(`/orders/${number}/returns`, {
        method: "POST",
        body: {
          kind,
          reason,
          details,
          lines: chosen.map(([sku, l]) => ({
            sku,
            quantity: l.qty,
            ...(kind === "exchange" ? { exchange_sku: l.exchange } : {}),
          })),
        },
      });
      setInfo(next);
      setOpen(false);
      setLines({});
      setDetails("");
      setMessage(t("sent"));
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function cancel(returnNumber: string) {
    try {
      setInfo(
        await api<Info>(`/orders/${number}/returns/${returnNumber}/cancel`, { method: "POST" }),
      );
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : t("error"));
    }
  }

  const exchangeReady = kind !== "exchange" || chosen.every(([, l]) => l.exchange);

  return (
    <section className={styles.box} aria-labelledby="returns-title" data-testid="returns">
      <h2 className={styles.boxTitle} id="returns-title">
        {t("title")}
      </h2>
      {info.requests.map((r) => (
        <div key={r.number} className={styles.returnRow}>
          <p>
            <strong dir="ltr">{r.number}</strong> · {t(`kind.${r.kind}`)} ·{" "}
            <span data-testid="return-status">{t(`status.${r.status}`)}</span>
          </p>
          <ul className={styles.muted}>
            {r.items.map((i) => (
              <li key={i.id}>
                {i.name} ({i.size}, {i.colour}) × {i.quantity}
                {i.exchange_label ? ` → ${i.exchange_label}` : ""}
              </li>
            ))}
          </ul>
          {r.decision_note ? <p className={styles.muted}>{r.decision_note}</p> : null}
          {r.status === "requested" ? (
            <button
              type="button"
              className={styles.textButton}
              onClick={() => void cancel(r.number)}
            >
              {t("cancel")}
            </button>
          ) : null}
        </div>
      ))}
      {info.can_return && !open ? (
        <>
          {info.return_by ? (
            <p className={styles.muted}>
              {t("window", { date: formatDate(info.return_by, locale) })}
            </p>
          ) : null}
          <button type="button" className={styles.secondary} onClick={() => setOpen(true)}>
            {t("start")}
          </button>
        </>
      ) : null}
      {open ? (
        <form className={styles.form} onSubmit={submit}>
          <fieldset className={styles.row}>
            <legend className={styles.fieldLabel}>{t("whatWould")}</legend>
            {(["refund", "exchange"] as const).map((k) => (
              <label key={k} className={styles.check}>
                <input type="radio" name="kind" checked={kind === k} onChange={() => setKind(k)} />
                {t(`kind.${k}`)}
              </label>
            ))}
          </fieldset>
          {info.items
            .filter((i) => i.available > 0)
            .map((i) => {
              const line = lines[i.sku] ?? { qty: 0, exchange: "" };
              return (
                <div key={i.sku} className={styles.returnRow}>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>
                      {i.name} ({i.size}, {i.colour})
                    </span>
                    <select
                      value={line.qty}
                      aria-label={t("quantityOf", { name: i.name })}
                      onChange={(e) =>
                        setLines({ ...lines, [i.sku]: { ...line, qty: Number(e.target.value) } })
                      }
                    >
                      {Array.from({ length: i.available + 1 }, (_, n) => (
                        <option key={n} value={n}>
                          {n === 0 ? t("keep") : t("returnN", { count: n })}
                        </option>
                      ))}
                    </select>
                  </label>
                  {kind === "exchange" && line.qty > 0 ? (
                    <label className={styles.field}>
                      <span className={styles.fieldLabel}>{t("instead")}</span>
                      <select
                        value={line.exchange}
                        onChange={(e) =>
                          setLines({ ...lines, [i.sku]: { ...line, exchange: e.target.value } })
                        }
                      >
                        <option value="">{t("choose")}</option>
                        {i.exchange_options.map((o) => (
                          <option key={o.sku} value={o.sku} disabled={!o.in_stock}>
                            {o.size} · {o.colour}
                            {o.in_stock ? "" : ` (${t("soldOut")})`}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                </div>
              );
            })}
          <label className={styles.field}>
            <span className={styles.fieldLabel}>{t("reason")}</span>
            <select value={reason} onChange={(e) => setReason(e.target.value)} required>
              <option value="">{t("choose")}</option>
              {info.reasons.map((r) => (
                <option key={r.code} value={r.code}>
                  {t(`reasons.${r.code}`)}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>{t("details")}</span>
            <textarea
              rows={3}
              maxLength={1000}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </label>
          <p className={styles.muted}>{t("dontSend")}</p>
          <div className={styles.row}>
            <button
              className={styles.primary}
              disabled={busy || !chosen.length || !reason || !exchangeReady}
            >
              {t("submit")}
            </button>
            <button type="button" className={styles.textButton} onClick={() => setOpen(false)}>
              {t("close")}
            </button>
          </div>
        </form>
      ) : null}
      {message ? (
        <p className={styles.muted} role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}
