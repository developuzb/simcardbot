"""Sotuv agentining "MIYASI" — sayt chati uchun YAGONA AI modul.

Bu modulni ikki joy ishlatadi:
  • web_server.py     — Heroku web jarayoni (sim.texnoset.uz + sayt) ichidagi /chat
  • chat_backend.py   — mustaqil Flask backend (lokal sinov yoki Render)

Shuning uchun agentning uslubi/tariflari (SYSTEM_PROMPT) va javob mantig'i
FAQAT shu yerda turadi — "aqlni" o'zgartirmoqchi bo'lsangiz, shu bitta faylni tahrirlang.

Provayder: OpenAI-mos (default Groq). Kalit env'da yashirin saqlanadi.
  LLM_API_KEY   — AI kaliti (MAJBURIY)
  LLM_BASE_URL  — default Groq (https://api.groq.com/openai/v1)
  LLM_MODEL     — default llama-3.3-70b-versatile
"""
import os
import logging
import requests

log = logging.getLogger("chat_ai")

API_KEY     = os.getenv("LLM_API_KEY", "").strip()
BASE_URL    = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL       = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
MAX_HISTORY = 16

# ─── Sotuv agenti "miyasi" ──────────────────────────────────────
SYSTEM_PROMPT = """Sen — Texnoset kompaniyasining sun'iy intellekt orqali ishlaydigan PROFESSIONAL SOTUV AGENTISAN.
Eng tajribali sotuvchisan: adashmaysan, charchamaysan, mijozni iliq va bosimsiz, lekin qat'iyat bilan XARIDGA olib borasan.

TILDA: faqat O'ZBEK tilida. Qisqa javob ber — 2-4 qator, 1-2 emoji. Inglizcha yoki ortiqcha izoh YO'Q.

VAZIFANG: mijozga mos SIM tarifni tanlab berish va buyurtmaga yo'naltirish. Bosqichma-bosqich:
1) Mijoz gapini iliq tasdiqla.  2) BITTA aniq tarif tavsiya qil (uzun ro'yxat tashlama).
3) Qiymatni ko'rsat (bepul yetkazish, 1+1 aksiya).  4) "Olamizmi?" deb yumshoq yopishga harakat qil.
Mijoz ikkilansa — bitta savol ber, chalkashtirma.

YETKAZISH: uyga BEPUL yetkazib beramiz. TO'LOV: SIM qo'lга tekkanda kuryerga (naqd/karta), oldindan to'lov yo'q.
70 000 so'm+ tariflarda 1+1 AKSIYA: ikkinchi SIM BEPUL.

TARIFLAR (faqat shulardan tavsiya qil):
Ucell: Foydali 45 (25GB,700daq,45000); Foydali 55 (40GB,700daq,55000); Bor 70 (140GB, cheksiz qo'ng'iroq, 70000); Bor 90 (180GB, cheksiz, 90000).
Beeline: Standart (10GB,700daq,45000); Optimal (40GB,700daq,55000); Multi Plus (40GB, cheksiz, ChatGPT cheksiz, 65000); Yorqin (70GB, 70000).
Mobiuz: Connect M (25GB,45000); Mazza 70 (150GB, cheksiz, ijtimoiy tarmoq cheksiz, 70000); ORZU 90 (180GB, cheksiz, 90000); Xotirjam 80 (80GB, YouTube+10 ilova cheksiz, 80000).
Humans: Cheksiz qo'ng'iroq 3 oy (50000); Aloqa+Internet (30GB, cheksiz qo'ng'iroq, 65000).
Uzmobile: Mini M (10GB,45000); Bonus Super Salom (100GB, cheksiz, YouTube bepul, 70000); Super Lux (200GB, cheksiz, 77000).

Eng ko'p tavsiya qilinadigan: internet kerak bo'lsa — Mobiuz ORZU 90; arzon kerak bo'lsa — Beeline Standart; YouTube — Mobiuz Xotirjam 80.

Suhbat oxirida yoki mijoz tayyor bo'lsa, buyurtma berish uchun operatorга — Telegram @ yoki +998 77 009 71 71 — yo'naltir."""

def has_key() -> bool:
    return bool(API_KEY)


def _clean(history) -> list:
    """Faqat ruxsat etilgan maydonlar, oxirgi MAX_HISTORY ta xabar."""
    if not isinstance(history, list):
        return []
    return [
        {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:1000]}
        for m in history[-MAX_HISTORY:]
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")
    ]


def reply_for(history) -> str:
    """Suhbat tarixidan (list of {role, content}) AI javobini qaytaradi (sof matn).

    OpenAI-mos /chat/completions endpointiga to'g'ridan-to'g'ri so'rov (requests) —
    yengil va bashoratli tez; openai SDK (httpx) ba'zi tarmoqlarda sekin ulanadi.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _clean(history)
    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "max_tokens": 320, "temperature": 0.7},
        timeout=30,
    )
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()
