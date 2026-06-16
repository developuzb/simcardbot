"""Har mijozga bitta forum topic — user_id -> thread_id (JSON).

Mijoz /start bosganda buyurtmalar guruhida unga topic ochiladi.
Qayta /start bosса yangi ochilmaydi — shu yerda saqlangan thread
qayta ishlatiladi. Buyurtma bersa ham o'sha topic ichiga tushadi.

Heroku fayl tizimi restartда tozalanishi mumkin — DATA_DIR=/data
ulansa doimiy bo'ladi. Best-effort: asosiy oqimni hech qachon buzmaydi.
"""
import os
import json
import logging
from threading import Lock
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_FILE = os.path.join(_DATA_DIR, "lead_topics.json")
_lock = Lock()
_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is not None:
        return _data
    d = {}
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
    except Exception as e:
        logger.error("lead_topics load xatolik: %s", e)
    _data = d
    return _data


def _save():
    try:
        atomic_write_json(_FILE, _data, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.error("lead_topics save xatolik: %s", e)


def get_topic(user_id) -> int | None:
    """Mijozning forum topic thread_id'si (yo'q bo'lsa None)."""
    v = _load().get(str(user_id))
    try:
        return int(v) if v else None
    except (ValueError, TypeError):
        return None


def set_topic(user_id, thread_id: int):
    with _lock:
        d = _load()
        d[str(user_id)] = int(thread_id)
        _save()


def clear_topic(user_id):
    """Topic o'chirilgan/yopilgan bo'lsa — keyingi safar qayta ochish uchun."""
    with _lock:
        d = _load()
        if str(user_id) in d:
            d.pop(str(user_id), None)
            _save()
