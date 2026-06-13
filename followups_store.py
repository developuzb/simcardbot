"""Tugallanmagan buyurtmalarni kuzatish (abandonment) va fikr to'plash.

Mijoz buyurtmani boshlab, tugatmasa — 2 soatdan keyin undan fikr
so'raymiz. Fikrlar adminга AI tahlili bilan yetkaziladi.

JSON faylда saqlanadi (DATA_DIR aware). Heroku wipe'da yo'qoladi —
bu kritik emas (eski abandonmentlar follow-up olmaydi, xolos).
"""
import json
import os
import logging
from threading import Lock
from datetime import datetime, timezone
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_FILE = os.path.join(_DATA_DIR, "followups.json")
_lock = Lock()
_data: dict | None = None

# Bu bosqichlarga yetgan mijoz "qiziqqan" hisoblanadi (follow-up arzir)
_ENGAGED_STAGES_PREFIX = ("tariff:", "delivery", "phone", "location", "confirm")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    global _data
    if _data is None:
        try:
            if os.path.exists(_FILE):
                with open(_FILE, encoding="utf-8") as f:
                    _data = json.load(f)
            else:
                _data = {}
        except Exception as e:
            logger.error(f"followups load xatolik: {e}")
            _data = {}
    return _data


def _save():
    try:
        atomic_write_json(_FILE, _data, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.error(f"followups save xatolik: {e}")


def touch(user_id, stage: str, name: str = ""):
    """Mijoz faolligini qayd etadi (har bosqichda chaqiriladi)."""
    with _lock:
        d = _load()
        uid = str(user_id)
        rec = d.get(uid, {"started": _now(), "followed_up": False,
                          "awaiting_feedback": False, "completed": False})
        rec["last"] = _now()
        rec["stage"] = stage
        if name:
            rec["name"] = name
        rec["completed"] = False
        d[uid] = rec
        _save()


def complete(user_id):
    """Buyurtma tugadi — follow-up kerak emas."""
    with _lock:
        d = _load()
        uid = str(user_id)
        if uid in d:
            d[uid]["completed"] = True
            d[uid]["awaiting_feedback"] = False
            _save()


def due_for_followup(hours: float = 2.0) -> list:
    """2 soatdan beri faolligi yo'q, tugatmagan, hali so'ralmagan mijozlar."""
    now = datetime.now(timezone.utc)
    out = []
    with _lock:
        d = _load()
        for uid, rec in d.items():
            if rec.get("completed") or rec.get("followed_up"):
                continue
            stage = rec.get("stage", "")
            if not stage.startswith(_ENGAGED_STAGES_PREFIX):
                continue
            try:
                last = datetime.fromisoformat(rec["last"])
            except (KeyError, ValueError):
                continue
            if (now - last).total_seconds() >= hours * 3600:
                out.append({"user_id": uid, "name": rec.get("name", ""), "stage": stage})
    return out


def mark_followed(user_id):
    with _lock:
        d = _load()
        uid = str(user_id)
        if uid in d:
            d[uid]["followed_up"] = True
            d[uid]["awaiting_feedback"] = True
            d[uid]["followed_at"] = _now()
            _save()


def is_awaiting_feedback(user_id) -> bool:
    with _lock:
        rec = _load().get(str(user_id))
        return bool(rec and rec.get("awaiting_feedback"))


def save_feedback(user_id, text: str):
    with _lock:
        d = _load()
        uid = str(user_id)
        if uid in d:
            d[uid]["feedback"] = text
            d[uid]["awaiting_feedback"] = False
            d[uid]["completed"] = True  # boshqa follow-up bo'lmasin
            _save()


def snapshot() -> dict:
    """Analitika uchun jamlama."""
    with _lock:
        d = _load()
        total = len(d)
        completed = sum(1 for r in d.values() if r.get("completed") and not r.get("feedback"))
        abandoned = sum(1 for r in d.values()
                        if not r.get("completed") and str(r.get("stage", "")).startswith(_ENGAGED_STAGES_PREFIX))
        followed = sum(1 for r in d.values() if r.get("followed_up"))
        feedbacks = [r["feedback"] for r in d.values() if r.get("feedback")]
        # eng ko'p tashlab ketilgan bosqich
        stage_counts: dict = {}
        for r in d.values():
            if not r.get("completed"):
                s = str(r.get("stage", "")).split(":")[0]
                if s:
                    stage_counts[s] = stage_counts.get(s, 0) + 1
        return {
            "sessions": total, "abandoned": abandoned, "followed_up": followed,
            "feedbacks": feedbacks, "drop_stages": stage_counts,
        }
