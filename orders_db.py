"""Buyurtmalar bazasi — orders.json faylida saqlanadi.

sheets_handler buyurtma funksiyalari bilan bir xil interfeys (async),
shuning uchun admin/kuryer kodlari o'zgarishsiz ishlaydi.
DATA_DIR=/data (volume) ulansa doimiy bo'ladi.
"""
import json
import os
import logging
import secrets
from threading import Lock
from datetime import datetime
from storage_utils import atomic_write_json

logger = logging.getLogger(__name__)

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
DB_FILE = os.path.join(_DATA_DIR, "orders.json")
_lock = Lock()
_orders: list | None = None

# Buyurtma holatlari
STATUSES = [
    "Yangi",                # admin tasdig'ini kutmoqda
    "Tasdiqlangan",         # guruhda, kuryer kutilmoqda
    "Kuryerda",             # kuryer qabul qildi
    "Yo'lda",               # kuryer yo'lga chiqdi
    "Yetkazildi",
    "Mijoz yo'q",
    "Bekor",
    "Hudud tashqarisida",   # zona tashqarisidagi lead (admin qo'lda hal qiladi)
]


def _load() -> list:
    global _orders
    if _orders is None:
        try:
            if os.path.exists(DB_FILE):
                with open(DB_FILE, encoding="utf-8") as f:
                    _orders = json.load(f)
            else:
                _orders = []
        except Exception as e:
            logger.error(f"orders_db load xatolik: {e}")
            _orders = []
    return _orders


def _save():
    try:
        atomic_write_json(DB_FILE, _orders, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.error(f"orders_db save xatolik: {e}")


async def create_order(data: dict, status: str = "Yangi") -> int:
    """Yangi buyurtma yaratadi, ketma-ket raqam qaytaradi.

    Har buyurtmaga qisqa noyob `token` beriladi — bu Heroku wipe'dan
    keyin raqamlar takrorlansa ham, eski Telegram tugmasi YANGI
    buyurtmaga ta'sir qilmasligini ta'minlaydi (callback'da tekshiriladi).
    """
    with _lock:
        orders = _load()
        num = max((int(o.get("num", 0)) for o in orders), default=1000) + 1
        now = datetime.now()
        order = {
            "num": num,
            "token": secrets.token_hex(3),  # 6 hex belgi — noyob kalit
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "name": data.get("name", ""),
            "user_id": str(data.get("user_id", "")),
            "phone": data.get("phone", ""),
            "operator": data.get("operator", ""),
            "op_id": data.get("op_id", ""),
            "tariff": data.get("tariff", ""),
            "region": data.get("region", ""),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "distance_km": data.get("distance_km"),
            "delivery_price": int(data.get("delivery_price", 0)),
            "delivery_type": data.get("delivery_type", ""),
            "tariff_price": int(data.get("tariff_price", 0)),
            "total": int(data.get("tariff_price", 0)) + int(data.get("delivery_price", 0)),
            "promo": bool(data.get("promo", False)),
            "status": status,
            "courier_id": "",
            "courier_name": "",
            "group_msg_id": None,
            "rating": "",
            "note": "",
        }
        orders.append(order)
        _save()
        return num


async def rate_order(order_num, score: int) -> bool:
    """Atomik baholash — faqat hali baholanmagan bo'lsa yozadi."""
    with _lock:
        for o in _load():
            if str(o.get("num")) == str(order_num):
                if o.get("rating"):
                    return False
                o["rating"] = int(score)
                _save()
                return True
    return False


async def get_order_by_num(order_num) -> dict | None:
    with _lock:
        for o in _load():
            if str(o.get("num")) == str(order_num):
                return dict(o)
    return None


async def update_order(order_num, updates: dict) -> bool:
    with _lock:
        for o in _load():
            if str(o.get("num")) == str(order_num):
                o.update(updates)
                _save()
                return True
    return False


async def update_order_if(order_num, expected_status, updates: dict) -> bool:
    """Atomik: holat kutilganidek bo'lsagina yangilaydi (poyga himoyasi).

    expected_status — str yoki tuple.
    """
    if isinstance(expected_status, str):
        expected_status = (expected_status,)
    with _lock:
        for o in _load():
            if str(o.get("num")) == str(order_num):
                if o.get("status") not in expected_status:
                    return False
                o.update(updates)
                _save()
                return True
    return False


async def get_all_orders(status: str | None = None) -> list:
    with _lock:
        orders = [dict(o) for o in _load()]
    if status is not None:
        orders = [o for o in orders if o.get("status") == status]
    return list(reversed(orders))  # yangilari birinchi


async def get_orders_by_courier(courier_id) -> list:
    with _lock:
        return [dict(o) for o in _load()
                if str(o.get("courier_id")) == str(courier_id)]


async def get_stats() -> dict:
    with _lock:
        orders = [dict(o) for o in _load()]
    stats = {"total": len(orders), "revenue": 0, "by_status": {}}
    for s in STATUSES:
        stats["by_status"][s] = 0
    for o in orders:
        s = o.get("status", "")
        if s in stats["by_status"]:
            stats["by_status"][s] += 1
        if s == "Yetkazildi":
            try:
                stats["revenue"] += int(o.get("total", 0))
            except (ValueError, TypeError):
                pass
    return stats
