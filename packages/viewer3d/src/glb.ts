/**
 * GLB inspection, read before any loader touches the file (D1 fix): damaged, incomplete or unsupported files
 * fail fast with a specific reason instead of an endless spinner. No three.js here, so it is cheap and testable.
 */

/** Same list as the model pipeline (packages/asset-pipeline). */
export const SUPPORTED_REQUIRED = new Set([
  "KHR_draco_mesh_compression",
  "EXT_meshopt_compression",
  "KHR_mesh_quantization",
  "KHR_texture_transform",
  "KHR_materials_unlit",
  "KHR_materials_emissive_strength",
  "KHR_materials_clearcoat",
  "KHR_materials_iridescence",
  "KHR_materials_sheen",
  "KHR_materials_transmission",
  "KHR_materials_volume",
  "KHR_materials_ior",
  "KHR_materials_specular",
  "KHR_materials_anisotropy",
  "KHR_lights_punctual",
  "EXT_texture_webp",
  "EXT_texture_avif",
  "EXT_mesh_gpu_instancing",
  "KHR_materials_variants",
]);

export type ModelErrorCode =
  | "badheader"
  | "version"
  | "truncated"
  | "corrupt"
  | "basisu"
  | "extension"
  | "draco"
  | "meshopt"
  | "timeout"
  | "empty"
  | "network"
  | "http";

export class ModelError extends Error {
  constructor(
    readonly code: ModelErrorCode,
    message: string,
  ) {
    super(message);
  }
}

/** Messages for staff previews (shoppers always see the friendly "couldn't load" with Try again). */
export const MODEL_MESSAGES: Record<ModelErrorCode, string> = {
  badheader:
    "This file isn't a valid .glb model. It may be damaged, or a different file renamed to .glb.",
  version: "Only glTF 2.0 models are supported.",
  truncated: "This file is incomplete. It may not have finished exporting or downloading.",
  corrupt: "This .glb file is damaged and can't be read.",
  basisu: "This model uses KTX2 (Basis) textures, which the viewer doesn't support yet.",
  extension: "This model needs a glTF extension the viewer doesn't support.",
  draco: "This model uses Draco compression, and the Draco decoder couldn't start on this device.",
  meshopt:
    "This model uses Meshopt compression, which needs WebAssembly, and WebAssembly is blocked here.",
  timeout: "Preparing this model took longer than 60 seconds, so it was stopped.",
  empty: "This file has no visible 3D geometry.",
  network: "The model couldn't be downloaded.",
  http: "The model couldn't be downloaded.",
};

export interface GlbJson {
  extensionsUsed?: string[];
  extensionsRequired?: string[];
  meshes?: Array<{
    primitives: Array<{
      extensions?: {
        KHR_materials_variants?: { mappings: Array<{ material: number; variants: number[] }> };
      };
    }>;
  }>;
  extensions?: { KHR_materials_variants?: { variants: Array<{ name: string }> } };
}

export function inspectGlb(buf: ArrayBuffer): GlbJson {
  const fail = (code: ModelErrorCode) => new ModelError(code, MODEL_MESSAGES[code]);
  if (buf.byteLength < 20) throw fail("badheader");
  const dv = new DataView(buf);
  if (dv.getUint32(0, true) !== 0x46546c67) throw fail("badheader");
  if (dv.getUint32(4, true) !== 2) throw fail("version");
  if (dv.getUint32(8, true) > buf.byteLength) throw fail("truncated");
  const jsonLength = dv.getUint32(12, true);
  if (dv.getUint32(16, true) !== 0x4e4f534a || 20 + jsonLength > buf.byteLength)
    throw fail("corrupt");
  let json: GlbJson;
  try {
    json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jsonLength))) as GlbJson;
  } catch {
    throw fail("corrupt");
  }
  const required = json.extensionsRequired ?? [];
  if (required.includes("KHR_texture_basisu")) throw fail("basisu");
  const unknown = required.filter((x) => !SUPPORTED_REQUIRED.has(x));
  if (unknown.length)
    throw new ModelError("extension", `${MODEL_MESSAGES.extension} (${unknown.join(", ")})`);
  return json;
}

/** WebAssembly can be blocked by a page's security policy; Draco then uses its JavaScript decoder (D6). */
export function webAssemblyAllowed(): boolean {
  try {
    new WebAssembly.Module(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]));
    return true;
  } catch {
    return false;
  }
}

/** Downloads with progress. Network and HTTP failures are real errors (Try again), never a timer (D4). */
export async function download(
  url: string,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<ArrayBuffer> {
  let response: Response;
  try {
    response = await fetch(url, { credentials: "same-origin", ...(signal ? { signal } : {}) });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ModelError("network", MODEL_MESSAGES.network);
  }
  if (!response.ok) throw new ModelError("http", `${MODEL_MESSAGES.http} (${response.status})`);
  const total = Number(response.headers.get("content-length")) || 0;
  if (!response.body || !total) {
    const buf = await response.arrayBuffer();
    onProgress(1);
    return buf;
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.byteLength;
    onProgress(Math.min(received / total, 1));
  }
  const out = new Uint8Array(received);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.byteLength;
  }
  return out.buffer;
}
