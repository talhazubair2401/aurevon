"use client";

import { useState } from "react";
import { api, call, useApiData } from "../lib/api";
import { useSession } from "../lib/session";
import c from "./content.module.css";
import ui from "./ui.module.css";

/** The fields coupons and automatic promotions share: amount, limits, categories and schedule. */
export type DiscountFields = {
  kind: "percent" | "fixed";
  value: string;
  max_discount: string;
  min_subtotal: string;
  categories: string[];
  starts_at: string; // yyyy-MM-ddTHH:mm in the browser's time zone, or ""
  ends_at: string;
  is_active: boolean;
};

export const STATE: Record<string, string> = {
  live: "Live",
  scheduled: "Scheduled",
  ended: "Ended",
  off: "Switched off",
  used_up: "Fully used",
};

export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromFields(v: DiscountFields) {
  return {
    kind: v.kind,
    value: v.value,
    max_discount: v.max_discount.trim() || null,
    min_subtotal: v.min_subtotal.trim() || "0",
    categories: v.categories,
    starts_at: v.starts_at ? new Date(v.starts_at).toISOString() : null,
    ends_at: v.ends_at ? new Date(v.ends_at).toISOString() : null,
    is_active: v.is_active,
  };
}

export function initialFields(d?: {
  kind: string;
  value: string;
  max_discount: string | null;
  min_subtotal: string;
  categories: string[];
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
}): DiscountFields {
  return {
    kind: (d?.kind as DiscountFields["kind"]) ?? "percent",
    value: d ? String(Number(d.value)) : "",
    max_discount: d?.max_discount ? String(Number(d.max_discount)) : "",
    min_subtotal: d && Number(d.min_subtotal) ? String(Number(d.min_subtotal)) : "",
    categories: d?.categories ?? [],
    starts_at: toLocalInput(d?.starts_at),
    ends_at: toLocalInput(d?.ends_at),
    is_active: d?.is_active ?? true,
  };
}

export function describe(d: { kind: string; value: string; max_discount: string | null }): string {
  const amount =
    d.kind === "percent" ? `${Number(d.value)}% off` : `Rs ${Number(d.value).toLocaleString()} off`;
  return d.max_discount
    ? `${amount} (up to Rs ${Number(d.max_discount).toLocaleString()})`
    : amount;
}

const loadCategories = () => call(() => api.GET("/api/v1/staff/catalog/categories"));

export function DiscountFieldsEditor({
  id,
  value: v,
  onChange,
}: {
  id: string;
  value: DiscountFields;
  onChange: (v: DiscountFields) => void;
}) {
  const { can } = useSession();
  const { data: categories } = useApiData(can("catalog.view") ? loadCategories : noCategories);
  const [showCats, setShowCats] = useState(v.categories.length > 0);
  const field = (k: "value" | "max_discount" | "min_subtotal", label: string) => (
    <div className={ui.field}>
      <label htmlFor={`${id}-${k}`}>{label}</label>
      <input
        id={`${id}-${k}`}
        className={ui.input}
        inputMode="decimal"
        value={v[k]}
        onChange={(e) => onChange({ ...v, [k]: e.target.value })}
      />
    </div>
  );
  const when = (k: "starts_at" | "ends_at", label: string) => (
    <div className={ui.field}>
      <label htmlFor={`${id}-${k}`}>{label}</label>
      <input
        id={`${id}-${k}`}
        type="datetime-local"
        className={ui.input}
        value={v[k]}
        onChange={(e) => onChange({ ...v, [k]: e.target.value })}
      />
    </div>
  );
  return (
    <>
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor={`${id}-kind`}>Discount</label>
          <select
            id={`${id}-kind`}
            className={ui.select}
            value={v.kind}
            onChange={(e) => onChange({ ...v, kind: e.target.value as DiscountFields["kind"] })}
          >
            <option value="percent">Percentage off</option>
            <option value="fixed">Fixed amount off (Rs)</option>
          </select>
        </div>
        {field("value", v.kind === "percent" ? "Percent (at most 90)" : "Amount (Rs)")}
        {v.kind === "percent" && field("max_discount", "Largest discount (Rs, optional)")}
        {field("min_subtotal", "Minimum bag value (Rs, optional)")}
        {when("starts_at", "Starts")}
        {when("ends_at", "Ends")}
      </div>
      <label className={ui.row}>
        <input
          type="checkbox"
          checked={showCats}
          onChange={(e) => {
            setShowCats(e.target.checked);
            if (!e.target.checked) onChange({ ...v, categories: [] });
          }}
        />
        Only for some categories
      </label>
      {showCats && (
        <fieldset className={ui.row}>
          <legend>Categories</legend>
          {(categories ?? []).map((cat) => (
            <label key={cat.slug} className={ui.row}>
              <input
                type="checkbox"
                checked={v.categories.includes(cat.slug)}
                onChange={(e) =>
                  onChange({
                    ...v,
                    categories: e.target.checked
                      ? [...v.categories, cat.slug]
                      : v.categories.filter((s) => s !== cat.slug),
                  })
                }
              />
              {cat.name_en}
            </label>
          ))}
        </fieldset>
      )}
    </>
  );
}

const noCategories = async () => [] as Array<{ slug: string; name_en: string }>;
