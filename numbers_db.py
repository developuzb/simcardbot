"""
Raqamlar bazasi — numbers_db.json fayli asosida.
Har bir raqam: { "number": "93-301-10-05", "status": "mavjud" | "sotildi" }
"""
import json
import os
from threading import Lock

DB_FILE = os.path.join(os.path.dirname(__file__), "numbers_db.json")
_lock = Lock()
_db: dict[str, list[dict]] = {}


# ─── ICHKI YORDAMCHILAR ─────────────────────────────────────────

def _load():
    global _db
    if os.path.exists(DB_FILE):
        with open(DB_FILE, encoding="utf-8") as f:
            _db = json.load(f)
    else:
        _db = _default_db()
        _save()


def _save():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(_db, f, ensure_ascii=False, indent=2)


def _default_db() -> dict:
    return {
        "ucell": [
            {"number": n, "status": "mavjud"} for n in [
                "93-301-10-05", "93-301-10-12", "93-302-20-07", "93-302-20-18",
                "93-303-30-03", "93-303-30-21", "93-501-40-09", "93-501-40-14",
                "93-502-50-06", "93-502-50-17", "93-503-60-02", "93-503-60-23",
                "93-504-70-08", "93-504-70-19", "93-505-80-04", "93-505-80-11",
                "93-506-90-16", "93-506-90-25", "93-507-11-13", "93-507-11-28",
            ]
        ],
        "beeline": [
            {"number": n, "status": "mavjud"} for n in [
                "90-101-10-03", "90-101-10-17", "90-102-20-08", "90-102-20-22",
                "90-103-30-05", "90-103-30-19", "90-201-40-11", "90-201-40-26",
                "90-202-50-07", "90-202-50-14", "90-203-60-02", "90-203-60-18",
                "90-301-70-09", "90-301-70-23", "90-302-80-04", "90-302-80-16",
                "90-303-90-12", "90-303-90-27", "90-401-11-06", "90-401-11-21",
            ]
        ],
        "ums": [
            {"number": n, "status": "mavjud"} for n in [
                "91-401-10-04", "91-401-10-18", "91-402-20-09", "91-402-20-23",
                "91-403-30-05", "91-403-30-16", "91-501-40-11", "91-501-40-24",
                "91-502-50-07", "91-502-50-20", "91-503-60-03", "91-503-60-15",
                "91-504-70-08", "91-504-70-22", "91-505-80-02", "91-505-80-17",
                "91-506-90-13", "91-506-90-26", "91-507-11-06", "91-507-11-19",
            ]
        ],
        "humans": [
            {"number": n, "status": "mavjud"} for n in [
                "99-701-10-05", "99-701-10-21", "99-702-20-08", "99-702-20-24",
                "99-703-30-03", "99-703-30-17", "99-801-40-10", "99-801-40-25",
                "99-802-50-06", "99-802-50-19", "99-803-60-02", "99-803-60-14",
                "99-901-70-09", "99-901-70-22", "99-902-80-04", "99-902-80-16",
                "99-903-90-11", "99-903-90-27", "99-904-11-07", "99-904-11-23",
            ]
        ],
        "uzmobile": [
            {"number": n, "status": "mavjud"} for n in [
                "94-601-10-06", "94-601-10-19", "94-602-20-03", "94-602-20-22",
                "94-603-30-08", "94-603-30-17", "94-701-40-12", "94-701-40-25",
                "94-702-50-05", "94-702-50-20", "94-703-60-09", "94-703-60-18",
                "94-704-70-04", "94-704-70-23", "94-705-80-07", "94-705-80-14",
                "94-706-90-02", "94-706-90-16", "94-707-11-10", "94-707-11-24",
            ]
        ],
    }


# ─── PUBLIC API ─────────────────────────────────────────────────

def get_available(operator_id: str) -> list[str]:
    with _lock:
        return [n["number"] for n in _db.get(operator_id, []) if n.get("status") == "mavjud"]


def get_all(operator_id: str) -> list[dict]:
    with _lock:
        return list(_db.get(operator_id, []))


def mark_sold(operator_id: str, number: str) -> bool:
    with _lock:
        for n in _db.get(operator_id, []):
            if n["number"] == number:
                n["status"] = "sotildi"
                _save()
                return True
    return False


def mark_available(operator_id: str, number: str) -> bool:
    with _lock:
        for n in _db.get(operator_id, []):
            if n["number"] == number:
                n["status"] = "mavjud"
                _save()
                return True
    return False


def add_number(operator_id: str, number: str) -> bool:
    with _lock:
        if operator_id not in _db:
            _db[operator_id] = []
        for n in _db[operator_id]:
            if n["number"] == number:
                return False
        _db[operator_id].append({"number": number, "status": "mavjud"})
        _save()
        return True


def remove_number(operator_id: str, number: str) -> bool:
    with _lock:
        before = len(_db.get(operator_id, []))
        _db[operator_id] = [n for n in _db.get(operator_id, []) if n["number"] != number]
        if len(_db.get(operator_id, [])) < before:
            _save()
            return True
    return False


def stats() -> dict:
    with _lock:
        result = {}
        for op_id, numbers in _db.items():
            mavjud = sum(1 for n in numbers if n["status"] == "mavjud")
            sotildi = sum(1 for n in numbers if n["status"] == "sotildi")
            result[op_id] = {"mavjud": mavjud, "sotildi": sotildi, "jami": len(numbers)}
        return result


# ─── IMPORT VAQTIDA YUKLASH ─────────────────────────────────────
_load()
