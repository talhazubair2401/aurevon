"use client";

import { useState } from "react";
import { CatalogNav, Message, type Msg } from "../../../components/CatalogNav";
import { Shell } from "../../../components/Shell";
import c from "../../../components/content.module.css";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Category = Schemas["CategoryOut"];
type Row = { en: string; ur: string; values: Record<string, string> };
const loadCategories = () => call(() => api.GET("/api/v1/staff/catalog/categories"));

export default function CategoriesPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Catalogue</h1>
      <CatalogNav />
      <Categories />
    </Shell>
  );
}

function Categories() {
  const { can } = useSession();
  const { data: rows, error, reload } = useApiData(loadCategories);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!rows) return <p className={ui.muted}>Loading…</p>;
  const canEdit = can("catalog.edit");
  return (
    <>
      <p className={ui.muted}>
        Each category has its own sizes, in order: letters (XS, S, M…) or numbers (28, 30, 32…), and
        its own size chart in centimetres.
      </p>
      {rows.map((cat) => (
        <CategoryEditor key={cat.slug} category={cat} canEdit={canEdit} onSaved={reload} />
      ))}
      {canEdit && <CategoryEditor category={null} canEdit onSaved={reload} />}
    </>
  );
}

function CategoryEditor({
  category,
  canEdit,
  onSaved,
}: {
  category: Category | null;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const key = category?.slug ?? "new";
  const [slug, setSlug] = useState(category?.slug ?? "");
  const [department, setDepartment] = useState(category?.department ?? "women");
  const [code, setCode] = useState(category?.code ?? "");
  const [nameEn, setNameEn] = useState(category?.name_en ?? "");
  const [nameUr, setNameUr] = useState(category?.name_ur ?? "");
  const [sizesText, setSizesText] = useState((category?.sizes ?? []).join(", "));
  const [chart, setChart] = useState<Row[]>(
    (category?.size_chart ?? []).map((r) => ({
      en: r.name.en ?? "",
      ur: r.name.ur ?? "",
      values: { ...r.values },
    })),
  );
  const [message, setMessage] = useState<Msg>(null);
  const sizes = sizesText
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);

  const save = async () => {
    setMessage(null);
    const body = {
      slug,
      department,
      code: code.toUpperCase(),
      name_en: nameEn,
      name_ur: nameUr,
      sizes,
      size_chart: chart.map((r) => ({
        name: { en: r.en, ur: r.ur },
        values: Object.fromEntries(sizes.map((s) => [s, r.values[s] ?? ""]).filter(([, v]) => v)),
      })),
      products: 0,
    };
    try {
      if (category)
        await call(() =>
          api.PUT("/api/v1/staff/catalog/categories/{slug}", {
            params: { path: { slug: category.slug } },
            body,
          }),
        );
      else await call(() => api.POST("/api/v1/staff/catalog/categories", { body }));
      setMessage({ ok: true, text: "Saved." });
      onSaved();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };
  const id = (f: string) => `${key}-${f}`;

  return (
    <section className={ui.panel} aria-labelledby={id("title")}>
      <div className={c.panelHead}>
        <h2 id={id("title")} className={ui.subtitle}>
          {category
            ? `${category.department === "women" ? "Women" : "Men"} · ${category.name_en}`
            : "New category"}
        </h2>
        {category && <span className={c.mono}>{category.products} products</span>}
      </div>
      <div className={c.shared}>
        {!category && (
          <>
            <div className={ui.field}>
              <label htmlFor={id("slug")}>Address</label>
              <input
                id={id("slug")}
                className={`${ui.input} ${c.mono}`}
                value={slug}
                placeholder="women-jeans"
                onChange={(e) => setSlug(e.target.value.toLowerCase())}
              />
            </div>
            <div className={ui.field}>
              <label htmlFor={id("dept")}>Department</label>
              <select
                id={id("dept")}
                className={ui.select}
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option value="women">Women</option>
                <option value="men">Men</option>
              </select>
            </div>
          </>
        )}
        <div className={ui.field}>
          <label htmlFor={id("code")}>SKU code (3 letters)</label>
          <input
            id={id("code")}
            className={`${ui.input} ${c.mono}`}
            value={code}
            maxLength={3}
            disabled={!canEdit || (category?.products ?? 0) > 0}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={id("en")}>English name</label>
          <input
            id={id("en")}
            className={ui.input}
            value={nameEn}
            disabled={!canEdit}
            onChange={(e) => setNameEn(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={id("ur")}>Urdu name</label>
          <input
            id={id("ur")}
            className={ui.input}
            lang="ur"
            dir="rtl"
            value={nameUr}
            disabled={!canEdit}
            onChange={(e) => setNameUr(e.target.value)}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor={id("sizes")}>Sizes, in order, separated by commas</label>
          <input
            id={id("sizes")}
            className={`${ui.input} ${c.mono}`}
            value={sizesText}
            disabled={!canEdit}
            placeholder="XS, S, M, L, XL or 28, 30, 32"
            onChange={(e) => setSizesText(e.target.value)}
          />
        </div>
      </div>
      <h3 className={c.columnTitle}>Size chart (cm)</h3>
      <div className={c.chartWrap}>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Measurement (English)</th>
              <th scope="col">Urdu</th>
              {sizes.map((s) => (
                <th key={s} scope="col">
                  {s}
                </th>
              ))}
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {chart.map((row, index) => (
              <tr key={index}>
                <td>
                  <input
                    aria-label={`Measurement ${index + 1}`}
                    className={ui.input}
                    value={row.en}
                    disabled={!canEdit}
                    onChange={(e) =>
                      setChart(
                        chart.map((r, i) => (i === index ? { ...r, en: e.target.value } : r)),
                      )
                    }
                  />
                </td>
                <td>
                  <input
                    aria-label={`Measurement ${index + 1} in Urdu`}
                    className={ui.input}
                    lang="ur"
                    dir="rtl"
                    value={row.ur}
                    disabled={!canEdit}
                    onChange={(e) =>
                      setChart(
                        chart.map((r, i) => (i === index ? { ...r, ur: e.target.value } : r)),
                      )
                    }
                  />
                </td>
                {sizes.map((s) => (
                  <td key={s}>
                    <input
                      aria-label={`${row.en || `Measurement ${index + 1}`}, size ${s}, cm`}
                      className={`${ui.input} ${c.cm}`}
                      inputMode="decimal"
                      value={row.values[s] ?? ""}
                      disabled={!canEdit}
                      onChange={(e) =>
                        setChart(
                          chart.map((r, i) =>
                            i === index
                              ? { ...r, values: { ...r.values, [s]: e.target.value } }
                              : r,
                          ),
                        )
                      }
                    />
                  </td>
                ))}
                <td>
                  {canEdit && (
                    <button
                      className={c.small}
                      onClick={() => setChart(chart.filter((_, i) => i !== index))}
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canEdit && (
        <div className={c.actions}>
          <button
            className={ui.secondary}
            onClick={() => setChart([...chart, { en: "", ur: "", values: {} }])}
          >
            Add measurement
          </button>
          <button className={ui.button} onClick={() => void save()}>
            {category ? "Save category" : "Add category"}
          </button>
        </div>
      )}
      <Message message={message} />
    </section>
  );
}
