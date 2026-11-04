# Content Security Policy (MTS v2.1 §12, A-26; decision 0005)

The policies are no longer static files. Each Next.js app builds its enforcing policy per request, with a fresh
nonce, from `packages/csp` (`buildPolicy`). The proxy never sets or replaces it; it only enforces the caching
rules and a script-free fallback (see `docs/runbooks/csp-and-caching.md`).

V-05 records in this folder:

- `V-05-run-1.md` (M1) and `V-05-run-2.md` (M3): report-only baselines; evidence for D-08.
- `V-05-run-3.md` (D-08): the enforcing nonce policy against the production builds.

Next runs: M5, M6 (with the 3D viewer and `webAssembly: true`), M14.
