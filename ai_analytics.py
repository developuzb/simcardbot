"""AI analitika: statistikani matn qilib formatlash va Claude orqali insight."""
import logging
from data import OPERATORS, TARIFFS
import analytics_store
import ai_client
import followups_store

logger = logging.getLogger(__name__)

_DROP_LABELS = {
    "tariff": "Tarif tanlashda", "delivery": "Yetkazishni tanlashda",
    "phone": "Telefon so'ralganda", "location": "Lokatsiya so'ralganda",
    "confirm": "Tasdiqlash oldidan",
}


def _tariff_name(key: str) -> str:
    """'op_id:tariff_id' -> 'Operator Tarif'."""
    try:
        op_id, tid = key.split(":", 1)
    except ValueError:
        return key
    op = OPERATORS.get(op_id, {}).get("name", op_id)
    for t in TARIFFS.get(op_id, []):
        if t["id"] == tid:
            return f"{op} {t['name']}"
    return f"{op} {tid}"


def _top(d: dict, n: int = 5) -> list:
    return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]


def format_stats() -> str:
    s = analytics_store.snapshot()
    sessions = s["ai_sessions"]
    ai_orders = s["ai_orders"]
    conv = (ai_orders / sessions * 100) if sessions else 0

    fu = followups_store.snapshot()
    lines = [
        "🤖 <b>AI suhbat statistikasi</b>",
        f"<i>(hisob boshlanishi: {s['since']})</i>\n",
        f"💬 Jami AI suhbat: <b>{sessions}</b>",
        f"🛒 AI orqali buyurtma: <b>{ai_orders}</b>",
        f"📈 Aylanish (konversiya): <b>{conv:.0f}%</b>",
        f"📦 Jami buyurtma: <b>{s['orders']}</b>",
        f"💰 Jami summa: <b>{s['revenue']:,} so'm</b>",
        f"🟠 Hudud tashqarisida: <b>{s['out_of_zone']}</b>",
        f"🚪 Tugatmagan (abandon): <b>{fu['abandoned']}</b>",
        f"📩 Fikr so'rovi: <b>{s.get('followups_sent', 0)}</b> · javob: <b>{s.get('feedbacks', 0)}</b>",
    ]
    if fu["drop_stages"]:
        lines.append("\n<b>Qayerda tashlab ketishadi:</b>")
        for st, c in _top(fu["drop_stages"]):
            lines.append(f"  • {_DROP_LABELS.get(st, st)} — {c}")

    if s["operators"]:
        lines.append("\n<b>So'ralgan operatorlar:</b>")
        for op_id, c in _top(s["operators"]):
            name = OPERATORS.get(op_id, {}).get("name", op_id)
            lines.append(f"  • {name} — {c}")

    if s["tariffs"]:
        lines.append("\n<b>Eng ko'p tanlangan tariflar:</b>")
        for key, c in _top(s["tariffs"]):
            lines.append(f"  • {_tariff_name(key)} — {c}")

    if s["advice"]:
        lines.append("\n<b>So'rovlar mavzusi:</b>")
        labels = {"arzon": "Arzon narx", "internet": "Ko'p internet",
                  "youtube": "YouTube/ijtimoiy", "qongiroq": "Qo'ng'iroq",
                  "boshqa": "Boshqa"}
        for cat, c in _top(s["advice"]):
            lines.append(f"  • {labels.get(cat, cat)} — {c}")

    return "\n".join(lines)


def _build_data_summary() -> str:
    s = analytics_store.snapshot()
    fu = followups_store.snapshot()
    sessions = s["ai_sessions"] or 1
    conv = s["ai_orders"] / sessions * 100
    ops = ", ".join(f"{OPERATORS.get(k, {}).get('name', k)}={v}"
                    for k, v in _top(s["operators"])) or "—"
    tariffs = ", ".join(f"{_tariff_name(k)}={v}" for k, v in _top(s["tariffs"])) or "—"
    advice = ", ".join(f"{k}={v}" for k, v in _top(s["advice"])) or "—"
    drops = ", ".join(f"{_DROP_LABELS.get(st, st)}={c}" for st, c in _top(fu["drop_stages"])) or "—"
    feedbacks = " | ".join(f"«{f[:80]}»" for f in fu["feedbacks"][-6:]) or "—"
    return (
        f"AI suhbatlar: {s['ai_sessions']}\n"
        f"Buyurtmalar: {s['orders']} (AI orqali {s['ai_orders']})\n"
        f"Konversiya: {conv:.0f}%\n"
        f"Daromad: {s['revenue']} so'm\n"
        f"Hudud tashqarisida: {s['out_of_zone']}\n"
        f"Tugatmaganlar (abandon): {fu['abandoned']}\n"
        f"Eng ko'p tashlab ketilgan bosqich: {drops}\n"
        f"So'ralgan operatorlar: {ops}\n"
        f"Tanlangan tariflar: {tariffs}\n"
        f"So'rov mavzulari: {advice}\n"
        f"Mijoz fikrlari (tugatmaganlar): {feedbacks}"
    )


_INSIGHT_SYSTEM = (
    "Sen Texnoset SIM karta yetkazib berish biznesi uchun tajribali sotuv va "
    "marketing tahlilchisisan. Senga real statistika beriladi.\n"
    "FAQAT O'ZBEK TILIDA, aniq va amaliy yoz. Inglizcha/umumiy gaplar YO'Q.\n\n"
    "Format (qat'iy):\n"
    "📊 <b>Holat:</b> 1-2 jumla — biznes qanday ketyapti (konversiya, daromad).\n"
    "🔍 <b>Kuzatuvlar:</b> 3 tagacha aniq nuqta — RAQAMGA tayanib (masalan "
    "'konversiya 20% — past, 10 mijozdan 8 tasi tarif tanlashda ketib qolgan').\n"
    "💡 <b>Tavsiyalar:</b> 3 tagacha ANIQ, bajariladigan qadam — har biri qaysi "
    "muammoni hal qilishini ko'rsat (masalan 'tarif bosqichida ketishyapti → "
    "shu yerда chegirma yoki sodda taqqoslash qo'shing'). Mijoz fikrlariga tayan.\n\n"
    "Umumiy maslahat berma — faqat shu raqamlardan kelib chiqqan, sotuvni "
    "oshiradigan aniq harakatlar. Har tavsiya bitta jumla."
)


async def generate_insight() -> str:
    summary = _build_data_summary()
    s = analytics_store.snapshot()
    if s["ai_sessions"] == 0 and s["orders"] == 0:
        return ("📊 Hozircha tahlil uchun ma'lumot yetarli emas.\n"
                "Bir nechta buyurtma va AI suhbatdan keyin qaytadan urinib ko'ring.")
    try:
        return await ai_client.complete(
            system=_INSIGHT_SYSTEM,
            messages=[{"role": "user", "content": f"Real statistika:\n{summary}\n\nShu raqamlar asosida tahlil va aniq tavsiyalar ber."}],
            max_tokens=600,
        )
    except Exception as e:
        logger.error(f"generate_insight xatolik: {e}")
        return "⚠️ AI tahlil hozir mavjud emas. Birozdan keyin urinib ko'ring."


def daily_report_text() -> str:
    """Kunlik avtomatik hisobot uchun bugungi qisqa matn."""
    s = analytics_store.snapshot()
    from datetime import datetime
    key = datetime.now().strftime("%Y-%m-%d")
    today = s["today"].get(key, {"orders": 0, "revenue": 0, "ai_sessions": 0, "out_of_zone": 0})
    return (
        f"🌙 <b>Kunlik hisobot — {key}</b>\n\n"
        f"📦 Bugungi buyurtma: <b>{today['orders']}</b>\n"
        f"💰 Bugungi summa: <b>{today['revenue']:,} so'm</b>\n"
        f"💬 AI suhbat: <b>{today['ai_sessions']}</b>\n"
        f"🟠 Hudud tashqarisida: <b>{today['out_of_zone']}</b>"
    )


# ─── INDIVIDUAL (PER-MIJOZ) PROFESSIONAL INSIGHT ────────────────

_CUSTOMER_INSIGHT_SYSTEM = (
    "Sen Texnoset SIM karta biznesi uchun TAJRIBALI sotuv tahlilchisisan. "
    "Senga BITTA mijozning bot bilan real suhbati (yozganlari, tanlovi, natijasi) "
    "beriladi. Admin-sotuvchi uchun shu mijoz bo'yicha qisqa, professional va "
    "AMALIY insight yoz — u shu insight bilan mijozni yaxshiroq yopsin.\n"
    "FAQAT O'ZBEK TILIDA. Inglizcha/umumiy gap YO'Q. Aniq va qisqa.\n\n"
    "Qat'iy format (aynan shu 5 qator, har biri 1 qator, HTML <b> bilan):\n"
    "🎯 <b>Lead:</b> Issiq yoki Iliq yoki Sovuq — + 3-4 so'z izoh\n"
    "😊 <b>Kayfiyat:</b> (masalan: qiziqqan / ikkilanayotgan / narxga sezgir / shoshayotgan / shubhali)\n"
    "🧩 <b>Asosiy nuqta:</b> mijozning eng kuchli signali yoki e'tirozi\n"
    "✅ <b>Keyingi qadam:</b> admin AYNAN nima qilsin (qo'ng'iroq qil / chegirma taklif et / eslatma yubor) — aniq\n"
    "💡 <b>Yopish taktikasi:</b> shu mijozni qanday yopish — 1 ta aniq jumla\n\n"
    "Faqat shu 5 qatorni yoz. Boshqa kirish/xulosa matni qo'shma."
)


async def customer_insight(profile: dict) -> str:
    """Bitta mijoz uchun professional, strukturali sotuv insight'i (O'zbekcha)."""
    q = profile.get("questions") or []
    q_block = "\n".join(f"- {str(x)[:140]}" for x in q[-6:]) or "(savol yo'q, faqat tugmalar)"
    usr = (
        f"Mijoz: {profile.get('name', '—')}\n"
        f"Tanlovi: {profile.get('operator', '—')} / tarif: {profile.get('tariff', '—')}\n"
        f"Bosqich: {profile.get('stage', '—')}\n"
        f"Natija: {profile.get('outcome', '—')}\n"
        f"Mijoz yozganlari:\n{q_block}"
    )
    try:
        out = await ai_client.complete(
            _CUSTOMER_INSIGHT_SYSTEM,
            [{"role": "user", "content": usr}],
            max_tokens=350,
        )
        return (out or "").strip()
    except Exception as e:
        logger.error(f"customer_insight xatolik: {e}")
        return ""
