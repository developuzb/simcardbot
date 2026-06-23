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

import requests
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

# ─── Lead (sayt formasi -> Telegram) ────────────────────────────
# Lead qabul qiladigan Telegram chat: LEAD_CHAT_ID, bo'lmasa kuryer guruhi,
# bo'lmasa birinchi admin. Bot token bot.py bilan bir xil (.env / config var).
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
_LEAD_CHAT = (os.environ.get("LEAD_CHAT_ID")
              or os.environ.get("COURIER_GROUP_ID")
              or (os.environ.get("ADMIN_IDS", "").split(",")[0].strip() or ""))
_lead_last = {}          # IP bo'yicha lead spam himoyasi
_LEAD_COOLDOWN = 5.0


def _send_lead_to_telegram(name, phone, source, plan):
    """Lead'ni Telegram chatga yuboradi. True/False qaytaradi."""
    if not BOT_TOKEN or not _LEAD_CHAT:
        logger.warning("[lead] BOT_TOKEN yoki LEAD_CHAT_ID sozlanmagan")
        return False
    text = ("\U0001F525 YANGI LEAD (saytdan)\n\n"
            "\U0001F464 Ism: %s\n\U0001F4DE Tel: %s\n\U0001F3F7 Tarif: %s\n\U0001F310 Manba: %s"
            % (name, phone, plan or "—", source or "sayt"))
    try:
        r = requests.post(
            "https://api.telegram.org/bot%s/sendMessage" % BOT_TOKEN,
            json={"chat_id": _LEAD_CHAT, "text": text}, timeout=15,
        )
        if not r.ok:
            logger.error("[lead] Telegram javobi: %s %s", r.status_code, r.text[:200])
        return r.ok
    except Exception as e:
        logger.error("[lead] yuborilmadi: %s", e)
        return False


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

    def _handle_lead(self):
        """Sayt lead-formasi (ism+telefon) -> Telegram operator chatiga."""
        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        now = time.monotonic()
        if now - _lead_last.get(ip, 0) < _LEAD_COOLDOWN:
            self._send_json(429, {"ok": False, "error": "too_many"})
            return
        _lead_last[ip] = now
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(data, dict):
                raise ValueError
        except Exception:
            self._send_json(400, {"ok": False, "error": "bad_request"})
            return
        name = str(data.get("name", "")).strip()[:80]
        phone = str(data.get("phone", "")).strip()[:40]
        source = str(data.get("source", "sayt")).strip()[:40]
        plan = str(data.get("plan", "")).strip()[:40]
        if not name or len("".join(c for c in phone if c.isdigit())) < 7:
            self._send_json(400, {"ok": False, "error": "name_phone_required"})
            return
        ok = _send_lead_to_telegram(name, phone, source, plan)
        self._send_json(200 if ok else 502, {"ok": ok})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        # Sayt chati -> AI sotuv agenti
        if path == "/chat":
            self._handle_chat()
            return
        # Sayt lead-formasi -> Telegram
        if path == "/lead":
            self._handle_lead()
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
        host = self.headers.get("Host", "").split(":")[0].lower()
        rel = self.path.split("?", 1)[0]
        target = self.translate_path(self.path)
        # texnoset.uz / www -> ekosistema hub (shu bitta dyno, qo'shimcha xarajatsiz)
        if host in ("texnoset.uz", "www.texnoset.uz"):
            if rel == "/" or not os.path.isfile(target):
                self.path = "/hub.html"
            return super().do_GET()
        # sim.texnoset.uz va boshqalar -> SIM sayt (mavjud bo'lmagan yo'l -> index.html)
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
