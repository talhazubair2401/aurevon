/**
 * Garment model pipeline (MTS v2.1 §4 "3D asset pipeline"; decision 0007).
 *
 * 1. Read the GLB container ourselves: wrong, damaged or unsupported files fail with a specific reason (D1).
 * 2. Khronos glTF validator: any error refuses the file; warnings are reported.
 * 3. Optimise with glTF-Transform: deduplicate, prune, WebP textures, Draco geometry (D-02).
 *    Textures are never resized: there is no approved asset budget yet (A-13, D-01).
 * 4. Measure the result and warn (never refuse) above the provisional D-01 figures.
 *
 * The figures below are provisional warnings for staff, not performance limits (decision 0007).
 */
import { createHash } from "node:crypto";
import { Logger, NodeIO } from "@gltf-transform/core";
import {
  ALL_EXTENSIONS,
  KHRDracoMeshCompression,
  KHRMaterialsVariants,
} from "@gltf-transform/extensions";
import { dedup, draco, prune, textureCompress } from "@gltf-transform/functions";
import draco3d from "draco3dgltf";
import validator from "gltf-validator";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";
import sharp from "sharp";

export const PROVISIONAL_WARNINGS = Object.freeze({
  bytes: 8 * 1024 * 1024,
  triangles: 150_000,
  maxTexturePx: 2048,
  gpuMb: 150,
});

/** Same list as the v2 viewer (it reads these), plus material variants for colours (D-03). */
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

export const MAX_INPUT_BYTES = 100 * 1024 * 1024;

export class PipelineError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

const MESSAGES = {
  badheader:
    "This file isn't a valid .glb model. It may be damaged, or a different file renamed to .glb.",
  truncated:
    "This file is incomplete. It may not have finished exporting or downloading. Export it again.",
  corrupt: "This .glb file is damaged and can't be read. Export it again.",
  basisu:
    "This model uses KTX2 (Basis) textures, which aren't supported yet. Export it with JPEG, PNG or WebP textures.",
  toolarge: "The file is larger than 100 MB.",
  empty: "This file has no visible 3D geometry.",
};

/** The GLB header and JSON chunk, checked before anything else reads the file. */
export function inspectGlb(buf) {
  if (buf.byteLength > MAX_INPUT_BYTES) throw new PipelineError("toolarge", MESSAGES.toolarge);
  if (buf.byteLength < 20) throw new PipelineError("badheader", MESSAGES.badheader);
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (dv.getUint32(0, true) !== 0x46546c67)
    throw new PipelineError("badheader", MESSAGES.badheader);
  const version = dv.getUint32(4, true);
  if (version !== 2) {
    throw new PipelineError(
      "version",
      `This model uses glTF version ${version}. Only glTF 2.0 is supported.`,
    );
  }
  if (dv.getUint32(8, true) > buf.byteLength)
    throw new PipelineError("truncated", MESSAGES.truncated);
  const jsonLength = dv.getUint32(12, true);
  if (dv.getUint32(16, true) !== 0x4e4f534a || 20 + jsonLength > buf.byteLength) {
    throw new PipelineError("corrupt", MESSAGES.corrupt);
  }
  let json;
  try {
    json = JSON.parse(new TextDecoder().decode(buf.subarray(20, 20 + jsonLength)));
  } catch {
    throw new PipelineError("corrupt", MESSAGES.corrupt);
  }
  const required = json.extensionsRequired ?? [];
  if (required.includes("KHR_texture_basisu")) throw new PipelineError("basisu", MESSAGES.basisu);
  const unknown = required.filter((x) => !SUPPORTED_REQUIRED.has(x));
  if (unknown.length) {
    throw new PipelineError(
      "extension",
      `This model needs a glTF extension that isn't supported: ${unknown.join(", ")}.`,
    );
  }
  return json;
}

async function io() {
  await MeshoptDecoder.ready;
  await MeshoptEncoder.ready;
  return new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
    "draco3d.decoder": await draco3d.createDecoderModule(),
    "draco3d.encoder": await draco3d.createEncoderModule(),
    "meshopt.decoder": MeshoptDecoder,
    "meshopt.encoder": MeshoptEncoder,
  });
}

async function validate(buf) {
  const report = await validator.validateBytes(new Uint8Array(buf), {
    maxIssues: 50,
    // External files are never fetched: a GLB must be self-contained.
    externalResourceFunction: () =>
      Promise.reject(new Error("External resources are not allowed in a .glb")),
  });
  const pick = (severity) =>
    report.issues.messages
      .filter((m) => m.severity === severity)
      .slice(0, 10)
      .map((m) => `${m.code}: ${m.message}${m.pointer ? ` (${m.pointer})` : ""}`);
  return {
    errors: report.issues.numErrors,
    warnings: report.issues.numWarnings,
    errorList: pick(0),
    warningList: pick(1),
  };
}

function triangleCount(prim) {
  const mode = prim.getMode();
  const count = prim.getIndices()?.getCount() ?? prim.getAttribute("POSITION")?.getCount() ?? 0;
  if (mode === 4) return count / 3; // TRIANGLES
  if (mode === 5 || mode === 6) return Math.max(count - 2, 0); // STRIP, FAN
  return 0;
}

/** Measurements of the optimised document (MTS §4 asset record: triangles, max_texture_px, est_gpu_mb). */
async function measure(doc) {
  const root = doc.getRoot();
  let triangles = 0;
  let geometryBytes = 0;
  const seen = new Set();
  for (const mesh of root.listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      triangles += triangleCount(prim);
      for (const acc of [prim.getIndices(), ...prim.listAttributes()]) {
        if (acc && !seen.has(acc)) {
          seen.add(acc);
          geometryBytes += acc.getArray()?.byteLength ?? 0;
        }
      }
    }
  }
  let maxTexturePx = 0;
  let textureBytes = 0;
  for (const texture of root.listTextures()) {
    const image = texture.getImage();
    if (!image) continue;
    const meta = await sharp(Buffer.from(image)).metadata();
    const w = meta.width ?? 0;
    const h = meta.height ?? 0;
    maxTexturePx = Math.max(maxTexturePx, w, h);
    textureBytes += w * h * 4 * 1.333; // RGBA plus mipmaps, as the v2 viewer estimates it
  }
  return {
    triangles: Math.round(triangles),
    meshes: root.listMeshes().length,
    textures: root.listTextures().length,
    maxTexturePx,
    estGpuMb: Math.round(((geometryBytes + textureBytes) / 1048576) * 10) / 10,
  };
}

function variantsOf(doc) {
  const ext = doc
    .getRoot()
    .listExtensionsUsed()
    .find((e) => e.extensionName === KHRMaterialsVariants.EXTENSION_NAME);
  return ext ? ext.listVariants().map((v) => v.getName()) : [];
}

function bounds(doc) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const node of doc.getRoot().listNodes()) {
    const mesh = node.getMesh();
    if (!mesh) continue;
    const m = node.getWorldMatrix();
    for (const prim of mesh.listPrimitives()) {
      const pos = prim.getAttribute("POSITION");
      if (!pos) continue;
      const lo = pos.getMin([]);
      const hi = pos.getMax([]);
      for (const x of [lo[0], hi[0]])
        for (const y of [lo[1], hi[1]])
          for (const z of [lo[2], hi[2]]) {
            const p = [
              m[0] * x + m[4] * y + m[8] * z + m[12],
              m[1] * x + m[5] * y + m[9] * z + m[13],
              m[2] * x + m[6] * y + m[10] * z + m[14],
            ];
            for (let i = 0; i < 3; i++) {
              min[i] = Math.min(min[i], p[i]);
              max[i] = Math.max(max[i], p[i]);
            }
          }
    }
  }
  return { min, max, size: max.map((v, i) => v - min[i]) };
}

/** Runs the whole pipeline. Returns { report, output } or throws PipelineError with a staff-readable reason. */
export async function processGlb(input) {
  const buf = input instanceof Uint8Array ? input : new Uint8Array(input);
  inspectGlb(buf);
  const validation = await validate(buf);
  if (validation.errors > 0) {
    const error = new PipelineError(
      "invalid",
      "The glTF validator found errors in this model. Export it again.",
    );
    error.details = validation.errorList;
    throw error;
  }
  const reader = await io();
  const doc = await reader.readBinary(buf);
  doc.setLogger(new Logger(Logger.Verbosity.SILENT)); // stdout carries only the JSON result
  const root = doc.getRoot();
  if (!root.listMeshes().some((m) => m.listPrimitives().length))
    throw new PipelineError("empty", MESSAGES.empty);

  const notes = [];
  if (root.listAnimations().length)
    notes.push("The model has animations; the viewer ignores them (delivery spec: none).");
  if (root.listCameras().length)
    notes.push("The model has cameras; the viewer uses its own (delivery spec: none).");
  const box = bounds(doc);
  const height = box.size[1];
  if (!(height > 0.3 && height < 3)) {
    notes.push(
      `The model is ${height.toFixed(2)} m tall. Garments are delivered at real-world scale in metres.`,
    );
  }

  await doc.transform(
    dedup(),
    prune(),
    // WebP textures without resizing (A-13: no budget yet).
    textureCompress({ encoder: sharp, targetFormat: "webp", quality: 90 }),
    draco({ method: "edgebreaker" }),
  );
  // Draco is the only geometry compression in the output (D-02); Meshopt from the source is decoded on read.
  for (const ext of root.listExtensionsUsed()) {
    if (ext.extensionName === "EXT_meshopt_compression") ext.dispose();
  }
  if (
    !root
      .listExtensionsUsed()
      .some((e) => e.extensionName === KHRDracoMeshCompression.EXTENSION_NAME)
  ) {
    notes.push("Draco compression wasn't applied (no compressible geometry).");
  }
  const output = await reader.writeBinary(doc);
  const measured = await measure(doc);
  const warnings = [];
  const W = PROVISIONAL_WARNINGS;
  if (output.byteLength > W.bytes)
    warnings.push(
      `File is ${(output.byteLength / 1048576).toFixed(1)} MB (provisional guide: 8 MB).`,
    );
  if (measured.triangles > W.triangles)
    warnings.push(
      `${measured.triangles.toLocaleString("en")} triangles (provisional guide: 150,000).`,
    );
  if (measured.maxTexturePx > W.maxTexturePx)
    warnings.push(`A texture is ${measured.maxTexturePx} px (provisional guide: 2048 px).`);
  if (measured.estGpuMb > W.gpuMb)
    warnings.push(`Estimated GPU memory ${measured.estGpuMb} MB (provisional guide: 150 MB).`);

  return {
    output,
    report: {
      bytes: output.byteLength,
      sourceBytes: buf.byteLength,
      compression: "draco",
      ...measured,
      heightM: Math.round(height * 1000) / 1000,
      variants: variantsOf(doc),
      checksum: createHash("sha256").update(output).digest("hex"),
      validator: { warnings: validation.warnings, warningList: validation.warningList },
      warnings,
      notes,
    },
  };
}
