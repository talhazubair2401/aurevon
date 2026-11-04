"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Schemas } from "../lib/api";
import c from "./content.module.css";
import ui from "./ui.module.css";

/**
 * Building blocks for the content and SEO screens (M4). Every value is plain text; links are storefront paths
 * (/shop?department=women). The API checks everything again and is the final authority (MTS §3).
 */
export type FieldSpec = Schemas["FieldSpecOut"];
export type Locale = "en" | "ur";
export type Copy = Record<Locale, Record<string, unknown>>;

export const LOCALES: Array<{ code: Locale; name: string }> = [
  { code: "en", name: "English" },
  { code: "ur", name: "Urdu (optional, falls back to English)" },
];

export function asCopy(value: unknown): Copy {
  const v = (value && typeof value === "object" ? value : {}) as Partial<Copy>;
  return { en: { ...(v.en ?? {}) }, ur: { ...(v.ur ?? {}) } };
}

export function ContentNav() {
  const pathname = usePathname();
  const links = [
    { href: "/content", label: "Homepage" },
    { href: "/content/banners", label: "Banners" },
    { href: "/content/pages", label: "Pages" },
    { href: "/content/navigation", label: "Navigation" },
  ];
  return (
    <nav className={c.subnav} aria-label="Content">
      {links.map((link) => {
        const active =
          link.href === "/content" ? pathname === "/content" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={active ? c.subnavActive : c.subnavLink}
            aria-current={active ? "page" : undefined}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function SeoNav() {
  const pathname = usePathname();
  return (
    <nav className={c.subnav} aria-label="SEO">
      {[
        { href: "/seo", label: "Search titles and descriptions" },
        { href: "/seo/redirects", label: "Redirects" },
      ].map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={pathname === link.href ? c.subnavActive : c.subnavLink}
          aria-current={pathname === link.href ? "page" : undefined}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}

export function Status({ live, draft }: { live: boolean; draft: boolean }) {
  return (
    <span className={ui.row}>
      <span className={live ? c.statusLive : c.status}>{live ? "Live" : "Not published"}</span>
      {draft && <span className={c.statusDraft}>Unpublished changes</span>}
    </span>
  );
}

function Field({
  field,
  locale,
  value,
  onChange,
  disabled,
  idPrefix,
}: {
  field: FieldSpec;
  locale: Locale;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  idPrefix: string;
}) {
  const id = `${idPrefix}-${locale}-${field.name}`;
  const urdu = locale === "ur";
  const common = {
    id,
    value,
    disabled,
    maxLength: field.max_length,
    lang: locale,
    dir: urdu ? "rtl" : "ltr",
    onChange: (e: { target: { value: string } }) => onChange(e.target.value),
  } as const;
  const required = field.required && locale === "en";
  return (
    <div className={ui.field}>
      <label htmlFor={id}>
        {field.label}
        {required ? " (required)" : ""}
        {field.kind === "href" ? " — a storefront path, such as /shop" : ""}
      </label>
      {field.kind === "textarea" ? (
        <textarea className={`${c.textarea} ${urdu ? c.urdu : ""}`} {...common} />
      ) : (
        <input
          className={`${ui.input} ${urdu ? c.urdu : ""} ${field.kind === "href" ? c.mono : ""}`}
          {...common}
          {...(field.kind === "href" ? { dir: "ltr", inputMode: "url" as const } : {})}
        />
      )}
      <span className={c.counter} aria-hidden="true">
        {value.length}/{field.max_length}
      </span>
    </div>
  );
}

/** English and Urdu side by side. Links are shared by both languages and edited once, in the English column. */
export function BilingualFields({
  fields,
  value,
  onChange,
  disabled = false,
  idPrefix,
}: {
  fields: FieldSpec[];
  value: Copy;
  onChange: (next: Copy) => void;
  disabled?: boolean;
  idPrefix: string;
}) {
  const set = (locale: Locale, name: string, text: string) =>
    onChange({ ...value, [locale]: { ...value[locale], [name]: text } });
  const shared = fields.filter((f) => !f.translatable);
  return (
    <>
      <div className={c.bilingual}>
        {LOCALES.map(({ code, name }) => (
          <div key={code} className={c.column}>
            <p className={c.columnTitle}>{name}</p>
            {fields
              .filter((f) => f.translatable)
              .map((f) => (
                <Field
                  key={f.name}
                  field={f}
                  locale={code}
                  value={String(value[code][f.name] ?? "")}
                  onChange={(text) => set(code, f.name, text)}
                  disabled={disabled}
                  idPrefix={idPrefix}
                />
              ))}
          </div>
        ))}
      </div>
      {shared.length > 0 && (
        <div className={c.shared}>
          {shared.map((f) => (
            <Field
              key={f.name}
              field={f}
              locale="en"
              value={String(value.en[f.name] ?? "")}
              onChange={(text) => set("en", f.name, text)}
              disabled={disabled}
              idPrefix={idPrefix}
            />
          ))}
        </div>
      )}
    </>
  );
}

export interface Block {
  type: "heading" | "paragraph" | "list";
  text?: string;
  items?: string[];
}

export function asBlocks(value: unknown): Block[] {
  return Array.isArray(value) ? (value as Block[]) : [];
}

/** A page body: headings, paragraphs and bulleted lists, as plain text. */
export function BodyBlocks({
  value,
  onChange,
  locale,
  disabled = false,
}: {
  value: Block[];
  onChange: (next: Block[]) => void;
  locale: Locale;
  disabled?: boolean;
}) {
  const update = (index: number, block: Block) =>
    onChange(value.map((b, i) => (i === index ? block : b)));
  const move = (index: number, by: number) => {
    const next = [...value];
    const [item] = next.splice(index, 1);
    next.splice(index + by, 0, item!);
    onChange(next);
  };
  const urdu = locale === "ur";
  return (
    <div className={c.column}>
      {value.map((block, index) => {
        const id = `block-${locale}-${index}`;
        return (
          <div key={index} className={c.block}>
            <div className={c.blockTools}>
              <label htmlFor={`${id}-type`} className={c.columnTitle}>
                Block {index + 1}
              </label>
              <select
                id={`${id}-type`}
                className={ui.select}
                value={block.type}
                disabled={disabled}
                onChange={(e) => {
                  const type = e.target.value as Block["type"];
                  const text =
                    block.type === "list" ? (block.items ?? []).join("\n") : (block.text ?? "");
                  update(
                    index,
                    type === "list" ? { type, items: text.split("\n") } : { type, text },
                  );
                }}
              >
                <option value="heading">Heading</option>
                <option value="paragraph">Paragraph</option>
                <option value="list">Bulleted list</option>
              </select>
              <button
                type="button"
                className={c.small}
                disabled={disabled || index === 0}
                onClick={() => move(index, -1)}
                aria-label={`Move block ${index + 1} up`}
              >
                ↑
              </button>
              <button
                type="button"
                className={c.small}
                disabled={disabled || index === value.length - 1}
                onClick={() => move(index, 1)}
                aria-label={`Move block ${index + 1} down`}
              >
                ↓
              </button>
              <button
                type="button"
                className={c.small}
                disabled={disabled}
                onClick={() => onChange(value.filter((_, i) => i !== index))}
              >
                Remove
              </button>
            </div>
            <textarea
              id={id}
              aria-label={`Block ${index + 1} ${block.type === "list" ? "items, one per line" : "text"}`}
              className={`${c.textarea} ${urdu ? c.urdu : ""}`}
              lang={locale}
              dir={urdu ? "rtl" : "ltr"}
              disabled={disabled}
              rows={block.type === "heading" ? 1 : 4}
              value={block.type === "list" ? (block.items ?? []).join("\n") : (block.text ?? "")}
              placeholder={block.type === "list" ? "One item per line" : undefined}
              onChange={(e) =>
                update(
                  index,
                  block.type === "list"
                    ? { type: "list", items: e.target.value.split("\n") }
                    : { type: block.type, text: e.target.value },
                )
              }
            />
          </div>
        );
      })}
      <div className={c.blockTools}>
        {(["paragraph", "heading", "list"] as const).map((type) => (
          <button
            key={type}
            type="button"
            className={c.small}
            disabled={disabled}
            onClick={() =>
              onChange([...value, type === "list" ? { type, items: [""] } : { type, text: "" }])
            }
          >
            Add {type === "list" ? "list" : type}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Strips empty list lines before sending; the API drops empty blocks itself. */
export function cleanBlocks(blocks: Block[]): Block[] {
  return blocks.map((b) =>
    b.type === "list" ? { type: "list", items: (b.items ?? []).filter((i) => i.trim()) } : b,
  );
}

/** Storefront address of a path, for "view on the store" links. The staff app lives under /staff. */
export function storefrontUrl(path: string, locale: Locale = "en"): string {
  return path === "/" ? `/${locale}` : `/${locale}${path}`;
}
