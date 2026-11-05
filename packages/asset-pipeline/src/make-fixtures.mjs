/**
 * Small test garments for the pipeline, viewer and 3D suites (no real garment yet: that is V-02).
 * A tunic-like lathe shape with two material variants named by colour slug (D-03): ivory and sage.
 * Writes: garment.glb (plain), garment-draco.glb, garment-meshopt.glb, garment-novariants.glb,
 * corrupt.glb, truncated.glb, not-a-model.glb, needs-unknown-extension.glb.
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Document, NodeIO } from "@gltf-transform/core";
import {
  ALL_EXTENSIONS,
  EXTMeshoptCompression,
  KHRMaterialsVariants,
} from "@gltf-transform/extensions";
import { draco, meshopt } from "@gltf-transform/functions";
import draco3d from "draco3dgltf";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";

const out = process.argv[2] ?? "fixtures";

function lathe(profile, segments) {
  const pos = [];
  const idx = [];
  for (let i = 0; i < profile.length; i++) {
    const [r, y] = profile[i];
    for (let s = 0; s <= segments; s++) {
      const a = (s / segments) * Math.PI * 2;
      pos.push(Math.sin(a) * r, y, Math.cos(a) * r * 0.6);
    }
  }
  const row = segments + 1;
  for (let i = 0; i < profile.length - 1; i++)
    for (let s = 0; s < segments; s++) {
      const a = i * row + s;
      const b = a + row;
      idx.push(a, b, a + 1, b, b + 1, a + 1);
    }
  return { pos: new Float32Array(pos), idx: new Uint32Array(idx) };
}

async function png(size) {
  const { default: sharp } = await import("sharp");
  // A woven-looking pattern: a solid colour would be folded into the material and dropped as a texture.
  const pixels = Buffer.alloc(size * size * 3);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const v = ((x >> 2) + (y >> 2)) % 2 ? 200 : 170;
      pixels.set([v, v - 20, v - 50], (y * size + x) * 3);
    }
  return new Uint8Array(
    await sharp(pixels, { raw: { width: size, height: size, channels: 3 } })
      .png()
      .toBuffer(),
  );
}

function garment({ variants = true, texture = null } = {}) {
  const doc = new Document();
  const buffer = doc.createBuffer();
  const base = doc
    .createMaterial("fabric")
    .setBaseColorFactor([0.69, 0.54, 0.37, 1])
    .setRoughnessFactor(0.9);
  if (texture) {
    base.setBaseColorTexture(doc.createTexture("weave").setImage(texture).setMimeType("image/png"));
  }
  const { pos, idx } = lathe(
    [
      [0.12, 0.75],
      [0.22, 0.72],
      [0.3, 0.6],
      [0.28, 0.3],
      [0.26, 0.0],
      [0.3, -0.35],
      [0.36, -0.7],
      [0.37, -0.75],
    ],
    48,
  );
  const prim = doc
    .createPrimitive()
    .setAttribute("POSITION", doc.createAccessor().setType("VEC3").setArray(pos).setBuffer(buffer))
    .setAttribute(
      "TEXCOORD_0",
      doc
        .createAccessor()
        .setType("VEC2")
        .setArray(
          new Float32Array((pos.length / 3) * 2).map((_, i) =>
            i % 2 ? (pos[(i >> 1) * 3 + 1] + 1) / 2 : 0.5,
          ),
        )
        .setBuffer(buffer),
    )
    .setIndices(doc.createAccessor().setType("SCALAR").setArray(idx).setBuffer(buffer))
    .setMaterial(base);
  const mesh = doc.createMesh("tunic").addPrimitive(prim);
  const node = doc.createNode("tunic").setMesh(mesh).setTranslation([0, 0.75, 0]);
  doc.createScene("garment").addChild(node);
  if (variants) {
    const ext = doc.createExtension(KHRMaterialsVariants);
    const ivory = ext.createVariant("ivory");
    const sage = ext.createVariant("sage");
    const ivoryMat = doc
      .createMaterial("ivory")
      .setBaseColorFactor([0.95, 0.93, 0.89, 1])
      .setRoughnessFactor(0.9);
    const sageMat = doc
      .createMaterial("sage")
      .setBaseColorFactor([0.55, 0.62, 0.52, 1])
      .setRoughnessFactor(0.9);
    prim.setExtension(
      "KHR_materials_variants",
      ext
        .createMappingList()
        .addMapping(ext.createMapping().setMaterial(ivoryMat).addVariant(ivory))
        .addMapping(ext.createMapping().setMaterial(sageMat).addVariant(sage)),
    );
  }
  return doc;
}

await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  "draco3d.encoder": await draco3d.createEncoderModule(),
  "draco3d.decoder": await draco3d.createDecoderModule(),
  "meshopt.encoder": MeshoptEncoder,
  "meshopt.decoder": MeshoptDecoder,
});
await mkdir(out, { recursive: true });
const write = (name, bytes) => writeFile(join(out, name), bytes);

const plain = await io.writeBinary(garment());
await write("garment.glb", plain);
await write("garment-novariants.glb", await io.writeBinary(garment({ variants: false })));
const d = garment();
await d.transform(draco());
await write("garment-draco.glb", await io.writeBinary(d));
const m = garment();
m.createExtension(EXTMeshoptCompression).setRequired(true);
await m.transform(meshopt({ encoder: MeshoptEncoder }));
await write("garment-meshopt.glb", await io.writeBinary(m));

await write("garment-textured.glb", await io.writeBinary(garment({ texture: await png(64) })));
await write(
  "garment-large-texture.glb",
  await io.writeBinary(garment({ texture: await png(2560) })),
);

const corrupt = new Uint8Array(plain);
corrupt.fill(0x7b, 24, 60); // JSON chunk overwritten
await write("corrupt.glb", corrupt);
await write("truncated.glb", plain.slice(0, Math.floor(plain.byteLength / 2)));
await write(
  "not-a-model.glb",
  new TextEncoder().encode("<svg xmlns='http://www.w3.org/2000/svg'/>"),
);
const unknown = garment();
unknown.getRoot(); // a required extension nothing supports
const bytes = await io.writeBinary(unknown);
const dv = new DataView(bytes.buffer, bytes.byteOffset);
const len = dv.getUint32(12, true);
const json = JSON.parse(new TextDecoder().decode(bytes.subarray(20, 20 + len)));
json.extensionsUsed = [...(json.extensionsUsed ?? []), "EXT_made_up"];
json.extensionsRequired = ["EXT_made_up"];
let text = JSON.stringify(json);
while (text.length % 4 !== 0) text += " ";
const jsonBytes = new TextEncoder().encode(text);
const rest = bytes.subarray(20 + len);
const outBytes = new Uint8Array(20 + jsonBytes.length + rest.length);
const ov = new DataView(outBytes.buffer);
ov.setUint32(0, 0x46546c67, true);
ov.setUint32(4, 2, true);
ov.setUint32(8, outBytes.length, true);
ov.setUint32(12, jsonBytes.length, true);
ov.setUint32(16, 0x4e4f534a, true);
outBytes.set(jsonBytes, 20);
outBytes.set(rest, 20 + jsonBytes.length);
await write("needs-unknown-extension.glb", outBytes);
console.log("fixtures written to", out);
