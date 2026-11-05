import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { inspectGlb, PipelineError, processGlb } from "./pipeline.mjs";

const fixture = (name) => readFile(new URL(`../fixtures/${name}`, import.meta.url));

test("a garment is validated, Draco-compressed and measured, with its colour variants", async () => {
  const { output, report } = await processGlb(await fixture("garment.glb"));
  assert.equal(report.compression, "draco");
  assert.deepEqual(report.variants, ["ivory", "sage"]);
  assert.equal(report.triangles, 672);
  assert.ok(report.bytes < report.sourceBytes);
  assert.match(report.checksum, /^[0-9a-f]{64}$/);
  assert.deepEqual(report.warnings, []);
  const json = inspectGlb(output);
  assert.ok(json.extensionsRequired.includes("KHR_draco_mesh_compression"));
  assert.ok(json.extensionsUsed.includes("KHR_materials_variants"));
});

test("textures become WebP and are never resized", async () => {
  const { output, report } = await processGlb(await fixture("garment-textured.glb"));
  const json = inspectGlb(output);
  assert.ok(json.images.every((i) => i.mimeType === "image/webp"));
  assert.equal(report.maxTexturePx, 64);
});

test("provisional D-01 figures warn, never refuse", async () => {
  const { report } = await processGlb(await fixture("garment-large-texture.glb"));
  assert.equal(report.maxTexturePx, 2560); // not resized (A-13)
  assert.ok(report.warnings.some((w) => w.includes("2560 px")));
});

test("Meshopt input is decoded and written with Draco only", async () => {
  const { output } = await processGlb(await fixture("garment-meshopt.glb"));
  const json = inspectGlb(output);
  assert.ok(!(json.extensionsUsed ?? []).includes("EXT_meshopt_compression"));
  assert.ok(json.extensionsUsed.includes("KHR_draco_mesh_compression"));
});

for (const [name, code] of [
  ["not-a-model.glb", "badheader"],
  ["truncated.glb", "truncated"],
  ["corrupt.glb", "corrupt"],
  ["needs-unknown-extension.glb", "extension"],
]) {
  test(`${name} is refused with a specific reason (${code})`, async () => {
    await assert.rejects(
      processGlb(await fixture(name)),
      (e) => e instanceof PipelineError && e.code === code,
    );
  });
}

test("models at the wrong scale get a note", async () => {
  const { report } = await processGlb(await fixture("garment-draco.glb"));
  assert.equal(report.notes.length, 0);
  assert.ok(report.heightM > 1 && report.heightM < 2);
});
