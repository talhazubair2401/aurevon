"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ApiError, api, cartWrite, getSession } from "@/lib/client";
import styles from "./Cart.module.css";

/** "Add to bag" and "Save" on the product page. Without a chosen size, the button asks for one. */
export function AddToBag({
  sku,
  available,
  slug,
  className,
}: {
  sku?: string | undefined;
  available?: boolean | undefined;
  slug: string;
  className?: string | undefined;
}) {
  const t = useTranslations("cart");
  const locale = useLocale();
  const [state, setState] = useState<"idle" | "busy" | "added" | "error">("idle");
  const [message, setMessage] = useState("");
  const [saved, setSaved] = useState<"no" | "yes" | "sign-in">("no");

  async function add() {
    if (!sku) {
      setState("error");
      setMessage(t("chooseSize"));
      return;
    }
    setState("busy");
    try {
      await cartWrite("/cart/items", "POST", locale, { sku, quantity: 1 });
      setState("added");
      setMessage(t("added"));
    } catch (e) {
      setState("error");
      setMessage(e instanceof ApiError ? e.message : t("error"));
    }
  }

  async function save() {
    if (!(await getSession())) {
      setSaved("sign-in");
      return;
    }
    try {
      await api("/me/wishlist", { method: "POST", body: { slug } });
      setSaved("yes");
    } catch {
      setSaved("no");
    }
  }

  return (
    <div className={styles.addWrap}>
      <div className={styles.addRow}>
        <button
          type="button"
          className={className ?? styles.primary}
          onClick={add}
          disabled={state === "busy" || available === false}
          data-testid="add-to-bag"
        >
          {available === false ? t("soldOut") : state === "busy" ? t("adding") : t("addToBag")}
        </button>
        <button
          type="button"
          className={styles.saveButton}
          onClick={save}
          aria-pressed={saved === "yes"}
          aria-label={saved === "yes" ? t("saved") : t("save")}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"
              fill={saved === "yes" ? "currentColor" : "none"}
              stroke="currentColor"
              strokeWidth="1.4"
            />
          </svg>
        </button>
      </div>
      <p className={styles.addStatus} role="status" aria-live="polite">
        {state === "added" ? (
          <>
            {message}{" "}
            <Link href="/cart" className={styles.inlineLink}>
              {t("viewBag")}
            </Link>
          </>
        ) : state === "error" ? (
          <span className={styles.errorText}>{message}</span>
        ) : saved === "sign-in" ? (
          <>
            {t("signInToSave")}{" "}
            <Link href="/account/sign-in" className={styles.inlineLink}>
              {t("signIn")}
            </Link>
          </>
        ) : saved === "yes" ? (
          t("savedNote")
        ) : null}
      </p>
    </div>
  );
}
