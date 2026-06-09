import asyncio
import os
import gspread
from functools import partial
from google.oauth2.service_account import Credentials
from datetime import datetime
from config import GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID, SHEET_NAME
import logging
import time

logger = logging.getLogger(__name__)

# Credentials fayli yo'q bo'lsa — Sheets'ga urinmaymiz (tez, log spam yo'q).
_SHEETS_ENABLED: bool | None = None


def _sheets_enabled() -> bool:
    global _SHEETS_ENABLED
    if _SHEETS_ENABLED is None:
        _SHEETS_ENABLED = os.path.exists(GOOGLE_CREDENTIALS_FILE)
        if not _SHEETS_ENABLED:
            logger.warning(
                "Google Sheets o'chiq: '%s' topilmadi. Buyurtmalar saqlanmaydi.",
                GOOGLE_CREDENTIALS_FILE,
            )
    return _SHEETS_ENABLED

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COURIER_SHEET_NAME = "Kuryerlar"

O = {
    "num": 0, "date": 1, "time": 2, "name": 3, "user_id": 4,
    "phone": 5, "operator": 6, "tariff": 7, "sim": 8, "region": 9,
    "delivery_price": 10, "tariff_price": 11, "total": 12,
    "status": 13, "courier_id": 14, "courier_name": 15, "note": 16,
}

C = {
    "telegram_id": 0, "name": 1, "phone": 2, "regions": 3,
    "status": 4, "completed": 5, "joined": 6,
}

ORDER_HEADERS = [
    "№", "Sana", "Vaqt", "Mijoz ismi", "Telegram ID", "Telefon",
    "Operator", "Tarif", "Sim raqami", "Hudud",
    "Yetkazish narxi", "Tarif narxi", "Jami",
    "Status", "Kuryer ID", "Kuryer ismi", "Izoh",
]

COURIER_HEADERS = [
    "Telegram ID", "Ism", "Telefon", "Hududlar",
    "Holat", "Bajarilgan", "Qo'shilgan",
]

_client = None
_order_sheet = None
_courier_sheet = None
_couriers_cache: dict = {}
_couriers_cache_time: float = 0
CACHE_TTL = 300


async def _run(fn, *args, **kwargs):
    """Sinxron gspread chaqiruvlarini thread executor'da ishlatish."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


def _get_client():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_sheet():
    global _order_sheet
    if not _sheets_enabled():
        return None
    if _order_sheet is None:
        try:
            client = _get_client()
            ss = client.open_by_key(SPREADSHEET_ID)
            try:
                _order_sheet = ss.worksheet(SHEET_NAME)
            except gspread.WorksheetNotFound:
                _order_sheet = ss.add_worksheet(title=SHEET_NAME, rows=2000, cols=20)
                _order_sheet.append_row(ORDER_HEADERS)
        except Exception as e:
            logger.error(f"Order sheet xatolik: {e}")
            return None
    return _order_sheet


def get_courier_sheet():
    global _courier_sheet
    if not _sheets_enabled():
        return None
    if _courier_sheet is None:
        try:
            client = _get_client()
            ss = client.open_by_key(SPREADSHEET_ID)
            try:
                _courier_sheet = ss.worksheet(COURIER_SHEET_NAME)
            except gspread.WorksheetNotFound:
                _courier_sheet = ss.add_worksheet(title=COURIER_SHEET_NAME, rows=500, cols=10)
                _courier_sheet.append_row(COURIER_HEADERS)
        except Exception as e:
            logger.error(f"Courier sheet xatolik: {e}")
            return None
    return _courier_sheet


# ─── BUYURTMALAR ────────────────────────────────────────────────

async def save_order(order_data: dict) -> int | None:
    sheet = get_sheet()
    if not sheet:
        return None

    def _sync():
        all_rows = sheet.get_all_values()
        nums = []
        for row in all_rows[1:]:
            try:
                nums.append(int(row[O["num"]]))
            except (ValueError, IndexError):
                pass
        order_num = max(nums, default=0) + 1

        now = datetime.now()
        total = order_data.get("delivery_price", 0) + order_data.get("tariff_price", 0)
        row = [""] * len(ORDER_HEADERS)
        row[O["num"]] = order_num
        row[O["date"]] = now.strftime("%Y-%m-%d")
        row[O["time"]] = now.strftime("%H:%M:%S")
        row[O["name"]] = order_data.get("name", "")
        row[O["user_id"]] = str(order_data.get("user_id", ""))
        row[O["phone"]] = order_data.get("contact_phone", "")
        row[O["operator"]] = order_data.get("operator_name", "")
        row[O["tariff"]] = order_data.get("tariff_name", "")
        row[O["sim"]] = order_data.get("sim_number", "")
        row[O["region"]] = order_data.get("region", "")
        row[O["delivery_price"]] = order_data.get("delivery_price", 0)
        row[O["tariff_price"]] = order_data.get("tariff_price", 0)
        row[O["total"]] = total
        row[O["status"]] = "Yangi"
        row[O["courier_id"]] = ""
        row[O["courier_name"]] = ""
        row[O["note"]] = ""
        sheet.append_row(row)
        return order_num

    try:
        return await _run(_sync)
    except Exception as e:
        logger.error(f"save_order xatolik: {e}")
        return None


async def get_all_orders(status: str | None = None) -> list[dict]:
    sheet = get_sheet()
    if not sheet:
        return []

    def _sync():
        rows = sheet.get_all_values()[1:]
        orders = []
        for row in rows:
            if len(row) < len(ORDER_HEADERS):
                row += [""] * (len(ORDER_HEADERS) - len(row))
            order = _row_to_order(row)
            if status is None or order["status"] == status:
                orders.append(order)
        return orders

    try:
        return await _run(_sync)
    except Exception as e:
        logger.error(f"get_all_orders xatolik: {e}")
        return []


async def get_order_by_num(order_num: int) -> dict | None:
    sheet = get_sheet()
    if not sheet:
        return None

    def _sync():
        rows = sheet.get_all_values()[1:]
        for i, row in enumerate(rows):
            if len(row) < len(ORDER_HEADERS):
                row += [""] * (len(ORDER_HEADERS) - len(row))
            if str(row[O["num"]]) == str(order_num):
                return _row_to_order(row, sheet_row=i + 2)
        return None

    try:
        return await _run(_sync)
    except Exception as e:
        logger.error(f"get_order_by_num xatolik: {e}")
        return None


async def update_order(order_num: int, updates: dict) -> bool:
    """Barcha o'zgarishlarni bitta batch API chaqiruvida yuboradi."""
    sheet = get_sheet()
    if not sheet:
        return False

    def _sync():
        rows = sheet.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if str(row[O["num"]]) == str(order_num):
                cells = []
                for field, value in updates.items():
                    if field in O:
                        cells.append(gspread.Cell(i, O[field] + 1, value))
                if cells:
                    sheet.update_cells(cells)
                return True
        return False

    try:
        return await _run(_sync)
    except Exception as e:
        logger.error(f"update_order xatolik: {e}")
        return False


async def get_orders_by_courier(courier_id: int | str) -> list[dict]:
    sheet = get_sheet()
    if not sheet:
        return []

    def _sync():
        rows = sheet.get_all_values()[1:]
        result = []
        for row in rows:
            if len(row) < len(ORDER_HEADERS):
                row += [""] * (len(ORDER_HEADERS) - len(row))
            if str(row[O["courier_id"]]) == str(courier_id):
                result.append(_row_to_order(row))
        return result

    try:
        return await _run(_sync)
    except Exception as e:
        logger.error(f"get_orders_by_courier xatolik: {e}")
        return []


async def get_stats() -> dict:
    orders = await get_all_orders()
    stats = {
        "total": len(orders), "Yangi": 0, "Tayinlandi": 0,
        "Yo'lda": 0, "Yetkazildi": 0, "Bekor": 0, "revenue": 0,
    }
    for o in orders:
        s = o.get("status", "")
        if s in stats:
            stats[s] += 1
        if s == "Yetkazildi":
            try:
                stats["revenue"] += int(o.get("total", 0))
            except ValueError:
                pass
    return stats


def _row_to_order(row: list, sheet_row: int = None) -> dict:
    return {
        "num": row[O["num"]],
        "date": row[O["date"]],
        "time": row[O["time"]],
        "name": row[O["name"]],
        "user_id": row[O["user_id"]],
        "phone": row[O["phone"]],
        "operator": row[O["operator"]],
        "tariff": row[O["tariff"]],
        "sim": row[O["sim"]],
        "region": row[O["region"]],
        "delivery_price": row[O["delivery_price"]],
        "tariff_price": row[O["tariff_price"]],
        "total": row[O["total"]],
        "status": row[O["status"]],
        "courier_id": row[O["courier_id"]],
        "courier_name": row[O["courier_name"]],
        "note": row[O["note"]],
        "_sheet_row": sheet_row,
    }


# ─── KURYERLAR ───────────────────────────────────────────────────

def _load_couriers_from_sheet() -> dict:
    sheet = get_courier_sheet()
    if not sheet:
        return {}
    try:
        rows = sheet.get_all_values()[1:]
        couriers = {}
        for row in rows:
            if len(row) < len(COURIER_HEADERS):
                row += [""] * (len(COURIER_HEADERS) - len(row))
            tid = row[C["telegram_id"]].strip()
            if tid:
                couriers[tid] = {
                    "telegram_id": tid,
                    "name": row[C["name"]],
                    "phone": row[C["phone"]],
                    "regions": row[C["regions"]],
                    "status": row[C["status"]],
                    "completed": row[C["completed"]],
                    "joined": row[C["joined"]],
                }
        return couriers
    except Exception as e:
        logger.error(f"_load_couriers xatolik: {e}")
        return {}


async def _get_couriers_cache() -> dict:
    global _couriers_cache, _couriers_cache_time
    if time.time() - _couriers_cache_time > CACHE_TTL:
        loop = asyncio.get_event_loop()
        _couriers_cache = await loop.run_in_executor(None, _load_couriers_from_sheet)
        _couriers_cache_time = time.time()
    return _couriers_cache


async def is_courier(telegram_id: int | str) -> bool:
    return str(telegram_id) in await _get_couriers_cache()


async def get_courier(telegram_id: int | str) -> dict | None:
    return (await _get_couriers_cache()).get(str(telegram_id))


async def get_all_couriers() -> list[dict]:
    return list((await _get_couriers_cache()).values())


async def add_courier(telegram_id: int | str, name: str, phone: str, regions: str) -> bool:
    global _couriers_cache
    sheet = get_courier_sheet()
    if not sheet:
        return False

    tid = str(telegram_id)

    def _sync():
        rows = sheet.get_all_values()[1:]
        for row in rows:
            if row and str(row[C["telegram_id"]]).strip() == tid:
                return False
        now = datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([tid, name, phone, regions, "Faol", "0", now])
        return True

    try:
        result = await _run(_sync)
        if result:
            now = datetime.now().strftime("%Y-%m-%d")
            _couriers_cache[tid] = {
                "telegram_id": tid, "name": name, "phone": phone,
                "regions": regions, "status": "Faol", "completed": "0", "joined": now,
            }
        return result
    except Exception as e:
        logger.error(f"add_courier xatolik: {e}")
        return False


async def remove_courier(telegram_id: int | str) -> bool:
    global _couriers_cache
    sheet = get_courier_sheet()
    if not sheet:
        return False

    tid = str(telegram_id)

    def _sync():
        rows = sheet.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[C["telegram_id"]]).strip() == tid:
                sheet.delete_rows(i)
                return True
        return False

    try:
        result = await _run(_sync)
        if result:
            _couriers_cache.pop(tid, None)
        return result
    except Exception as e:
        logger.error(f"remove_courier xatolik: {e}")
        return False


async def update_courier_completed(telegram_id: int | str) -> bool:
    global _couriers_cache
    sheet = get_courier_sheet()
    if not sheet:
        return False

    tid = str(telegram_id)

    def _sync():
        rows = sheet.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[C["telegram_id"]]).strip() == tid:
                current = int(row[C["completed"]] or 0)
                sheet.update_cell(i, C["completed"] + 1, current + 1)
                return current + 1
        return None

    try:
        new_count = await _run(_sync)
        if new_count is not None and tid in _couriers_cache:
            _couriers_cache[tid]["completed"] = str(new_count)
        return new_count is not None
    except Exception as e:
        logger.error(f"update_courier_completed xatolik: {e}")
        return False


def invalidate_courier_cache():
    global _couriers_cache_time
    _couriers_cache_time = 0
