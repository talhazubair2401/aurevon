import styles from "./Icon.module.css";

/**
 * Simple line icons drawn for AureVon (no third-party icon set). Decorative by default (aria-hidden);
 * the control that holds an icon carries the accessible name. Directional icons mirror in right-to-left.
 */
const paths = {
  search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Zm4.6-1.9L20 20",
  account: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8c.8-3.4 3.6-5.5 7-5.5s6.2 2.1 7 5.5",
  bag: "M5 8h14l-1 12H6L5 8Zm4 0V6.5a3 3 0 0 1 6 0V8",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6 6 18",
  chevronForward: "M9 5l7 7-7 7",
  chevronBack: "M15 5l-7 7 7 7",
} as const;

export type IconName = keyof typeof paths;

const directional = new Set<IconName>(["chevronForward", "chevronBack"]);

export function Icon({
  name,
  size = 22,
  label,
}: {
  name: IconName;
  size?: number;
  label?: string;
}) {
  return (
    <svg
      className={[styles.icon, directional.has(name) ? styles.mirror : ""]
        .filter(Boolean)
        .join(" ")}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="square"
      strokeLinejoin="miter"
      focusable="false"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
      data-icon={name}
    >
      <path d={paths[name]} />
    </svg>
  );
}
