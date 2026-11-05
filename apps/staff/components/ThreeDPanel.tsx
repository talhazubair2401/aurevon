"use client";

import { decoderPath, ProductViewer } from "@aurevon/viewer3d";
import { useEffect, useState } from "react";
import { api, call, errorMessage, type Schemas } from "../lib/api";
import { useSession } from "../lib/session";
import { Message, type Msg } from "./CatalogNav";
import c from "./content.module.css";
import ui from "./ui.module.css";

type Product = Schemas["ProductOut"];
type Model = Schemas["Model3DOut"];

interface Report {
  error?: string;
  warnings?: string[];
  notes?: string[];
  heightM?: number;
  sourceBytes?: number;
}

const mb = (bytes: number | null | undefined) =>
  bytes ? `${(bytes / 1_048_576).toFixed(1)} MB` : "—";

/**
 * Garment models (MTS §4; decision 0007): upload a .glb, the pipeline validates and compresses it (Draco, WebP)
 * into a draft, staff check the draft in the same viewer shoppers get, then someone with publishing rights
 * approves it. Size and texture figures are provisional guides only (D-01): they warn, never refuse.
 */
export function ThreeDPanel({
  product,
  onSaved,
  colours,
}: {
  product: Product;
  onSaved: (p: Product) => void;
  colours: string[];
}) {
  const { can } = useSession();
  const canEdit = can("catalog.edit");
  const canPublish = can("catalog.publish");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Msg>(null);
  const models = product.models3d;
  const processing = models.some((m) => m.status === "processing");

  // The pipeline runs in the background; check every few seconds until it finishes.
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => {
      call(() =>
        api.GET("/api/v1/staff/catalog/products/{product_id}", {
          params: { path: { product_id: product.id } },
        }),
      )
        .then(onSaved)
        .catch(() => undefined);
    }, 3000);
    return () => clearInterval(timer);
  }, [processing, product.id, onSaved]);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    const form = new FormData();
    form.append("file", file);
    try {
      onSaved(
        await call(() =>
          api.POST("/api/v1/staff/catalog/products/{product_id}/models3d", {
            params: { path: { product_id: product.id } },
            body: {} as never,
            bodySerializer: () => form,
          }),
        ),
      );
      setFile(null);
      setMessage({ ok: true, text: "Uploaded. Checking and compressing the model…" });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={ui.panel} aria-labelledby="threed-title">
      <h2 id="threed-title" className={ui.subtitle}>
        3D model
      </h2>
      {!product.shoppers_see_3d && (
        <p className={ui.banner} data-testid="threed-off">
          3D is off for shoppers until the device, pilot garment and viewer checks (V-01 to V-03)
          pass. You can upload, check and approve models now; shoppers see them once 3D is switched
          on.
        </p>
      )}
      <p className={ui.muted}>
        A .glb file (glTF 2.0) from the 3D specialist. Name material variants by colour (for example
        ivory, sage), or upload one model per colour and choose its colours. Damaged or unsupported
        files are refused with the reason; size and texture figures are provisional guides only.
      </p>

      {models.map((m) => (
        <ModelCard
          key={m.id}
          product={product}
          model={m}
          colours={colours}
          onSaved={onSaved}
          canEdit={canEdit}
          canPublish={canPublish}
        />
      ))}

      {canEdit && (
        <>
          <div className={ui.field}>
            <label htmlFor="threed-file">Model file (.glb)</label>
            <input
              id="threed-file"
              type="file"
              accept=".glb,model/gltf-binary"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className={c.actions}>
            <button className={ui.button} disabled={!file || busy} onClick={() => void upload()}>
              {busy ? "Uploading…" : "Upload model"}
            </button>
          </div>
        </>
      )}
      <Message message={message} />
    </section>
  );
}

function ModelCard({
  product,
  model,
  colours,
  onSaved,
  canEdit,
  canPublish,
}: {
  product: Product;
  model: Model;
  colours: string[];
  onSaved: (p: Product) => void;
  canEdit: boolean;
  canPublish: boolean;
}) {
  const [picked, setPicked] = useState<string[]>(model.colours);
  const [checked, setChecked] = useState(false);
  const [previewColour, setPreviewColour] = useState(
    Object.keys(model.variant_map)[0] ?? colours[0] ?? "",
  );
  const [message, setMessage] = useState<Msg>(null);
  const report = (model.report ?? {}) as Report;
  const path = { params: { path: { product_id: product.id, asset_id: model.id } } };
  const covered = Object.keys(model.variant_map);

  const act = async (run: () => Promise<Product>, done: string) => {
    setMessage(null);
    try {
      onSaved(await run());
      setMessage({ ok: true, text: done });
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    }
  };

  return (
    <div className={c.shared} data-model3d={model.status}>
      <p>
        <strong>{model.file_name}</strong> <span className={ui.tag}>{model.status}</span>
      </p>
      {model.status === "processing" && (
        <p className={ui.muted}>Checking and compressing… this page updates by itself.</p>
      )}
      {model.status === "failed" && (
        <p className={ui.error}>{report.error ?? "The model couldn't be processed."}</p>
      )}

      {model.status !== "processing" && model.status !== "failed" && (
        <>
          <dl className={c.facts}>
            <dt>Size</dt>
            <dd>
              {mb(model.bytes)} ({model.compression || "uncompressed"}; uploaded{" "}
              {mb(report.sourceBytes)})
            </dd>
            <dt>Triangles</dt>
            <dd>{model.triangles?.toLocaleString("en") ?? "—"}</dd>
            <dt>Largest texture</dt>
            <dd>{model.max_texture_px ? `${model.max_texture_px} px` : "None"}</dd>
            <dt>Estimated GPU memory</dt>
            <dd>{model.est_gpu_mb ? `${model.est_gpu_mb} MB` : "—"}</dd>
            <dt>Variants</dt>
            <dd>{model.variants.length ? model.variants.join(", ") : "None"}</dd>
            <dt>Colours shown</dt>
            <dd>{covered.length ? covered.join(", ") : "None yet"}</dd>
          </dl>
          {(report.warnings ?? []).length > 0 && (
            <div>
              <p className={ui.muted}>
                Provisional guides (decision 0007, D-01: warnings only, not limits):
              </p>
              <ul>
                {report.warnings!.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {(report.notes ?? []).length > 0 && (
            <ul>
              {report.notes!.map((n) => (
                <li key={n} className={ui.muted}>
                  {n}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {model.status === "draft" && model.variants.length === 0 && canEdit && (
        <fieldset className={ui.field}>
          <legend>This model has no colour variants. Which colours does it show?</legend>
          {colours.map((col) => (
            <label key={col} className={ui.row}>
              <input
                type="checkbox"
                checked={picked.includes(col)}
                onChange={(e) =>
                  setPicked(e.target.checked ? [...picked, col] : picked.filter((x) => x !== col))
                }
              />
              {col}
            </label>
          ))}
          <div className={c.actions}>
            <button
              className={ui.secondary}
              onClick={() =>
                void act(
                  () =>
                    call(() =>
                      api.PUT(
                        "/api/v1/staff/catalog/products/{product_id}/models3d/{asset_id}/colours",
                        {
                          ...path,
                          body: { colours: picked } as never,
                        },
                      ),
                    ),
                  "Colours saved.",
                )
              }
            >
              Save colours
            </button>
          </div>
        </fieldset>
      )}

      {model.preview_url && (model.status === "draft" || model.status === "approved") && (
        <>
          {covered.length > 1 && (
            <div className={ui.field}>
              <label htmlFor={`preview-colour-${model.id}`}>Preview colour</label>
              <select
                id={`preview-colour-${model.id}`}
                className={ui.select}
                value={previewColour}
                onChange={(e) => setPreviewColour(e.target.value)}
              >
                {covered.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className={c.preview3d}>
            <ProductViewer
              src={model.preview_url}
              decoderPath={decoderPath("/staff/3d/draco")}
              variant={model.variant_map[previewColour] ?? ""}
              colourName={covered.length ? previewColour : undefined}
              detailedErrors
            >
              <span />
            </ProductViewer>
          </div>
        </>
      )}

      {model.status === "draft" && canPublish && (
        <>
          <label className={ui.row}>
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            I checked this model in the viewer: it loads, looks right in every colour, and rotates
            and zooms properly.
          </label>
          <div className={c.actions}>
            <button
              className={ui.button}
              disabled={!checked}
              onClick={() =>
                void act(
                  () =>
                    call(() =>
                      api.POST(
                        "/api/v1/staff/catalog/products/{product_id}/models3d/{asset_id}/approve",
                        {
                          ...path,
                          body: { checked: true } as never,
                        },
                      ),
                    ),
                  "Approved.",
                )
              }
            >
              Approve model
            </button>
          </div>
        </>
      )}
      {model.status === "draft" && !canPublish && (
        <p className={ui.muted}>
          Someone with publishing rights approves models after checking them here.
        </p>
      )}
      {(model.status === "approved" || model.status === "draft" || model.status === "failed") &&
        canPublish && (
          <div className={c.actions}>
            <button
              className={ui.secondary}
              onClick={() =>
                void act(
                  () =>
                    call(() =>
                      api.POST(
                        "/api/v1/staff/catalog/products/{product_id}/models3d/{asset_id}/retire",
                        path,
                      ),
                    ),
                  "Removed.",
                )
              }
            >
              {model.status === "approved" ? "Retire model" : "Discard"}
            </button>
          </div>
        )}
      <Message message={message} />
    </div>
  );
}
