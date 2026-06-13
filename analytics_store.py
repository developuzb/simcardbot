"""AI suhbat va buyurtma analitikasi — JSON faylga yoziladi.

Eslatma: Heroku/Railway fayl tizimi restartда tozalanadi, shuning uchun
DATA_DIR=/data (volume) ulansa doimiy bo'ladi. Aks holda hisoblar
oxirgi restartdan beri yig'iladi (taxminan kunlik).
"""
import json
import os
import logging
from datetime import datetime
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_FILE = os.path.join(_DATA_DIR, "analytics.json")

_cache: dict | None = None


def _empty() -> dict:
    return {
        "since": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ai_sessions": 0,      # AI chat necha marta ochildi
        "ai_orders": 0,        # AI orqali buyurtma
        "orders": 0,           # jami buyurtma (AI + oddiy)
        "revenue": 0,          # jami buyurtma summasi (so'm)
        "out_of_zone": 0,      # hudud tashqarisidagi urinishlar
        "followups_sent": 0,   # tugatmaganlarga yuborilgan fikr so'rovlari
        "feedbacks": 0,        # qaytib kelgan fikrlar
        "operators": {},       # {op_id: count}
        "tariffs": {},         # {"op_id:tariff_id": count}
        "advice": {},          # {kategoriya: count}
        "today": {},           # {"YYYY-MM-DD": {orders, revenue, ai_sessions, out_of_zone}}
    }


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    data = _empty()
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in _empty().items():
                data[k] = saved.get(k, v)
    except Exception as e:
        logger.error(f"analytics load xatolik: {e}")
    _cache = data
    return _cache


def _save():
    try:
        atomic_write_json(_FILE, _cache, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"analytics save xatolik: {e}")


def _today_bucket() -> dict:
    d = _load()
    key = datetime.now().strftime("%Y-%m-%d")
    if key not in d["today"]:
        d["today"][key] = {"orders": 0, "revenue": 0, "ai_sessions": 0, "out_of_zone": 0}
        # faqat oxirgi 14 kunni saqlaymiz
        if len(d["today"]) > 14:
            for old in sorted(d["today"])[:-14]:
                d["today"].pop(old, None)
    return d["today"][key]


# ─── VOQEALARNI YOZISH ───────────────────────────────────────────

def ai_session():
    d = _load()
    d["ai_sessions"] += 1
    _today_bucket()["ai_sessions"] += 1
    _save()


def operator_asked(op_id: str):
    d = _load()
    d["operators"][op_id] = d["operators"].get(op_id, 0) + 1
    _save()


def tariff_chosen(op_id: str, tariff_id: str):
    d = _load()
    key = f"{op_id}:{tariff_id}"
    d["tariffs"][key] = d["tariffs"].get(key, 0) + 1
    _save()


_ADVICE_KEYWORDS = {
    "arzon": ["arzon", "narx", "qancha", "tejam", "byudjet"],
    "internet": ["internet", "gb", "gigabayt", "trafik", "ko'p internet"],
    "youtube": ["youtube", "video", "tiktok", "ijtimoiy", "instagram", "telegram"],
    "qongiroq": ["qo'ng'iroq", "qongiroq", "daqiqa", "minut", "gaplash"],
}


def advice_query(text: str):
    d = _load()
    t = (text or "").lower()
    cat = "boshqa"
    for c, kws in _ADVICE_KEYWORDS.items():
        if any(k in t for k in kws):
            cat = c
            break
    d["advice"][cat] = d["advice"].get(cat, 0) + 1
    _save()


def order_placed(revenue: int, via_ai: bool = False):
    d = _load()
    d["orders"] += 1
    d["revenue"] += int(revenue or 0)
    if via_ai:
        d["ai_orders"] += 1
    bucket = _today_bucket()
    bucket["orders"] += 1
    bucket["revenue"] += int(revenue or 0)
    _save()


def out_of_zone():
    d = _load()
    d["out_of_zone"] += 1
    _today_bucket()["out_of_zone"] += 1
    _save()


def followup_sent():
    d = _load()
    d["followups_sent"] = d.get("followups_sent", 0) + 1
    _save()


def feedback_received():
    d = _load()
    d["feedbacks"] = d.get("feedbacks", 0) + 1
    _save()


# ─── O'QISH ──────────────────────────────────────────────────────

def snapshot() -> dict:
    return dict(_load())


def reset():
    global _cache
    _cache = _empty()
    _save()
