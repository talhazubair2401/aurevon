"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "@aurevon/ui";
import { Link, usePathname } from "@/i18n/navigation";
import styles from "./Shell.module.css";

interface Props {
  items: Array<{ href: string; label: string }>;
  labels: { open: string; close: string; title: string; nav: string };
  languageSwitcher: ReactNode;
}

/**
 * Phone navigation in a native modal <dialog>: the browser traps focus, makes the page inert, closes on
 * Escape and returns focus to the menu button. Closes on navigation.
 */
export function MobileMenu({ items, labels, languageSwitcher }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    dialog.current?.close();
  }, [pathname]);

  return (
    <div className={styles.mobileOnly}>
      <button
        type="button"
        className={styles.iconLink}
        aria-label={labels.open}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          dialog.current?.showModal();
          setOpen(true);
        }}
      >
        <Icon name="menu" />
      </button>
      <dialog
        ref={dialog}
        className={styles.menuDialog}
        aria-label={labels.title}
        onClose={() => setOpen(false)}
        onClick={(event) => {
          // A click on the backdrop (the dialog element itself) closes the menu.
          if (event.target === event.currentTarget) dialog.current?.close();
        }}
      >
        <div className={styles.menuPanel}>
          <div className={styles.menuTop}>
            <button
              type="button"
              className={styles.iconLink}
              aria-label={labels.close}
              onClick={() => dialog.current?.close()}
            >
              <Icon name="close" />
            </button>
          </div>
          <nav aria-label={labels.nav}>
            <ul className={styles.menuList}>
              {items.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={styles.menuLink}
                    onClick={() => dialog.current?.close()}
                  >
                    {item.label}
                    <Icon name="chevronForward" size={18} />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className={styles.menuFooter}>{languageSwitcher}</div>
        </div>
      </dialog>
    </div>
  );
}
