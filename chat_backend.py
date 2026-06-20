"""
Texnoset — Sotuv agenti CHAT BACKEND (mustaqil Flask server)
============================================================
Bu — agentni ALOHIDA ishlatish uchun yengil Flask o'rami (lokal sinov yoki Render).
Heroku'da esa shu mantiq web_server.py (/chat) ichida ishlaydi.

Agentning "miyasi" (SYSTEM_PROMPT + javob mantig'i) chat_ai.py da — YAGONA manba.
Bu fayl faqat HTTP qatlam: rate-limit, CORS, JSON.

ISHGA TUSHIRISH:
  pip install flask flask-cors requests python-dotenv
  .env ichida LLM_API_KEY=gsk_xxxxx  (yoki: set LLM_API_KEY=...)
  python chat_backend.py

SOZLAMALAR (env): LLM_API_KEY (majburiy), LLM_BASE_URL, LLM_MODEL, PORT, ALLOW_ORIGIN.
"""
import os
import time
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# .env'dan o'qish (fayl joylashgan papkadan — qaysi cwd'dan ishga tushirilsa ham topiladi)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import chat_ai  # agentning "miyasi" — SYSTEM_PROMPT, reply_for(), has_key()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chat")

PORT   = int(os.environ.get("PORT", "8000"))
ORIGIN = os.environ.get("ALLOW_ORIGIN", "*")

app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": ORIGIN}})

_last = {}  # IP bo'yicha oddiy rate-limit
COOLDOWN = 1.5


def _limited(ip):
    now = time.monotonic()
    if now - _last.get(ip, 0) < COOLDOWN:
        return True
    _last[ip] = now
    return False


@app.route("/chat", methods=["POST"])
def chat():
    if not chat_ai.has_key():
        return jsonify({"error": "LLM_API_KEY sozlanmagan"}), 500

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if _limited(ip):
        return jsonify({"reply": "Bir soniya 🙂 yana yozing."})

    data = request.get_json(silent=True) or {}
    history = data.get("messages", [])
    try:
        reply = chat_ai.reply_for(history)
        return jsonify({"reply": reply})
    except Exception as e:
        log.warning("AI xato: %s", e)
        return jsonify({"reply": "Kechirasiz, bir oz texnik nosozlik 😅 "
                                 "Iltimos, to'g'ridan-to'g'ri yozing: +998 77 009 71 71"}), 200


@app.route("/health")
def health():
    return jsonify({"ok": True, "model": chat_ai.MODEL, "key": chat_ai.has_key()})


if __name__ == "__main__":
    log.info("Chat backend ishga tushdi — port %s, model %s, kalit %s",
             PORT, chat_ai.MODEL, "BOR" if chat_ai.has_key() else "YO'Q!")
    app.run(host="0.0.0.0", port=PORT)
