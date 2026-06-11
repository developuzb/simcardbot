"""Ofis lokatsiyasi va yetkazish radiusini saqlovchi oddiy JSON store.

Admin lokatsiyani yuborganda shu yerga yoziladi. Bot qayta ishga
tushganda shu fayldan o'qiydi. Fayl bo'lmasa — config.py dagi env
qiymatlari (DELIVERY_LAT/LON/RADIUS_KM) ishlatiladi.
"""
import json
import os
import logging
from config import DELIVERY_LAT, DELIVERY_LON, DELIVERY_RADIUS_KM, DELIVERY_ZONE_NAME

logger = logging.getLogger(__name__)

# Railway'da Volume ulansa, DATA_DIR=/data qilib doimiy saqlash mumkin.
# Aks holda loyiha papkasiga yoziladi (redeployда yo'qoladi).
_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
_SETTINGS_FILE = os.path.join(_DATA_DIR, "office_settings.json")

_cache: dict | None = None


def _defaults() -> dict:
    return {
        "lat": DELIVERY_LAT,
        "lon": DELIVERY_LON,
        "radius_km": DELIVERY_RADIUS_KM,
        "zone_name": DELIVERY_ZONE_NAME,
        # Kuryerlar guruhi (env COURIER_GROUP_ID birinchi, keyin /setgroup)
        "courier_group_id": int(os.getenv("COURIER_GROUP_ID", "0")),
    }


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    data = _defaults()
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            data.update({k: saved[k] for k in data if k in saved})
    except Exception as e:
        logger.error(f"settings_store load xatolik: {e}")
    _cache = data
    return _cache


def get_office() -> dict:
    """Joriy ofis sozlamalari: {lat, lon, radius_km, zone_name}."""
    return dict(_load())


def set_office(lat: float, lon: float, radius_km: float | None = None,
               zone_name: str | None = None) -> bool:
    """Ofis lokatsiyasini saqlaydi. radius/zone_name berilmasa eskisi qoladi."""
    global _cache
    current = _load()
    current["lat"] = float(lat)
    current["lon"] = float(lon)
    if radius_km is not None:
        current["radius_km"] = float(radius_km)
    if zone_name is not None:
        current["zone_name"] = zone_name
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        _cache = current
        return True
    except Exception as e:
        logger.error(f"settings_store save xatolik: {e}")
        return False


def set_radius(radius_km: float) -> bool:
    o = _load()
    return set_office(o["lat"], o["lon"], radius_km=radius_km)


def get_courier_group() -> int:
    """Kuryerlar guruhi chat ID. Env COURIER_GROUP_ID ustun, keyin /setgroup."""
    env = os.getenv("COURIER_GROUP_ID", "")
    if env.lstrip("-").isdigit() and int(env) != 0:
        return int(env)
    try:
        return int(_load().get("courier_group_id") or 0)
    except (ValueError, TypeError):
        return 0


def set_courier_group(chat_id: int) -> bool:
    global _cache
    current = _load()
    current["courier_group_id"] = int(chat_id)
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        _cache = current
        return True
    except Exception as e:
        logger.error(f"set_courier_group xatolik: {e}")
        return False
