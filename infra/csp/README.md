# Content Security Policy (MTS v2.1 §12, A-26, V-05)

`*-baseline.txt` are the MTS §12 baselines **without** nonces or hashes. The proxy sends them as
`Content-Security-Policy-Report-Only`, and `e2e/tests/csp.spec.ts` records every violation the production
builds produce. Those results decide D-08 (nonce-based vs hash-based) before M4. The policy switches to
enforcing mode only once a run shows zero violations.

The proxy reads the policies from the environment (`STOREFRONT_CSP`, `STAFF_CSP`), set in `infra/compose.yaml`
from these files' contents. Keep them in sync when editing.
