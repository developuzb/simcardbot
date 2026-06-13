"""Referal: kim kimni taklif qilgani va chegirma ishlatilganmi (JSON).

Heroku fayl tizimi restartda tozalanishi mumkin — DATA_DIR=/data ulansa
doimiy bo'ladi. Best-effort: hech qachon asosiy oqimni buzmaydi.
"""
import os
import json
import logging
from threading import Lock
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_FILE = os.path.join(_DATA_DIR, "referrals.json")
_lock = Lock()
_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is not None:
        return _data
    d = {"users": {}, "counts": {}}
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            d["users"] = saved.get("users", {})
            d["counts"] = saved.get("counts", {})
    except Exception as e:
        logger.error("referrals load xatolik: %s", e)
    _data = d
    return _data


def _save():
    try:
        atomic_write_json(_FILE, _data, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.error("referrals save xatolik: %s", e)


def register(user_id, referrer_id) -> bool:
    """Yangi mijozni taklif qilgan bilan bog'laydi. Faqat 1 marta, o'zini emas."""
    uid, rid = str(user_id), str(referrer_id)
    if not rid.isdigit() or uid == rid:
        return False
    with _lock:
        d = _load()
        if uid in d["users"]:
            return False
        d["users"][uid] = {"referrer": rid, "discount_used": False}
        d["counts"][rid] = d["counts"].get(rid, 0) + 1
        _save()
        return True


def has_discount(user_id) -> bool:
    """Mijoz referal chegirmasiga loyiqmi (taklif qilingan va hali ishlatmagan)."""
    u = _load()["users"].get(str(user_id))
    return bool(u and not u.get("discount_used"))


def referrer_of(user_id):
    u = _load()["users"].get(str(user_id))
    return u.get("referrer") if u else None


def mark_used(user_id):
    with _lock:
        d = _load()
        u = d["users"].get(str(user_id))
        if u and not u.get("discount_used"):
            u["discount_used"] = True
            _save()


def invited_count(user_id) -> int:
    return _load()["counts"].get(str(user_id), 0)
