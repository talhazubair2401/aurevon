# 0002 — M1 toolchain and version pins

Date: 4 November 2026 · Status: in effect (R-03 confirmed at M1 as MTS v2.1 requires)

| Component | Version | Note |
| --- | --- | --- |
| Python | 3.13 | |
| Django | 5.2.19 (LTS) | R-03; supported to April 2028 |
| Django REST Framework | 3.18.3 | |
| PostgreSQL | 17 | Must match production's major version once P-10 selects a provider |
| Redis | 7.4 | |
| Node.js | 22 LTS | |
| pnpm | 10.28.0 | |
| Next.js | 16.4.5 | |
| React | 19.3.1 | React Three Fiber 9 supports React 19.0–19.3 |
| TypeScript | 5.9.3 | 6.x/7.x not yet supported by openapi-typescript and typescript-eslint |
| ESLint | 9.39.5 | eslint-plugin-react does not yet support ESLint 10 |

Versions are exact (`save-exact`, pinned requirements). Upgrades are deliberate, one at a time, with CI green.
React, React Three Fiber and Three.js move together (MTS §3 version alignment rule; V-03).
