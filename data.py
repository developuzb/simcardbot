OPERATORS = {
    "ucell": {"name": "Ucell", "emoji": "🟡", "prefix": "+99893"},
    "beeline": {"name": "Beeline", "emoji": "🟠", "prefix": "+99890"},
    "ums": {"name": "Mobiuz (UMS)", "emoji": "🔴", "prefix": "+99891"},
    "humans": {"name": "Humans", "emoji": "🔵", "prefix": "+99899"},
    "uzmobile": {"name": "Uzmobile", "emoji": "🟢", "prefix": "+99894"},
}

# ─── TARIF REJALARI ─────────────────────────────────────────────
# Manba: ucell.uz | beeline.uz | mobi.uz | humans.uz | uztelecom.uz
# Yangilangan: 2026-iyun (faqat hozirgi aktiv tariflar)

TARIFFS = {
    # ucell.uz/uz/tariffs → "Bor" tarif seriyasi (hozirgi aktiv)
    "ucell": [
        {
            "id": "ucell_bor_70",
            "name": "Bor 70",
            "price": 70_000,
            "desc": "70 GB • Cheksiz qo'ng'iroq • 1 500 SMS • Hafta oxiri & kecha cheksiz • Yandex Plus",
        },
        {
            "id": "ucell_bor_90",
            "name": "Bor 90",
            "price": 90_000,
            "desc": "90 GB • Cheksiz qo'ng'iroq • 2 000 SMS • Hafta oxiri & kecha cheksiz • Yandex Plus",
        },
        {
            "id": "ucell_bor_110",
            "name": "Bor 110",
            "price": 110_000,
            "desc": "200 GB + 100 GB 5G • Cheksiz qo'ng'iroq • 2 500 SMS • Yandex Plus",
        },
        {
            "id": "ucell_bor_160",
            "name": "Bor 160",
            "price": 160_000,
            "desc": "350 GB + 150 GB 5G • Cheksiz qo'ng'iroq • 3 000 SMS • OVVA TV • Yandex Plus",
        },
    ],

    # beeline.uz/uz/products/tariffs → aktiv tariflar
    "beeline": [
        {
            "id": "bee_standart",
            "name": "Standart",
            "price": 45_000,
            "desc": "10 GB + 15 GB TAS-IX • 700 daqiqa • 500 SMS • KINOM & riitm",
        },
        {
            "id": "bee_optimal",
            "name": "Optimal",
            "price": 55_000,
            "desc": "15 GB + 25 GB TAS-IX • 700 daqiqa • 500 SMS • KINOM, riitm & Setanta Sports",
        },
        {
            "id": "bee_multi_plus",
            "name": "Multi Plus",
            "price": 65_000,
            "desc": "40 GB • Cheksiz qo'ng'iroq • 500 SMS • Kecha cheksiz (01:00-08:00) • AI xizmatlar bepul",
        },
        {
            "id": "bee_status_silver",
            "name": "Status Silver",
            "price": 110_000,
            "desc": "200 GB • Cheksiz qo'ng'iroq • 1 500 SMS • Ustunlik xizmatlari",
        },
    ],

    # mobi.uz/uz/tariff/ → Connect va ORZU seriyalari (aktiv)
    "ums": [
        {
            "id": "ums_connect_m",
            "name": "Connect M",
            "price": 45_000,
            "desc": "10 GB + 15 GB TAS-IX • 700 daqiqa • 500 SMS",
        },
        {
            "id": "ums_connect_l",
            "name": "Connect L",
            "price": 55_000,
            "desc": "15 GB + 25 GB TAS-IX • 700 daqiqa • 500 SMS",
        },
        {
            "id": "ums_mazza_70",
            "name": "Mazza 70",
            "price": 70_000,
            "desc": "150 GB • Cheksiz qo'ng'iroq • 5 000 SMS • Kid Security & MobiMusic",
        },
        {
            "id": "ums_orzu_90",
            "name": "ORZU 90",
            "price": 90_000,
            "desc": "180 GB • Cheksiz qo'ng'iroq • 5 000 SMS • Kid Security & MobiMusic",
        },
    ],

    # humans.uz/calculator/ → konstruktor asosida paketlar
    "humans": [
        {
            "id": "hum_standart",
            "name": "Standart",
            "price": 48_000,
            "desc": "40 GB • Cheksiz qo'ng'iroq • Telegram, Instagram, WhatsApp, Facebook, ChatGPT bepul",
        },
        {
            "id": "hum_youtube",
            "name": "YouTube+",
            "price": 56_000,
            "desc": "40 GB + Cheksiz YouTube • Cheksiz qo'ng'iroq • Ijtimoiy tarmoqlar bepul",
        },
        {
            "id": "hum_multi",
            "name": "Multi",
            "price": 61_000,
            "desc": "40 GB + Cheksiz YouTube & TikTok • Cheksiz qo'ng'iroq • Kecha cheksiz (01:00-07:00)",
        },
        {
            "id": "hum_premium",
            "name": "Premium",
            "price": 75_000,
            "desc": "40 GB + Barcha ilovalar cheksiz • Cheksiz qo'ng'iroq • Cheksiz SMS • Kecha cheksiz",
        },
    ],

    # uztelecom.uz → Uzmobile Mobile seriyasi (aktiv)
    "uzmobile": [
        {
            "id": "uzm_mobile_mini",
            "name": "Mobile Mini",
            "price": 45_000,
            "desc": "30 GB • 1 000 daqiqa • 1 000 SMS • TelecomTV kanallar",
        },
        {
            "id": "uzm_mobile_optimal",
            "name": "Mobile Optimal",
            "price": 61_000,
            "desc": "45 GB • Cheksiz qo'ng'iroq • 1 000 SMS • TelecomTV kanallar",
        },
        {
            "id": "uzm_mobile_ideal",
            "name": "Mobile Ideal",
            "price": 77_000,
            "desc": "100 GB • Cheksiz qo'ng'iroq • Cheksiz SMS • 120+ TelecomTV kanali",
        },
        {
            "id": "uzm_barakali_xxl",
            "name": "Barakali Plus XXL",
            "price": 115_000,
            "desc": "150 GB • Cheksiz qo'ng'iroq • Cheksiz SMS • 120+ TelecomTV kanali",
        },
    ],
}

# ─── NAMUNA RAQAMLAR ─────────────────────────────────────────────

AVAILABLE_NUMBERS = {
    "ucell": [
        "93-301-11-22", "93-302-33-44", "93-303-55-66",
        "93-501-77-88", "93-502-99-00",
    ],
    "beeline": [
        "90-101-22-33", "90-102-44-55", "90-103-66-77",
        "90-201-88-99", "90-202-11-00",
    ],
    "ums": [
        "91-401-12-34", "91-402-56-78", "91-403-90-12",
        "91-501-34-56", "91-502-78-90",
    ],
    "humans": [
        "99-701-23-45", "99-702-67-89", "99-703-01-23",
        "99-801-45-67", "99-802-89-01",
    ],
    "uzmobile": [
        "94-601-11-23", "94-602-45-67", "94-603-89-01",
        "94-701-23-45", "94-702-67-89",
    ],
}

# ─── HUDUDLAR VA KOORDINATALAR ───────────────────────────────────

REGIONS_COORDS = {
    "Toshkent shahar": (41.2995, 69.2401),
    "Toshkent viloyati": (41.1173, 69.2040),
    "Samarqand": (39.6270, 66.9750),
    "Buxoro": (39.7747, 64.4286),
    "Namangan": (41.0011, 71.6728),
    "Andijon": (40.7821, 72.3442),
    "Farg'ona": (40.3864, 71.7864),
    "Qashqadaryo": (38.8600, 65.7900),
    "Surxondaryo": (37.2400, 67.2800),
    "Xorazm": (41.3700, 60.3600),
    "Navoiy": (40.0900, 65.3700),
    "Jizzax": (40.1158, 67.8422),
    "Sirdaryo": (40.8340, 68.6640),
    "Qoraqalpog'iston": (42.4600, 59.6100),
}
