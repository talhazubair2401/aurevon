"use client";

import Link from "next/link";
import { ContentNav, Status, storefrontUrl } from "../../../components/ContentEditor";
import { Shell } from "../../../components/Shell";
import ui from "../../../components/ui.module.css";
import { api, call, formatTime, useApiData } from "../../../lib/api";
import { useSession } from "../../../lib/session";

export default function PagesPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Content</h1>
      <ContentNav />
      <Pages />
    </Shell>
  );
}

const loadPages = () => call(() => api.GET("/api/v1/staff/cms/pages"));

function Pages() {
  const { can } = useSession();
  const { data: pages, error } = useApiData(loadPages);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!pages) return <p className={ui.muted}>Loading…</p>;

  return (
    <>
      <div className={ui.row}>
        <p className={ui.muted}>
          Content pages (our story, contact) and policy pages (shipping, returns, privacy, terms),
          at /pages/… on the store.
        </p>
        {can("cms.edit") && (
          <Link href="/content/pages/new" className={ui.button}>
            New page
          </Link>
        )}
      </div>
      <table className={ui.table}>
        <thead>
          <tr>
            <th scope="col">Page</th>
            <th scope="col">Type</th>
            <th scope="col">Status</th>
            <th scope="col">Updated</th>
          </tr>
        </thead>
        <tbody>
          {pages.map((page) => (
            <tr key={page.id}>
              <td>
                <Link href={`/content/pages/edit?id=${page.id}`}>{page.title}</Link>
                <br />
                {page.is_published ? (
                  <a
                    className={ui.link}
                    href={storefrontUrl(page.path)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {page.path}
                  </a>
                ) : (
                  <span className={ui.muted}>{page.path}</span>
                )}
              </td>
              <td>
                <span className={ui.tag}>{page.kind}</span>
              </td>
              <td>
                <Status live={page.is_published} draft={page.has_draft} />
              </td>
              <td>{formatTime(page.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
