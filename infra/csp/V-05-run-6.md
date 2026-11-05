# V-05 run 6: M6 with the 3D viewer

Date: 5 November 2026 · Production builds behind the routing proxy · Stack with `THREED_FOR_SHOPPERS=true` (test only)

Policy change (decision 0005 anticipated it): both apps add `'wasm-unsafe-eval'` to `script-src`, `worker-src 'self'
blob:`, and `blob:` in `img-src` and `connect-src` (Draco decoder worker, textures inside .glb files). Still no
`'unsafe-eval'`, no `'unsafe-inline'`, no third-party origin.

| Check                                                                              | Result                                                                   |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Run 5 pages plus `/en/products/block-print-kurta`, desktop and phone               | Enforcing policy, zero violations                                        |
| Product page with 3D: poster, 3D code, Draco WebAssembly decoder, model, variants  | Zero violations; Draco ran as WebAssembly; ready in 3.9–6.0 s (CI-class) |
| Draco decoder files `/3d/draco/187/*` (self-hosted, versioned by three.js release) | Same origin; served `public, max-age=31536000, immutable`                |
| Approved model `/media/products/3d/<sha256>.glb`                                   | Same origin; `model/gltf-binary`, immutable                              |
| Staff 3D preview (signed, short-lived address) and approval (staff journey)        | No policy errors                                                         |
| Injected script, third-party script, fallback policy (existing checks)             | Still blocked                                                            |

Results: `e2e/results/csp-v05-3d-{desktop,phone}.json`. Next runs: M14, and staging/production through the CDN.
