#!/usr/bin/env python3
"""Serve the AureVon v2 viewer with the intended Content-Security-Policy.

Usage (from this folder):
    python serve_v2.py                 # http://localhost:8080, intended CSP
    python serve_v2.py --lan           # also reachable from phones on the same Wi-Fi
    python serve_v2.py --csp nowasm    # same policy without 'wasm-unsafe-eval' (tests the JS Draco fallback)
    python serve_v2.py --csp off       # no CSP header

The policy hashes the page's inline <script> and <style> blocks, so it needs no
'unsafe-inline' for scripts or styles. The hashes are recomputed at start-up;
restart the server after editing index.html.
"""
import argparse, base64, hashlib, http.server, re, socket, socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def inline_hashes(html: str, tag: str):
    out = []
    for m in re.finditer(rf"<{tag}(\s[^>]*)?>(.*?)</{tag}>", html, re.S):
        attrs, body = m.group(1) or "", m.group(2)
        if tag == "script" and "src=" in attrs:
            continue
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
        out.append(f"'sha256-{digest}'")
    return out


def build_csp(mode: str) -> str:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = " ".join(inline_hashes(html, "script"))
    styles = " ".join(inline_hashes(html, "style"))
    wasm = "" if mode == "nowasm" else " 'wasm-unsafe-eval'"
    return "; ".join([
        "default-src 'self'",
        f"script-src 'self'{wasm} https://cdn.jsdelivr.net {scripts}",  # CDN only for this review build; production bundles and self-hosts
        f"style-src 'self' https://fonts.googleapis.com {styles}",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data: blob:",
        "connect-src 'self' blob: data: https://cdn.jsdelivr.net",
        "worker-src 'self' blob:",          # DRACOLoader runs its decoder in a blob: worker
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--lan", action="store_true", help="listen on all interfaces")
    ap.add_argument("--csp", choices=["intended", "nowasm", "off"], default="intended")
    a = ap.parse_args()
    csp = None if a.csp == "off" else build_csp(a.csp)

    class H(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".js": "text/javascript", ".glb": "model/gltf-binary"}

        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(ROOT), **kw)

        def end_headers(self):
            if csp:
                self.send_header("Content-Security-Policy", csp)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    host = "0.0.0.0" if a.lan else "127.0.0.1"
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((host, a.port), H) as srv:
        print(f"Serving {ROOT} on http://localhost:{a.port}  (CSP: {a.csp})")
        if a.lan:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
                print(f"On a phone on the same Wi-Fi, open http://{ip}:{a.port}")
            except OSError:
                pass
        srv.serve_forever()


if __name__ == "__main__":
    main()
