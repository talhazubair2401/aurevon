"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { CatalogNav, Message, type Msg } from "../../../../components/CatalogNav";
import { CopyFields, asProductCopy, useCatalogLists } from "../../../../components/ProductEditor";
import { Shell } from "../../../../components/Shell";
import c from "../../../../components/content.module.css";
import ui from "../../../../components/ui.module.css";
import { api, call, errorMessage } from "../../../../lib/api";
import { useSession } from "../../../../lib/session";

export default function NewProductPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Catalogue</h1>
      <CatalogNav />
      <NewProduct />
    </Shell>
  );
}

function NewProduct() {
  const router = useRouter();
  const { can } = useSession();
  const { categories } = useCatalogLists();
  const [slug, setSlug] = useState("");
  const [category, setCategory] = useState("");
  const [base, setBase] = useState("");
  const [copy, setCopy] = useState(asProductCopy(null));
  const [message, setMessage] = useState<Msg>(null);

  const create = async () => {
    setMessage(null);
    try {
      const product = await call(() =>
        api.POST("/api/v1/staff/catalog/products", {
          body: {
            slug,
            category: category || categories[0]?.slug,
            copy,
            ...(base ? { base_price: base } : {}),
          },
        }),
      );
      router.replace(`/catalog/products/edit?id=${product.id}`);
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="new-title">
      <h2 id="new-title" className={ui.subtitle}>
        New product
      </h2>
      <p className={ui.muted}>
        Saved as a draft. Add colours and sizes next; a style number and SKUs are given
        automatically.
      </p>
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor="n-slug">Address: /products/…</label>
          <input
            id="n-slug"
            className={`${ui.input} ${c.mono}`}
            value={slug}
            dir="ltr"
            placeholder="linen-kurta"
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor="n-category">Category</label>
          <select
            id="n-category"
            className={ui.select}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {categories.map((cat) => (
              <option key={cat.slug} value={cat.slug}>
                {cat.department === "women" ? "Women" : "Men"} · {cat.name_en}
              </option>
            ))}
          </select>
        </div>
        {can("prices.edit") && (
          <div className={ui.field}>
            <label htmlFor="n-price">Base price (PKR)</label>
            <input
              id="n-price"
              className={ui.input}
              inputMode="decimal"
              value={base}
              onChange={(e) => setBase(e.target.value)}
            />
          </div>
        )}
      </div>
      <CopyFields copy={copy} onChange={setCopy} disabled={false} />
      <div className={c.actions}>
        <button className={ui.button} disabled={!slug} onClick={() => void create()}>
          Create draft
        </button>
      </div>
      <Message message={message} />
    </section>
  );
}
