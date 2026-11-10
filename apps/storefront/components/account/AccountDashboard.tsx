"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { formatDate, type Locale } from "@aurevon/i18n";
import { Price } from "@aurevon/ui";
import { GarmentArt, type ArtKind } from "@/components/art/GarmentArt";
import { Link, useRouter } from "@/i18n/navigation";
import {
  ApiError,
  api,
  forgetSession,
  getSession,
  type Address,
  type AddressInput,
  type OrderSummary,
  type Profile,
  type Session,
} from "@/lib/client";
import type { components } from "@aurevon/api-client";

type Card = components["schemas"]["ProductCard"];
import styles from "./Account.module.css";

type Tab = "orders" | "addresses" | "wishlist" | "details";
const TABS: Tab[] = ["orders", "addresses", "wishlist", "details"];
const PROVINCES = ["punjab", "sindh", "kp", "balochistan", "ict", "gb", "ajk"] as const;

export function AccountDashboard() {
  const t = useTranslations("account");
  const router = useRouter();
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [tab, setTab] = useState<Tab>("orders");

  useEffect(() => {
    getSession(true).then((s) => {
      if (!s) router.replace("/account/sign-in?next=/account");
      setSession(s);
    });
    const hash = window.location.hash.slice(1) as Tab;
    if (TABS.includes(hash)) void Promise.resolve().then(() => setTab(hash));
  }, [router]);

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    forgetSession();
    router.replace("/");
    router.refresh();
  }

  if (!session) return <p className={styles.loading}>{t("loading")}</p>;

  return (
    <div className={styles.dashboard}>
      <header className={styles.dashHeader}>
        <p className={styles.kicker}>{t("kicker")}</p>
        <h1 className={styles.dashTitle}>
          {t("hello", { name: session.account.full_name || session.account.email })}
        </h1>
        {!session.account.email_verified ? (
          <p className={styles.notice}>{t("verifyNotice")}</p>
        ) : null}
      </header>
      <nav className={styles.tabs} aria-label={t("sections")}>
        {TABS.map((key) => (
          <button
            key={key}
            type="button"
            className={styles.tab}
            aria-current={tab === key ? "page" : undefined}
            onClick={() => {
              setTab(key);
              history.replaceState(null, "", `#${key}`);
            }}
          >
            {t(`tabs.${key}`)}
          </button>
        ))}
        <button type="button" className={`${styles.tab} ${styles.signOut}`} onClick={signOut}>
          {t("signOut")}
        </button>
      </nav>
      <section className={styles.panel}>
        {tab === "orders" ? (
          <Orders />
        ) : tab === "addresses" ? (
          <Addresses />
        ) : tab === "wishlist" ? (
          <Wishlist />
        ) : (
          <Details />
        )}
      </section>
    </div>
  );
}

function Orders() {
  const t = useTranslations("account");
  const tStatus = useTranslations("orders.status");
  const locale = useLocale() as Locale;
  const [rows, setRows] = useState<OrderSummary[] | null>(null);
  useEffect(() => {
    api<OrderSummary[]>("/me/orders").then(setRows, () => setRows([]));
  }, []);
  if (!rows) return <p className={styles.muted}>{t("loading")}</p>;
  if (!rows.length)
    return (
      <div className={styles.emptyState}>
        <p>{t("noOrders")}</p>
        <Link href="/shop" className={styles.link}>
          {t("startShopping")}
        </Link>
      </div>
    );
  return (
    <ul className={styles.orderList}>
      {rows.map((o) => (
        <li key={o.number}>
          <Link href={`/account/orders/${o.number}`} className={styles.orderRow}>
            <span className={styles.orderThumb}>
              {/* eslint-disable-next-line @next/next/no-img-element -- pre-sized thumbnail */}
              {o.first_image ? <img src={o.first_image} alt="" /> : null}
            </span>
            <span className={styles.orderMain}>
              <strong>{o.number}</strong>
              <span className={styles.muted}>
                {formatDate(o.placed_at, locale)} · {t("items", { count: o.item_count })}
              </span>
            </span>
            <span className={styles.badge} data-status={o.status}>
              {tStatus(o.status)}
            </span>
            <Price amount={o.total.amount} currency={o.total.currency} locale={locale} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Addresses() {
  const t = useTranslations("account");
  const tc = useTranslations("checkout");
  const [rows, setRows] = useState<Address[] | null>(null);
  const [editing, setEditing] = useState<Address | "new" | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api<Address[]>("/me/addresses").then(setRows), []);
  useEffect(() => {
    load();
  }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const body: AddressInput & { label: string; make_default: boolean } = {
      label: String(f.get("label") ?? ""),
      full_name: String(f.get("full_name") ?? ""),
      phone: String(f.get("phone") ?? ""),
      line1: String(f.get("line1") ?? ""),
      line2: String(f.get("line2") ?? ""),
      area: String(f.get("area") ?? ""),
      city: String(f.get("city") ?? ""),
      province: String(f.get("province") ?? "sindh") as AddressInput["province"],
      postal_code: String(f.get("postal_code") ?? ""),
      make_default: f.get("make_default") === "on",
    };
    try {
      if (editing === "new") await api("/me/addresses", { method: "POST", body });
      else if (editing) await api(`/me/addresses/${editing.id}`, { method: "PATCH", body });
      setEditing(null);
      setError("");
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    }
  }

  if (!rows) return <p className={styles.muted}>{t("loading")}</p>;
  if (editing) {
    const a = editing === "new" ? null : editing;
    return (
      <form className={styles.addressForm} onSubmit={save}>
        <h2 className={styles.panelTitle}>{a ? t("editAddress") : t("addAddress")}</h2>
        <div className={styles.formGrid}>
          <Field name="label" label={t("addressLabel")} value={a?.label} />
          <Field name="full_name" label={tc("fullName")} value={a?.full_name} required />
          <Field name="phone" label={tc("phone")} value={a?.phone} required type="tel" />
          <Field name="line1" label={tc("line1")} value={a?.line1} required wide />
          <Field name="line2" label={tc("line2")} value={a?.line2} wide />
          <Field name="area" label={tc("area")} value={a?.area} />
          <Field name="city" label={tc("city")} value={a?.city} required />
          <label className={styles.field}>
            <span className={styles.fieldLabel}>{tc("province")}</span>
            <select name="province" defaultValue={a?.province ?? "sindh"}>
              {PROVINCES.map((p) => (
                <option key={p} value={p}>
                  {tc(`provinces.${p}`)}
                </option>
              ))}
            </select>
          </label>
          <Field name="postal_code" label={tc("postalCode")} value={a?.postal_code} />
          <label className={styles.check}>
            <input type="checkbox" name="make_default" defaultChecked={a?.is_default} />{" "}
            {t("makeDefault")}
          </label>
        </div>
        {error ? <p className={styles.error}>{error}</p> : null}
        <div className={styles.actions}>
          <button className={styles.primary}>{t("save")}</button>
          <button type="button" className={styles.secondary} onClick={() => setEditing(null)}>
            {t("cancel")}
          </button>
        </div>
      </form>
    );
  }
  return (
    <div>
      <div className={styles.panelHead}>
        <h2 className={styles.panelTitle}>{t("tabs.addresses")}</h2>
        <button type="button" className={styles.secondary} onClick={() => setEditing("new")}>
          {t("addAddress")}
        </button>
      </div>
      {rows.length === 0 ? <p className={styles.muted}>{t("noAddresses")}</p> : null}
      <ul className={styles.cards}>
        {rows.map((a) => (
          <li key={a.id} className={styles.addressCard}>
            {a.is_default ? <span className={styles.defaultTag}>{t("default")}</span> : null}
            <strong>{a.label || a.full_name}</strong>
            <address>
              {a.full_name}
              <br />
              {a.line1}
              {a.line2 ? <>, {a.line2}</> : null}
              <br />
              {[a.area, a.city, a.postal_code].filter(Boolean).join(", ")}
              <br />
              <span dir="ltr">{a.phone}</span>
            </address>
            <div className={styles.cardActions}>
              <button type="button" className={styles.textButton} onClick={() => setEditing(a)}>
                {t("edit")}
              </button>
              <button
                type="button"
                className={styles.textButton}
                onClick={async () => {
                  await api(`/me/addresses/${a.id}`, { method: "DELETE" });
                  load();
                }}
              >
                {t("delete")}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({
  name,
  label,
  value,
  required,
  type,
  wide,
}: {
  name: string;
  label: string;
  value?: string | undefined;
  required?: boolean;
  type?: string;
  wide?: boolean;
}) {
  return (
    <label className={`${styles.field} ${wide ? styles.wide : ""}`}>
      <span className={styles.fieldLabel}>{label}</span>
      <input name={name} defaultValue={value ?? ""} required={required} type={type ?? "text"} />
    </label>
  );
}

function Wishlist() {
  const t = useTranslations("account");
  const locale = useLocale() as Locale;
  const [rows, setRows] = useState<Card[] | null>(null);
  const load = useCallback(() => api<Card[]>("/me/wishlist", { locale }).then(setRows), [locale]);
  useEffect(() => {
    load();
  }, [load]);
  if (!rows) return <p className={styles.muted}>{t("loading")}</p>;
  if (!rows.length) return <p className={styles.muted}>{t("noWishlist")}</p>;
  return (
    <ul className={styles.wishGrid}>
      {rows.map((p) => (
        <li key={p.slug} className={styles.wishItem}>
          <Link href={`/products/${p.slug}`} className={styles.wishLink}>
            <span className={styles.wishMedia}>
              {p.image?.url ? (
                // eslint-disable-next-line @next/next/no-img-element -- pre-sized card image
                <img src={p.image.url} alt="" />
              ) : (
                <GarmentArt
                  kind={(p.image?.demo_art ?? "kurta") as ArtKind}
                  colour={p.image?.tone ?? "#E5E0DB"}
                  float={false}
                />
              )}
            </span>
            <span className={styles.wishName}>{p.name}</span>
            <Price amount={p.price_min.amount} currency={p.price_min.currency} locale={locale} />
          </Link>
          <button
            type="button"
            className={styles.textButton}
            onClick={async () => {
              await api(`/me/wishlist/${p.slug}`, { method: "DELETE" });
              load();
            }}
          >
            {t("removeSaved")}
          </button>
        </li>
      ))}
    </ul>
  );
}

function Details() {
  const t = useTranslations("account");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [message, setMessage] = useState("");
  const [pwMessage, setPwMessage] = useState("");
  useEffect(() => {
    api<Profile>("/me").then(setProfile);
  }, []);
  if (!profile) return <p className={styles.muted}>{t("loading")}</p>;

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    try {
      setProfile(
        await api<Profile>("/me", {
          method: "PATCH",
          body: { full_name: f.get("full_name"), phone: f.get("phone") },
        }),
      );
      setMessage(t("saved"));
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : t("error"));
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const f = new FormData(form);
    try {
      await api("/me/password", {
        method: "POST",
        body: { current_password: f.get("current"), new_password: f.get("next") },
      });
      setPwMessage(t("passwordChanged"));
      form.reset();
    } catch (e) {
      setPwMessage(e instanceof ApiError ? e.message : t("error"));
    }
  }

  return (
    <div className={styles.detailsGrid}>
      <form className={styles.addressForm} onSubmit={saveProfile}>
        <h2 className={styles.panelTitle}>{t("profile")}</h2>
        <Field name="full_name" label={t("name")} value={profile.full_name} />
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{t("email")}</span>
          <input value={profile.email} readOnly disabled />
        </label>
        <Field name="phone" label={t("phone")} value={profile.phone} type="tel" />
        <button className={styles.primary}>{t("save")}</button>
        {message ? (
          <p className={styles.muted} role="status">
            {message}
          </p>
        ) : null}
      </form>
      <form className={styles.addressForm} onSubmit={changePassword} method="post">
        <h2 className={styles.panelTitle}>{t("security")}</h2>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{t("currentPassword")}</span>
          <input name="current" type="password" autoComplete="current-password" required />
        </label>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{t("newPassword")}</span>
          <input name="next" type="password" autoComplete="new-password" required />
        </label>
        <button className={styles.primary}>{t("changePassword")}</button>
        {pwMessage ? (
          <p className={styles.muted} role="status">
            {pwMessage}
          </p>
        ) : null}
      </form>
    </div>
  );
}
