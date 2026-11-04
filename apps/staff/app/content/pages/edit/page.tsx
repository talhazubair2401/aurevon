"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { ContentNav, Status, storefrontUrl } from "../../../../components/ContentEditor";
import { PageFields, usePageForm } from "../../../../components/PageForm";
import { Shell } from "../../../../components/Shell";
import c from "../../../../components/content.module.css";
import ui from "../../../../components/ui.module.css";
import { api, call, errorMessage, useApiData, type Schemas } from "../../../../lib/api";
import { useSession } from "../../../../lib/session";

type Page = Schemas["PageOut"];

export default function EditPagePage() {
  return (
    <Shell>
      <h1 className={ui.title}>Content</h1>
      <ContentNav />
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
        api.GET("/api/v1/staff/cms/pages/{page_id}", { params: { path: { page_id: id } } }),
      ),
    [id],
  );
  const { data: page, error, reload } = useApiData(load);
  // Kept here so a confirmation survives the editor reloading the saved page.
  const [message, setMessage] = useState<Message>(null);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!page) return <p className={ui.muted}>Loading…</p>;
  return (
    <Editor
      key={page.updated_at}
      page={page}
      onChanged={reload}
      message={message}
      setMessage={setMessage}
    />
  );
}

type Message = { ok: boolean; text: string } | null;

function Editor({
  page,
  onChanged,
  message,
  setMessage,
}: {
  page: Page;
  onChanged: () => void;
  message: Message;
  setMessage: (m: Message) => void;
}) {
  const { can } = useSession();
  const router = useRouter();
  const form = usePageForm(page.draft ?? page.content);
  const [slug, setSlug] = useState(page.slug);
  const [kind, setKind] = useState(page.kind);
  const [busy, setBusy] = useState(false);
  const canEdit = can("cms.edit");
  const canPublish = can("cms.publish");
  const path = { params: { path: { page_id: page.id } } };

  const run = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage({ ok: true, text: done });
      onChanged();
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const saveDraft = () =>
    call(() =>
      api.PUT("/api/v1/staff/cms/pages/{page_id}/draft", {
        ...path,
        body: { content: form.content },
      }),
    );

  return (
    <>
      <p>
        <button className={ui.link} onClick={() => router.push("/content/pages")}>
          ← All pages
        </button>
      </p>
      <section className={ui.panel} aria-labelledby="settings-title">
        <div className={c.panelHead}>
          <h2 id="settings-title" className={ui.subtitle}>
            {page.title}
          </h2>
          <Status live={page.is_published} draft={page.has_draft || form.dirty} />
        </div>
        <div className={c.shared}>
          <div className={ui.field}>
            <label htmlFor="page-slug">Address: /pages/…</label>
            <input
              id="page-slug"
              className={`${ui.input} ${c.mono}`}
              value={slug}
              disabled={!canEdit || busy || (page.is_published && !canPublish)}
              onChange={(e) => setSlug(e.target.value.toLowerCase())}
              dir="ltr"
            />
          </div>
          <div className={ui.field}>
            <label htmlFor="page-kind">Type</label>
            <select
              id="page-kind"
              className={ui.select}
              value={kind}
              disabled={!canEdit || busy}
              onChange={(e) => setKind(e.target.value as Page["kind"])}
            >
              <option value="content">Content page</option>
              <option value="policy">Policy page</option>
            </select>
          </div>
        </div>
        {page.is_published && slug !== page.slug && (
          <p className={ui.muted}>
            The old address /pages/{page.slug} will redirect to the new one, so existing links keep
            working.
          </p>
        )}
        {canEdit && (
          <div className={c.actions}>
            <button
              className={ui.secondary}
              disabled={busy || (slug === page.slug && kind === page.kind)}
              onClick={() =>
                void run(
                  () =>
                    call(() =>
                      api.PUT("/api/v1/staff/cms/pages/{page_id}", {
                        ...path,
                        body: { slug, kind },
                      }),
                    ),
                  "Page settings saved.",
                )
              }
            >
              Save settings
            </button>
          </div>
        )}
      </section>

      <section className={ui.panel} aria-labelledby="content-title">
        <h2 id="content-title" className={ui.subtitle}>
          Page content
        </h2>
        <PageFields form={form} specs={page.fields} disabled={!canEdit || busy} />
        <div className={c.actions}>
          {canEdit && (
            <button
              className={ui.secondary}
              disabled={busy || !form.dirty}
              onClick={() =>
                void run(saveDraft, "Draft saved. Shoppers still see the published version.")
              }
            >
              Save draft
            </button>
          )}
          {canPublish && (
            <button
              className={ui.button}
              disabled={busy || (!form.dirty && !page.has_draft && page.is_published)}
              onClick={() =>
                void run(async () => {
                  if (form.dirty) await saveDraft();
                  return call(() => api.POST("/api/v1/staff/cms/pages/{page_id}/publish", path));
                }, "Published. The store shows it now.")
              }
            >
              Publish
            </button>
          )}
          {canEdit && page.has_draft && (
            <button
              className={ui.link}
              disabled={busy}
              onClick={() =>
                void run(
                  () => call(() => api.DELETE("/api/v1/staff/cms/pages/{page_id}/draft", path)),
                  "Unpublished changes discarded.",
                )
              }
            >
              Discard changes
            </button>
          )}
          {canPublish && page.is_published && (
            <button
              className={ui.link}
              disabled={busy}
              onClick={() =>
                void run(
                  () => call(() => api.POST("/api/v1/staff/cms/pages/{page_id}/unpublish", path)),
                  "Unpublished. The page is no longer on the store.",
                )
              }
            >
              Unpublish
            </button>
          )}
          {page.is_published && (
            <a className={ui.link} href={storefrontUrl(page.path)} target="_blank" rel="noreferrer">
              View on the store
            </a>
          )}
        </div>
        {message && (
          <p className={message.ok ? ui.success : ui.error} role="status">
            {message.text}
          </p>
        )}
      </section>
    </>
  );
}
