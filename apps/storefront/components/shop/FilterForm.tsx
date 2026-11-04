"use client";

import { useEffect, useId, useRef, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { Facets } from "@/lib/api";
import { toSearch, type ShopState } from "@/lib/shop-query";
import styles from "./Shop.module.css";

/**
 * Filters as a plain GET form (works without JavaScript); with JavaScript, every change updates the URL
 * immediately and the server re-renders the grid. Price applies on submit or when leaving the field.
 */
export function FilterForm({
  state,
  facets,
  instant = true,
  submitLabel,
  onApplied,
}: {
  state: ShopState;
  facets: Facets;
  /** Apply each change at once (sidebar). The phone drawer applies on submit, so the grid doesn't reload behind it. */
  instant?: boolean;
  submitLabel?: string;
  onApplied?: () => void;
}) {
  const t = useTranslations("shop");
  const router = useRouter();
  const pathname = usePathname();
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const formRef = useRef<HTMLFormElement>(null);

  // Keep the controls in step with the URL (e.g. after "Clear all" or a department tab) without remounting,
  // so keyboard focus stays where it is.
  useEffect(() => {
    const form = formRef.current;
    if (!form) return;
    for (const el of Array.from(form.elements)) {
      if (!(el instanceof HTMLInputElement)) continue;
      if (el.name === "size") el.checked = state.size.includes(el.value);
      else if (el.name === "colour") el.checked = state.colour.includes(el.value);
      else if (el.name === "category") el.checked = el.value === (state.category ?? "");
      else if (el.name === "price_min" && document.activeElement !== el)
        el.value = state.price_min ?? "";
      else if (el.name === "price_max" && document.activeElement !== el)
        el.value = state.price_max ?? "";
    }
  }, [state]);

  function change(form: HTMLFormElement | null) {
    if (instant && form) apply(form);
  }

  function apply(form: HTMLFormElement) {
    const data = new FormData(form);
    const next: Partial<ShopState> = {
      size: data.getAll("size").map(String),
      colour: data.getAll("colour").map(String),
      sort: state.sort,
      ...(state.department ? { department: state.department } : {}),
      ...(state.collection ? { collection: state.collection } : {}),
    };
    const category = String(data.get("category") ?? "");
    if (category) next.category = category;
    const min = String(data.get("price_min") ?? "").trim();
    const max = String(data.get("price_max") ?? "").trim();
    if (min) next.price_min = min;
    if (max) next.price_max = max;
    router.replace(`${pathname}${toSearch(next)}`, { scroll: false });
    onApplied?.();
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    apply(event.currentTarget);
  }

  const categories = facets.categories.filter(
    (c) => !state.department || c.department === state.department,
  );

  return (
    <form
      ref={formRef}
      method="get"
      action={pathname}
      className={styles.filters}
      onSubmit={onSubmit}
    >
      {state.department ? <input type="hidden" name="department" value={state.department} /> : null}
      {state.collection ? <input type="hidden" name="collection" value={state.collection} /> : null}
      {state.sort !== "featured" ? <input type="hidden" name="sort" value={state.sort} /> : null}

      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>{t("category")}</legend>
        <ul className={styles.options}>
          <li>
            <label className={styles.option}>
              <input
                type="radio"
                name="category"
                value=""
                defaultChecked={!state.category}
                onChange={(e) => change(e.currentTarget.form)}
              />
              <span>{t("all")}</span>
            </label>
          </li>
          {categories.map((c) => (
            <li key={c.slug}>
              <label className={styles.option}>
                <input
                  type="radio"
                  name="category"
                  value={c.slug}
                  defaultChecked={state.category === c.slug}
                  onChange={(e) => change(e.currentTarget.form)}
                />
                <span>
                  {c.name}
                  {!state.department ? (
                    <span className={styles.optionMeta}>
                      {" "}
                      · {t(c.department as "women" | "men")}
                    </span>
                  ) : null}
                </span>
                <span className={styles.count}>{c.count}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>{t("size")}</legend>
        <ul className={styles.sizes}>
          {facets.sizes.map((s) => (
            <li key={s.value}>
              <input
                id={`${uid}-size-${s.value}`}
                className={styles.sizeInput}
                type="checkbox"
                name="size"
                value={s.value}
                defaultChecked={state.size.includes(s.value)}
                onChange={(e) => change(e.currentTarget.form)}
              />
              <label htmlFor={`${uid}-size-${s.value}`} className={styles.sizeChip}>
                {s.value}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>{t("colour")}</legend>
        <ul className={styles.options}>
          {facets.colours.map((c) => (
            <li key={c.slug}>
              <label className={styles.option}>
                <input
                  type="checkbox"
                  name="colour"
                  value={c.slug}
                  defaultChecked={state.colour.includes(c.slug)}
                  onChange={(e) => change(e.currentTarget.form)}
                />
                <svg
                  className={styles.swatch}
                  viewBox="0 0 12 12"
                  aria-hidden="true"
                  focusable="false"
                >
                  <circle cx="6" cy="6" r="5.5" fill={c.hex} />
                </svg>
                <span>{c.name}</span>
                <span className={styles.count}>{c.count}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>{t("price")}</legend>
        <div className={styles.priceRow}>
          <label className={styles.priceField}>
            <span className={styles.srOnly}>{t("priceMin")}</span>
            <input
              className={styles.priceInput}
              type="number"
              name="price_min"
              min={0}
              step={500}
              inputMode="numeric"
              placeholder={facets.price.min ? String(Math.floor(Number(facets.price.min))) : "0"}
              defaultValue={state.price_min ?? ""}
              aria-label={t("priceMin")}
              onBlur={(e) => change(e.currentTarget.form)}
            />
          </label>
          <span aria-hidden="true">–</span>
          <label className={styles.priceField}>
            <span className={styles.srOnly}>{t("priceMax")}</span>
            <input
              className={styles.priceInput}
              type="number"
              name="price_max"
              min={0}
              step={500}
              inputMode="numeric"
              placeholder={facets.price.max ? String(Math.ceil(Number(facets.price.max))) : ""}
              defaultValue={state.price_max ?? ""}
              aria-label={t("priceMax")}
              onBlur={(e) => change(e.currentTarget.form)}
            />
          </label>
        </div>
      </fieldset>

      <div className={styles.filterActions}>
        <button type="submit" className={instant ? styles.applyButton : styles.showResults}>
          {submitLabel ?? t("apply")}
        </button>
      </div>
    </form>
  );
}
