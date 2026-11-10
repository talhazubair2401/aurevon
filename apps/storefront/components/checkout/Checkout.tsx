"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { Locale } from "@aurevon/i18n";
import { Price } from "@aurevon/ui";
import { Link, useRouter } from "@/i18n/navigation";
import {
  ApiError,
  api,
  getCart,
  getSession,
  newIdempotencyKey,
  type Address,
  type AddressInput,
  type Cart,
  type Order,
  type Quote,
  type Session,
} from "@/lib/client";
import styles from "./Checkout.module.css";

const PROVINCES = ["punjab", "sindh", "kp", "balochistan", "ict", "gb", "ajk"] as const;
const EMPTY: AddressInput = {
  full_name: "",
  phone: "",
  line1: "",
  line2: "",
  area: "",
  city: "",
  province: "sindh",
  postal_code: "",
};

export function Checkout() {
  const t = useTranslations("checkout");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [cart, setCart] = useState<Cart | null>(null);
  const [saved, setSaved] = useState<Address[]>([]);
  const [chosen, setChosen] = useState<string>("new");
  const [address, setAddress] = useState<AddressInput>(EMPTY);
  const [email, setEmail] = useState("");
  const [method, setMethod] = useState<string>("");
  const [payment, setPayment] = useState<string>("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [placing, setPlacing] = useState(false);
  const [saveAddress, setSaveAddress] = useState(true);
  const key = useRef(newIdempotencyKey());

  useEffect(() => {
    (async () => {
      const s = await getSession();
      setSession(s);
      setCart(await getCart(locale));
      if (s) {
        setEmail(s.account.email);
        const rows = await api<Address[]>("/me/addresses");
        setSaved(rows);
        if (rows[0]) {
          setChosen(rows[0].id);
          setAddress(toInput(rows[0]));
        }
      }
    })().catch(() => setError(t("loadError")));
  }, [locale, t]);

  const ready = Boolean(address.city && address.province);
  const requote = useCallback(async () => {
    try {
      const q = await api<Quote>("/checkout/quote", {
        method: "POST",
        locale,
        body: {
          address: ready ? { city: address.city, province: address.province } : null,
          shipping_method: method || undefined,
          payment_method: payment || null,
        },
      });
      setQuote(q);
      if (!method && q.shipping_method) setMethod(q.shipping_method);
      if (payment && !q.payment_methods.includes(payment)) setPayment("");
    } catch (e) {
      if (e instanceof ApiError && e.code === "cart-empty") router.replace("/cart");
    }
  }, [address, method, payment, ready, locale, router]);

  useEffect(() => {
    if (!cart || cart.items.length === 0) return;
    const timer = window.setTimeout(requote, 350);
    return () => window.clearTimeout(timer);
  }, [cart, requote]);

  const guestBlocked = session === null && quote !== null && !quote.guest_checkout_allowed;

  function update(field: keyof AddressInput, value: string) {
    setAddress((a) => ({ ...a, [field]: value }));
    setChosen("new");
  }

  async function place(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFieldErrors({});
    if (!payment) {
      setError(t("choosePayment"));
      return;
    }
    setPlacing(true);
    try {
      const placed = await api<{ order: Order; next: "pay" | "confirmed" }>("/checkout/orders", {
        method: "POST",
        locale,
        idempotencyKey: key.current,
        body: {
          email: session ? undefined : email,
          phone: address.phone,
          address,
          shipping_method: method,
          payment_method: payment,
          save_address: Boolean(session) && chosen === "new" && saveAddress,
        },
      });
      window.dispatchEvent(new CustomEvent("av:cart", { detail: 0 }));
      if (placed.next === "pay") {
        const attempt = await api<{ redirect_url: string }>(
          `/orders/${placed.order.number}/payment-attempts`,
          {
            method: "POST",
          },
        );
        window.location.assign(attempt.redirect_url);
        return;
      }
      router.push(`/account/orders/${placed.order.number}?placed=1`);
    } catch (e) {
      key.current = newIdempotencyKey();
      if (e instanceof ApiError) {
        const errs = (e.body.errors ?? {}) as Record<string, unknown>;
        const flat: Record<string, string> = {};
        for (const [k, v] of Object.entries(errs)) {
          if (k === "address" && v && typeof v === "object") {
            for (const [ak, av] of Object.entries(v as Record<string, string[]>))
              flat[ak] = av[0] ?? "";
          } else flat[k] = Array.isArray(v) ? String(v[0]) : String(v);
        }
        setFieldErrors(flat);
        setError(e.code === "out-of-stock" ? t("soldOutWhile") : e.message);
        if (e.code === "out-of-stock" || e.code === "checkout-blocked")
          setCart(await getCart(locale));
      } else setError(t("placeError"));
      setPlacing(false);
    }
  }

  const items = cart?.items ?? [];
  const methods = quote?.payment_methods ?? [];
  const option = useMemo(
    () => quote?.shipping_options.find((o) => o.method === method),
    [quote, method],
  );

  if (session === undefined || !cart)
    return <p className={styles.loading}>{error || t("loading")}</p>;
  if (items.length === 0)
    return (
      <div className={styles.loading}>
        <p>{t("emptyBag")}</p>
        <Link href="/shop">{t("continue")}</Link>
      </div>
    );

  return (
    <form className={styles.layout} onSubmit={place} noValidate>
      <div className={styles.steps}>
        <p className={styles.kicker}>{t("kicker")}</p>
        <h1 className={styles.heading}>{t("title")}</h1>

        <section className={styles.step} aria-labelledby="step-contact">
          <h2 id="step-contact" className={styles.stepTitle}>
            <span className={styles.stepNumber}>01</span> {t("contact")}
          </h2>
          {session ? (
            <p className={styles.muted}>{t("signedInAs", { email: session.account.email })}</p>
          ) : guestBlocked ? (
            <p>
              {t("signInRequired")}{" "}
              <Link href="/account/sign-in?next=/checkout">{t("signIn")}</Link>
            </p>
          ) : (
            <>
              <Field label={t("email")} error={fieldErrors.email}>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  name="email"
                />
              </Field>
              <p className={styles.muted}>
                {t("haveAccount")} <Link href="/account/sign-in?next=/checkout">{t("signIn")}</Link>
              </p>
            </>
          )}
        </section>

        <section className={styles.step} aria-labelledby="step-address">
          <h2 id="step-address" className={styles.stepTitle}>
            <span className={styles.stepNumber}>02</span> {t("delivery")}
          </h2>
          {saved.length > 0 ? (
            <fieldset className={styles.choices}>
              <legend className={styles.visuallyHidden}>{t("savedAddresses")}</legend>
              {saved.map((a) => (
                <label key={a.id} className={styles.choice}>
                  <input
                    type="radio"
                    name="saved"
                    checked={chosen === a.id}
                    onChange={() => {
                      setChosen(a.id);
                      setAddress(toInput(a));
                    }}
                  />
                  <span>
                    <strong>{a.label || a.full_name}</strong>
                    <span className={styles.muted}>
                      {[a.line1, a.area, a.city].filter(Boolean).join(", ")}
                    </span>
                  </span>
                </label>
              ))}
              <label className={styles.choice}>
                <input
                  type="radio"
                  name="saved"
                  checked={chosen === "new"}
                  onChange={() => {
                    setChosen("new");
                    setAddress(EMPTY);
                  }}
                />
                <span>{t("newAddress")}</span>
              </label>
            </fieldset>
          ) : null}
          {chosen === "new" ? (
            <div className={styles.grid}>
              <Field label={t("fullName")} error={fieldErrors.full_name} wide>
                <input
                  autoComplete="name"
                  value={address.full_name}
                  onChange={(e) => update("full_name", e.target.value)}
                  name="full_name"
                  required
                />
              </Field>
              <Field label={t("phone")} hint={t("phoneHint")} error={fieldErrors.phone} wide>
                <input
                  type="tel"
                  autoComplete="tel"
                  inputMode="tel"
                  value={address.phone}
                  onChange={(e) => update("phone", e.target.value)}
                  name="phone"
                  required
                  dir="ltr"
                />
              </Field>
              <Field label={t("line1")} error={fieldErrors.line1} wide>
                <input
                  autoComplete="address-line1"
                  value={address.line1}
                  onChange={(e) => update("line1", e.target.value)}
                  name="line1"
                  required
                />
              </Field>
              <Field label={t("line2")} wide>
                <input
                  autoComplete="address-line2"
                  value={address.line2 ?? ""}
                  onChange={(e) => update("line2", e.target.value)}
                  name="line2"
                />
              </Field>
              <Field label={t("area")}>
                <input
                  value={address.area ?? ""}
                  onChange={(e) => update("area", e.target.value)}
                  name="area"
                />
              </Field>
              <Field label={t("city")} error={fieldErrors.city}>
                <input
                  autoComplete="address-level2"
                  value={address.city}
                  onChange={(e) => update("city", e.target.value)}
                  name="city"
                  required
                />
              </Field>
              <Field label={t("province")} error={fieldErrors.province}>
                <select
                  value={address.province}
                  onChange={(e) => update("province", e.target.value)}
                  name="province"
                >
                  {PROVINCES.map((p) => (
                    <option key={p} value={p}>
                      {t(`provinces.${p}`)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("postalCode")} error={fieldErrors.postal_code}>
                <input
                  inputMode="numeric"
                  autoComplete="postal-code"
                  value={address.postal_code ?? ""}
                  onChange={(e) => update("postal_code", e.target.value)}
                  name="postal_code"
                  dir="ltr"
                />
              </Field>
              {session ? (
                <label className={styles.check}>
                  <input
                    type="checkbox"
                    checked={saveAddress}
                    onChange={(e) => setSaveAddress(e.target.checked)}
                  />
                  {t("saveAddress")}
                </label>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className={styles.step} aria-labelledby="step-method">
          <h2 id="step-method" className={styles.stepTitle}>
            <span className={styles.stepNumber}>03</span> {t("method")}
          </h2>
          {!ready ? (
            <p className={styles.muted}>{t("enterCity")}</p>
          ) : quote && quote.shipping_options.length === 0 ? (
            <p className={styles.errorText}>{t("noDelivery")}</p>
          ) : (
            <fieldset className={styles.choices}>
              <legend className={styles.visuallyHidden}>{t("method")}</legend>
              {quote?.shipping_options.map((o) => (
                <label key={o.method} className={styles.choice}>
                  <input
                    type="radio"
                    name="method"
                    checked={method === o.method}
                    onChange={() => setMethod(o.method)}
                  />
                  <span className={styles.choiceBody}>
                    <strong>{t(`methods.${o.method}`)}</strong>
                    <span className={styles.muted}>
                      {t("days", { min: o.days_min, max: o.days_max })}
                    </span>
                  </span>
                  <span>
                    {Number(o.fee.amount) === 0 ? (
                      t("free")
                    ) : (
                      <Price amount={o.fee.amount} currency={o.fee.currency} locale={locale} />
                    )}
                  </span>
                </label>
              ))}
            </fieldset>
          )}
        </section>

        <section className={styles.step} aria-labelledby="step-payment">
          <h2 id="step-payment" className={styles.stepTitle}>
            <span className={styles.stepNumber}>04</span> {t("payment")}
          </h2>
          <fieldset className={styles.choices}>
            <legend className={styles.visuallyHidden}>{t("payment")}</legend>
            {methods.includes("card") ? (
              <label className={styles.choice}>
                <input
                  type="radio"
                  name="payment"
                  value="card"
                  checked={payment === "card"}
                  onChange={() => setPayment("card")}
                />
                <span className={styles.choiceBody}>
                  <strong>{t("card")}</strong>
                  <span className={styles.muted}>{t("cardNote")}</span>
                </span>
              </label>
            ) : null}
            {methods.includes("cod") ? (
              <label className={styles.choice}>
                <input
                  type="radio"
                  name="payment"
                  value="cod"
                  checked={payment === "cod"}
                  onChange={() => setPayment("cod")}
                />
                <span className={styles.choiceBody}>
                  <strong>{t("cod")}</strong>
                  <span className={styles.muted}>
                    {option && Number(option.cod_fee.amount) > 0
                      ? t("codFee", { fee: option.cod_fee.amount })
                      : t("codNote")}
                  </span>
                </span>
              </label>
            ) : null}
            {methods.length === 0 && quote ? (
              <p className={styles.errorText}>{t("noPayment")}</p>
            ) : null}
          </fieldset>
        </section>
      </div>

      <aside className={styles.summary} aria-labelledby="summary-title">
        <h2 id="summary-title" className={styles.summaryTitle}>
          {t("summary")}
        </h2>
        <ul className={styles.items}>
          {items.map((i) => (
            <li key={i.id}>
              <span>
                {i.name}
                <span className={styles.muted}>
                  {" "}
                  · {i.size} × {i.quantity}
                </span>
              </span>
              <Price
                amount={i.line_total.amount}
                currency={i.line_total.currency}
                locale={locale}
              />
            </li>
          ))}
        </ul>
        {quote ? (
          <dl className={styles.totals}>
            <Row label={t("subtotal")} amount={quote.subtotal.amount} locale={locale} />
            {Number(quote.discount.amount) > 0 ? (
              <Row
                label={quote.discount_label || t("discount")}
                amount={`-${quote.discount.amount}`}
                locale={locale}
              />
            ) : null}
            <Row
              label={t("shipping")}
              amount={quote.shipping_fee.amount}
              locale={locale}
              freeLabel={ready ? t("free") : "—"}
            />
            {Number(quote.cod_fee.amount) > 0 ? (
              <Row label={t("codFeeLabel")} amount={quote.cod_fee.amount} locale={locale} />
            ) : null}
            {Number(quote.tax.amount) > 0 && !quote.tax_included ? (
              <Row label={t("tax")} amount={quote.tax.amount} locale={locale} />
            ) : null}
            <div className={styles.grand}>
              <dt>{t("total")}</dt>
              <dd>
                <Price
                  amount={quote.total.amount}
                  currency={quote.total.currency}
                  locale={locale}
                />
              </dd>
            </div>
            {Number(quote.tax.amount) > 0 && quote.tax_included ? (
              <p className={styles.muted}>{t("taxIncluded", { amount: quote.tax.amount })}</p>
            ) : null}
          </dl>
        ) : null}
        {quote?.coupon_error ? <p className={styles.errorText}>{quote.coupon_error}</p> : null}
        {error ? (
          <p className={styles.errorText} role="alert">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          className={styles.place}
          disabled={placing || guestBlocked || !quote || !method}
          data-testid="place-order"
        >
          {placing ? t("placing") : payment === "card" ? t("continueToPay") : t("placeOrder")}
        </button>
        <p className={styles.terms}>{t("terms")}</p>
      </aside>
    </form>
  );
}

function toInput(a: Address): AddressInput {
  return {
    full_name: a.full_name,
    phone: a.phone,
    line1: a.line1,
    line2: a.line2,
    area: a.area,
    city: a.city,
    province: a.province,
    postal_code: a.postal_code ?? "",
  };
}

function Row({
  label,
  amount,
  locale,
  freeLabel,
}: {
  label: string;
  amount: string;
  locale: Locale;
  freeLabel?: string;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {freeLabel && Number(amount) === 0 ? (
          freeLabel
        ) : (
          <Price amount={amount} currency="PKR" locale={locale} />
        )}
      </dd>
    </div>
  );
}

function Field({
  label,
  hint,
  error,
  wide,
  children,
}: {
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
  wide?: boolean;
  children: React.ReactElement;
}) {
  return (
    <label
      className={`${styles.field} ${wide ? styles.wide : ""}`}
      data-invalid={error ? "true" : undefined}
    >
      <span className={styles.fieldLabel}>{label}</span>
      {children}
      {hint && !error ? <span className={styles.hint}>{hint}</span> : null}
      {error ? <span className={styles.errorText}>{error}</span> : null}
    </label>
  );
}
