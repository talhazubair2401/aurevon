"use client";

import { useState } from "react";
import type { Schemas } from "../lib/api";
import {
  asBlocks,
  asCopy,
  BilingualFields,
  BodyBlocks,
  cleanBlocks,
  LOCALES,
  type Block,
  type Copy,
  type FieldSpec,
} from "./ContentEditor";
import c from "./content.module.css";
import ui from "./ui.module.css";

/** Title, summary, search fields and body for both languages. Body blocks are kept apart from the fields. */
export function usePageForm(source: unknown) {
  const copy = asCopy(source);
  const [fields, setFields] = useState<Copy>({
    en: Object.fromEntries(Object.entries(copy.en).filter(([k]) => k !== "body")),
    ur: Object.fromEntries(Object.entries(copy.ur).filter(([k]) => k !== "body")),
  });
  const [body, setBody] = useState<Record<"en" | "ur", Block[]>>({
    en: asBlocks(copy.en.body),
    ur: asBlocks(copy.ur.body),
  });
  const [dirty, setDirty] = useState(false);
  const content = {
    en: { ...fields.en, body: cleanBlocks(body.en) },
    ur: { ...fields.ur, body: cleanBlocks(body.ur) },
  };
  return { fields, setFields, body, setBody, dirty, setDirty, content };
}

export function PageFields({
  form,
  specs,
  disabled,
}: {
  form: ReturnType<typeof usePageForm>;
  specs: FieldSpec[] | Schemas["FieldSpecOut"][];
  disabled: boolean;
}) {
  return (
    <>
      <BilingualFields
        fields={specs}
        value={form.fields}
        idPrefix="page"
        disabled={disabled}
        onChange={(next) => {
          form.setFields(next);
          form.setDirty(true);
        }}
      />
      <h3 className={ui.subtitle}>Body</h3>
      <div className={c.bilingual}>
        {LOCALES.map(({ code, name }) => (
          <div key={code} className={c.column}>
            <p className={c.columnTitle}>{name}</p>
            <BodyBlocks
              locale={code}
              value={form.body[code]}
              disabled={disabled}
              onChange={(blocks) => {
                form.setBody({ ...form.body, [code]: blocks });
                form.setDirty(true);
              }}
            />
          </div>
        ))}
      </div>
    </>
  );
}

/** The page fields the API describes, for screens that create a page before any page exists. */
export const PAGE_FIELD_SPECS: FieldSpec[] = [
  {
    name: "title",
    label: "Title",
    kind: "text",
    max_length: 120,
    required: true,
    translatable: true,
  },
  {
    name: "summary",
    label: "Summary",
    kind: "textarea",
    max_length: 300,
    required: false,
    translatable: true,
  },
  {
    name: "seo_title",
    label: "Search title",
    kind: "text",
    max_length: 70,
    required: false,
    translatable: true,
  },
  {
    name: "seo_description",
    label: "Search description",
    kind: "textarea",
    max_length: 160,
    required: false,
    translatable: true,
  },
];
