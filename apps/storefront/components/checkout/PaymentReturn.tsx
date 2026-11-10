"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError, api } from "@/lib/client";
import styles from "./Checkout.module.css";

type Status = { order_status: string; payment_status: string; attempt: string | null };

/**
 * Back from the payment provider. The browser's return never decides anything (A-23): this page asks the API,
 * which checks with the provider directly, and waits for a verified result.
 */
export function PaymentReturn({ number }: { number: string }) {
  const t = useTranslations("checkout");
  const router = useRouter();
  const [state, setState] = useState<"checking" | "failed" | "slow" | "missing">("checking");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let stop = false;
    let tries = 0;
    async function poll() {
      try {
        const s = await api<Status>(`/orders/${number}/payment-status`);
        if (stop) return;
        if (s.payment_status === "paid") {
          router.replace(`/account/orders/${number}?placed=1`);
          return;
        }
        if (s.attempt === "not_paid" || s.order_status === "cancelled") {
          setState("failed");
          return;
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setState("missing");
          return;
        }
      }
      tries += 1;
      if (tries > 10) setState("slow");
      window.setTimeout(poll, tries < 5 ? 1500 : 4000);
    }
    poll();
    return () => {
      stop = true;
    };
  }, [number, router]);

  async function retry() {
    setBusy(true);
    try {
      const a = await api<{ redirect_url: string }>(`/orders/${number}/payment-attempts`, {
        method: "POST",
      });
      window.location.assign(a.redirect_url);
    } catch (e) {
      setBusy(false);
      alertMessage(e);
    }
  }

  function alertMessage(e: unknown) {
    if (e instanceof ApiError) setState("failed");
  }

  return (
    <div className={styles.status} role="status" aria-live="polite">
      {state === "checking" || state === "slow" ? (
        <>
          <div className={styles.spinner} aria-hidden="true" />
          <h1>{t("confirming")}</h1>
          <p className={styles.muted}>
            {state === "slow" ? t("confirmingSlow") : t("confirmingBody")}
          </p>
          {state === "slow" ? (
            <Link href={`/account/orders/${number}`}>{t("viewOrder")}</Link>
          ) : null}
        </>
      ) : state === "missing" ? (
        <>
          <h1>{t("orderMissing")}</h1>
          <Link href="/">{t("continue")}</Link>
        </>
      ) : (
        <>
          <h1>{t("paymentFailed")}</h1>
          <p className={styles.muted}>{t("paymentFailedBody")}</p>
          <button
            type="button"
            className={styles.place}
            onClick={retry}
            disabled={busy}
            data-testid="retry-payment"
          >
            {t("tryAgain")}
          </button>
          <Link href={`/account/orders/${number}`}>{t("viewOrder")}</Link>
        </>
      )}
    </div>
  );
}
