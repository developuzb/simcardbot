"""sim.texnoset.uz uchun statik web server (Heroku 'web' jarayoni).

website/index.html — Claude Design'da yasalgan, mustaqil (self-contained) landing.
Bot bilan bir ilovada ishlaydi: 'worker' — bot, 'web' — shu sayt.
"""
import os
import socketserver
import http.server
from functools import partial

PORT = int(os.environ.get("PORT", "8000"))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=600")
        super().end_headers()

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
