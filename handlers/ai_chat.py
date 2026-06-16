import asyncio
import logging
import math
import re
import time
from datetime import datetime, timezone, timedelta
import openai
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

from states import AIState
from data import OPERATORS, TARIFFS, operator_number_hint
from config import (
    ADMIN_IDS, DELIVERY_TYPES, ADMIN_CONTACT,
    DELIVERY_ZONE_NAME, WORK_START_HOUR, WORK_END_HOUR,
    PROMO_1PLUS1_MIN_PRICE, PROMO_1PLUS1_BADGE, PROMO_1PLUS1_TEXT,
    PAYMENT_NOTE, PASSPORT_NOTE, NUMBER_NOTE, TRUST_NOTE, REFERRAL_DISCOUNT,
)
import settings_store
import analytics_store
import tariff_advice
import orders_db
import followups_store
import referrals_store
import ai_client
import ai_analytics
from handlers import dispatch

# ─── Yordamchilar: ish vaqti, rate-limit ────────────────────────

def _is_working_hours() -> bool:
    tashkent = datetime.now(timezone.utc) + timedelta(hours=5)
    return WORK_START_HOUR <= tashkent.hour < WORK_END_HOUR


_AI_COOLDOWN = 3.0       # AI so'rovlari orasidagi minimal vaqt (soniya)
_ORDER_COOLDOWN = 45.0   # buyurtmalar orasidagi minimal vaqt (soniya)
_last_ai_call: dict = {}
_last_order: dict = {}


def _rate_limited(store: dict, user_id, cooldown: float) -> bool:
    now = time.monotonic()
    last = store.get(user_id, 0.0)
    if now - last < cooldown:
        return True
    store[user_id] = now
    return False

logger = logging.getLogger(__name__)
router = Router()

MAX_TOKENS = 400
# MODEL va client ai_client modulidan olinadi (takrorni yo'qotish, Bug 5)
MODEL = ai_client.MODEL


def _get_delivery_zones():
    o = settings_store.get_office()
    return [(o["zone_name"], o["lat"], o["lon"], o["radius_km"])]


def _get_client() -> openai.AsyncOpenAI:
    """ai_client moduli orqali yagona client qaytaradi."""
    return ai_client.get_client()


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _check_zone(lat: float, lon: float) -> str | None:
    for name, zlat, zlon, radius in _get_delivery_zones():
        if _haversine(lat, lon, zlat, zlon) <= radius:
            return name
    return None


def _looks_like_phone(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return 9 <= len(digits) <= 13


# Mijoz operator nomini yozsa — darhol o'sha operatorga (AI'siz)
_OP_KEYWORDS = {
    "ucell": "ucell", "юсел": "ucell", "usell": "ucell", "uсell": "ucell",
    "beeline": "beeline", "билайн": "beeline", "biliin": "beeline", "bilayn": "beeline",
    "mobiuz": "ums", "mobi": "ums", "ums": "ums", "мобиуз": "ums", "mobiuz(ums)": "ums",
    "humans": "humans", "хуманс": "humans", "human": "humans",
    "uzmobile": "uzmobile", "узмобайл": "uzmobile", "uzmobil": "uzmobile", "uzmobayl": "uzmobile",
}


def _detect_operator(text: str) -> str | None:
    return _OP_KEYWORDS.get(text.lower().strip())


# ─── SYSTEM PROMPT (faqat maslahat uchun, tool YO'Q) ─────────────

def _build_system_prompt() -> str:
    tariff_lines = []
    for op_id, op in OPERATORS.items():
        for t in TARIFFS.get(op_id, []):
            promo = " [1+1 AKSIYA: 2-SIM bepul]" if t["price"] >= PROMO_1PLUS1_MIN_PRICE else ""
            calls = "cheksiz qo'ng'iroq" if t.get("minutes") is None else f"{t['minutes']} daqiqa"
            sms = "cheksiz SMS" if t.get("sms") is None else f"{t['sms']} SMS"
            apps = (" | bepul ilovalar: " + ", ".join(t["apps"])) if t.get("apps") else ""
            tariff_lines.append(
                f"[{op_id}/{t['id']}] {op['emoji']} {op['name']} | {t['name']} | "
                f"{t['price']:,} so'm/oy | {t.get('gb', '?')} GB | {calls} | {sms}{apps} | "
                f"{t['desc']}{promo}"
            )
    zones = " va ".join(z[0] for z in _get_delivery_zones())
    return (
        "Sen Suxrob — Texnoset SIM karta xizmatining AI sotuv yordamchisisan (tajribali, professional). "
        "Mijoz bilan ILIQ, SAMIMIY, ishonchli gaplash — xuddi yaqin tanishingga yordam "
        "berayotgandek. Maqsading: mijozga chin dildan yordam berib, uni buyurtma berishgacha "
        "yumshoq yetaklash. Hech qachon bosim o'tkazma, lekin har javobda keyingi qadamга undaymiz.\n"
        "Faqat O'ZBEK TILIDA. Inglizcha, metamatn, texnik izoh — YO'Q. "
        "Qisqa: 2-4 qator, 1-2 emoji.\n\n"
        "🎯 KAYFIYATGA QARAB SOTUV TAKTIKASI (professional sotuvchidek):\n"
        "• IKKILANAYOTGAN mijoz → tinchlantir, soddalashtir, BITTA aniq tavsiya ber, "
        "«ko'pchilik shuni oladi» de. Tanlash yukini yengillashtir.\n"
        "• NARXGA SEZGIR mijoz → qiymatni ko'rsat: kunlik narx, BEPUL yetkazish, 1+1 aksiya. "
        "«Bu narxga bundan yaxshisi yo'q» tarzida.\n"
        "• QIZIQQAN/TAYYOR mijoz → maqtab tasdiqla va darhol tugmaga yo'naltir, kechiktirma.\n"
        "• SHOSHAYOTGAN mijoz → tezkor yetkazishni eslat, 1 soatda yetadi de.\n"
        "• SHUBHALANAYOTGAN mijoz → ishonch ber: uyga yetkazamiz, raqamni o'zingiz tanlaysiz, "
        "kuryer keladi. Xavotirini yo'qot.\n"
        "Har javob mijozni TANLOVGA yaqinlashtirsin — lekin samimiy, bosimsiz.\n\n"
        "🚫 ASOSIY QOIDA — MIJOZNI CHALKASHTIRMA:\n"
        "• Mijoz BITTA aniq narsa so'rasa (masalan 'menga internet kerak') → FAQAT BITTA eng mos tarif tavsiya qil. Uzun ro'yxat tashlama!\n"
        "• 3-4 tarifni vergul bilan sanab ketma — bu zeriktiradi.\n\n"
        "📊 TAQQOSLASH REJIMI (mijoz solishtirishni so'rasa):\n"
        "• Mijoz 'eng arzon', 'eng ko'p internet', 'youtube/tiktok', 'ko'p gaplashaman/qo'ng'iroq', "
        "'taqqosla', 'solishtir', 'hammasini/barcha operatorlarni ko'rsat' desa — "
        "javob OXIRIGA @@COMPARE arzon@@ (yoki internet / youtube / qongiroq) yoz.\n"
        "• Bunda o'zing ro'yxat YOZMA — faqat 1 qator iliq kirish ber ('Mana barchasini solishtirib beraman 👇'), "
        "tizim HAR OPERATORDAN eng mosini chiroyli (emoji + blockquote, tartibli) ko'rsatadi.\n\n"
        "✅ JAVOB TUZILISHI (bitta tavsiya uchun):\n"
        "1) Mijoz gapini iliq tasdiqla ('Zo'r tanlov!', 'Tushundim 👍', 'Internetni yaxshi ko'rasiz-a')\n"
        "2) BITTA tarifni tavsiya qil: <b>nom</b> + afzalliklar <blockquote> ichida + <b>narx</b>\n"
        "3) Iliq yo'naltir: 'Ucell tugmasini bossangiz, davom etamiz 👇'\n\n"
        "🎨 FORMATLASH (Telegram HTML — MAJBURIY):\n"
        "• Tarif NOMI va NARXini <b>...</b> bilan ajrat\n"
        "• Tarif afzalliklarini <blockquote>...</blockquote> ichiga yoz (2-3 qator, emoji bilan)\n"
        "• Faqat <b>, <i>, <blockquote> teglaridan foydalan. Boshqa teg YO'Q\n"
        "• Har bir teg ALBATTA yopilishi shart (<b>...</b>). Yarim ochiq teg qoldirma\n\n"
        "Mijoz nima deyishiga qarab:\n"
        "• Bitta narsa kerak bo'lsa → BITTA tarif (@@PICK). Solishtirishni so'rasa → @@COMPARE.\n"
        "• Ikkilansa — ro'yxat o'rniga BITTA savol ber: 'Internet ko'proq muhimmi yoki arzonroq?'\n"
        "• Mijoz tayyor/aniq bo'lsa (masalan 'ucell bor 70 ber') → darhol @@PICK bilan o'sha tarifга yo'naltir, kechiktirma.\n\n"
        "🎁 70 000 so'm+ tariflarda 1+1 AKSIYA (2-SIM BEPUL) — buni quvonch bilan ayt.\n"
        "Narx: '90 000 so'm/oy (kuniga ~3 000 so'm)'.\n"
        "YETKAZISH: " + " | ".join(
            f"{dt['desc']}=" + ("BEPUL" if dt['price'] == 0 else f"{dt['price']}")
            for dt in DELIVERY_TYPES.values()
        ) + "\n"
        "RAQAM: mijoz raqamni oldindan operator bilan kelishadi YOKI kuryer oldida o'zi tanlaydi. "
        "Raqam +998(operator kodi) ko'rinishida bo'ladi.\n"
        "TO'LOV: SIM qo'lga tekkanda kuryerga — naqd yoki karta. Oldindan to'lov YO'Q.\n"
        "PASPORT: SIM pasport bilan rasmiylashtiriladi — kuryer kelganda pasport kerak.\n"
        "HUDUD: faqat " + zones + ".\n\n"
        "TARIFLAR — shu ro'yxatni TO'LIQ bil (har birining GB, daqiqa, SMS, ilova va narxi). "
        "Mijoz so'rasa aniq raqamlar bilan javob ber; faqat shu ro'yxatdan tavsiya qil:\n"
        + "\n".join(tariff_lines) + "\n\n"
        "🔘 TUGMA BOSHQARUVI (MAJBURIY — har javob OXIRIDA alohida qatorga yoz):\n"
        "• Aniq BITTA tarif tavsiya qilsang: @@PICK op_id tariff_id@@ "
        "(yuqoridagi [op_id/tariff_id] dan AYNAN ko'chir — o'ylab topma!)\n"
        "• Barcha operatorlarni solishtirib ko'rsatish kerak bo'lsa: @@COMPARE arzon@@ "
        "(yoki internet / youtube / qongiroq)\n"
        "• Hali savol berayotgan/aniqlik bo'lmasa: @@ASK@@\n"
        "• Bu belgilar mijozga KO'RINMAYDI — tizim ularni avtomatik bajaradi.\n"
        "Mavzudan chetga chiqsa: 'Men faqat SIM karta bo'yicha yordam beraman 😊'\n"
        "DIQQAT: Sen maslahat berasan, buyurtma tugmalar orqali rasmiylashadi."
    )


_SYSTEM_PROMPT: str | None = None


def _get_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _build_system_prompt()
    return _SYSTEM_PROMPT


# ─── KLAVIATURALAR ──────────────────────────────────────────────

def _stage_keyboard(stage: str) -> object:
    b = InlineKeyboardBuilder()

    if stage == "operator":
        for op_id, op in OPERATORS.items():
            b.button(text=f"{op['emoji']} {op['name']}", callback_data=f"ai_op_{op_id}")
        b.adjust(2, 2, 1)
        b.row(
            InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="back_to_main"),
            InlineKeyboardButton(text="❌ Chiqish", callback_data="ai_exit"),
        )

    elif stage.startswith("tariff:"):
        op_id = stage.split(":", 1)[1]
        for t in TARIFFS.get(op_id, []):
            # Oilaviy (ko'p SIM) va boshqa muddatli tariflar bitta-SIM
            # oqimiga mos emas — ro'yxatda ko'rsatmaymiz.
            if t.get("family") or t.get("no_compare"):
                continue
            badge = f" {PROMO_1PLUS1_BADGE}" if t["price"] >= PROMO_1PLUS1_MIN_PRICE else ""
            b.button(
                text=f"📦 {t['name']} · {t['gb']} GB — {t['price']:,}{badge}",
                callback_data=f"ai_tf_{op_id}__{t['id']}",
            )
        b.adjust(1)
        b.row(
            InlineKeyboardButton(text="⬅️ Operatorlar", callback_data="ai_back_op"),
            InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="back_to_main"),
        )

    elif stage == "delivery":
        for key, dt in DELIVERY_TYPES.items():
            price_text = "Bepul 🎁" if dt["price"] == 0 else f"{dt['price']:,} so'm"
            b.button(
                text=f"{dt['emoji']} {dt['desc']} — {price_text}",
                callback_data=f"ai_del_{key}",
            )
        b.adjust(1)
        b.row(
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ai_back_tariff"),
            InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="back_to_main"),
        )

    elif stage == "done":
        b.button(text="🔄 Yangi buyurtma", callback_data="ai_restart")
        b.button(text="🏠 Bosh sahifa", callback_data="back_to_main")
        b.button(text="❌ Chiqish", callback_data="ai_exit")
        b.adjust(1)

    else:  # phone va boshqalar
        b.row(
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ai_back_delivery"),
            InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="back_to_main"),
        )

    return b.as_markup()


def _comparison_keyboard(category: str) -> object:
    """Taqqoslashдан keyin — aynan tavsiya qilingan tariflar tugmasi.
    Har tugma bevosita o'sha tarifni tanlaydi (ai_tf_ → ai_pick_tariff)."""
    b = InlineKeyboardBuilder()
    for p in tariff_advice.comparison_picks(category):
        op, t = p["op"], p["tariff"]
        badge = f" {PROMO_1PLUS1_BADGE}" if t["price"] >= PROMO_1PLUS1_MIN_PRICE else ""
        b.button(
            text=f"{op['emoji']} {op['name']} {t['name']} · {t['gb']}GB — {t['price']:,}{badge}",
            callback_data=f"ai_tf_{p['op_id']}__{t['id']}",
        )
    b.button(text="📋 Barcha operatorlar", callback_data="ai_back_op")
    b.button(text="❌ Chiqish", callback_data="ai_exit")
    b.adjust(1)
    return b.as_markup()


def _location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyamni yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _confirm_keyboard() -> object:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Buyurtmani tasdiqlash", callback_data="ai_confirm")
    b.button(text="❌ Bekor qilish", callback_data="ai_cancel_order")
    b.adjust(1)
    return b.as_markup()


def _order_summary(data: dict, zone: str, discount: int = 0) -> str:
    """Mijozga buyurtmani tasdiqlashdan oldin to'liq xulosa."""
    op_id = data.get("sel_operator", "")
    tariff = next((t for t in TARIFFS.get(op_id, []) if t["id"] == data.get("sel_tariff")), None)
    operator = OPERATORS.get(op_id, {"name": op_id})
    dtype = DELIVERY_TYPES.get(data.get("sel_delivery", "ish_vaqti"), {})
    tariff_price = tariff["price"] if tariff else 0
    delivery_price = dtype.get("price", 0)
    total = max(0, tariff_price + delivery_price - discount)
    promo = "🎁 <b>1+1 AKSIYA:</b> ikkinchi SIM BEPUL!\n" if tariff_price >= PROMO_1PLUS1_MIN_PRICE else ""
    disc_line = f"🎁 <b>Do'st chegirmasi:</b> -{discount:,} so'm\n" if discount else ""
    hint = operator_number_hint(op_id)
    delivery_text = "Bepul 🎁" if delivery_price == 0 else f"{delivery_price:,} so'm"
    return (
        "📋 <b>BUYURTMANGIZ</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"📡 <b>Operator:</b> {operator['name']}\n"
        f"📦 <b>Tarif:</b> {tariff['name'] if tariff else '—'} — {tariff_price:,} so'm/oy\n"
        f"{promo}"
        f"🚀 <b>Yetkazish:</b> {dtype.get('desc', '—')} — {delivery_text}\n"
        f"{disc_line}"
        f"📍 <b>Hudud:</b> {zone}\n"
        f"📞 <b>Tel:</b> {data.get('customer_phone', '—')}\n"
        f"💳 <b>Jami:</b> <b>{total:,} so'm</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"{NUMBER_NOTE}\n"
        f"{PAYMENT_NOTE}\n"
        f"{PASSPORT_NOTE}\n"
        f"📱 Raqamingiz <b>{hint}</b> ko'rinishida bo'ladi.\n"
        "<i>Aniq raqam va yetkazish vaqtini operatorimiz siz bilan kelishadi.</i>\n\n"
        "Hammasi to'g'rimi? 👇"
    )


# ─── AI MASLAHAT (sof matn, tool YO'Q) ──────────────────────────

# Few-shot priming — maslahat stsenariylari bilan (proxy + model uchun)
_PRIMING = [
    {"role": "user", "content": "Salom"},
    {"role": "assistant", "content": (
        "Salom! 😊 Men Suxrob — Texnoset AI yordamchisi, SIM karta tanlashda yordam beraman. "
        "Ayting-chi, telefoningizda nima ko'proq kerak — internetmi, qo'ng'iroqmi, "
        "yoki arzonroq bo'lgani?\n@@ASK@@"
    )},
    {"role": "user", "content": "menga eng arzon tarif kerak"},
    {"role": "assistant", "content": (
        "Tejamkorlikni yaxshi ko'raman 👍\n\n"
        "<b>Beeline Standart</b> — aynan siz uchun:\n"
        "<blockquote>📶 10 GB internet\n☎️ 700 daqiqa qo'ng'iroq\n💬 500 SMS</blockquote>\n"
        "💰 <b>45 000 so'm/oy</b> (kuniga 1 500 so'm)\n\n"
        "Beeline tugmasini bossangiz, davom etamiz 👇\n@@PICK beeline bee_standart@@"
    )},
    {"role": "user", "content": "ko'p internet kerak, qaysi tarif yaxshi?"},
    {"role": "assistant", "content": (
        "Internetni ko'p ishlatasiz-a, tushundim! 📶\n\n"
        "<b>Mobiuz ORZU 90</b> — bu zo'r tanlov:\n"
        "<blockquote>📶 180 GB internet\n☎️ Cheksiz qo'ng'iroq\n🎁 1+1: ikkinchi SIM BEPUL</blockquote>\n"
        "💰 <b>90 000 so'm/oy</b> (kuniga ~3 000 so'm)\n\n"
        "Mobiuz tugmasini tanlang 👇\n@@PICK ums ums_orzu_90@@"
    )},
    {"role": "user", "content": "YouTube ko'p ishlataman"},
    {"role": "assistant", "content": (
        "YouTube'ni yaxshi ko'rasiz-da 🎬\n\n"
        "<b>Mobiuz Xotirjam 80</b> — aynan mos:\n"
        "<blockquote>▶️ YouTube + 10 ilova cheksiz\n📶 80 GB internet\n☎️ Cheksiz qo'ng'iroq\n🎁 1+1: ikkinchi SIM bepul</blockquote>\n"
        "💰 <b>80 000 so'm/oy</b>\n\n"
        "Mobiuz tugmasini bossangiz, davom etamiz 👇\n@@PICK ums ums_xotirjam_80@@"
    )},
    {"role": "user", "content": "bilmadim qaysi birini olsam"},
    {"role": "assistant", "content": (
        "Hech qisi yo'q, birga tanlaymiz 😊\n"
        "Ayting-chi: internet ko'proq muhimmi, yoki arzonroq bo'lgani? "
        "Shunga qarab eng zo'rini topib beraman 👍\n@@ASK@@"
    )},
    {"role": "user", "content": "eng arzon tariflarni hammasini ko'rsat"},
    {"role": "assistant", "content": (
        "Albatta! Har operatordan eng arzon variantni solishtirib beraman 👇\n@@COMPARE arzon@@"
    )},
    {"role": "user", "content": "operatorlarni internet bo'yicha solishtir"},
    {"role": "assistant", "content": (
        "Yaxshi savol! Har operatordan eng ko'p internetlisini yonma-yon ko'rsataman 👇\n@@COMPARE internet@@"
    )},
]


_PICK_RE = re.compile(r"@@\s*PICK\s+([a-z0-9_]+)\s+([a-z0-9_]+)\s*@@", re.I)
_ASK_RE = re.compile(r"@@\s*ASK\s*@@", re.I)
_COMPARE_RE = re.compile(r"@@\s*COMPARE\s+([a-z]+)\s*@@", re.I)
_COMPARE_CATS = {"arzon", "internet", "youtube", "qongiroq"}


def _parse_markers(text: str):
    # AI javobidagi @@PICK op tid@@ / @@COMPARE cat@@ / @@ASK@@ belgilarini ajratadi.
    pick = None
    m = _PICK_RE.search(text)
    if m:
        op_id, tid = m.group(1), m.group(2)
        t = next((x for x in TARIFFS.get(op_id, [])
                  if x["id"] == tid and not x.get("family") and not x.get("no_compare")), None)
        if t:
            pick = (op_id, t)
    compare = None
    mc = _COMPARE_RE.search(text)
    if mc and mc.group(1).lower() in _COMPARE_CATS:
        compare = mc.group(1).lower()
    text = _PICK_RE.sub("", text)
    text = _COMPARE_RE.sub("", text)
    text = _ASK_RE.sub("", text).strip()
    return text, pick, compare


def _recommend_keyboard(pick) -> object:
    # AI aynan tavsiya qilgan tarif uchun bitta yorqin CTA (tanlov yukini kamaytiradi).
    op_id, t = pick
    op = OPERATORS.get(op_id, {})
    badge = f" {PROMO_1PLUS1_BADGE}" if t["price"] >= PROMO_1PLUS1_MIN_PRICE else ""
    b = InlineKeyboardBuilder()
    b.button(
        text=f"✅ {op.get('emoji', '')} {op.get('name', op_id)} {t['name']} — {t['price']:,}{badge}",
        callback_data=f"ai_tf_{op_id}__{t['id']}",
    )
    b.button(text="📋 Boshqa variantlar", callback_data="ai_back_op")
    b.button(text="❌ Chiqish", callback_data="ai_exit")
    b.adjust(1)
    return b.as_markup()


class _Streamer:
    """Native Bot API 9.5 (sendMessageDraft) orqali real-time silliq yozish.
    Agar native ishlamasa (eski klient/guruh/xato) — oddiy xabar+tahrirga qaytadi."""

    def __init__(self, message):
        self.msg = message
        self.bot = message.bot
        self.chat_id = message.chat.id
        self.draft_id = (message.message_id or int(time.monotonic() * 1000)) % 2_000_000_000
        self.last = 0.0
        self.shown = ""
        self.native = True
        self.placeholder = None  # fallback uchun haqiqiy xabar

    async def start(self):
        # native "Thinking…" qoralama puffagi (bo'sh text)
        try:
            await self.bot.send_message_draft(
                chat_id=self.chat_id, draft_id=self.draft_id, text="⏳ Bir soniya...", parse_mode=None,
            )
            return
        except Exception:
            self.native = False
        try:
            self.placeholder = await self.msg.answer("⏳ Bir soniya...")
        except Exception:
            self.placeholder = None

    def _clean(self, partial: str) -> str:
        vis = partial.split("@@")[0]              # marker boshlanishini yashir
        vis = re.sub(r"<[^>]*$", "", vis)         # tugallanmagan teg oxirini kes
        return _strip_html(vis).strip()[:3900]

    async def update(self, partial: str):
        now = time.monotonic()
        if now - self.last < (0.25 if self.native else 0.9):
            return
        vis = self._clean(partial)
        if not vis or vis == self.shown:
            return
        self.shown = vis
        self.last = now
        if self.native:
            try:
                await self.bot.send_message_draft(
                    chat_id=self.chat_id, draft_id=self.draft_id, text=vis, parse_mode=None,
                )
                return
            except Exception:
                self.native = False  # native uzildi -> oddiy usulga o'tamiz
        try:
            if self.placeholder is None:
                self.placeholder = await self.msg.answer(vis + " ▌")
            else:
                await self.placeholder.edit_text(vis + " ▌", parse_mode=None)
        except Exception:
            pass

    async def finish(self, final_html: str, kb=None):
        # Yakuniy to'liq xabarni saqlaymiz (draft ephemeral — yo'qoladi)
        if self.placeholder is not None:
            try:
                return await self.placeholder.edit_text(final_html, reply_markup=kb)
            except Exception:
                try:
                    return await self.placeholder.edit_text(_strip_html(final_html), reply_markup=kb)
                except Exception:
                    return self.placeholder
        try:
            return await self.msg.answer(final_html, reply_markup=kb)
        except Exception:
            return await self.msg.answer(_strip_html(final_html), reply_markup=kb)


async def _ai_reply(history: list, on_update=None):
    """AI javobini (matn, tavsiya) qaytaradi. on_update berilsa — real vaqtda
    (streaming) xabarni belgima-belgi yangilab boradi."""
    client = _get_client()
    messages = [{"role": "system", "content": _get_system_prompt()}] + _PRIMING + history
    if on_update is not None:
        try:
            stream = await client.chat.completions.create(
                model=MODEL, max_tokens=MAX_TOKENS, messages=messages, stream=True,
            )
            full = ""
            async for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content or ""
                except Exception:
                    delta = ""
                if delta:
                    full += delta
                    await on_update(full)
            if full.strip():
                text, pick, compare = _parse_markers(full)
                return _md_to_html(text), pick, compare
        except Exception as e:
            logger.warning("stream ishlamadi, oddiy chaqiruvga o'tildi: %s", e)
    resp = await client.chat.completions.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        messages=messages,
    )
    text = (resp.choices[0].message.content or "").strip()
    text, pick, compare = _parse_markers(text)
    return _md_to_html(text), pick, compare


_TAG_RE = re.compile(r"<[^>]+>")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_MD_BOLD2 = re.compile(r"__(.+?)__", re.DOTALL)
_MD_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)


def _md_to_html(text: str) -> str:
    """Markdownни Telegram HTML'ga o'giradi (model **...** chiqarsa ham
    xom ko'rinmasin). Faqat <b> bilan almashtiramiz."""
    text = _MD_BOLD.sub(r"<b>\1</b>", text)
    text = _MD_BOLD2.sub(r"<b>\1</b>", text)
    text = _MD_HEAD.sub("", text)          # '### Sarlavha' belgilarini olib tashlash
    text = text.replace("* ", "• ")        # markdown bullet -> nuqta
    return text


def _strip_html(text: str) -> str:
    """HTML teglarni olib tashlaydi (oraliq kadr va xato fallback uchun)."""
    return _TAG_RE.sub("", text)


async def _typewriter(answer_to, text: str, reply_markup, existing_msg=None):
    """Tez: bitta yengil 'yozilmoqda' kadri, keyin to'liq (HTML) matn.

    Oraliq kadrда teglar ko'rinmasligi uchun tozalanadi. Agar HTML
    noto'g'ri bo'lsa, teglarsiz toza matn yuboriladi (raw teg ko'rinmaydi).
    """
    msg = existing_msg
    plain = _strip_html(text)
    words = plain.split()

    # Placeholder bo'lmasa — to'g'ridan-to'g'ri
    if msg is None:
        try:
            return await answer_to.answer(text, reply_markup=reply_markup)
        except Exception:
            return await answer_to.answer(plain, reply_markup=reply_markup)

    if len(words) <= 8:
        try:
            return await msg.edit_text(text, reply_markup=reply_markup)
        except Exception:
            try:
                return await msg.edit_text(plain, reply_markup=reply_markup)
            except Exception:
                return msg

    # Uzunroq javob — bitta yengil "yozilmoqda" kadri (teglarsiz)
    try:
        half = " ".join(words[: max(1, len(words) * 6 // 10)]) + " ▌"
        await msg.edit_text(half, parse_mode=None)
        await asyncio.sleep(0.1)
    except Exception:
        pass
    # Yakuniy: HTML bilan; xato bo'lsa — toza matn (raw teg emas)
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
    except Exception:
        try:
            await msg.edit_text(plain, reply_markup=reply_markup)
        except Exception:
            pass
    return msg


def _fallback_text(stage: str) -> str:
    if stage == "operator":
        return "Salom! 😊 Qaysi operator kerak — yoki qancha internet ishlatasiz? Quyidan tanlang 👇"
    if stage.startswith("tariff:"):
        return "Qaysi tarif sizga mos — quyidagilardan tanlang 👇"
    if stage == "delivery":
        return "Yetkazib berish turini tanlang 👇"
    return "Quyidagi tugmalardan birini tanlang 👇"


# ─── BUYURTMANI KOD ORQALI RASMIYLASHTIRISH ─────────────────────

async def _place_order(data: dict, user_id: int, bot,
                       lat: float | None = None, lon: float | None = None) -> int:
    """Buyurtmani lokal bazaga yozadi va adminga tasdiqlash tugmalari
    bilan yuboradi. Admin tasdiqlagach kuryerlar guruhiga tushadi."""
    op_id = data.get("sel_operator", "")
    tariff_id = data.get("sel_tariff", "")
    dtype_key = data.get("sel_delivery", "ish_vaqti")
    customer_phone = data.get("customer_phone", "")
    customer_name = data.get("user_name", "Mehmon")
    region = data.get("region", DELIVERY_ZONE_NAME)

    tariff = next((t for t in TARIFFS.get(op_id, []) if t["id"] == tariff_id), None)
    operator = OPERATORS.get(op_id, {"name": op_id})
    dtype = DELIVERY_TYPES.get(dtype_key, DELIVERY_TYPES["ish_vaqti"])
    delivery_price = dtype["price"]
    delivery_name = f"{dtype['emoji']} {dtype['name']} ({dtype['desc']})"
    tariff_price = tariff.get("price", 0) if tariff else 0
    tariff_name = tariff.get("name", tariff_id) if tariff else tariff_id
    discount = int(data.get("ref_discount", 0) or 0)
    total = max(0, tariff_price + delivery_price - discount)

    order_num = await orders_db.create_order({
        "name": customer_name,
        "user_id": user_id,
        "phone": customer_phone,
        "operator": operator["name"],
        "op_id": op_id,
        "tariff": tariff_name,
        "region": region,
        "lat": lat,
        "lon": lon,
        "delivery_price": delivery_price,
        "delivery_type": delivery_name,
        "tariff_price": tariff_price,
        "discount": discount,
        "promo": tariff_price >= PROMO_1PLUS1_MIN_PRICE,
    })

    order = await orders_db.get_order_by_num(order_num)

    # Buyurtma kartochkasi (Tasdiqlash/Bekor tugmalari bilan) — buyurtmalar
    # GURUHIga tushadi (mijoz topic'ida, bo'lmasa guruhning umumiy qismida).
    placed_in_group = False
    try:
        placed_in_group = await dispatch.open_order_topic(bot, order)
    except Exception:
        logger.warning("Buyurtma guruhga joylanmadi (#%s)", order_num)

    # Guruhga tushmasa (guruh ulanmagan yoki xato) — admin SHAXSIY chatiga (fallback)
    if not placed_in_group:
        sent = 0
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    dispatch.order_card(order, f"🆕 <b>YANGI BUYURTMA #{order_num}</b> — tasdiqlang"),
                    reply_markup=dispatch.kb_admin_confirm(order),
                )
                if lat and lon:
                    await bot.send_location(admin_id, latitude=lat, longitude=lon)
                sent += 1
            except Exception as e:
                logger.warning("Adminga (%s) buyurtma #%s yuborilmadi: %s", admin_id, order_num, e)
        if sent == 0:
            logger.error("DIQQAT: #%s buyurtma hech bir adminga yetib bormadi!", order_num)

    if discount:
        try:
            referrals_store.mark_used(user_id)
            rid = referrals_store.referrer_of(user_id)
            if rid:
                await bot.send_message(
                    int(rid),
                    "🎉 Tabriklaymiz! Siz taklif qilgan do'stingiz buyurtma berdi. "
                    "Rahmat — yana do'stlaringizni taklif qiling! 🎁",
                )
        except Exception:
            logger.warning("Referal chegirma/xabar ishlamadi (user %s)", user_id)
    analytics_store.order_placed(total, via_ai=True)
    return order_num


# ─── START AI CHAT ───────────────────────────────────────────────

async def start_ai_chat(target, state: FSMContext, quick: bool = False):
    await state.clear()
    await state.set_state(AIState.chatting)
    user_name = target.from_user.first_name or "Mehmon"
    await state.update_data(ai_history=[], user_name=user_name, ai_stage="operator")
    analytics_store.ai_session()
    followups_store.touch(target.from_user.id, "operator", user_name)

    if quick:
        text = (
            f"🛒 Boshladik, {user_name}! 👋\n"
            "Men Suxrob — Texnoset AI yordamchisi, buyurtmangizni tez rasmiylashtiramiz.\n\n"
            "Qaysi operatorni xohlaysiz? Quyidan tanlang — yoki «arzonroq» / "
            "«internet ko'p» deb yozsangiz, mosini o'zim topaman 👇"
        )
    else:
        text = (
            f"Assalomu alaykum, {user_name}! 👋\n"
            "Men Suxrob — Texnoset'ning AI yordamchisiman, sizga eng mos SIM kartani tanlashda yordam beraman 😊\n\n"
            "Erkin yozing — masalan «arzonroq kerak» yoki «internet ko'p bo'lsin», "
            "men aynan sizga mosini topib beraman.\n\n"
            "Yoki to'g'ridan operatorni tanlang 👇"
        )
    keyboard = _stage_keyboard("operator")
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        # Rasmli (caption) xabarni edit_text qilib bo'lmaydi — o'chirib,
        # yangi matnli xabar yuboramiz.
        try:
            await target.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            try:
                await target.message.delete()
            except Exception:
                pass
            await target.message.answer(text, reply_markup=keyboard)
        await target.answer()


# ─── INJECTION FILTER ───────────────────────────────────────────

_INJECTION_PATTERNS = [
    "ignore previous", "ignore all", "forget instructions", "new instructions",
    "system prompt", "you are now", "pretend you are", "act as", "jailbreak",
    "tool call", "tool_call", "callfunction", "function_call", "<system>", "</system>",
    "oldingi ko'rsatmalarni", "ko'rsatmalarni unut", "sen endi", "rolni o'zgartir",
]


def _is_injection(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _INJECTION_PATTERNS)


# ─── ISSIQ MIJOZ (real-time individual insight) ─────────────────

_BUY_SIGNALS = [
    "olaman", "sotib ola", "buyurtma ber", "buyurtma qila", "zakaz",
    "qachon yetkaz", "bugun kerak", "hozir kerak", "tezroq kerak",
    "tayyorman", "qabul qilaman", "olib kel", "olsam bo'lad",
]


def _buying_signal(text: str) -> bool:
    t = (text or "").lower()
    return any(s in t for s in _BUY_SIGNALS)


async def _send_admin(bot, text: str):
    """Adminlarga xabar — HTML buzilsa, toza matn bilan qayta yuboradi."""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            try:
                await bot.send_message(admin_id, _strip_html(text))
            except Exception:
                pass


async def _notify_hot_lead(bot, data: dict, user, last_text: str):
    """Jonli suhbatda kuchli sotib olish signali — adminga professional insight."""
    op = OPERATORS.get(data.get("sel_operator", ""), {}).get("name", "—")
    profile = {
        "name": data.get("user_name") or (user.first_name or "Mijoz"),
        "operator": op,
        "tariff": data.get("sel_tariff", "—"),
        "questions": _customer_questions(data) + [last_text],
        "outcome": "ISSIQ — hali buyurtma bermagan, hozir jonli suhbatda",
        "stage": data.get("ai_stage", "—"),
    }
    insight = await ai_analytics.customer_insight(profile)
    uname = f"@{user.username}" if user.username else f"ID: {user.id}"
    msg = (
        "🔥 <b>ISSIQ MIJOZ — hozir suhbatda!</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 {profile['name']} ({uname})\n"
        f"📡 {profile['operator']} — {profile['tariff']}\n"
        f"💬 Oxirgi xabar: «{last_text[:120]}»"
        + (f"\n\n🧠 <b>AI Insight:</b>\n{insight}" if insight else "")
    )
    if not await dispatch.post_to_orders_group(bot, msg, user_id=user.id):
        await _send_admin(bot, msg)


# ─── IKKINCHI XABAR: SOTUVGA UNDOVCHI / MASLAHATCHI ─────────────

def _consult_keyboard() -> object:
    """Ikkinchi (sotuv) xabar ostidagi tezkor yo'naltirish tugmalari."""
    b = InlineKeyboardBuilder()
    b.button(text="💬 Maslahat / taqqoslash", callback_data="ai_help_compare")
    b.button(text="🏠 Bosh sahifa", callback_data="back_to_main")
    b.adjust(1)
    return b.as_markup()


async def _send_sales_followup(message, *, picked: bool = False):
    """Tugmali xabardan keyin — mijoz bilan gaplashuvchi, sotuvga undovchi
    ikkinchi xabar. Mijozni keyingi qadamга iliq yetaklaydi."""
    if picked:
        text = (
            "💬 <b>Suxrob:</b> Zo'r tanlov! 👏 Shu tarifni ko'pchilik oladi.\n"
            "Yuqoridagi tugmani bossangiz — bir daqiqada rasmiylashtiramiz, eshigingizgacha "
            "<b>bepul</b> yetkazamiz 🚀\nSavolingiz bo'lsa — bemalol yozing, tushuntiraman 😊"
        )
    else:
        text = (
            "💬 <b>Suxrob:</b> Qaysi biri ko'proq yoqdi? 😊 Ayting — farqini tushuntirib, "
            "aynan <b>sizga mosini</b> tanlab beraman.\n"
            "Yoki to'g'ridan operatorni bossangiz, buyurtmani birga yakunlaymiz 👇"
        )
    try:
        await message.answer(text, reply_markup=_consult_keyboard())
    except Exception:
        pass


@router.callback_query(F.data == "ai_help_compare")
async def ai_help_compare(callback: CallbackQuery, state: FSMContext):
    """Ikkinchi xabardagi 'Maslahat/taqqoslash' — barchasini solishtirib beradi."""
    await state.set_state(AIState.chatting)
    await state.update_data(ai_stage="operator")
    try:
        await callback.message.answer(
            tariff_advice.format_comparison("arzon"),
            reply_markup=_comparison_keyboard("arzon"),
        )
    except Exception:
        pass
    await callback.answer()


# ─── ERKIN MATN HANDLERI ────────────────────────────────────────

@router.message(AIState.chatting, F.text & ~F.text.startswith("/"))
async def handle_ai_message(message: Message, state: FSMContext):
    data = await state.get_data()
    stage: str = data.get("ai_stage", "operator")

    # Follow-up'dan keyin kelgan fikr (mijoz hali shu suhbatda bo'lsa ham)
    if followups_store.is_awaiting_feedback(message.from_user.id):
        await _record_and_analyze_feedback(
            message.bot, message.from_user.id,
            data.get("user_name", "Mijoz"), message.text.strip(),
        )
        await message.answer(
            "Rahmat fikringiz uchun! 🙏 Tayyor bo'lsangiz, davom etamiz 👇",
            reply_markup=_stage_keyboard(stage if stage in ("operator", "done") else "operator"),
        )
        return

    # Telefon bosqichi — AI EMAS, to'g'ridan-to'g'ri kod
    if stage == "phone":
        if not _looks_like_phone(message.text):
            await message.answer(
                "📞 Iltimos, to'g'ri telefon raqam kiriting.\n<i>Masalan: +998901234567</i>",
                reply_markup=_phone_keyboard(),
            )
            return
        await state.update_data(customer_phone=message.text.strip(), ai_stage="location")
        followups_store.touch(message.from_user.id, "location", data.get("user_name", ""))
        await message.answer(
            "Rahmat! Raqamingizni oldim ✅\n\n"
            "Oxirgi qadam! 🏁 Joylashuvingizni yuboring — eshigingizgacha yetkazib beramiz 📍👇",
            reply_markup=_location_keyboard(),
        )
        return

    # Lokatsiya kutilayotganda matn yozilsa — eslatma
    if stage == "location":
        await message.answer(
            "📍 Iltimos, pastdagi tugma orqali <b>joylashuvingizni</b> yuboring 👇",
            reply_markup=_location_keyboard(),
        )
        return

    # Tasdiqlash kutilayotganda matn yozilsa — tugmaga yo'naltir
    if stage == "confirm":
        await message.answer(
            "Buyurtmani yakunlash uchun yuqoridagi <b>«✅ Tasdiqlash»</b> tugmasini bosing 👆",
        )
        return

    if _is_injection(message.text):
        await message.answer(
            "Men faqat SIM karta bo'yicha yordam beraman 😊",
            reply_markup=_stage_keyboard(stage),
        )
        return

    # Issiq mijoz: kuchli sotib olish signali — adminni bir marta ogohlantir
    if not data.get("hot_alerted") and stage != "done" and _buying_signal(message.text):
        await state.update_data(hot_alerted=True)
        asyncio.create_task(_notify_hot_lead(message.bot, data, message.from_user, message.text))

    # Operator nomini yozsa — darhol tarifga (AI'siz, tez)
    op_id = _detect_operator(message.text)
    if op_id and (stage == "operator" or stage.startswith("tariff:")):
        op = OPERATORS[op_id]
        analytics_store.operator_asked(op_id)
        await state.update_data(ai_stage=f"tariff:{op_id}", sel_operator=op_id)
        await message.answer(
            f"Ajoyib tanlov! {op['emoji']} <b>{op['name']}</b> 👌\n\n"
            "Endi sizga mos tarifni birga tanlaymiz 👇",
            reply_markup=_stage_keyboard(f"tariff:{op_id}"),
        )
        return

    analytics_store.advice_query(message.text)

    # Tarif maslahati — har kompaniyadan eng mos variantni KOD orqali
    # taqqoslab ko'rsatamiz. Tugmalar AYNAN tavsiya qilingan tariflar.
    category = tariff_advice.detect_category(message.text)
    if category and (stage == "operator" or stage.startswith("tariff:")):
        await state.update_data(ai_stage="operator")
        await message.answer(
            tariff_advice.format_comparison(category),
            reply_markup=_comparison_keyboard(category),
        )
        await _send_sales_followup(message)
        return

    # Boshqa/erkin savollar — AI maslahat (sof matn). Rate-limit (xarajat/DoS).
    if _rate_limited(_last_ai_call, message.from_user.id, _AI_COOLDOWN):
        await message.answer(
            "Birozdan so'ng yozing 🙂 yoki quyidan tanlang 👇",
            reply_markup=_stage_keyboard(stage),
        )
        return

    history: list = data.get("ai_history", [])
    history.append({"role": "user", "content": message.text})

    streamer = _Streamer(message)
    await streamer.start()
    try:
        ai_text, pick, compare = await _ai_reply(history, on_update=streamer.update)
        if not ai_text:
            ai_text = _fallback_text(stage)
        history.append({"role": "assistant", "content": ai_text})
        if len(history) > 12:
            history = history[-12:]
        await state.update_data(ai_history=history)
        in_pick_stage = stage == "operator" or stage.startswith("tariff:")
        # AI barcha operatorlarni solishtirishni so'radi (@@COMPARE)
        if compare and in_pick_stage:
            await streamer.finish(ai_text or "Mana barchasini solishtirib beraman 👇", None)
            await state.update_data(ai_stage="operator")
            await message.answer(
                tariff_advice.format_comparison(compare),
                reply_markup=_comparison_keyboard(compare),
            )
            await _send_sales_followup(message)
            return
        if pick and in_pick_stage:
            await streamer.finish(ai_text, _recommend_keyboard(pick))
            await _send_sales_followup(message, picked=True)
        else:
            await streamer.finish(ai_text, _stage_keyboard(stage))
    except openai.AuthenticationError:
        await streamer.finish("⚠️ AI kalit xato. Admin bilan bog'laning.")
    except openai.RateLimitError:
        await streamer.finish("⚠️ AI band. Bir oz kutib qayta urinib ko'ring.", _stage_keyboard(stage))
    except Exception:
        await streamer.finish(_fallback_text(stage), _stage_keyboard(stage))


# ─── RAQAM ULASHISH (Telegram kontakt tugmasi) ──────────────────

@router.message(AIState.chatting, F.contact)
async def handle_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("ai_stage") != "phone":
        return
    phone = (message.contact.phone_number or "").strip()
    await state.update_data(customer_phone=phone, ai_stage="location")
    followups_store.touch(message.from_user.id, "location", data.get("user_name", ""))
    await message.answer(
        "Rahmat, raqam oldim ✅\nOxirgi qadam — joylashuvingizni yuboring 📍👇",
        reply_markup=_location_keyboard(),
    )


# ─── GPS LOKATSIYA HANDLERI ──────────────────────────────────────

@router.message(AIState.chatting, F.location)
async def handle_location(message: Message, state: FSMContext):
    data = await state.get_data()
    stage: str = data.get("ai_stage", "operator")

    # Faqat "location" bosqichida buyurtma yaratiladi — dublikat va
    # "bo'sh buyurtma" (tarif/telefonsiz) himoyasi.
    if stage != "location":
        if stage == "done":
            await message.answer(
                "✅ Buyurtmangiz allaqachon qabul qilingan!\n"
                "Yana buyurtma kerak bo'lsa, quyidagi tugmani bosing 👇",
                reply_markup=_stage_keyboard("done"),
            )
        else:
            await message.answer(
                "Avval tarif va telefon raqamini hal qilaylik 😊 "
                "Quyidan davom etamiz 👇",
                reply_markup=_stage_keyboard(stage),
            )
        return

    lat = message.location.latitude
    lon = message.location.longitude
    zone = _check_zone(lat, lon)

    if not zone:
        await _handle_out_of_zone(message, state, data, lat, lon)
        return

    # Hudud ichida — lokatsiyani saqlab, TASDIQLASH bosqichiga o'tamiz
    discount = REFERRAL_DISCOUNT if referrals_store.has_discount(message.from_user.id) else 0
    await state.update_data(region=zone, cust_lat=lat, cust_lon=lon, ai_stage="confirm", ref_discount=discount)
    followups_store.touch(message.from_user.id, "confirm", data.get("user_name", ""))
    data = await state.get_data()
    await message.answer(_order_summary(data, zone, discount), reply_markup=_confirm_keyboard())


async def _handle_out_of_zone(message: Message, state: FSMContext, data: dict, lat, lon):
    """Hudud tashqarisidagi mijozni lead sifatida SAQLAYDI va adminga yuboradi."""
    office = settings_store.get_office()
    distance = _haversine(lat, lon, office["lat"], office["lon"])
    op_id = data.get("sel_operator", "")
    tariff = next((t for t in TARIFFS.get(op_id, []) if t["id"] == data.get("sel_tariff")), None)
    operator = OPERATORS.get(op_id, {"name": op_id})
    dtype = DELIVERY_TYPES.get(data.get("sel_delivery", "ish_vaqti"), {})

    # Lead'ni bazaga yozamiz — admin panelda ko'rinadi, yo'qolmaydi
    try:
        lead_num = await orders_db.create_order({
            "name": data.get("user_name", message.from_user.first_name or "Mijoz"),
            "user_id": message.from_user.id,
            "phone": data.get("customer_phone", ""),
            "operator": operator["name"], "op_id": op_id,
            "tariff": tariff["name"] if tariff else "—",
            "region": "Hudud tashqarisida", "lat": lat, "lon": lon,
            "distance_km": round(distance, 1),
            "delivery_price": dtype.get("price", 0),
            "delivery_type": dtype.get("desc", "—"),
            "tariff_price": tariff["price"] if tariff else 0,
            "promo": (tariff["price"] if tariff else 0) >= PROMO_1PLUS1_MIN_PRICE,
        }, status="Hudud tashqarisida")
    except Exception:
        logger.exception("Hudud tashqarisi lead saqlashda xatolik")
        lead_num = "—"

    await message.answer(
        f"📍 Joylashuvingiz yetkazish hududidan uzoqroqda (taxminan {distance:.0f} km).\n\n"
        "Lekin buyurtmangizni shaxsan ko'rib chiqamiz! 🤝\n"
        f"👨‍💼 Admin tez orada bog'lanadi: {ADMIN_CONTACT}",
        reply_markup=ReplyKeyboardRemove(),
    )
    username = message.from_user.username
    uname = f"@{username}" if username else f"ID: {message.from_user.id}"
    admin_text = (
        f"🟠 <b>HUDUD TASHQARISIDAGI BUYURTMA #{lead_num}</b>\n\n"
        f"👤 Mijoz: {data.get('user_name', '—')} ({uname})\n"
        f"📞 Tel: <code>{data.get('customer_phone', '—')}</code>\n"
        f"📡 {operator['name']} — {tariff['name'] if tariff else '—'}\n"
        f"📍 Masofa: ~{distance:.1f} km (ruxsat {office['radius_km']:.0f} km)\n"
        f"🗺 https://maps.google.com/?q={lat},{lon}\n"
        "Mijoz bilan bog'lanib, qo'lda kelishishingiz mumkin."
    )
    # Mijoz topic'iga (yoki General'ga); guruh ishlamasa — admin DM fallback
    if not await dispatch.post_to_orders_group(message.bot, admin_text, user_id=message.from_user.id):
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(admin_id, admin_text)
                await message.bot.send_location(admin_id, latitude=lat, longitude=lon)
            except Exception as e:
                logger.warning("Adminga (%s) lead yuborilmadi: %s", admin_id, e)
    analytics_store.out_of_zone()
    await state.update_data(ai_stage="done")


def _customer_questions(data: dict) -> list:
    return [m["content"] for m in data.get("ai_history", []) if m.get("role") == "user"]


async def _send_admin_chat_summary(bot, data: dict, order_num, outcome: str, user_id=None):
    """Har bir mijoz bilan chat xulosasi + AI sotuv tavsiyasi — mijoz topic'iga."""
    op = OPERATORS.get(data.get("sel_operator", ""), {}).get("name", "—")
    tariff = data.get("sel_tariff", "—")
    questions = _customer_questions(data)
    q_block = "\n".join(f"  • «{q[:90]}»" for q in questions[-5:]) if questions else "  (faqat tugmalar, savol yo'q)"
    name = data.get("user_name", "Mijoz")
    phone = data.get("customer_phone", "—")

    # Professional individual insight (admin uchun)
    insight = await ai_analytics.customer_insight({
        "name": name, "operator": op, "tariff": tariff,
        "questions": questions, "outcome": outcome, "stage": "Buyurtma yakuni",
    })
    rec_line = f"\n\n🧠 <b>AI Insight:</b>\n{insight}" if insight else ""
    text = (
        f"🧠 <b>MIJOZ XULOSASI — #{order_num}</b> ({outcome})\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 {name} · <code>{phone}</code>\n"
        f"📡 Tanlovi: {op} — {tariff}\n"
        f"💬 <b>Savollari:</b>\n{q_block}"
        f"{rec_line}"
    )
    if not await dispatch.post_to_orders_group(bot, text, user_id=user_id):
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass


@router.callback_query(AIState.chatting, F.data == "ai_confirm")
async def ai_confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("ai_stage") != "confirm":
        return await callback.answer("Bu buyurtma allaqachon yakunlangan.", show_alert=True)
    if _rate_limited(_last_order, callback.from_user.id, _ORDER_COOLDOWN):
        return await callback.answer("Biroz kuting — buyurtma yaqinda yuborildi.", show_alert=True)

    await callback.answer("⏳ Yuborilmoqda...")
    await state.update_data(ai_stage="done")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        order_num = await _place_order(
            data, callback.from_user.id, callback.bot,
            lat=data.get("cust_lat"), lon=data.get("cust_lon"),
        )
    except Exception:
        logger.exception("Buyurtma yaratishda xatolik")
        await state.update_data(ai_stage="confirm")
        return await callback.message.answer(
            "⚠️ Buyurtmani saqlashda xatolik. Qayta urinib ko'ring.",
            reply_markup=_confirm_keyboard(),
        )

    followups_store.complete(callback.from_user.id)
    asyncio.create_task(_send_admin_chat_summary(callback.bot, data, order_num, "BUYURTMA BERDI ✅", user_id=callback.from_user.id))

    op_id = data.get("sel_operator", "")
    hint = operator_number_hint(op_id)
    await callback.message.answer(
        f"🎉 <b>Rahmat! Buyurtmangiz qabul qilindi</b> (#{order_num})\n\n"
        "⏳ Admin tasdiqlashi bilan operatorimiz siz bilan bog'lanib, "
        "<b>SIM raqamni tanlash</b> va <b>yetkazib berish vaqtini</b> kelishadi.\n"
        f"📱 Raqamingiz <b>{hint}</b> ko'rinishida bo'ladi.\n"
        f"{PAYMENT_NOTE}\n"
        f"{PASSPORT_NOTE}\n\n"
        "Har bosqichda sizga xabar beramiz! 🙏",
        reply_markup=_stage_keyboard("done"),
    )


@router.callback_query(AIState.chatting, F.data == "ai_cancel_order")
async def ai_cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.update_data(ai_stage="done")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("Bekor qilindi.")
    await callback.message.answer(
        "❌ Buyurtma bekor qilindi.\n\nYangi buyurtma uchun pastdan tanlang 👇",
        reply_markup=_stage_keyboard("done"),
    )


# ─── TUGMA CALLBACK HANDLERLARI ─────────────────────────────────

@router.callback_query(AIState.chatting, F.data.startswith("ai_op_"))
async def ai_pick_operator(callback: CallbackQuery, state: FSMContext):
    op_id = callback.data.replace("ai_op_", "")
    op = OPERATORS.get(op_id)
    if not op:
        return await callback.answer("Xatolik.", show_alert=True)

    analytics_store.operator_asked(op_id)
    await state.update_data(ai_stage=f"tariff:{op_id}", sel_operator=op_id)
    followups_store.touch(callback.from_user.id, f"tariff:{op_id}",
                          (await state.get_data()).get("user_name", ""))
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(f"{op['emoji']} Tanlandi!")
    await callback.message.answer(
        f"✅ <b>{op['name']}</b> — tarifni tanlang 👇\n"
        "<i>Bilmasangiz «internet ko'p» yoki «arzonroq» deb yozing.</i>",
        reply_markup=_stage_keyboard(f"tariff:{op_id}"),
    )


@router.callback_query(AIState.chatting, F.data.startswith("ai_tf_"))
async def ai_pick_tariff(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.replace("ai_tf_", "").split("__", 1)
    if len(parts) < 2:
        return await callback.answer("Xatolik.", show_alert=True)
    op_id, tariff_id = parts
    tariff = next((t for t in TARIFFS.get(op_id, []) if t["id"] == tariff_id), None)
    if not tariff:
        return await callback.answer("Tarif topilmadi.", show_alert=True)

    analytics_store.tariff_chosen(op_id, tariff_id)
    await state.update_data(ai_stage="delivery", sel_tariff=tariff_id, sel_operator=op_id)
    followups_store.touch(callback.from_user.id, "delivery",
                          (await state.get_data()).get("user_name", ""))
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("📦 Tanlandi!")
    op_name = OPERATORS.get(op_id, {}).get("name", op_id)
    detail = tariff_advice.tariff_detail_block(tariff)
    promo_extra = ""
    if tariff["price"] >= PROMO_1PLUS1_MIN_PRICE:
        promo_extra = "🎁 Bu tarifга <b>1+1</b> — ikkinchi SIM BEPUL, yaqinlaringizga ham oling!\n"
    await callback.message.answer(
        f"✅ <b>{op_name} — {tariff['name']}</b>\n"
        f"{detail}\n"
        f"{promo_extra}"
        "🚚 Yetkazishni tanlang 👇",
        reply_markup=_stage_keyboard("delivery"),
    )


@router.callback_query(AIState.chatting, F.data.startswith("ai_del_"))
async def ai_pick_delivery(callback: CallbackQuery, state: FSMContext):
    dtype_key = callback.data.replace("ai_del_", "")
    dtype = DELIVERY_TYPES.get(dtype_key)
    if not dtype:
        return await callback.answer("Xatolik.", show_alert=True)

    price_text = "Bepul 🎁" if dtype["price"] == 0 else f"{dtype['price']:,} so'm"
    await state.update_data(ai_stage="phone", sel_delivery=dtype_key)
    followups_store.touch(callback.from_user.id, "phone",
                          (await state.get_data()).get("user_name", ""))
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(f"{dtype['emoji']} Tanlandi!")
    work_note = ""
    if dtype["price"] > 0 and not _is_working_hours():
        work_note = (
            f"\n\n🕐 <i>Hozir ish vaqtidan tashqari ({WORK_START_HOUR}:00–{WORK_END_HOUR}:00). "
            "Buyurtmangiz ish vaqti boshlanishi bilan yetkaziladi.</i>"
        )
    await callback.message.answer(
        f"Bo'ldi! {dtype['emoji']} <b>{dtype['name']}</b> ({dtype['desc']}) — {price_text} ✅"
        f"{work_note}\n\n"
        "📞 Telefon raqamingizni yuboring — <b>«📱 Raqamni ulashish»</b> tugmasi orqali "
        "(yoki qo'lda) 👇",
        reply_markup=_phone_keyboard(),
    )


@router.callback_query(AIState.chatting, F.data == "ai_back_op")
async def ai_back_operator(callback: CallbackQuery, state: FSMContext):
    await state.update_data(ai_stage="operator", sel_operator=None, sel_tariff=None)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer()
    await callback.message.answer(
        "Qaysi operatorni xohlaysiz? 👇",
        reply_markup=_stage_keyboard("operator"),
    )


@router.callback_query(AIState.chatting, F.data == "ai_back_tariff")
async def ai_back_tariff(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    op_id = data.get("sel_operator")
    await state.update_data(ai_stage=(f"tariff:{op_id}" if op_id else "operator"), sel_tariff=None)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer()
    if not op_id:
        return await callback.message.answer(
            "Qaysi operatorni xohlaysiz? 👇", reply_markup=_stage_keyboard("operator"),
        )
    op = OPERATORS.get(op_id, {})
    await callback.message.answer(
        f"✅ <b>{op.get('name', op_id)}</b> — tarifni tanlang 👇",
        reply_markup=_stage_keyboard(f"tariff:{op_id}"),
    )


@router.callback_query(AIState.chatting, F.data == "ai_back_delivery")
async def ai_back_delivery(callback: CallbackQuery, state: FSMContext):
    await state.update_data(ai_stage="delivery")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer()
    await callback.message.answer(
        "🚚 Yetkazishni tanlang 👇", reply_markup=_stage_keyboard("delivery"),
    )


# ─── UMUMIY CALLBACK HANDLERLARI ────────────────────────────────

@router.callback_query(F.data == "open_ai_chat")
async def open_ai_chat(callback: CallbackQuery, state: FSMContext):
    await start_ai_chat(callback, state)


@router.callback_query(F.data == "new_order")
async def open_quick_order(callback: CallbackQuery, state: FSMContext):
    # Tezkor buyurtma ham AI oqimi orqali (tugmalar + Suxrob yordami)
    await start_ai_chat(callback, state, quick=True)


@router.callback_query(F.data == "ai_restart")
async def ai_restart(callback: CallbackQuery, state: FSMContext):
    await start_ai_chat(callback, state)


@router.callback_query(F.data == "ai_exit")
async def ai_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Rahmat! Yana murojaat eting 😊\n\nBoshqatdan boshlash uchun /start bosing."
    )
    await callback.answer()


# ─── BOSH SAHIFA SUXROB AI (holatdan tashqari umumiy savollar) ───

_GENERAL_SYSTEM = (
    "Sen Suxrob — Texnoset SIM karta yetkazib berish xizmatining yordamchisisan.\n"
    "Texnoset O'zbekistondagi barcha operatorlar (Ucell, Beeline, Mobiuz, Humans, "
    "Uzmobile) SIM kartalarini uyga yetkazib beradi. Operator/tarif tanlanadi, "
    "raqamni operator bog'lanib kelishadi, kuryer yetkazadi.\n\n"
    "Mijozga ILIQ, ANIQ va TUSHUNARLI javob ber — har doim NIMA demoqchiligingni "
    "to'liq tushuntir, mijoz adashmasin. Faqat O'ZBEK TILIDA.\n\n"
    "🎨 FORMATLASH (Telegram HTML — MAJBURIY):\n"
    "• Markdown ISHLATMA — '**' yoki '#' YO'Q. Faqat <b>...</b>, <i>...</i>, <blockquote>...</blockquote>.\n"
    "• Qalin so'zlar uchun <b>...</b>, sarlavha/qadamlar yoki ro'yxat uchun <blockquote>...</blockquote>.\n"
    "• Har bir teg ALBATTA yopilsin. Bo'limlarni alohida bloklarga ajrat — chiroyli va o'qish oson bo'lsin.\n\n"
    "Misol javob ko'rinishi:\n"
    "<b>Beeline SIM kartani uyga yetkazamiz</b> 📲\n"
    "<blockquote>1. «🛒 Tezkor buyurtma»ni bosing\n2. Beeline'ni tanlang\n"
    "3. Tarifni tanlang\n4. Kuryer uyingizga yetkazadi</blockquote>\n"
    "Savol bo'lsa — «🤖 AI yordamchi»ni bosing 😊\n\n"
    "Buyurtma/tarif istasa — «🤖 AI yordamchi» yoki «🛒 Tezkor buyurtma» tugmasini taklif qil.\n"
    "Agar savol TUSHUNARSIZ yoki mavzudan tashqari bo'lsa — 'Kechirasiz, savolingizni "
    "to'liq tushunmadim 😔' deb ayt va «📞 Aloqa» bo'limiga yo'naltir.\n"
    "Inglizcha/metamatn YO'Q."
)


async def _general_reply(text: str, on_update=None) -> str:
    client = _get_client()
    messages = [
        {"role": "system", "content": _GENERAL_SYSTEM},
        {"role": "user", "content": text},
    ]
    if on_update is not None:
        try:
            stream = await client.chat.completions.create(
                model=MODEL, max_tokens=350, messages=messages, stream=True,
            )
            full = ""
            async for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content or ""
                except Exception:
                    delta = ""
                if delta:
                    full += delta
                    await on_update(full)
            if full.strip():
                return _md_to_html(full.strip())
        except Exception as e:
            logger.warning("stream (general) ishlamadi: %s", e)
    resp = await client.chat.completions.create(
        model=MODEL, max_tokens=350, messages=messages,
    )
    out = (resp.choices[0].message.content or "").strip()
    return _md_to_html(out)


def _home_help_keyboard() -> object:
    b = InlineKeyboardBuilder()
    b.button(text="🤖 AI yordamchi bilan tanlash", callback_data="open_ai_chat")
    b.button(text="🛒 Tezkor buyurtma", callback_data="new_order")
    b.button(text="📞 Aloqa", callback_data="contact")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def home_assistant(message: Message, state: FSMContext):
    """Bosh ekran (holatsiz) — mijoz matn yozsa, to'liq AI sotuv suhbatini
    AVTOMATIK boshlaymiz va xabarni o'sha oqim orqali qayta ishlaymiz.
    Ya'ni /start'dan keyin shunchaki yozish AI yordamchini ishga soladi."""
    if message.text.strip() in ("❌ Bekor qilish", "❌ Bekor"):
        return await message.answer("Bosh sahifa uchun /start bosing 😊", reply_markup=ReplyKeyboardRemove())

    # Abandonment follow-up'dan keyingi fikr — alohida ko'rib chiqamiz
    if followups_store.is_awaiting_feedback(message.from_user.id):
        await _record_and_analyze_feedback(
            message.bot, message.from_user.id,
            message.from_user.first_name or "Mijoz", message.text.strip(),
        )
        await message.answer(
            "Rahmat fikringiz uchun! 🙏 Albatta inobatga olamiz.\n\n"
            "Tayyor bo'lsangiz, buyurtmani bir necha soniyada yakunlaymiz 👇",
            reply_markup=_home_help_keyboard(),
        )
        return

    if _is_injection(message.text):
        await message.answer(
            "Men faqat SIM karta xizmati bo'yicha yordam beraman 😊",
            reply_markup=_home_help_keyboard(),
        )
        return

    # To'liq AI sotuv suhbatini boshlaymiz va shu xabarni o'sha oqimga uzatamiz
    user_name = message.from_user.first_name or "Mijoz"
    await state.set_state(AIState.chatting)
    await state.update_data(ai_history=[], user_name=user_name, ai_stage="operator")
    analytics_store.ai_session()
    followups_store.touch(message.from_user.id, "operator", user_name)
    await handle_ai_message(message, state)


# ─── ABANDONMENT FOLLOW-UP (2 soat) ─────────────────────────────

_FB_REASONS = {
    "narx": "Narx qimmat tuyuldi",
    "keyin": "Keyinroq olmoqchiman",
    "boshqa": "Boshqa joydan oldim",
    "kordim": "Shunchaki ko'rib chiqdim",
}


def _feedback_keyboard() -> object:
    b = InlineKeyboardBuilder()
    for code, label in _FB_REASONS.items():
        b.button(text=label, callback_data=f"fb_reason_{code}")
    b.button(text="🛒 Buyurtmani yakunlash", callback_data="new_order")
    b.adjust(1)
    return b.as_markup()


async def send_followup(bot, user_id, name: str):
    """2 soatdan beri tugatmagan mijozga fikr so'rab xabar yuboradi."""
    try:
        await bot.send_message(
            int(user_id),
            f"Salom{', ' + name if name else ''}! 😊 Men Suxrob — Texnoset'dan.\n\n"
            "Buyurtmangizni yakunlamabsiz — biror narsa xalaqit berdimi yoki "
            "savol qoldimi? 🤔\n"
            "Fikringizni yozing yoki quyidan tanlang — sizga yordam beraman 👇\n\n"
            "<i>(Tarif hali ham sizni kutmoqda — bir necha soniyada yakunlaymiz)</i>",
            reply_markup=_feedback_keyboard(),
        )
        return True
    except Exception as e:
        logger.warning("Follow-up yuborilmadi (%s): %s", user_id, e)
        return False


async def _record_and_analyze_feedback(bot, user_id, name: str, feedback: str):
    followups_store.save_feedback(user_id, feedback)
    analytics_store.feedback_received()
    # Professional individual insight (admin uchun)
    insight = await ai_analytics.customer_insight({
        "name": name, "outcome": "TUGATMAGAN (abandon)",
        "stage": "Buyurtma tashlab ketilgan",
        "questions": [f"Tashlab ketish sababi: {feedback}"],
    })
    rec_line = f"\n\n🧠 <b>AI Insight:</b>\n{insight}" if insight else ""
    text = (
        f"📝 <b>MIJOZ FIKRI (tugatmagan buyurtma)</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 {name} (ID: {user_id})\n"
        f"💬 «{feedback}»"
        f"{rec_line}"
    )
    if not await dispatch.post_to_orders_group(bot, text, user_id=user_id):
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass


@router.callback_query(F.data.startswith("fb_reason_"))
async def feedback_reason(callback: CallbackQuery):
    code = callback.data.replace("fb_reason_", "")
    reason = _FB_REASONS.get(code, code)
    await callback.answer("Rahmat! 🙏")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _record_and_analyze_feedback(
        callback.bot, callback.from_user.id,
        callback.from_user.first_name or "Mijoz", reason,
    )
    await callback.message.answer(
        "Rahmat fikringiz uchun! 🙏\n\n"
        "Agar fikringiz o'zgarsa — biz shu yerdamiz. Buyurtmani istalgan vaqt "
        "yakunlashingiz mumkin 👇",
        reply_markup=_home_help_keyboard(),
    )


async def followup_loop(bot):
    """Har 10 daqiqada tugatmagan mijozlarni tekshirib, fikr so'raydi."""
    while True:
        await asyncio.sleep(600)
        try:
            for item in followups_store.due_for_followup(hours=2.0):
                ok = await send_followup(bot, item["user_id"], item["name"])
                followups_store.mark_followed(item["user_id"])
                if ok:
                    analytics_store.followup_sent()
                await asyncio.sleep(0.3)
        except Exception as e:
            logger.error("followup_loop xatolik: %s", e)
