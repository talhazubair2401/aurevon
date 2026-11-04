AureVon 3D viewer v2 (review build, P-09 Phase 2)
==================================================

This folder is separate from v1 (prototypes/aurevon-3d-viewer-prototype.html), which is unchanged.

What's here
- index.html    The v2 viewer page (React Three Fiber over three.js r160).
- draco/        Draco decoder files from three.js r160, served from the same domain as the page.
- serve_v2.py   Local web server that sends the intended Content-Security-Policy.

Open it
The page must be served over http(s); opening index.html directly from disk won't work.
  1. Install Python 3 if needed.
  2. In this folder run:   python serve_v2.py
  3. Open http://localhost:8080

Real-device testing (phones on the same Wi-Fi as this computer)
  python serve_v2.py --lan
  Then open the address it prints on each phone. See section 7 of the P-09 Production Readiness Report.

Other modes
  python serve_v2.py --csp nowasm   Same policy without 'wasm-unsafe-eval' (Draco falls back to the JavaScript decoder)
  python serve_v2.py --csp off      No security policy header

Notes
- React, React Three Fiber and three.js load from the jsDelivr CDN in this review build only.
  Production should bundle and self-host them (decision P-01).
- All product data (prices, stock, SKUs) is demo data.
