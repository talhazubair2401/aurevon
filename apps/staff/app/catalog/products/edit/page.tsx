"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { CatalogNav } from "../../../../components/CatalogNav";
import { ProductEditor } from "../../../../components/ProductEditor";
import { Shell } from "../../../../components/Shell";
import ui from "../../../../components/ui.module.css";
import { api, call, useApiData, type Schemas } from "../../../../lib/api";

export default function EditProductPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Catalogue</h1>
      <CatalogNav />
      <Suspense fallback={<p className={ui.muted}>Loading…</p>}>
        <Loader />
      </Suspense>
    </Shell>
  );
}

function Loader() {
  const id = useSearchParams().get("id") ?? "";
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/catalog/products/{product_id}", {
          params: { path: { product_id: id } },
        }),
      ),
    [id],
  );
  const { data, error } = useApiData(load);
  const [saved, setSaved] = useState<Schemas["ProductOut"] | null>(null);
  const product = saved ?? data;
  if (error) return <p className={ui.error}>{error}</p>;
  if (!product) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <p>
        <Link href="/catalog" className={ui.link}>
          ← All products
        </Link>
      </p>
      <ProductEditor key={product.id} product={product} onSaved={setSaved} />
    </>
  );
}
