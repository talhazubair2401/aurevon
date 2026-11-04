"use client";

import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import styles from "./Field.module.css";

interface FieldText {
  /** Visible label; every field has one (WCAG 3.3.2). */
  label: ReactNode;
  /** Help shown under the label, linked with aria-describedby. */
  hint?: ReactNode;
  /** Validation message. Sets aria-invalid and is linked with aria-describedby. */
  error?: ReactNode;
  /** Shown as "(optional)" next to the label; required fields stay unmarked, as most fields are required. */
  optionalLabel?: ReactNode;
}

function useFieldIds(id?: string) {
  const generated = useId();
  const base = id ?? `f${generated.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return { id: base, hint: `${base}-hint`, error: `${base}-error` };
}

function describedBy(
  ids: ReturnType<typeof useFieldIds>,
  hint: unknown,
  error: unknown,
  extra?: string,
) {
  return (
    [hint ? ids.hint : "", error ? ids.error : "", extra ?? ""].filter(Boolean).join(" ") ||
    undefined
  );
}

function Label({
  htmlFor,
  label,
  optionalLabel,
}: { htmlFor: string } & Pick<FieldText, "label" | "optionalLabel">) {
  return (
    <label className={styles.label} htmlFor={htmlFor}>
      {label}
      {optionalLabel ? <span className={styles.optional}> {optionalLabel}</span> : null}
    </label>
  );
}

function Messages({
  ids,
  hint,
  error,
}: { ids: ReturnType<typeof useFieldIds> } & Pick<FieldText, "hint" | "error">) {
  return (
    <>
      {hint ? (
        <p id={ids.hint} className={styles.hint}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={ids.error} className={styles.error}>
          {error}
        </p>
      ) : null}
    </>
  );
}

export interface TextFieldProps
  extends FieldText, Omit<InputHTMLAttributes<HTMLInputElement>, "children"> {}

export function TextField({
  label,
  hint,
  error,
  optionalLabel,
  id,
  className,
  ...input
}: TextFieldProps) {
  const ids = useFieldIds(id);
  return (
    <div className={[styles.field, className ?? ""].filter(Boolean).join(" ")}>
      <Label htmlFor={ids.id} label={label} optionalLabel={optionalLabel} />
      <Messages ids={ids} hint={hint} error={error} />
      <input
        {...input}
        id={ids.id}
        className={styles.control}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(ids, hint, error, input["aria-describedby"])}
      />
    </div>
  );
}

export interface SelectFieldProps extends FieldText, SelectHTMLAttributes<HTMLSelectElement> {}

export function SelectField({
  label,
  hint,
  error,
  optionalLabel,
  id,
  className,
  children,
  ...select
}: SelectFieldProps) {
  const ids = useFieldIds(id);
  return (
    <div className={[styles.field, className ?? ""].filter(Boolean).join(" ")}>
      <Label htmlFor={ids.id} label={label} optionalLabel={optionalLabel} />
      <Messages ids={ids} hint={hint} error={error} />
      <select
        {...select}
        id={ids.id}
        className={[styles.control, styles.select].join(" ")}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(ids, hint, error, select["aria-describedby"])}
      >
        {children}
      </select>
    </div>
  );
}

export interface CheckboxFieldProps
  extends
    Omit<FieldText, "optionalLabel">,
    Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "children"> {}

export function CheckboxField({ label, hint, error, id, className, ...input }: CheckboxFieldProps) {
  const ids = useFieldIds(id);
  return (
    <div className={[styles.checkboxField, className ?? ""].filter(Boolean).join(" ")}>
      <input
        {...input}
        type="checkbox"
        id={ids.id}
        className={styles.checkbox}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(ids, hint, error, input["aria-describedby"])}
      />
      <div>
        <label className={styles.checkboxLabel} htmlFor={ids.id}>
          {label}
        </label>
        <Messages ids={ids} hint={hint} error={error} />
      </div>
    </div>
  );
}
