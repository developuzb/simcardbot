"""Sayt buyurtmasi <-> bot o'rtasidagi 'pending' ko'prik.

Sayt formasi /api/order ga buyurtma yuboradi -> bu yerda qisqa TOKEN bilan
vaqtincha saqlanadi. Mijoz Telegram botiga ?start=ord<token> bilan o'tib
/start bosganda, bot shu tokendagi buyurtmani o'qib davom ettiradi (guruhda
topic ochadi). Bot va sayt BITTA jarayonda ishlagani uchun fayl umumiy.
"""
import os
import json
import time
import secrets
import logging
from threading import Lock
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_FILE = os.path.join(_DATA_DIR, "web_pending.json")
_lock = Lock()
_TTL = 24 * 3600  # 24 soat — keyin eskirgan deb hisoblanadi


def _load() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error("web_pending load xatolik: %s", e)
    return {}


def _save(d: dict):
    try:
        atomic_write_json(_FILE, d, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.error("web_pending save xatolik: %s", e)


def _prune(d: dict) -> dict:
    now = time.time()
    for k in [k for k, v in d.items() if now - v.get("ts", 0) > _TTL]:
        d.pop(k, None)
    return d


def put_pending(data: dict) -> str:
    """Buyurtmani saqlaydi va qisqa tokenni qaytaradi."""
    token = secrets.token_hex(6)
    with _lock:
        d = _prune(_load())
        d[token] = {"data": data, "ts": time.time()}
        _save(d)
    logger.info("web_pending saqlandi token=%s", token)
    return token


def pop_pending(token: str):
    """Tokendagi buyurtmani qaytaradi va o'chiradi (yo'q/eskirgan bo'lsa None)."""
    if not token:
        return None
    with _lock:
        d = _load()
        entry = d.pop(token, None)
        if entry is not None:
            _save(d)
    if not entry or time.time() - entry.get("ts", 0) > _TTL:
        return None
    return entry.get("data")
