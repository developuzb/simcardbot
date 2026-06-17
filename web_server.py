"""sim.texnoset.uz uchun statik web server (Heroku 'web' jarayoni).

website/index.html — Claude Design'da yasalgan, mustaqil (self-contained) landing.
Bot bilan bir ilovada ishlaydi: 'worker' — bot, 'web' — shu sayt.
"""
import os
import json
import logging
import socketserver
import http.server
from functools import partial

logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", "8000"))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # HTML, manifest va service-worker hech qachon uzoq keshlanmasin —
        # aks holda yangi versiya chiqsa ham foydalanuvchi eskisini ko'radi.
        path = self.path.split("?", 1)[0].lower()
        if (path in ("", "/") or path.endswith((".html", ".json", ".webmanifest"))
                or path.endswith("service-worker.js")):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        else:
            # Rasm/ikona/statik resurslar — uzoq keshlansin
            self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Saytdagi buyurtma formasi shu yerga JSON yuboradi -> bot topic ochadi
        if self.path.split("?", 1)[0] != "/api/order":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(data, dict):
                raise ValueError("payload dict bo'lishi kerak")
        except Exception as e:
            logger.warning("[web] /api/order noto'g'ri JSON: %s", e)
            self._send_json(400, {"ok": False, "error": "bad_request"})
            return
        try:
            import web_bridge
            token = web_bridge.put_pending(data)
            self._send_json(200, {"ok": True, "token": token})
        except Exception as e:
            logger.error("[web] /api/order saqlanmadi: %s", e)
            self._send_json(503, {"ok": False, "error": "store_failed"})

    def do_GET(self):
        # Mavjud bo'lmagan yo'llar uchun ham index.html (SPA fallback)
        rel = self.path.split("?", 1)[0]
        target = self.translate_path(self.path)
        if rel != "/" and not os.path.isfile(target):
            self.path = "/index.html"
        return super().do_GET()


def main():
    handler = partial(Handler, directory=WEB_DIR)
    with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"[web] sim.texnoset.uz statik server :{PORT} -> {WEB_DIR}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
