"use client";

import { useTranslations } from "next-intl";
import { Button } from "@aurevon/ui";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("error");
  return (
    <div className="av-centred" role="alert">
      <h1 className="av-heading">{t("title")}</h1>
      <p>{t("body")}</p>
      <p>
        <Button variant="secondary" onClick={reset}>
          {t("retry")}
        </Button>
      </p>
    </div>
  );
}
