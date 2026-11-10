"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { Icon } from "@aurevon/ui";
import { Link } from "@/i18n/navigation";
import { getCart, onCartChange } from "@/lib/client";

/** The header bag with its item count, kept current by cart changes anywhere on the page. */
export function BagLink({
  label,
  className,
  countClass,
  hiddenClass,
}: {
  label: string;
  className: string;
  countClass: string;
  hiddenClass: string;
}) {
  const locale = useLocale();
  const [count, setCount] = useState(0);
  useEffect(() => {
    const stop = onCartChange(setCount);
    getCart(locale).catch(() => undefined);
    return stop;
  }, [locale]);
  return (
    <Link href="/cart" className={className} data-testid="bag-link">
      <Icon name="bag" />
      {/* The name is real text, not aria-label, so the visible count is part of it (WCAG 2.5.3). */}
      <span className={hiddenClass}>{count ? `${label} (${count})` : label}</span>
      {count > 0 ? (
        <span className={countClass} aria-hidden="true">
          {count}
        </span>
      ) : null}
    </Link>
  );
}
