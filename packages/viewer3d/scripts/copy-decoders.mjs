#!/usr/bin/env node
/** Copies three.js's Draco decoder into <public dir>/3d/draco/<three revision>/ (run before dev and build). */
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";

const publicDir = resolve(process.argv[2] ?? "public");
const require = createRequire(import.meta.url);
const threeDir = dirname(dirname(require.resolve("three"))); // three/build/three.cjs
const revision = JSON.parse(readFileSync(join(threeDir, "package.json"), "utf8")).version.split(
  ".",
)[1];
const from = join(threeDir, "examples/jsm/libs/draco");
const to = join(publicDir, "3d/draco", revision);
mkdirSync(to, { recursive: true });
for (const file of ["draco_decoder.js", "draco_decoder.wasm", "draco_wasm_wrapper.js"])
  copyFileSync(join(from, file), join(to, file));
console.log(`Draco decoder (three r${revision}) -> ${to}`);
