"""
Texnoset — Sotuv agenti CHAT BACKEND (Heroku / sayt uchun)
==========================================================
Bu kichik server saytdagi chat va sun'iy intellekt o'rtasida turadi.
API kalitni YASHIRIN saqlaydi (saytga qo'yib bo'lmaydi — o'g'irlanadi).

LOKAL ISHGA TUSHIRISH:
  pip install -r requirements.txt
  set LLM_API_KEY=gsk_xxxxx        # Windows (Linux/Mac: export)
  python chat_backend.py

HEROKU env'lari (Settings → Config Vars):
  LLM_API_KEY   — AI kaliti (MAJBURIY)
  LLM_BASE_URL  — default Groq: https://api.groq.com/openai/v1
  LLM_MODEL     — default: llama-3.3-70b-versatile
  ALLOW_ORIGIN  — sayt domeningiz (masalan https://texnoset.uz). Default: *
"""
import os
import time
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chat")

API_KEY  = os.environ.get("LLM_API_KEY", "").strip()
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
MODEL    = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
PORT     = int(os.environ.get("PORT", "8000"))
ORIGIN   = os.environ.get("ALLOW_ORIGIN", "*")

app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": ORIGIN}})

SYSTEM_PROMPT = """Sen — Texnoset kompaniyasining sun'iy intellekt orqali ishlaydigan PROFESSIONAL SOTUV AGENTISAN.
Eng tajribali sotuvchisan: adashmaysan, charchamaysan, mijozni iliq va bosimsiz, lekin qat'iyat bilan XARIDGA olib borasan.

TILDA: faqat O'ZBEK tilida. Qisqa javob ber — 2-4 qator, 1-2 emoji. Inglizcha yoki ortiqcha izoh YO'Q.

VAZIFANG: mijozga mos SIM tarifni tanlab berish va buyurtmaga yo'naltirish. Bosqichma-bosqich:
1) Mijoz gapini iliq tasdiqla.  2) BITTA aniq tarif tavsiya qil (uzun ro'yxat tashlama).
3) Qiymatni ko'rsat (bepul yetkazish, 1+1 aksiya).  4) "Olamizmi?" deb yumshoq yopishga harakat qil.
Mijoz ikkilansa — bitta savol ber, chalkashtirma.

YETKAZISH: uyga BEPUL yetkazib beramiz. TO'LOV: SIM qo'lga tekkanda kuryerga (naqd/karta), oldindan to'lov yo'q.
70 000 so'm+ tariflarda 1+1 AKSIYA: ikkinchi SIM BEPUL.

TARIFLAR (faqat shulardan tavsiya qil):
Ucell: Foydali 45 (25GB,700daq,45000); Foydali 55 (40GB,700daq,55000); Bor 70 (140GB, cheksiz qo'ng'iroq, 70000); Bor 90 (180GB, cheksiz, 90000).
Beeline: Standart (10GB,700daq,45000); Optimal (40GB,700daq,55000); Multi Plus (40GB, cheksiz, ChatGPT cheksiz, 65000); Yorqin (70GB, 70000).
Mobiuz: Connect M (25GB,45000); Mazza 70 (150GB, cheksiz, ijtimoiy tarmoq cheksiz, 70000); ORZU 90 (180GB, cheksiz, 90000); Xotirjam 80 (80GB, YouTube+10 ilova cheksiz, 80000).
Humans: Cheksiz qo'ng'iroq 3 oy (50000); Aloqa+Internet (30GB, cheksiz qo'ng'iroq, 65000).
Uzmobile: Mini M (10GB,45000); Bonus Super Salom (100GB, cheksiz, YouTube bepul, 70000); Super Lux (200GB, cheksiz, 77000).

Eng ko'p tavsiya qilinadigan: internet kerak bo'lsa — Mobiuz ORZU 90; arzon kerak bo'lsa — Beeline Standart; YouTube — Mobiuz Xotirjam 80.

Suhbat oxirida yoki mijoz tayyor bo'lsa, buyurtma berish uchun operatorga — Telegram yoki +998 77 009 71 71 — yo'naltir."""

_last = {}
COOLDOWN = 1.5
MAX_HISTORY = 16


def _limited(ip):
    now = time.monotonic()
    if now - _last.get(ip, 0) < COOLDOWN:
        return True
    _last[ip] = now
    return False


@app.route("/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "LLM_API_KEY sozlanmagan"}), 500

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if _limited(ip):
        return jsonify({"reply": "Bir soniya 🙂 yana yozing."})

    data = request.get_json(silent=True) or {}
    history = data.get("messages", [])
    if not isinstance(history, list):
        history = []
    clean = [
        {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:1000]}
        for m in history[-MAX_HISTORY:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + clean

    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "max_tokens": 320, "temperature": 0.7},
            timeout=30,
        )
        r.raise_for_status()
        reply = r.json()["choices"][0]["message"]["content"].strip()
        return jsonify({"reply": reply})
    except Exception as e:
        log.warning("AI xato: %s", e)
        return jsonify({"reply": "Kechirasiz, bir oz texnik nosozlik 😅 "
                                 "Iltimos, to'g'ridan-to'g'ri yozing: +998 77 009 71 71"}), 200


@app.route("/health")
def health():
    return jsonify({"ok": True, "model": MODEL, "key": bool(API_KEY)})


if __name__ == "__main__":
    log.info("Chat backend ishga tushdi — port %s, model %s, kalit %s",
             PORT, MODEL, "BOR" if API_KEY else "YO'Q!")
    app.run(host="0.0.0.0", port=PORT)
