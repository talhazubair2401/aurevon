# AureVon M6 Completion Report: 3D Product Experience

**Date:** 5 November 2026 · **Baseline:** MTS v2.1 §4, decision 0007 (D-01 to D-05), P-09 v2 reference
**Commits:** `5e6cd8b`/`f4a73f8` (model pipeline, 3D records, approval), `f4fa8b7` (viewer, storefront and staff
integration, 3D tests), `75491f0`/`165fb41` (fixes) · **CI:** all four jobs green on `165fb41`
**Status:** Built and tested. **3D is OFF for shoppers** (`THREED_FOR_SHOPPERS=false` everywhere except the CI
test stack) until V-01, V-02 and V-03 pass.

## Built
- **Viewer (`packages/viewer3d`):** the product image is the poster and renders first on the server; the 3D code
  loads only on the client, takes over when its first frame is ready, and "Show image / Show 3D" switches back
  and forth. All P-09 v2 fixes carried over: specific failure reasons instead of a spinner, no fixed timeout
  (slow loads change the message only), rendering only while visible and on screen, Try again, WebGL context
  loss handled, everything freed on unmount. Controls per D-05: wheel scrolls the page, Ctrl/⌘ + wheel zooms,
  + and − buttons, one-time hint, keyboard (arrows, +/−, Home), touch pinch and two-finger tilt unchanged.
- **Colours (D-03):** material variants named by colour slug switch without reloading the model; a per-colour
  model covers the colours staff choose; a colour without 3D shows its photos.
- **Model pipeline (D-02):** Khronos validation, Draco geometry and WebP textures, no resizing; damaged,
  incomplete or unsupported files are refused with the reason. D-01 figures (8 MB, 150,000 triangles, 2048 px,
  150 MB GPU) are shown to staff as provisional warnings only; nothing is refused for size.
- **Staff workflow:** upload → background processing → draft previewed in the shoppers' viewer through a
  10-minute signed address → approval by someone with publishing rights after confirming the check → public,
  content-addressed file. Retire and discard. The panel says when 3D is off for shoppers.
- **Self-hosted Draco decoder** under `/3d/draco/<three.js release>/`, cached for good.
- **CSP (V-05 run 6):** `'wasm-unsafe-eval'` and `blob:` workers/images for both apps; still no `'unsafe-eval'`,
  `'unsafe-inline'` or third-party origin. Zero violations with 3D running.

## Tests
Backend 197 (9 new for 3D) · viewer unit 8 · pipeline 9 · end-to-end 164 on desktop and phone, including the
ported 3D suite (poster first, 3D takeover, image/3D toggle, no rendering when hidden, variant switch without
reload, wheel vs Ctrl + wheel, keyboard and buttons, failed download with Try again, damaged file) and the staff
upload-preview-approve journey · `infra/csp/V-05-run-6.md`.

## Choices made in implementation
1. **One switch:** the API sends 3D to the storefront only when `THREED_FOR_SHOPPERS` is on; nothing else to flip.
2. **Public 3D data is per colour,** so several approved models (per-colour models) can coexist.
3. **`seed_demo_3d`** puts a demo model through the real pipeline and approval for local review and tests
   (demo data only; refuses where demo data is off).

## Remaining blockers
- **V-01:** test on the three phones (iPhone/Safari, mid-range and low-end Android/Chrome).
- **V-02:** pilot garment GLB from the CLO 3D / Marvelous Designer specialist (owner sources, D-04).
- **V-03:** rerun the 3D suite with the pilot garment; then set the final D-01 budget and switch 3D on.
- Real catalogue content and imagery decision; P-11, P-13, P-14; P-10 hosting.
