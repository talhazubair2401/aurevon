"use client";

import { BlockPanel } from "../../../components/BlockPanel";
import { ContentNav, storefrontUrl } from "../../../components/ContentEditor";
import { Shell } from "../../../components/Shell";
import ui from "../../../components/ui.module.css";
import { api, call, errorMessage, useApiData } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { useState } from "react";

export default function BannersPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Content</h1>
      <ContentNav />
      <Banners />
    </Shell>
  );
}

const loadBanners = () => call(() => api.GET("/api/v1/staff/cms/banners"));
const PLACEMENT: Record<string, string> = { shop_editorial: "/shop" };

function Banners() {
  const { can } = useSession();
  const { data: banners, error, reload } = useApiData(loadBanners);
  const [visibilityError, setVisibilityError] = useState<string | null>(null);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!banners) return <p className={ui.muted}>Loading…</p>;
  const canPublish = can("cms.publish");

  return (
    <>
      <p className={ui.muted}>Editorial banners the storefront places on its pages.</p>
      {visibilityError && <p className={ui.error}>{visibilityError}</p>}
      {banners.map((banner) => (
        <BlockPanel
          key={banner.key}
          item={banner}
          canEdit={can("cms.edit")}
          canPublish={canPublish}
          viewHref={storefrontUrl(PLACEMENT[banner.key] ?? "/")}
          extra={
            <label className={ui.row}>
              <input
                type="checkbox"
                checked={banner.is_enabled}
                disabled={!canPublish}
                onChange={async (e) => {
                  setVisibilityError(null);
                  try {
                    await call(() =>
                      api.PUT("/api/v1/staff/cms/banners/{key}", {
                        params: { path: { key: banner.key } },
                        body: { is_enabled: e.target.checked },
                      }),
                    );
                    reload();
                  } catch (err) {
                    setVisibilityError(errorMessage(err));
                  }
                }}
              />
              Shown on the store
            </label>
          }
          onSaveDraft={(content) =>
            call(() =>
              api.PUT("/api/v1/staff/cms/banners/{key}/draft", {
                params: { path: { key: banner.key } },
                body: { content },
              }),
            )
          }
          onPublish={() =>
            call(() =>
              api.POST("/api/v1/staff/cms/banners/{key}/publish", {
                params: { path: { key: banner.key } },
              }),
            )
          }
          onDiscard={() =>
            call(() =>
              api.DELETE("/api/v1/staff/cms/banners/{key}/draft", {
                params: { path: { key: banner.key } },
              }),
            )
          }
        />
      ))}
    </>
  );
}
