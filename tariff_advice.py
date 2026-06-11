"""Tarif tanlashda yordam: har kompaniyadan eng mos variantni tanlab,
bold + blockquote, chiziq bilan ajratilgan taqqoslash ko'rinishini quradi.

Kod orqali ishlaydi (AI'siz) — ma'lumot va format 100% ishonchli, tez.
"""
from data import OPERATORS, TARIFFS
from config import PROMO_1PLUS1_MIN_PRICE

_DIVIDER = "➖➖➖➖➖➖➖➖➖➖"

# Mijoz so'rovini kategoriyaga ajratish (tartib = ustuvorlik)
_CATEGORY_KEYWORDS = [
    ("youtube", ["youtube", "ютуб", "video", "tiktok", "тикток", "ijtimoiy",
                 "instagram", "telegram", "ilova", "social"]),
    ("qongiroq", ["qo'ng'iroq", "qongiroq", "qўнғироқ", "daqiqa", "minut",
                  "gaplash", "qo'ngiroq", "звонок"]),
    ("internet", ["internet", "gb", "gigabayt", "trafik", "ko'p internet",
                  "interneti", "tezlik", "5g"]),
    ("arzon", ["arzon", "narx", "qancha", "tejam", "byudjet", "eng arzon",
               "qimmat emas", "chiqim"]),
]


def detect_category(text: str) -> str | None:
    t = (text or "").lower()
    for cat, kws in _CATEGORY_KEYWORDS:
        if any(k in t for k in kws):
            return cat
    return None


def _best_for(op_id: str, category: str) -> dict | None:
    # Oilaviy yoki boshqa muddatli (3 oylik) tariflarni bitta-oylik
    # taqqoslashdan chiqaramiz
    tariffs = [t for t in TARIFFS.get(op_id, [])
               if not t.get("family") and not t.get("no_compare")]
    if not tariffs:
        return None
    if category == "arzon":
        return min(tariffs, key=lambda t: t["price"])
    if category == "internet":
        return max(tariffs, key=lambda t: t["gb"])
    if category == "youtube":
        yt = [t for t in tariffs if "youtube" in t.get("apps", [])]
        if yt:
            return min(yt, key=lambda t: t["price"])
        # YouTube tarif yo'q bo'lsa — eng ko'p internetli
        return max(tariffs, key=lambda t: t["gb"])
    if category == "qongiroq":
        unlim = [t for t in tariffs if t["minutes"] is None]
        if unlim:
            return min(unlim, key=lambda t: t["price"])
        return max(tariffs, key=lambda t: t["minutes"] or 0)
    return min(tariffs, key=lambda t: t["price"])


def _limits_block(t: dict, category: str) -> str:
    calls = "Cheksiz qo'ng'iroq" if t["minutes"] is None else f"{t['minutes']} daqiqa"
    sms = "Cheksiz SMS" if t["sms"] is None else f"{t['sms']:,} SMS"
    lines = [
        f"📶 {t['gb']} GB internet",
        f"☎️ {calls}",
        f"💬 {sms}",
    ]
    if category == "youtube" and "youtube" in t.get("apps", []):
        lines.append("▶️ YouTube cheksiz")
    if t["price"] >= PROMO_1PLUS1_MIN_PRICE:
        lines.append("🎁 1+1: ikkinchi SIM bepul")
    lines.append(f"💰 <b>{t['price']:,} so'm/oy</b>")
    return "<blockquote>" + "\n".join(lines) + "</blockquote>"


_INTRO = {
    "arzon": "💰 Tejamkorlar uchun har operatordan eng arzon variantni tanladim 👇",
    "internet": "📶 Internet ko'p kerak bo'lsa — mana har operatordan eng dadil variant 👇",
    "youtube": "🎬 YouTube va ijtimoiy tarmoqlar uchun eng mos tariflar 👇",
    "qongiroq": "☎️ Ko'p gaplashuvchilar uchun cheksiz qo'ng'iroqli tariflar 👇",
}

_CLOSING = (
    "\n\n💡 <b>Savolingiz bormi?</b> Bemalol yozing — istalgan tarifni "
    "batafsil tushuntiraman yoki taqqoslab beraman 😊\n"
    "Yoqqanini tanlash uchun pastdan operatorni bosing 👇"
)


def tariff_detail_block(t: dict) -> str:
    """Mijoz tarifni tanlaganda — beriladigan limitlarni blok ko'rinishida."""
    parts = [p.strip() for p in t.get("desc", "").split("•") if p.strip()]
    body = "\n".join(f"• {p}" for p in parts) if parts else "—"
    block = f"<blockquote>{body}</blockquote>"
    extra = f"\n💰 <b>{t['price']:,} so'm/oy</b>"
    if t["price"] >= PROMO_1PLUS1_MIN_PRICE:
        extra += "\n🎁 <b>1+1 AKSIYA:</b> ikkinchi SIM karta BEPUL!"
    return f"{block}{extra}"


def format_comparison(category: str) -> str:
    intro = _INTRO.get(category, "Mana har operatordan eng mos variant 👇")
    blocks = []
    for op_id, op in OPERATORS.items():
        t = _best_for(op_id, category)
        if not t:
            continue
        blocks.append(
            f"{op['emoji']} <b>{op['name']} — {t['name']}</b>\n"
            f"{_limits_block(t, category)}"
        )
    body = f"\n{_DIVIDER}\n".join(blocks)
    return f"{intro}\n\n{body}{_CLOSING}"
