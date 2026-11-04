import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "text";
export type ButtonSize = "md" | "lg";

interface Common {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Stretch to the container width (mobile forms, checkout). */
  block?: boolean;
  children: ReactNode;
}

function classes(variant: ButtonVariant, size: ButtonSize, block: boolean, extra?: string): string {
  return [styles.button, styles[variant], styles[size], block ? styles.block : "", extra ?? ""]
    .filter(Boolean)
    .join(" ");
}

export interface ButtonProps
  extends Common, Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Shows the action is running; the button stays focusable and announces its busy state. */
  busy?: boolean;
}

/**
 * Primary is charcoal, secondary is an outline, text is an underlined action (P-19 defaults).
 * A busy button uses aria-disabled rather than disabled, so keyboard focus is never lost mid-action.
 */
export function Button({
  variant = "primary",
  size = "md",
  block = false,
  busy = false,
  type = "button",
  className,
  onClick,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      className={classes(variant, size, block, className)}
      aria-busy={busy || undefined}
      aria-disabled={busy || rest["aria-disabled"] || undefined}
      onClick={(event) => {
        if (busy) {
          event.preventDefault();
          return;
        }
        onClick?.(event);
      }}
    >
      {busy ? <span className={styles.spinner} aria-hidden="true" /> : null}
      <span className={styles.label}>{children}</span>
    </button>
  );
}

export interface ButtonLinkProps
  extends Common, Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "children"> {
  href: string;
}

/** A link that looks like a button: navigation stays a link for assistive technology. */
export function ButtonLink({
  variant = "primary",
  size = "md",
  block = false,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <a {...rest} className={classes(variant, size, block, className)}>
      <span className={styles.label}>{children}</span>
    </a>
  );
}
