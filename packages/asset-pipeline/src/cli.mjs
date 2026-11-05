#!/usr/bin/env node
/**
 * Called by the API worker: `aurevon-asset-pipeline <input.glb> <output.glb>`.
 * Prints one JSON line: {"ok": true, "report": {...}} or {"ok": false, "code", "message", "details"}.
 * Exit code 0 for both (the JSON carries the result); 2 only for wrong usage or an unexpected crash.
 */
import { readFile, writeFile } from "node:fs/promises";
import { PipelineError, processGlb } from "./pipeline.mjs";

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  process.stderr.write("usage: aurevon-asset-pipeline <input.glb> <output.glb>\n");
  process.exit(2);
}
try {
  const result = await processGlb(await readFile(input));
  await writeFile(output, result.output);
  process.stdout.write(JSON.stringify({ ok: true, report: result.report }) + "\n");
} catch (error) {
  if (error instanceof PipelineError) {
    process.stdout.write(
      JSON.stringify({
        ok: false,
        code: error.code,
        message: error.message,
        details: error.details ?? [],
      }) + "\n",
    );
  } else {
    process.stdout.write(
      JSON.stringify({
        ok: false,
        code: "read",
        message: "The model couldn't be read. Export it again.",
        details: [String(error?.message ?? error).slice(0, 300)],
      }) + "\n",
    );
  }
}
