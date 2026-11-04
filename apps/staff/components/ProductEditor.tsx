"use client";

import { useState } from "react";
import { api, call, errorMessage, useApiData, type Schemas } from "../lib/api";
import { useSession } from "../lib/session";
import { Message, type Msg } from "./CatalogNav";
import { LOCALES } from "./ContentEditor";
import c from "./content.module.css";
import ui from "./ui.module.css";

type Product = Schemas["ProductOut"];
type Copy = Record<"en" | "ur", Record<string, string>>;

export const COPY_FIELDS: Array<{ name: string; label: string; long?: boolean; max: number }> = [
  { name: "name", label: "Name", max: 160 },
  { name: "description", label: "Description", long: true, max: 4000 },
  { name: "fabric", label: "Fabric", max: 300 },
  { name: "care", label: "Care", max: 300 },
  { name: "fit_note", label: "Fit note", max: 300 },
];

export function asProductCopy(value: unknown): Copy {
  const v = (value ?? {}) as Partial<Copy>;
  return { en: { ...(v.en ?? {}) }, ur: { ...(v.ur ?? {}) } };
}

export function CopyFields({
  copy,
  onChange,
  disabled,
}: {
  copy: Copy;
  onChange: (next: Copy) => void;
  disabled: boolean;
}) {
  return (
    <div className={c.bilingual}>
      {LOCALES.map(({ code, name }) => (
        <div key={code} className={c.column}>
          <p className={c.columnTitle}>{name}</p>
          {COPY_FIELDS.map((f) => {
            const id = `copy-${code}-${f.name}`;
            const common = {
              id,
              value: copy[code][f.name] ?? "",
              maxLength: f.max,
              disabled,
              lang: code,
              dir: code === "ur" ? "rtl" : "ltr",
              onChange: (e: { target: { value: string } }) =>
                onChange({ ...copy, [code]: { ...copy[code], [f.name]: e.target.value } }),
            } as const;
            return (
              <div key={f.name} className={ui.field}>
                <label htmlFor={id}>
                  {f.label}
                  {f.name === "name" && code === "en" ? " (required)" : ""}
                </label>
                {f.long ? (
                  <textarea className={c.textarea} {...common} />
                ) : (
                  <input className={ui.input} {...common} />
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

const loadCategories = () => call(() => api.GET("/api/v1/staff/catalog/categories"));
const loadColours = () => call(() => api.GET("/api/v1/staff/catalog/colours"));

export function useCatalogLists() {
  const categories = useApiData(loadCategories).data ?? [];
  const colours = useApiData(loadColours).data ?? [];
  return { categories, colours };
}

/** Product editor: details, the colour-by-size grid, prices and publishing, each saved on its own. */
export function ProductEditor({
  product,
  onSaved,
}: {
  product: Product;
  onSaved: (p: Product) => void;
}) {
  const { can } = useSession();
  const { categories, colours } = useCatalogLists();
  const canEdit = can("catalog.edit");
  const path = { params: { path: { product_id: product.id } } };

  const [slug, setSlug] = useState(product.slug);
  const [category, setCategory] = useState(product.category);
  const [featured, setFeatured] = useState(product.is_featured);
  const [copy, setCopy] = useState(asProductCopy(product.copy));
  const [detailsMsg, setDetailsMsg] = useState<Msg>(null);

  const active = product.variant_list.filter((v) => v.is_active);
  const [pickedColours, setPickedColours] = useState(() => [
    ...new Set(active.map((v) => v.colour)),
  ]);
  const [pickedSizes, setPickedSizes] = useState(() => [...new Set(active.map((v) => v.size))]);
  const [variantsMsg, setVariantsMsg] = useState<Msg>(null);

  const [base, setBase] = useState(product.base_price);
  const [overrides, setOverrides] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      product.variant_list.filter((v) => v.price_overridden).map((v) => [v.sku, v.price]),
    ),
  );
  const [pricesMsg, setPricesMsg] = useState<Msg>(null);
  const [statusMsg, setStatusMsg] = useState<Msg>(null);

  const run = async (action: () => Promise<Product>, done: string, set: (m: Msg) => void) => {
    set(null);
    try {
      const updated = await action();
      onSaved(updated);
      set({ ok: true, text: done });
    } catch (e) {
      set({ ok: false, text: errorMessage(e) });
    }
  };
  const toggle = (list: string[], value: string, on: boolean) =>
    on ? [...list, value] : list.filter((v) => v !== value);
  const live = product.status === "published";

  return (
    <>
      <section className={ui.panel} aria-labelledby="details-title">
        <div className={c.panelHead}>
          <h2 id="details-title" className={ui.subtitle}>
            Details
          </h2>
          <span className={live ? c.statusLive : c.status}>{product.status}</span>
        </div>
        <div className={c.shared}>
          <div className={ui.field}>
            <label htmlFor="p-slug">Address: /products/…</label>
            <input
              id="p-slug"
              className={`${ui.input} ${c.mono}`}
              value={slug}
              dir="ltr"
              disabled={!canEdit || (live && !can("catalog.publish"))}
              onChange={(e) => setSlug(e.target.value.toLowerCase())}
            />
          </div>
          <div className={ui.field}>
            <label htmlFor="p-category">Category</label>
            <select
              id="p-category"
              className={ui.select}
              value={category}
              disabled={!canEdit || product.variant_list.length > 0}
              onChange={(e) => setCategory(e.target.value)}
            >
              {categories.map((cat) => (
                <option key={cat.slug} value={cat.slug}>
                  {cat.department === "women" ? "Women" : "Men"} · {cat.name_en}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label className={ui.row}>
          <input
            type="checkbox"
            checked={featured}
            disabled={!canEdit}
            onChange={(e) => setFeatured(e.target.checked)}
          />
          Featured on the homepage
        </label>
        <p className={ui.muted}>Style no. {product.style_number}</p>
        <CopyFields copy={copy} onChange={setCopy} disabled={!canEdit} />
        {canEdit && (
          <div className={c.actions}>
            <button
              className={ui.button}
              onClick={() =>
                void run(
                  () =>
                    call(() =>
                      api.PUT("/api/v1/staff/catalog/products/{product_id}", {
                        ...path,
                        body: { slug, category, is_featured: featured, copy },
                      }),
                    ),
                  live ? "Saved. The store shows it now." : "Saved.",
                  setDetailsMsg,
                )
              }
            >
              Save details
            </button>
          </div>
        )}
        <Message message={detailsMsg} />
      </section>

      <section className={ui.panel} aria-labelledby="variants-title">
        <h2 id="variants-title" className={ui.subtitle}>
          Colours and sizes
        </h2>
        <p className={ui.muted}>
          Each colour in each size is a variant with its own SKU. Taking one out hides it; its SKU
          is kept.
        </p>
        <fieldset className={c.column} disabled={!canEdit}>
          <legend className={c.columnTitle}>Colours</legend>
          <div className={ui.row}>
            {colours.map((col) => (
              <label key={col.slug} className={ui.row}>
                <input
                  type="checkbox"
                  checked={pickedColours.includes(col.slug)}
                  onChange={(e) =>
                    setPickedColours(toggle(pickedColours, col.slug, e.target.checked))
                  }
                />
                {col.name_en}
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset className={c.column} disabled={!canEdit}>
          <legend className={c.columnTitle}>
            Sizes ({categories.find((x) => x.slug === product.category)?.name_en})
          </legend>
          <div className={ui.row}>
            {product.category_sizes.map((s) => (
              <label key={s} className={ui.row}>
                <input
                  type="checkbox"
                  checked={pickedSizes.includes(s)}
                  onChange={(e) => setPickedSizes(toggle(pickedSizes, s, e.target.checked))}
                />
                {s}
              </label>
            ))}
          </div>
        </fieldset>
        {canEdit && (
          <div className={c.actions}>
            <button
              className={ui.button}
              onClick={() =>
                void run(
                  () =>
                    call(() =>
                      api.PUT("/api/v1/staff/catalog/products/{product_id}/variants", {
                        ...path,
                        body: {
                          colours: pickedColours,
                          sizes: product.category_sizes.filter((s) => pickedSizes.includes(s)),
                        },
                      }),
                    ),
                  "Colours and sizes saved.",
                  setVariantsMsg,
                )
              }
            >
              Save colours and sizes
            </button>
          </div>
        )}
        <Message message={variantsMsg} />
      </section>

      <section className={ui.panel} aria-labelledby="prices-title">
        <h2 id="prices-title" className={ui.subtitle}>
          Prices (PKR)
        </h2>
        <div className={ui.field}>
          <label htmlFor="p-base">Base price, for every variant without its own</label>
          <input
            id="p-base"
            className={ui.input}
            inputMode="decimal"
            value={base}
            disabled={!can("prices.edit")}
            onChange={(e) => setBase(e.target.value)}
          />
        </div>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">Colour</th>
              <th scope="col">Size</th>
              <th scope="col">Own price (empty: base)</th>
              <th scope="col">In stock</th>
            </tr>
          </thead>
          <tbody>
            {active.map((v) => (
              <tr key={v.sku}>
                <td className={c.mono}>{v.sku}</td>
                <td>{v.colour}</td>
                <td>{v.size}</td>
                <td>
                  <input
                    className={ui.input}
                    aria-label={`Own price for ${v.sku}`}
                    inputMode="decimal"
                    value={overrides[v.sku] ?? ""}
                    placeholder={base}
                    disabled={!can("prices.edit")}
                    onChange={(e) => setOverrides({ ...overrides, [v.sku]: e.target.value })}
                  />
                </td>
                <td>{v.available}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className={ui.muted}>Stock quantities are entered with inventory (M9).</p>
        {can("prices.edit") && (
          <div className={c.actions}>
            <button
              className={ui.button}
              onClick={() =>
                void run(
                  () =>
                    call(() =>
                      api.PUT("/api/v1/staff/catalog/products/{product_id}/prices", {
                        ...path,
                        body: {
                          base_price: base,
                          overrides: Object.fromEntries(
                            active.map((v) => [v.sku, overrides[v.sku] || null]),
                          ),
                        },
                      }),
                    ),
                  "Prices saved.",
                  setPricesMsg,
                )
              }
            >
              Save prices
            </button>
          </div>
        )}
        <Message message={pricesMsg} />
      </section>

      {can("catalog.publish") && (
        <section className={ui.panel} aria-labelledby="status-title">
          <h2 id="status-title" className={ui.subtitle}>
            Publishing
          </h2>
          {product.publish_problems.length > 0 && product.status !== "published" && (
            <ul>
              {product.publish_problems.map((p) => (
                <li key={p} className={ui.muted}>
                  {p}
                </li>
              ))}
            </ul>
          )}
          <div className={c.actions}>
            {(["published", "draft", "archived"] as const)
              .filter((s) => s !== product.status)
              .map((s) => (
                <button
                  key={s}
                  className={s === "published" ? ui.button : ui.secondary}
                  onClick={() =>
                    void run(
                      () =>
                        call(() =>
                          api.POST("/api/v1/staff/catalog/products/{product_id}/status", {
                            ...path,
                            body: { status: s },
                          }),
                        ),
                      s === "published" ? "Published. The store shows it now." : `Moved to ${s}.`,
                      setStatusMsg,
                    )
                  }
                >
                  {s === "published" ? "Publish" : s === "draft" ? "Back to draft" : "Archive"}
                </button>
              ))}
            {live && (
              <a
                className={ui.link}
                href={`/en/products/${product.slug}`}
                target="_blank"
                rel="noreferrer"
              >
                View on the store
              </a>
            )}
          </div>
          <Message message={statusMsg} />
        </section>
      )}
    </>
  );
}
