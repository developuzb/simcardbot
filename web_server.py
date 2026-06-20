"""sim.texnoset.uz uchun statik web server (Heroku 'web' jarayoni).

website/index.html — Claude Design'da yasalgan, mustaqil (self-contained) landing.
Bot bilan bir ilovada ishlaydi: 'worker' — bot, 'web' — shu sayt.
"""
import os
import json
import time
import logging
import http.server
from functools import partial

import chat_ai

logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", "8000"))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website")

# Sayt chati (/chat) uchun CORS — boshqa domendagi nusxa (masalan GitHub Pages)
# ham shu backendga ulanishi mumkin. Vergul bilan bir nechta domen yoki "*".
ALLOW_ORIGIN = os.environ.get("ALLOW_ORIGIN", "*")
_ALLOWED = [o.strip() for o in ALLOW_ORIGIN.split(",") if o.strip()]

# Chat uchun oddiy per-IP sekinlashtirish (suiiste'molni kamaytiradi)
_CHAT_COOLDOWN = 1.5
_last_chat = {}


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

    def _cors_origin(self):
        """So'rov Origin'iga mos ruxsat (yoki '*')."""
        if not _ALLOWED or "*" in _ALLOWED:
            return "*"
        origin = self.headers.get("Origin", "")
        return origin if origin in _ALLOWED else _ALLOWED[0]

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight (POST + application/json shuni chaqiradi)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _handle_chat(self):
        """Sayt chati -> AI sotuv agenti (chat_ai). {messages:[...]} -> {reply:...}."""
        if not chat_ai.has_key():
            self._send_json(500, {"error": "LLM_API_KEY sozlanmagan"})
            return
        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        now = time.monotonic()
        if now - _last_chat.get(ip, 0) < _CHAT_COOLDOWN:
            self._send_json(200, {"reply": "Bir soniya 🙂 yana yozing."})
            return
        _last_chat[ip] = now
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
            history = data.get("messages", []) if isinstance(data, dict) else []
        except Exception as e:
            logger.warning("[chat] noto'g'ri JSON: %s", e)
            self._send_json(400, {"ok": False, "error": "bad_request"})
            return
        try:
            reply = chat_ai.reply_for(history)
            self._send_json(200, {"reply": reply})
        except Exception as e:
            logger.warning("[chat] AI xato: %s", e)
            self._send_json(200, {"reply": "Kechirasiz, bir oz texnik nosozlik 😅 "
                                           "Iltimos, to'g'ridan-to'g'ri yozing: +998 77 009 71 71"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        # Sayt chati -> AI sotuv agenti
        if path == "/chat":
            self._handle_chat()
            return
        # Saytdagi buyurtma formasi shu yerga JSON yuboradi -> bot topic ochadi
        if path != "/api/order":
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
    # Threaded: /chat (sekin AI chaqiruvi) statik fayllar berilishini bloklamaydi.
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler) as httpd:
        ai_state = "BOR" if chat_ai.has_key() else "kalit yoq"
        print(f"[web] sim.texnoset.uz statik server :{PORT} -> {WEB_DIR} (chat AI: {ai_state})", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
