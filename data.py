OPERATORS = {
    "ucell": {"name": "Ucell", "emoji": "🟡", "codes": ["93", "94"]},
    "beeline": {"name": "Beeline", "emoji": "🟠", "codes": ["90", "91"]},
    "ums": {"name": "Mobiuz (UMS)", "emoji": "🔴", "codes": ["97", "88"]},
    "humans": {"name": "Humans", "emoji": "🔵", "codes": ["33", "99"]},
    "uzmobile": {"name": "Uzmobile", "emoji": "🟢", "codes": ["95", "77"]},
}


def operator_number_hint(op_id: str) -> str:
    """Mijozga raqami qanday ko'rinishda bo'lishini tushuntiradi.
    Masalan Mobiuz: '+998 (97 yoki 88) XX-XXX-XX-XX'."""
    op = OPERATORS.get(op_id)
    if not op:
        return ""
    codes = op.get("codes", [])
    code_str = " yoki ".join(codes) if codes else "XX"
    return f"+998 ({code_str}) XX-XXX-XX-XX"

# ─── TARIF REJALARI ─────────────────────────────────────────────
# Manba: ucell.uz | beeline.uz | mobi.uz | humans.uz | uztelecom.uz
# Yangilangan: 2026-iyun (rasmiy saytlardan tekshirilgan aktiv tariflar)
#
# Tuzilgan maydonlar (kod orqali taqqoslash uchun):
#   gb       — oylik internet (GB, taxminiy umumiy)
#   minutes  — qo'ng'iroq daqiqasi (None = cheksiz)
#   sms      — SMS soni (None = cheksiz)
#   apps     — bepul/cheksiz ilovalar tegi: youtube, tiktok, telegram,
#              instagram, whatsapp, facebook, chatgpt, tv, yandex
#   desc     — mijozga ko'rsatiladigan qisqa tavsif

TARIFFS = {
    # ucell.uz/uz/tariffs → Foydali + Bor seriyalari (rasmiy saytdan tasdiqlangan)
    "ucell": [
        {
            "id": "ucell_foydali_45", "name": "Foydali 45", "price": 45_000,
            "gb": 25, "minutes": 700, "sms": 700, "apps": [],
            "desc": "10 GB + 15 GB Tas-IX • 700 daqiqa • 700 SMS",
        },
        {
            "id": "ucell_foydali_55", "name": "Foydali 55", "price": 55_000,
            "gb": 40, "minutes": 700, "sms": 700, "apps": [],
            "desc": "15 GB + 25 GB Tas-IX • 700 daqiqa • 700 SMS",
        },
        {
            "id": "ucell_bor_70", "name": "Bor 70", "price": 70_000,
            "gb": 140, "minutes": None, "sms": 1500, "apps": [],
            "desc": "70 + 70 GB (aksiya) • Cheksiz qo'ng'iroq • 1 500 SMS",
        },
        {
            "id": "ucell_bor_90", "name": "Bor 90", "price": 90_000,
            "gb": 180, "minutes": None, "sms": 2000, "apps": ["yandex"],
            "desc": "90 + 90 GB (aksiya) • Cheksiz qo'ng'iroq • 2 000 SMS • Yandex Plus",
        },
        {
            "id": "ucell_bor_110", "name": "Bor 110", "price": 110_000,
            "gb": 300, "minutes": None, "sms": 2500, "apps": ["yandex"],
            "desc": "200 GB + 100 GB 5G tarmog'ida • Cheksiz qo'ng'iroq • 2 500 SMS • Yandex Plus",
        },
        {
            "id": "ucell_bor_160", "name": "Bor 160", "price": 160_000,
            "gb": 500, "minutes": None, "sms": 3000, "apps": ["yandex"],
            "desc": "350 GB + 150 GB 5G tarmog'ida • Cheksiz qo'ng'iroq • 3 000 SMS • Yandex Plus (VIP)",
        },
    ],

    # beeline.uz/uz/products/tariffs (rasmiy saytdan tasdiqlangan, 2026-iyun)
    "beeline": [
        {
            "id": "bee_standart", "name": "Standart", "price": 45_000,
            "gb": 25, "minutes": 700, "sms": 500, "apps": [],
            "desc": "10 GB + 15 GB TAS-IX • 700 daqiqa • 500 SMS",
        },
        {
            "id": "bee_optimal", "name": "Optimal", "price": 55_000,
            "gb": 40, "minutes": 700, "sms": 500, "apps": [],
            "desc": "15 GB + 25 GB TAS-IX • 700 daqiqa • 500 SMS",
        },
        {
            "id": "bee_multi_plus", "name": "Multi Plus", "price": 65_000,
            "gb": 40, "minutes": None, "sms": 500,
            "apps": ["chatgpt", "telegram", "instagram", "facebook"],
            "desc": "40 GB • Cheksiz qo'ng'iroq • 500 SMS • ChatGPT, Claude cheksiz • +100 GB Telegram/Instagram/Facebook",
        },
        {
            "id": "bee_yorqin", "name": "Yorqin", "price": 70_000,
            "gb": 70, "minutes": 45000, "sms": 2000, "apps": [],
            "desc": "70 GB + Cheksiz internet • 45 000 daqiqa • 2 000 SMS",
        },
        {
            "id": "bee_vibe", "name": "Vibe", "price": 80_000,
            "gb": 80, "minutes": 45000, "sms": 500, "apps": ["instagram", "telegram"],
            "desc": "80 GB + Cheksiz internet • 45 000 daqiqa • 500 SMS • Ijtimoiy tarmoqlar bepul",
        },
        {
            "id": "bee_oila_max", "name": "Oila Max", "price": 90_000, "family": True,
            "gb": 225, "minutes": None, "sms": 1000, "apps": [],
            "desc": "3 raqamgacha • 225 GB • Cheksiz qo'ng'iroq • 1 000 SMS • Cheksiz tungi internet",
        },
        {
            "id": "bee_oila_ultra", "name": "Oila Ultra+", "price": 150_000, "family": True,
            "gb": 450, "minutes": None, "sms": 1000, "apps": [],
            "desc": "5 raqamgacha • 450 GB • Cheksiz qo'ng'iroq • 1 000 SMS • ZTE Blade A56 sovg'a",
        },
        {
            "id": "bee_oila_mega", "name": "Oila Mega+", "price": 180_000, "family": True,
            "gb": 700, "minutes": None, "sms": 1000, "apps": [],
            "desc": "7 raqamgacha • 700 GB • Cheksiz qo'ng'iroq • 1 000 SMS • ZTE Blade A56 sovg'a",
        },
    ],

    # mobi.uz/uz/tariff/ → Connect, Mazza, ORZU, Xotirjam (rasmiy saytdan, 2026-iyun)
    "ums": [
        {
            "id": "ums_connect_m", "name": "Connect M", "price": 45_000,
            "gb": 25, "minutes": 700, "sms": 700, "apps": [],
            "desc": "10 GB + 15 GB TAS-IX • 700 daqiqa • 700 SMS",
        },
        {
            "id": "ums_connect_l", "name": "Connect L", "price": 55_000,
            "gb": 40, "minutes": 700, "sms": 700, "apps": [],
            "desc": "15 GB + 25 GB TAS-IX • 700 daqiqa • 700 SMS",
        },
        {
            "id": "ums_connect_xl", "name": "Connect XL", "price": 65_000,
            "gb": 55, "minutes": 900, "sms": 1000, "apps": [],
            "desc": "20 GB + 35 GB TAS-IX • 900 daqiqa • 1 000 SMS",
        },
        {
            "id": "ums_mazza_70", "name": "Mazza 70", "price": 70_000,
            "gb": 150, "minutes": None, "sms": 5000,
            "apps": ["telegram", "instagram", "facebook", "tv"],
            "desc": "150 GB • Cheksiz qo'ng'iroq • 5 000 SMS • Ijtimoiy tarmoqlar cheksiz • MobiTV",
        },
        {
            "id": "ums_orzu_90", "name": "ORZU 90", "price": 90_000,
            "gb": 180, "minutes": None, "sms": 5000,
            "apps": ["telegram", "instagram", "facebook", "tv"],
            "desc": "180 GB • Cheksiz qo'ng'iroq • 5 000 SMS • Ijtimoiy tarmoqlar cheksiz • MobiTV",
        },
        {
            "id": "ums_orzu_110", "name": "ORZU 110", "price": 110_000,
            "gb": 250, "minutes": None, "sms": 5000,
            "apps": ["telegram", "instagram", "facebook", "tv"],
            "desc": "250 GB • Cheksiz qo'ng'iroq • 5 000 SMS • Ijtimoiy tarmoqlar cheksiz • MobiTV (50+ kanal)",
        },
        {
            "id": "ums_orzu_150", "name": "ORZU 150", "price": 150_000,
            "gb": 400, "minutes": None, "sms": 5000,
            "apps": ["telegram", "instagram", "facebook", "tv"],
            "desc": "400 GB • Cheksiz qo'ng'iroq • 5 000 SMS • Ijtimoiy tarmoqlar cheksiz • MobiTV +Sport",
        },
        {
            "id": "ums_xotirjam_80", "name": "Xotirjam 80", "price": 80_000,
            "gb": 80, "minutes": None, "sms": 3500,
            "apps": ["youtube", "telegram", "instagram", "facebook", "whatsapp"],
            "desc": "80 GB • Cheksiz qo'ng'iroq • 3 500 SMS • YouTube va 10+ ilova cheksiz",
        },
        {
            "id": "ums_xotirjam_100", "name": "Xotirjam 100", "price": 100_000,
            "gb": 200, "minutes": None, "sms": 5000,
            "apps": ["youtube", "telegram", "instagram", "facebook", "whatsapp"],
            "desc": "200 GB • Cheksiz qo'ng'iroq • 5 000 SMS • YouTube va 10+ ilova cheksiz",
        },
    ],

    # humans.uz → cheksiz aloqa yo'nalishi (mijoz tasdiqlagan)
    "humans": [
        {
            # 3 oylik aksiya — oylik tariflar bilan taqqoslanmaydi
            "id": "hum_cheksiz_qongiroq", "name": "Cheksiz qo'ng'iroq (3 oy)", "price": 50_000,
            "gb": 0, "minutes": None, "sms": None, "apps": [], "no_compare": True,
            "desc": "🎁 AKSIYA: 3 oyga cheksiz qo'ng'iroq • O'zbekiston bo'ylab • atigi 50 000 so'm",
        },
        {
            "id": "hum_aloqa_internet", "name": "Aloqa + Internet", "price": 65_000,
            "gb": 30, "minutes": None, "sms": 500, "apps": [],
            "desc": "Cheksiz qo'ng'iroq + internet • 1 oy",
        },
    ],

    # uztelecom.uz → Uzmobile (rasmiy saytdan tasdiqlangan, 2026-iyun)
    "uzmobile": [
        {
            "id": "uzm_mini_m", "name": "Mobile Mini M", "price": 45_000,
            "gb": 10, "minutes": 700, "sms": 700, "apps": [],
            "desc": "10 GB • 700 daqiqa • 700 SMS",
        },
        {
            "id": "uzm_optimal", "name": "Optimal", "price": 55_000,
            "gb": 15, "minutes": 700, "sms": 700, "apps": [],
            "desc": "15 GB • 700 daqiqa • 700 SMS",
        },
        {
            "id": "uzm_balance", "name": "Balance", "price": 65_000,
            "gb": 20, "minutes": 800, "sms": 800, "apps": [],
            "desc": "20 GB • 800 daqiqa • 800 SMS",
        },
        {
            "id": "uzm_bonus_salom", "name": "Bonus Super Salom", "price": 70_000,
            "gb": 100, "minutes": None, "sms": 1000, "apps": ["youtube"],
            "desc": "100 GB • Cheksiz qo'ng'iroq • 1 000 SMS • YouTube va ilovalar bepul",
        },
        {
            "id": "uzm_super_lux", "name": "Super Lux", "price": 77_000,
            "gb": 200, "minutes": None, "sms": 3000, "apps": [],
            "desc": "200 GB • Cheksiz qo'ng'iroq • 3 000 SMS • Bepul ilovalar",
        },
        {
            "id": "uzm_bonus_super_lux", "name": "Bonus Super Lux", "price": 77_000,
            "gb": 200, "minutes": None, "sms": 3000, "apps": [],
            "desc": "200 GB • Cheksiz qo'ng'iroq • 3 000 SMS • Bepul ilovalar",
        },
        {
            "id": "uzm_ideal_plus", "name": "Ideal Plus", "price": 85_000,
            "gb": 150, "minutes": None, "sms": 2000, "apps": [],
            "desc": "150 GB • Cheksiz qo'ng'iroq • 2 000 SMS • Bepul ilovalar",
        },
        {
            "id": "uzm_bonus_ideal_plus", "name": "Bonus Ideal Plus", "price": 85_000,
            "gb": 150, "minutes": None, "sms": 2000, "apps": [],
            "desc": "150 GB • Cheksiz qo'ng'iroq • 2 000 SMS • Bepul ilovalar",
        },
        {
            "id": "uzm_mobile_lux", "name": "Mobile Lux", "price": 101_000,
            "gb": 200, "minutes": None, "sms": 3000, "apps": [],
            "desc": "200 GB • Cheksiz qo'ng'iroq • 3 000 SMS • Bepul ilovalar",
        },
        {
            "id": "uzm_mobile_elite", "name": "Mobile Elite", "price": 150_000,
            "gb": 350, "minutes": None, "sms": 3000, "apps": [],
            "desc": "350 GB • Cheksiz qo'ng'iroq • 3 000 SMS • Bepul ilovalar",
        },
    ],
}
