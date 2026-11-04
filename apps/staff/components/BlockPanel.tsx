"use client";

import { useState, type ReactNode } from "react";
import { errorMessage, type Schemas } from "../lib/api";
import { asCopy, BilingualFields, Status, type Copy } from "./ContentEditor";
import c from "./content.module.css";
import ui from "./ui.module.css";

type Item = Schemas["EditableBlockOut"];

/**
 * One homepage section or banner: edit, save as a draft, publish, or discard the draft. Shoppers see only
 * published content; "Publish" saves the form first, so what is published is exactly what is on screen.
 */
export function BlockPanel({
  item,
  canEdit,
  canPublish,
  onSaveDraft,
  onPublish,
  onDiscard,
  extra,
  viewHref,
}: {
  item: Item;
  canEdit: boolean;
  canPublish: boolean;
  onSaveDraft: (content: Copy) => Promise<Item>;
  onPublish: () => Promise<Item>;
  onDiscard: () => Promise<Item>;
  extra?: ReactNode;
  viewHref: string;
}) {
  // The latest saved state of this item, from each action's response (no page reload needed).
  const [current, setCurrent] = useState<Item>(item);
  const [value, setValue] = useState<Copy>(asCopy(item.draft ?? item.content));
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const hasDraft = current.draft !== null && current.draft !== undefined;

  const run = async (action: () => Promise<Item>, done: string, reset = false) => {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await action();
      setCurrent(updated);
      if (reset) setValue(asCopy(updated.draft ?? updated.content));
      setDirty(false);
      setMessage({ ok: true, text: done });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className={ui.panel}
      aria-labelledby={`panel-${item.key}`}
      data-testid={`panel-${item.key}`}
    >
      <div className={c.panelHead}>
        <h2 id={`panel-${item.key}`} className={ui.subtitle}>
          {item.label}
        </h2>
        <Status live={item.is_enabled} draft={hasDraft || dirty} />
      </div>
      {extra}
      <BilingualFields
        fields={item.fields}
        value={value}
        idPrefix={item.key}
        disabled={!canEdit || busy}
        onChange={(next) => {
          setValue(next);
          setDirty(true);
        }}
      />
      <div className={c.actions}>
        {canEdit && (
          <button
            className={ui.secondary}
            disabled={busy || !dirty}
            onClick={() =>
              void run(
                () => onSaveDraft(value),
                "Draft saved. Shoppers still see the published version.",
              )
            }
          >
            Save draft
          </button>
        )}
        {canPublish && (
          <button
            className={ui.button}
            disabled={busy || (!dirty && !hasDraft)}
            onClick={() =>
              void run(async () => {
                if (dirty) await onSaveDraft(value);
                return onPublish();
              }, "Published. The store shows it now.")
            }
          >
            Publish
          </button>
        )}
        {canEdit && (hasDraft || dirty) && (
          <button
            className={ui.link}
            disabled={busy}
            onClick={() =>
              void run(
                async () => (hasDraft ? onDiscard() : { ...current, draft: null }),
                "Changes discarded.",
                true,
              )
            }
          >
            Discard changes
          </button>
        )}
        <a className={ui.link} href={viewHref} target="_blank" rel="noreferrer">
          View on the store
        </a>
        {!canPublish && canEdit && (
          <span className={ui.muted}>Someone with publishing rights makes drafts live.</span>
        )}
      </div>
      {message && (
        <p className={message.ok ? ui.success : ui.error} role="status">
          {message.text}
        </p>
      )}
    </section>
  );
}
