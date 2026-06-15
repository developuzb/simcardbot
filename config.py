import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
def _parse_admin_ids(raw: str) -> list:
    """ADMIN_IDS ni xavfsiz parse qiladi.

    Bo'sh elementlar, problar va raqam bo'lmagan qiymatlar tashlab yuboriladi.
    Natija bo'sh bo'lsa — ogohlantirish loglanadi.
    """
    import logging as _logging
    result = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            _logging.getLogger(__name__).warning(
                "ADMIN_IDS ichida noto'g'ri qiymat tashlab yuborildi: %r", part
            )
    if not result:
        _logging.getLogger(__name__).warning(
            "ADMIN_IDS bo'sh yoki to'g'ri qiymat yo'q — adminlarga xabar yetib bormaydi!"
        )
    return result


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", "123456789"))

# AI API (OpenAI-compatible). Hozir BEPUL Google Gemini ishlatilmoqda.
# Kalit: https://aistudio.google.com/apikey (karta kerak emas, bepul)
# O'zgaruvchi nomlari TOKENMIX_* qolgan — ular umumiy OpenAI-compatible sozlama.
TOKENMIX_API_KEY = os.getenv("TOKENMIX_API_KEY", "")
TOKENMIX_BASE_URL = os.getenv(
    "TOKENMIX_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)
TOKENMIX_MODEL = os.getenv("TOKENMIX_MODEL", "gemini-3.1-flash-lite")

# Eski Anthropic kaliti — faqat eski kod bilan moslik uchun saqlanib qolgan
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Mijoz aloqasi (Telegram username va telefon)
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "@texnoset_digital")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "+998770097171")
FOUNDER_CONTACT = os.getenv("FOUNDER_CONTACT", "@aflaha_s")
OFFICE_ADDRESS = os.getenv(
    "OFFICE_ADDRESS",
    "Qashqadaryo, Qarshi tumani, Qovchin shaharchasi — markaziy yo'lning "
    "4-km qismida (har ikki tomondan kirishda), Eski garaj yaqinida.",
)
WORK_DAYS = os.getenv("WORK_DAYS", "har kuni")

# Ish vaqti (Toshkent, soat). Tezkor yetkazish faqat shu oraliqda.
WORK_START_HOUR = int(os.getenv("WORK_START_HOUR", "9"))
WORK_END_HOUR = int(os.getenv("WORK_END_HOUR", "21"))

# 1+1 aksiya: shu narx va undan qimmat tariflarga 2-SIM/raqam bepul
PROMO_1PLUS1_MIN_PRICE = int(os.getenv("PROMO_1PLUS1_MIN_PRICE", "70000"))
PROMO_1PLUS1_BADGE = "🎁 1+1"
PROMO_1PLUS1_TEXT = "🎁 <b>1+1 AKSIYA:</b> bu tarifga ikkinchi SIM karta BEPUL!"

# Google Sheets
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "YOUR_SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Buyurtmalar")

# Yetkazib berish narxlari (so'm)
DELIVERY_PRICES = {
    "Toshkent shahar": 15_000,
    "Toshkent viloyati": 20_000,
    "Samarqand": 25_000,
    "Buxoro": 30_000,
    "Namangan": 25_000,
    "Andijon": 25_000,
    "Farg'ona": 25_000,
    "Qashqadaryo": 30_000,
    "Surxondaryo": 35_000,
    "Xorazm": 35_000,
    "Navoiy": 30_000,
    "Jizzax": 25_000,
    "Sirdaryo": 25_000,
    "Qoraqalpog'iston": 40_000,
}

DEFAULT_DELIVERY_PRICE = 35_000

# Yetkazib berish hududi (Railway Variables dan o'rnatiladi)
DELIVERY_LAT = float(os.getenv("DELIVERY_LAT", "41.2995"))
DELIVERY_LON = float(os.getenv("DELIVERY_LON", "69.2401"))
DELIVERY_RADIUS_KM = float(os.getenv("DELIVERY_RADIUS_KM", "12.0"))
DELIVERY_ZONE_NAME = os.getenv("DELIVERY_ZONE_NAME", "Yetkazib berish hududi")

# Yetkazib berish tezligi turlari (bepul birinchi o'rinda)
DELIVERY_TYPES = {
    "ish_vaqti": {
        "name": "Bepul yetkazish",
        "desc": "6 soat ichida",
        "price": 0,
        "emoji": "🆓",
    },
    "tezkor": {
        "name": "Tezkor yetkazish",
        "desc": "1 soat ichida",
        "price": 10_000,
        "emoji": "⚡",
    },
    "standart": {
        "name": "Standart yetkazish",
        "desc": "2 soat ichida",
        "price": 5_000,
        "emoji": "🚗",
    },
}

# ─── Referal: taklif qilingan do'st BIRINCHI buyurtmada chegirma oladi ──
REFERRAL_DISCOUNT = int(os.getenv("REFERRAL_DISCOUNT", "5000"))

# ─── Mijozga ko'rsatiladigan ishonch/aniqlik matnlari (yagona manba) ────
# Biznes faktlari shu yerda — hamma joyda bir xil ishlatiladi (qarama-qarshilik bo'lmasin)
PAYMENT_NOTE = "💵 To'lov — SIM qo'lingizga tekkanda kuryerga (naqd yoki karta)"
PASSPORT_NOTE = "🪪 Rasmiylashtirish uchun pasportingizni tayyorlab qo'ying"
NUMBER_NOTE = "📱 Raqamni oldindan operator bilan kelishasiz yoki kuryer oldida o'zingiz tanlaysiz"
TRUST_NOTE = "✅ Rasmiy SIM · Pasport bilan rasmiylashtiriladi · Yoqmasa — olishingiz shart emas"
