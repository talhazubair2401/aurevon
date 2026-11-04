import type { AnchorHTMLAttributes, ElementType, HTMLAttributes, ReactNode } from "react";
import { formatMoney, type Locale } from "@aurevon/i18n";
import { interimWordmark } from "@aurevon/design-tokens";
import styles from "./Primitives.module.css";

function cx(...names: Array<string | false | undefined>): string {
  return names.filter(Boolean).join(" ");
}

/** Hidden visually, still read by screen readers. */
export function VisuallyHidden({ children, ...rest }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span {...rest} className={cx(styles.visuallyHidden, rest.className)}>
      {children}
    </span>
  );
}

/** First focusable element on every page (WCAG 2.4.1). Target must have the given id and tabIndex={-1}. */
export function SkipLink({ href = "#main", children }: { href?: string; children: ReactNode }) {
  return (
    <a className={styles.skipLink} href={href}>
      {children}
    </a>
  );
}

/**
 * The interim AUREVON wordmark in Playfair Display capitals (decision 0004, item 6), until an official logo
 * is supplied. Always Latin and left-to-right, including on Urdu pages.
 */
export function Wordmark({
  as: Tag = "span",
  size = "md",
  className,
  ...rest
}: Omit<HTMLAttributes<HTMLElement>, "children" | "lang" | "dir"> & {
  as?: ElementType;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <Tag
      {...rest}
      lang="en"
      dir="ltr"
      className={cx(styles.wordmark, styles[`wordmark-${size}`], className)}
    >
      {interimWordmark}
    </Tag>
  );
}

/** Centred content column: max width 1440px with responsive gutters (P-19 default). */
export function Container({
  as: Tag = "div",
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLElement> & { as?: ElementType }) {
  return (
    <Tag {...rest} className={cx(styles.container, className)}>
      {children}
    </Tag>
  );
}

/** Underlined text link; underline thickens on hover so the cue never depends on colour alone. */
export function TextLink({
  className,
  children,
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a {...rest} className={cx(styles.link, className)}>
      {children}
    </a>
  );
}

export type AlertTone = "info" | "success" | "error";

/**
 * Inline message. Errors use role="alert" (announced at once); info and success use role="status".
 * Meaning is carried by text and a title, never by colour alone.
 */
export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx(styles.alert, styles[`alert-${tone}`])}
    >
      {title ? <p className={styles.alertTitle}>{title}</p> : null}
      {children ? <div className={styles.alertBody}>{children}</div> : null}
    </div>
  );
}

/** A price from the API's decimal string (MTS §8). Formats only; the server is authoritative (A-15). */
export function Price({
  amount,
  currency,
  locale,
  className,
}: {
  amount: string;
  currency?: string;
  locale: Locale;
  className?: string;
}) {
  return (
    <span className={cx(styles.price, className)} dir="ltr">
      {formatMoney(amount, locale, currency)}
    </span>
  );
}
