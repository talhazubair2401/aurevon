"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { Locale } from "@aurevon/i18n";
import { Price } from "@aurevon/ui";
import { GarmentArt, type ArtKind } from "@/components/art/GarmentArt";
import { Link } from "@/i18n/navigation";
import { ApiError, cartWrite, getCart, type Cart, type CartLine } from "@/lib/client";
import styles from "./Cart.module.css";

export function CartPage() {
  const t = useTranslations("cart");
  const locale = useLocale() as Locale;
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCart(locale).then(setCart, () => setError(t("error")));
  }, [locale, t]);

  async function run(fn: () => Promise<Cart>) {
    setBusy(true);
    setError("");
    try {
      setCart(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function applyCoupon(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = String(new FormData(event.currentTarget).get("code") ?? "").trim();
    if (code) await run(() => cartWrite("/cart/coupon", "POST", locale, { code }));
  }

  if (!cart) {
    return <p className={styles.loading}>{error || t("loading")}</p>;
  }

  if (cart.items.length === 0) {
    return (
      <div className={styles.empty}>
        <p className={styles.kicker}>{t("title")}</p>
        <h1 className={styles.heading}>{t("emptyTitle")}</h1>
        <p className={styles.muted}>{t("emptyBody")}</p>
        <Link href="/shop" className={styles.primaryLink}>
          {t("continue")}
        </Link>
      </div>
    );
  }

  const blocked = cart.items.some((i) => i.problem);

  return (
    <div className={styles.layout}>
      <section aria-labelledby="bag-title">
        <p className={styles.kicker}>{t("count", { count: cart.count })}</p>
        <h1 id="bag-title" className={styles.heading}>
          {t("title")}
        </h1>
        <ul className={styles.lines}>
          {cart.items.map((line) => (
            <Line
              key={line.id}
              line={line}
              locale={locale}
              busy={busy}
              onQuantity={(q) =>
                run(() => cartWrite(`/cart/items/${line.id}`, "PATCH", locale, { quantity: q }))
              }
              onRemove={() => run(() => cartWrite(`/cart/items/${line.id}`, "DELETE", locale))}
            />
          ))}
        </ul>
      </section>

      <aside className={styles.summary} aria-labelledby="summary-title">
        <h2 id="summary-title" className={styles.summaryTitle}>
          {t("summary")}
        </h2>
        <dl className={styles.totals}>
          <div>
            <dt>{t("subtotal")}</dt>
            <dd>
              <Price
                amount={cart.subtotal.amount}
                currency={cart.subtotal.currency}
                locale={locale}
              />
            </dd>
          </div>
          <div>
            <dt>{t("delivery")}</dt>
            <dd className={styles.muted}>{t("deliveryLater")}</dd>
          </div>
        </dl>

        {cart.coupon_code ? (
          <p className={styles.coupon}>
            {t("couponApplied", { code: cart.coupon_code })}{" "}
            <button
              type="button"
              className={styles.textButton}
              onClick={() => run(() => cartWrite("/cart/coupon", "DELETE", locale))}
            >
              {t("remove")}
            </button>
          </p>
        ) : (
          <form className={styles.couponForm} onSubmit={applyCoupon}>
            <label htmlFor="coupon" className={styles.label}>
              {t("couponLabel")}
            </label>
            <div className={styles.couponRow}>
              <input
                id="coupon"
                name="code"
                className={styles.input}
                autoComplete="off"
                maxLength={40}
              />
              <button type="submit" className={styles.secondary} disabled={busy}>
                {t("apply")}
              </button>
            </div>
          </form>
        )}

        {error ? (
          <p className={styles.errorText} role="alert">
            {error}
          </p>
        ) : null}
        {blocked ? <p className={styles.errorText}>{t("fixProblems")}</p> : null}

        {blocked ? (
          <span className={`${styles.primaryLink} ${styles.disabledLink}`} aria-disabled="true">
            {t("checkout")}
          </span>
        ) : (
          <Link href="/checkout" className={styles.primaryLink} data-testid="to-checkout">
            {t("checkout")}
          </Link>
        )}
        <p className={styles.assurance}>{t("assurance")}</p>
      </aside>
    </div>
  );
}

function Line({
  line,
  locale,
  busy,
  onQuantity,
  onRemove,
}: {
  line: CartLine;
  locale: Locale;
  busy: boolean;
  onQuantity: (q: number) => void;
  onRemove: () => void;
}) {
  const t = useTranslations("cart");
  const max = Math.max(1, Math.min(10, line.available || line.quantity));
  const image = line.image as {
    url?: string | null;
    demo_art?: string | null;
    tone?: string;
  } | null;
  return (
    <li className={styles.line}>
      <Link
        href={`/products/${line.product_slug}`}
        className={styles.thumb}
        tabIndex={-1}
        aria-hidden="true"
      >
        {image?.url ? (
          // eslint-disable-next-line @next/next/no-img-element -- pre-sized thumbnail from object storage
          <img src={image.url} alt="" />
        ) : (
          <GarmentArt
            kind={(image?.demo_art ?? "kurta") as ArtKind}
            colour={image?.tone ?? "#E5E0DB"}
            float={false}
          />
        )}
      </Link>
      <div className={styles.lineBody}>
        <Link href={`/products/${line.product_slug}`} className={styles.lineName}>
          {line.name}
        </Link>
        <p className={styles.lineMeta}>
          {(line.colour as { name?: string }).name} · {t("size")} {line.size}
        </p>
        {line.problem === "unavailable" ? (
          <p className={styles.errorText}>{t("noLongerAvailable")}</p>
        ) : line.problem === "insufficient" ? (
          <p className={styles.errorText}>{t("onlyLeft", { count: line.available })}</p>
        ) : null}
        <div className={styles.lineControls}>
          <label className={styles.qtyLabel}>
            <span className={styles.visuallyHidden}>{t("quantityFor", { name: line.name })}</span>
            <select
              className={styles.qty}
              value={line.quantity}
              disabled={busy || line.problem === "unavailable"}
              onChange={(e) => onQuantity(Number(e.target.value))}
            >
              {Array.from({ length: Math.max(max, line.quantity) }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className={styles.textButton} onClick={onRemove} disabled={busy}>
            {t("remove")}
          </button>
        </div>
      </div>
      <Price
        className={styles.linePrice ?? ""}
        amount={line.line_total.amount}
        currency={line.line_total.currency}
        locale={locale}
      />
    </li>
  );
}
