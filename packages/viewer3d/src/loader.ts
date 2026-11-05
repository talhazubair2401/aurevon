/**
 * Model loading (MTS §4 `loadModel`, D1 fix): every path ends in the model or a specific error.
 * - Draco: WebAssembly decoder first, then the JavaScript one; time limits on starting the decoder.
 * - Meshopt: its decoder is only imported where WebAssembly is allowed (D6).
 * - GLTFLoader reports some failures by throwing instead of calling onError (found in P-09), so both are caught.
 * - Material variants (KHR_materials_variants) select each colour (decision 0007, D-03).
 */
import * as THREE from "three";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { type GLTF, GLTFLoader, type GLTFParser } from "three/examples/jsm/loaders/GLTFLoader.js";
import { type GlbJson, inspectGlb, MODEL_MESSAGES, ModelError, webAssemblyAllowed } from "./glb";

const LIMITS = { parseMs: 60_000, dracoStartMs: 30_000 }; // time limits only, never asset limits

export interface LoadedModel {
  scene: THREE.Group;
  parser: GLTFParser;
  json: GlbJson;
  decoder: "wasm" | "js" | null;
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  return Promise.race([
    promise,
    new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new ModelError("timeout", MODEL_MESSAGES.timeout)), ms);
    }),
  ]).finally(() => clearTimeout(timer));
}

function parse(loader: GLTFLoader, buf: ArrayBuffer): Promise<GLTF> {
  return new Promise((resolve, reject) => {
    try {
      loader.parse(buf, "", resolve, reject);
    } catch (error) {
      reject(error);
    }
  });
}

export async function loadModel(buf: ArrayBuffer, decoderPath: string): Promise<LoadedModel> {
  const json = inspectGlb(buf);
  const used = json.extensionsUsed ?? [];
  const wasm = webAssemblyAllowed();
  const loader = new GLTFLoader();
  if (used.includes("EXT_meshopt_compression")) {
    if (!wasm) throw new ModelError("meshopt", MODEL_MESSAGES.meshopt);
    const { MeshoptDecoder } = await import("three/examples/jsm/libs/meshopt_decoder.module.js");
    loader.setMeshoptDecoder(MeshoptDecoder);
  }
  if (!used.includes("KHR_draco_mesh_compression")) {
    const gltf = await withTimeout(parse(loader, buf), LIMITS.parseMs);
    return { scene: gltf.scene, parser: gltf.parser, json, decoder: null };
  }
  for (const type of wasm ? (["wasm", "js"] as const) : (["js"] as const)) {
    const draco = new DRACOLoader().setDecoderPath(decoderPath);
    // setDecoderConfig() only warns about its future removal; the setting itself is still read (r187).
    (draco as unknown as { decoderConfig: { type: string } }).decoderConfig.type = type;
    loader.setDRACOLoader(draco);
    try {
      const gltf = await withTimeout(
        parse(loader, buf.slice(0)),
        type === "wasm" ? LIMITS.dracoStartMs : LIMITS.parseMs,
      );
      draco.dispose(); // decoding is done; release the worker
      return { scene: gltf.scene, parser: gltf.parser, json, decoder: type };
    } catch (error) {
      draco.dispose(); // also stops a stuck worker
      console.warn(`[viewer3d] Draco ${type} decoder failed:`, (error as Error)?.message);
    }
  }
  throw new ModelError("draco", MODEL_MESSAGES.draco);
}

/** Frees geometry, materials, textures and decoded images (MTS §4 `dispose`; verified in P-09). */
export function disposeObject(root: THREE.Object3D, extra: THREE.Material[] = []): void {
  const materials = new Set<THREE.Material>(extra);
  root.traverse((node) => {
    const mesh = node as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    if (mesh.material)
      ([] as THREE.Material[]).concat(mesh.material).forEach((m) => materials.add(m));
  });
  for (const material of materials) {
    for (const value of Object.values(material)) {
      if (value && (value as THREE.Texture).isTexture) {
        const texture = value as THREE.Texture;
        const image = texture.source?.data as { close?: () => void } | undefined;
        texture.dispose();
        image?.close?.(); // ImageBitmaps hold decoded pixels until closed
      }
    }
    material.dispose();
  }
}

/**
 * Material variants (KHR_materials_variants): switch every primitive to the material for `name`, or back to its
 * default when `name` is empty. Returns the variant materials it created, so they can be disposed later.
 */
export class Variants {
  private defaults = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();
  private created = new Set<THREE.Material>();
  readonly names: string[];

  constructor(private readonly model: LoadedModel) {
    this.names = (model.json.extensions?.KHR_materials_variants?.variants ?? []).map((v) => v.name);
    model.scene.traverse((node) => {
      const mesh = node as THREE.Mesh;
      if (mesh.isMesh) this.defaults.set(mesh, mesh.material);
    });
  }

  async select(name: string): Promise<void> {
    const index = name ? this.names.indexOf(name) : -1;
    const jobs: Promise<void>[] = [];
    for (const [mesh, original] of this.defaults) {
      if (index < 0) {
        mesh.material = original;
        continue;
      }
      const link = this.model.parser.associations.get(mesh) as
        { meshes?: number; primitives?: number } | undefined;
      const def =
        link?.meshes !== undefined && link.primitives !== undefined
          ? this.model.json.meshes?.[link.meshes]?.primitives[link.primitives]
          : undefined;
      const mapping = def?.extensions?.KHR_materials_variants?.mappings.find((m) =>
        m.variants.includes(index),
      );
      if (!mapping) {
        mesh.material = original;
        continue;
      }
      jobs.push(
        (
          this.model.parser.getDependency("material", mapping.material) as Promise<THREE.Material>
        ).then((material) => {
          this.created.add(material);
          mesh.material = material;
        }),
      );
    }
    await Promise.all(jobs);
  }

  materials(): THREE.Material[] {
    return [...this.created, ...[...this.defaults.values()].flat()];
  }
}

/** Centres the model on the plinth at a common height (as the v2 viewer). */
export function fitToStage(scene: THREE.Object3D, floor: number): THREE.Group {
  const box = new THREE.Box3().setFromObject(scene);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  if (!Number.isFinite(size.y) || size.length() === 0)
    throw new ModelError("empty", MODEL_MESSAGES.empty);
  const s = 2.9 / Math.max(size.y, size.x * 1.1, size.z * 1.1, 1e-6);
  scene.position.sub(centre).multiplyScalar(s);
  scene.scale.setScalar(s);
  const wrapper = new THREE.Group();
  wrapper.add(scene);
  wrapper.position.y = floor + 0.12 + (size.y * s) / 2;
  return wrapper;
}
