"""Reklama (avto-post) sozlamalari.

Saqlanadigan ma'lumotlar:
  - groups : reklama yuboriladigan maqsad guruh/kanallar [{id, title}]
  - posts  : tasdiqlangan reklama postlari (navbat bilan yuboriladi) [{id, text, photo}]
  - times  : kunlik yuborish vaqtlari (Toshkent), masalan ["10:00", "19:00"]
  - enabled: avto-yuborish yoqilganmi
  - rotate_idx / next_post_id : ichki hisoblagichlar

JSON'da saqlanadi (DATA_DIR). ⚠️ Heroku dyno fayl-xotirasi vaqtinchalik —
restartда tozalanadi. Doimiy bo'lishi uchun guruhlar/vaqtlarni env'ga yozing:
  AD_GROUP_IDS="-100123,-100456"   AD_TIMES="10:00,19:00"   AD_ENABLED="true"
Env berilsa, u JSON ustidan ustun turadi.
"""
import json
import os
import logging
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_FILE = os.path.join(_DATA_DIR, "ads.json")

_cache: dict | None = None


def _defaults() -> dict:
    return {
        "groups": [],        # [{"id": int, "title": str}]
        "posts": [],         # [{"id": int, "text": str, "photo": str}]
        "times": [],         # ["10:00", "19:00"] (Toshkent)
        "enabled": False,
        "rotate_idx": 0,
        "next_post_id": 1,
    }


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    data = _defaults()
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k in data:
                if k in saved:
                    data[k] = saved[k]
    except Exception as e:
        logger.error("ads_store load xatolik: %s", e)
    _cache = data
    return _cache


def _save() -> bool:
    try:
        atomic_write_json(_FILE, _cache, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("ads_store save xatolik: %s", e)
        return False


# ─── ENV FALLBACK ────────────────────────────────────────────────

def _env_group_ids() -> list[int]:
    out = []
    for p in os.getenv("AD_GROUP_IDS", "").split(","):
        p = p.strip()
        if p.lstrip("-").isdigit():
            out.append(int(p))
    return out


def _env_times() -> list[str]:
    return [t.strip() for t in os.getenv("AD_TIMES", "").split(",") if t.strip()]


# ─── GURUHLAR ────────────────────────────────────────────────────

def get_groups() -> list[dict]:
    """Reklama guruhlari (JSON + env birlashtirilgan, takrorsiz)."""
    d = _load()
    groups = [dict(g) for g in d.get("groups", [])]
    have = {g["id"] for g in groups}
    for gid in _env_group_ids():
        if gid not in have:
            groups.append({"id": gid, "title": f"Guruh {gid} (env)"})
            have.add(gid)
    return groups


def add_group(chat_id: int, title: str = "") -> bool:
    """Guruhni qo'shadi. Yangi qo'shilsa True, allaqachon bo'lsa False."""
    d = _load()
    chat_id = int(chat_id)
    for g in d.setdefault("groups", []):
        if g["id"] == chat_id:
            if title:
                g["title"] = title
            _save()
            return False
    d["groups"].append({"id": chat_id, "title": title or f"Guruh {chat_id}"})
    _save()
    return True


def remove_group(chat_id: int) -> bool:
    d = _load()
    chat_id = int(chat_id)
    before = len(d.get("groups", []))
    d["groups"] = [g for g in d.get("groups", []) if g["id"] != chat_id]
    _save()
    return len(d["groups"]) < before


# ─── POSTLAR ─────────────────────────────────────────────────────

def get_posts() -> list[dict]:
    return [dict(p) for p in _load().get("posts", [])]


def add_post(text: str, photo: str = "") -> int:
    """Tasdiqlangan postni qo'shadi. Post ID qaytaradi."""
    d = _load()
    pid = int(d.get("next_post_id", 1))
    d.setdefault("posts", []).append({"id": pid, "text": text or "", "photo": photo or ""})
    d["next_post_id"] = pid + 1
    _save()
    return pid


def remove_post(post_id: int) -> bool:
    d = _load()
    post_id = int(post_id)
    before = len(d.get("posts", []))
    d["posts"] = [p for p in d.get("posts", []) if p["id"] != post_id]
    _save()
    return len(d["posts"]) < before


def next_rotation_post() -> dict | None:
    """Navbatdagi postni qaytaradi va indeksni oldinga suradi."""
    d = _load()
    posts = d.get("posts", [])
    if not posts:
        return None
    idx = int(d.get("rotate_idx", 0)) % len(posts)
    post = dict(posts[idx])
    d["rotate_idx"] = (idx + 1) % len(posts)
    _save()
    return post


# ─── VAQTLAR ─────────────────────────────────────────────────────

def get_times() -> list[str]:
    """Kunlik yuborish vaqtlari (env ustun)."""
    env = _env_times()
    if env:
        return env
    return list(_load().get("times", []))


def set_times(times: list[str]) -> bool:
    d = _load()
    d["times"] = list(times)
    return _save()


# ─── YOQILGAN/O'CHIQ ─────────────────────────────────────────────

def is_enabled() -> bool:
    v = os.getenv("AD_ENABLED", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return bool(_load().get("enabled", False))


def set_enabled(value: bool) -> bool:
    d = _load()
    d["enabled"] = bool(value)
    return _save()
