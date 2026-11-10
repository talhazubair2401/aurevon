"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import styles from "@/components/checkout/Checkout.module.css";

/**
 * Pages opened from a link in an email: newsletter confirmation and one-click unsubscribe. The token is in the
 * URL fragment (#token=...), so it never reaches server logs or the Referer header; it is posted once.
 */
export function EmailLink({ kind }: { kind: "confirm" | "unsubscribe" }) {
  const t = useTranslations("newsletter");
  const [state, setState] = useState<"working" | "done" | "failed">("working");

  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (!token) {
      void Promise.resolve().then(() => setState("failed"));
      return;
    }
    const path = kind === "confirm" ? "/api/v1/newsletter/confirm" : "/api/v1/unsubscribe";
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ token }),
      credentials: "same-origin",
    })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        setState("done");
        history.replaceState(null, "", window.location.pathname);
      })
      .catch(() => setState("failed"));
  }, [kind]);

  const title =
    state === "working"
      ? t(kind === "confirm" ? "confirming" : "unsubscribing")
      : state === "failed"
        ? t(kind === "confirm" ? "confirmFailed" : "unsubscribeFailed")
        : kind === "confirm"
          ? t("confirmed")
          : t("unsubscribed");

  return (
    <div className={styles.status} role="status" aria-live="polite">
      {state === "working" ? <div className={styles.spinner} aria-hidden="true" /> : null}
      <h1>{title}</h1>
      {state !== "working" ? (
        <p className={styles.muted}>
          {kind === "unsubscribe" ? (
            <>
              {t("managePreferences")} <Link href="/account#details">{t("myAccount")}</Link>
            </>
          ) : (
            <Link href="/">{t("continue")}</Link>
          )}
        </p>
      ) : null}
    </div>
  );
}
