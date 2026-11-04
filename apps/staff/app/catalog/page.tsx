"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { CatalogNav } from "../../components/CatalogNav";
import { Shell } from "../../components/Shell";
import ui from "../../components/ui.module.css";
import { api, call, formatTime, useApiData } from "../../lib/api";
import { useSession } from "../../lib/session";

export default function CatalogPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Catalogue</h1>
      <CatalogNav />
      <Products />
    </Shell>
  );
}

type Status = "" | "draft" | "published" | "archived";

function Products() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status>("");
  const load = useCallback(
    () =>
      call(() =>
        api.GET("/api/v1/staff/catalog/products", {
          params: { query: { ...(query ? { q: query } : {}), ...(status ? { status } : {}) } },
        }),
      ),
    [query, status],
  );
  const { data: rows, error } = useApiData(load);

  return (
    <>
      <form
        className={ui.row}
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(q.trim());
        }}
      >
        <input
          className={ui.input}
          aria-label="Search by name, address or SKU"
          placeholder="Name, address or SKU"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          className={ui.select}
          aria-label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value as Status)}
        >
          <option value="">All statuses</option>
          <option value="draft">Drafts</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
        <button className={ui.secondary} type="submit">
          Search
        </button>
        {can("catalog.edit") && (
          <Link href="/catalog/products/new" className={ui.button}>
            New product
          </Link>
        )}
      </form>
      {error && <p className={ui.error}>{error}</p>}
      {!rows ? (
        <p className={ui.muted}>Loading…</p>
      ) : (
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Product</th>
              <th scope="col">Style</th>
              <th scope="col">Category</th>
              <th scope="col">Base price</th>
              <th scope="col">Variants</th>
              <th scope="col">Status</th>
              <th scope="col">Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link href={`/catalog/products/edit?id=${p.id}`}>{p.name}</Link>
                </td>
                <td>{p.style_number}</td>
                <td>{p.category}</td>
                <td>PKR {p.base_price}</td>
                <td>{p.variants}</td>
                <td>
                  <span className={ui.tag}>{p.status}</span>
                </td>
                <td>{formatTime(p.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
