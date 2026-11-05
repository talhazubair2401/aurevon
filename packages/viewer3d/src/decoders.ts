/**
 * Where the Draco decoder lives (MTS §4: self-hosted, never a third-party CDN). The folder is versioned by the
 * three.js release, so a three.js upgrade never mixes decoder files; `aurevon-copy-decoders` puts them there.
 * Server-safe: no three.js import.
 */
export const THREE_REVISION = "187";

export function decoderPath(base = "/3d/draco"): string {
  return `${base}/${THREE_REVISION}/`;
}
