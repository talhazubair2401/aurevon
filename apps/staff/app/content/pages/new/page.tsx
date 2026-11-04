"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ContentNav } from "../../../../components/ContentEditor";
import { PAGE_FIELD_SPECS, PageFields, usePageForm } from "../../../../components/PageForm";
import { Shell } from "../../../../components/Shell";
import c from "../../../../components/content.module.css";
import ui from "../../../../components/ui.module.css";
import { api, call, errorMessage } from "../../../../lib/api";

export default function NewPagePage() {
  return (
    <Shell>
      <h1 className={ui.title}>Content</h1>
      <ContentNav />
      <NewPage />
    </Shell>
  );
}

function NewPage() {
  const router = useRouter();
  const form = usePageForm({ en: { body: [{ type: "paragraph", text: "" }] } });
  const [slug, setSlug] = useState("");
  const [kind, setKind] = useState<"content" | "policy">("content");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const page = await call(() =>
        api.POST("/api/v1/staff/cms/pages", { body: { slug, kind, content: form.content } }),
      );
      router.replace(`/content/pages/edit?id=${page.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="new-title">
      <h2 id="new-title" className={ui.subtitle}>
        New page
      </h2>
      <p className={ui.muted}>The page is saved as a draft; publish it when it is ready.</p>
      <div className={c.shared}>
        <div className={ui.field}>
          <label htmlFor="new-slug">Address: /pages/…</label>
          <input
            id="new-slug"
            className={`${ui.input} ${c.mono}`}
            value={slug}
            placeholder="size-guide"
            dir="ltr"
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
          />
        </div>
        <div className={ui.field}>
          <label htmlFor="new-kind">Type</label>
          <select
            id="new-kind"
            className={ui.select}
            value={kind}
            onChange={(e) => setKind(e.target.value as "content" | "policy")}
          >
            <option value="content">Content page</option>
            <option value="policy">Policy page</option>
          </select>
        </div>
      </div>
      <PageFields form={form} specs={PAGE_FIELD_SPECS} disabled={busy} />
      <div className={c.actions}>
        <button className={ui.button} disabled={busy || !slug} onClick={() => void create()}>
          Create draft
        </button>
        <button className={ui.link} onClick={() => router.push("/content/pages")}>
          Cancel
        </button>
      </div>
      {error && (
        <p className={ui.error} role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
