"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import { Icon } from "@aurevon/ui";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { Facets } from "@/lib/api";
import { SORTS, toSearch, withoutCursor, type ShopState } from "@/lib/shop-query";
import { FilterForm } from "./FilterForm";
import styles from "./Shop.module.css";

const SORT_LABELS = {
  featured: "sortFeatured",
  newest: "sortNewest",
  price_asc: "sortPriceAsc",
  price_desc: "sortPriceDesc",
} as const;

/** Sort select: a GET form without JavaScript, instant with it. */
export function SortSelect({ state }: { state: ShopState }) {
  const t = useTranslations("shop");
  const router = useRouter();
  const pathname = usePathname();
  return (
    <form method="get" action={pathname} className={styles.sortForm}>
      {state.q ? <input type="hidden" name="q" value={state.q} /> : null}
      {state.department ? <input type="hidden" name="department" value={state.department} /> : null}
      {state.category ? <input type="hidden" name="category" value={state.category} /> : null}
      {state.collection ? <input type="hidden" name="collection" value={state.collection} /> : null}
      {state.size.map((s) => (
        <input key={`s-${s}`} type="hidden" name="size" value={s} />
      ))}
      {state.colour.map((c) => (
        <input key={`c-${c}`} type="hidden" name="colour" value={c} />
      ))}
      {state.price_min ? <input type="hidden" name="price_min" value={state.price_min} /> : null}
      {state.price_max ? <input type="hidden" name="price_max" value={state.price_max} /> : null}
      <label className={styles.sortLabel}>
        <span>{t("sortBy")}</span>
        <select
          name="sort"
          className={styles.sortSelect}
          defaultValue={state.sort}
          onChange={(e) => {
            const sort = e.currentTarget.value as ShopState["sort"];
            router.replace(`${pathname}${toSearch({ ...withoutCursor(state), sort })}`, {
              scroll: false,
            });
          }}
        >
          {SORTS.map((s) => (
            <option key={s} value={s}>
              {t(SORT_LABELS[s])}
            </option>
          ))}
        </select>
      </label>
      <noscript>
        <button type="submit" className={styles.applyButton}>
          {t("apply")}
        </button>
      </noscript>
    </form>
  );
}

/** Phone and tablet: filters in a native modal dialog (focus trapped, Escape closes). */
export function MobileFilters({
  state,
  facets,
  active,
}: {
  state: ShopState;
  facets: Facets;
  active: number;
}) {
  const t = useTranslations("shop");
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <div className={styles.mobileFilters}>
      <button
        type="button"
        className={styles.filterButton}
        aria-haspopup="dialog"
        onClick={() => dialog.current?.showModal()}
      >
        {t("filters")}
        {active ? <span className={styles.activeCount}>{active}</span> : null}
      </button>
      <dialog
        ref={dialog}
        className={styles.filterDialog}
        aria-label={t("filters")}
        onClick={(e) => {
          if (e.target === e.currentTarget) dialog.current?.close();
        }}
      >
        <div className={styles.filterDialogPanel}>
          <div className={styles.filterDialogTop}>
            <h2 className={styles.filterDialogTitle}>{t("filters")}</h2>
            <button
              type="button"
              className={styles.iconButton}
              aria-label={t("closeFilters")}
              onClick={() => dialog.current?.close()}
            >
              <Icon name="close" />
            </button>
          </div>
          <FilterForm
            state={state}
            facets={facets}
            instant={false}
            submitLabel={t("showResults")}
            onApplied={() => dialog.current?.close()}
          />
        </div>
      </dialog>
    </div>
  );
}
