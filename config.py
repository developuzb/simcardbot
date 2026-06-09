import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

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

# Yetkazib berish tezligi turlari
DELIVERY_TYPES = {
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
    "ish_vaqti": {
        "name": "Ish vaqtida yetkazish",
        "desc": "12 soat ichida (bepul)",
        "price": 0,
        "emoji": "🕐",
    },
}
