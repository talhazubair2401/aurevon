"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { formatDate, type Locale } from "@aurevon/i18n";
import { Price } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import { ApiError, api, type Order } from "@/lib/client";
import styles from "./Account.module.css";

/** One order, for its owner (signed in) or the guest browser that placed it (order cookie). */
export function OrderDetail({ number }: { number: string }) {
  const t = useTranslations("orders");
  const locale = useLocale() as Locale;
  const params = useSearchParams();
  const [order, setOrder] = useState<Order | null>(null);
  const [missing, setMissing] = useState(false);
  const [payError, setPayError] = useState("");

  useEffect(() => {
    api<Order>(`/orders/${number}`, { locale }).then(setOrder, () => setMissing(true));
  }, [number, locale]);

  async function pay() {
    setPayError("");
    try {
      const a = await api<{ redirect_url: string }>(`/orders/${number}/payment-attempts`, {
        method: "POST",
      });
      window.location.assign(a.redirect_url);
    } catch (e) {
      setPayError(e instanceof ApiError ? e.message : t("error"));
    }
  }

  if (missing)
    return (
      <div className={styles.orderPage}>
        <h1 className={styles.dashTitle}>{t("notFound")}</h1>
        <p className={styles.muted}>{t("notFoundBody")}</p>
        <Link href="/account/sign-in" className={styles.link}>
          {t("signIn")}
        </Link>
      </div>
    );
  if (!order) return <p className={styles.loading}>{t("loading")}</p>;

  const m = (v: { amount: string; currency: string }) => (
    <Price amount={v.amount} currency={v.currency} locale={locale} />
  );
  const a = order.shipping_address as Record<string, string>;
  const placed = params.get("placed") === "1";

  return (
    <div className={styles.orderPage}>
      {placed ? (
        <div className={styles.placedNote} role="status" data-testid="order-placed">
          <strong>{t("thankYou")}</strong>
          {order.payment_method === "cod"
            ? t("placedCod", { email: order.email })
            : t("placedPaid", { email: order.email })}
        </div>
      ) : null}
      <header className={styles.orderHead}>
        <div>
          <p className={styles.kicker}>{t("order")}</p>
          <h1 className={styles.dashTitle} data-testid="order-number">
            {order.number}
          </h1>
          <p className={styles.muted}>
            {t("placedOn", { date: formatDate(order.placed_at, locale, { dateStyle: "long" }) })}
          </p>
        </div>
        <span className={styles.badge} data-status={order.status} data-testid="order-status">
          {t(`status.${order.status}`)}
        </span>
      </header>

      {order.can_pay ? (
        <div className={styles.placedNote}>
          <strong>{t("awaitingPayment")}</strong>
          {order.pay_by
            ? t("payBy", {
                time: formatDate(order.pay_by, locale, { timeStyle: "short", dateStyle: "medium" }),
              })
            : null}
          <div className={`${styles.actions} ${styles.spaced}`}>
            <button type="button" className={styles.primary} onClick={pay} data-testid="pay-now">
              {t("payNow")}
            </button>
          </div>
          {payError ? <p className={styles.error}>{payError}</p> : null}
        </div>
      ) : null}

      <div className={styles.orderGrid}>
        <section aria-labelledby="items-title">
          <h2 id="items-title" className={styles.boxTitle}>
            {t("items", { count: order.items.reduce((n, i) => n + i.quantity, 0) })}
          </h2>
          <ul className={styles.itemList}>
            {order.items.map((i) => (
              <li key={i.sku} className={styles.item}>
                <span className={styles.orderThumb}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- snapshot thumbnail */}
                  {i.image_url ? <img src={i.image_url} alt="" /> : null}
                </span>
                <div>
                  <Link href={`/products/${i.product_slug}`} className={styles.link}>
                    {i.name}
                  </Link>
                  <p className={styles.muted}>
                    {i.colour} · {t("size")} {i.size} · {t("qty", { count: i.quantity })}
                  </p>
                </div>
                {m(i.line_total)}
              </li>
            ))}
          </ul>

          {order.shipments.length ? (
            <div className={`${styles.box} ${styles.spacedLarge}`}>
              <h2 className={styles.boxTitle}>{t("tracking")}</h2>
              {order.shipments.map((s, idx) => (
                <p key={idx}>
                  {s.courier} · {s.tracking_number}{" "}
                  {s.tracking_url ? (
                    <a
                      href={s.tracking_url}
                      className={styles.link}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {t("track")}
                    </a>
                  ) : null}
                </p>
              ))}
            </div>
          ) : null}
        </section>

        <aside className={styles.side}>
          <div className={styles.box}>
            <h2 className={styles.boxTitle}>{t("summary")}</h2>
            <dl className={styles.totals}>
              <div>
                <dt>{t("subtotal")}</dt>
                <dd>{m(order.subtotal)}</dd>
              </div>
              {Number(order.discount.amount) > 0 ? (
                <div>
                  <dt>
                    {order.discount_label
                      ? t("discountCode", { code: order.discount_label })
                      : t("discount")}
                  </dt>
                  <dd>−{m(order.discount)}</dd>
                </div>
              ) : null}
              <div>
                <dt>{t("delivery")}</dt>
                <dd>{Number(order.shipping_fee.amount) > 0 ? m(order.shipping_fee) : t("free")}</dd>
              </div>
              {Number(order.cod_fee.amount) > 0 ? (
                <div>
                  <dt>{t("codFee")}</dt>
                  <dd>{m(order.cod_fee)}</dd>
                </div>
              ) : null}
              {Number(order.tax.amount) > 0 && !order.tax_included ? (
                <div>
                  <dt>{t("tax")}</dt>
                  <dd>{m(order.tax)}</dd>
                </div>
              ) : null}
              <div className={styles.grand}>
                <dt>{t("total")}</dt>
                <dd>{m(order.total)}</dd>
              </div>
            </dl>
            {Number(order.tax.amount) > 0 && order.tax_included ? (
              <p className={styles.muted}>{t("taxIncluded")}</p>
            ) : null}
            <p className={styles.muted}>
              {t(`method.${order.payment_method}`)} · {t(`payment.${order.payment_status}`)}
            </p>
          </div>

          <div className={styles.box}>
            <h2 className={styles.boxTitle}>{t("deliverTo")}</h2>
            <address className={styles.plainAddress}>
              {a.full_name}
              <br />
              {a.line1}
              {a.line2 ? `, ${a.line2}` : ""}
              <br />
              {[a.area, a.city, a.postal_code].filter(Boolean).join(", ")}
              <br />
              <span dir="ltr">{order.phone}</span>
            </address>
            {order.delivery_days ? (
              <p className={styles.muted}>{t("estimate", { days: order.delivery_days })}</p>
            ) : null}
          </div>

          <div className={styles.box}>
            <h2 className={styles.boxTitle}>{t("history")}</h2>
            <ul className={styles.timeline}>
              {order.history
                .filter((h) => h.kind === "order")
                .map((h, idx) => (
                  <li key={idx}>
                    <span>{t(`status.${h.status}`)}</span>
                    <span className={styles.muted}>{formatDate(h.at, locale)}</span>
                  </li>
                ))}
            </ul>
          </div>
          {order.can_return ? <p className={styles.muted}>{t("returnHint")}</p> : null}
        </aside>
      </div>
    </div>
  );
}
