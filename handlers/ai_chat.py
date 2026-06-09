import asyncio
import math
import random
import re
import anthropic
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatAction

from states import AIState
from data import OPERATORS, TARIFFS
from config import (
    ANTHROPIC_API_KEY, ADMIN_IDS, DELIVERY_TYPES, ADMIN_CONTACT,
    DELIVERY_ZONE_NAME,
    PROMO_1PLUS1_MIN_PRICE, PROMO_1PLUS1_BADGE, PROMO_1PLUS1_TEXT,
)
import settings_store
from sheets_handler import save_order

router = Router()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 400


def _get_delivery_zones():
    o = settings_store.get_office()
    return [(o["zone_name"], o["lat"], o["lon"], o["radius_km"])]


_ai_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url="https://aiprimetech.io",
            timeout=60.0,
            max_retries=2,
        )
    return _ai_client


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
            tariff_lines.append(
                f"{op['emoji']} {op['name']} | {t['name']} | {t['price']:,} so'm/oy | {t['desc']}{promo}"
            )
    zones = " va ".join(z[0] for z in _get_delivery_zones())
    return (
        "Sen Suxrob — Texnoset SIM karta sotuv mutaxassisisan. Tajribali, ishbilarmon, do'stona.\n"
        "Faqat O'ZBEK TILIDA yoz. Inglizcha, metamatn, texnik izoh — YO'Q.\n"
        "Uslub: qisqa, aniq, 1-3 jumla, 1-2 emoji.\n\n"
        "ASOSIY VAZIFA — mijozga ANIQ maslahat berish:\n"
        "• 'Arzon' desa → narxi past tarifni nom va narq bilan ayt\n"
        "• 'Ko'p internet' desa → eng ko'p GB li tarifni tavsiya qil\n"
        "• 'YouTube/TikTok/Telegram' desa → o'sha ilovani bepul beruvchi operatorni ayt\n"
        "• 'Cheksiz qo'ng'iroq' desa → cheksiz qo'ng'iroqli eng arzon tarifni tavsiya qil\n"
        "• 'Qaysi yaxshi?' desa → 2 ta eng ommabop tarifni solishtir\n"
        "• 70 000 so'm va undan qimmat tariflarda 🎁 1+1 AKSIYA bor "
        "(ikkinchi SIM karta BEPUL) — bularni tavsiya qilganda shuni ALBATTA ayt\n"
        "• Har javob oxirida: 'Pastdagi tugmadan tanlang 👇'\n\n"
        "NARQ FORMATI: '70 000 so'm/oy (kuniga ~2 333 so'm)'\n"
        "YETKAZISH: 1 soat=10000 | 2 soat=5000 | 12 soat=BEPUL\n"
        "HUDUD: faqat " + zones + ".\n\n"
        "TARIFLAR (bulardan maslahat ber):\n" + "\n".join(tariff_lines) + "\n\n"
        "Mavzudan chetga chiqsa: 'Men faqat SIM karta bo'yicha yordam beraman 😊'\n\n"
        "DIQQAT: Sen FAQAT maslahat berasan. Buyurtma tugmalar orqali rasmiylashadi."
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
        b.button(text="❌ Chiqish", callback_data="ai_exit")
        b.adjust(2, 2, 1, 1)

    elif stage.startswith("tariff:"):
        op_id = stage.split(":", 1)[1]
        for t in TARIFFS.get(op_id, []):
            badge = f" {PROMO_1PLUS1_BADGE}" if t["price"] >= PROMO_1PLUS1_MIN_PRICE else ""
            b.button(
                text=f"📦 {t['name']} — {t['price']:,} so'm{badge}",
                callback_data=f"ai_tf_{op_id}__{t['id']}",
            )
        b.button(text="⬅️ Operator o'zgartirish", callback_data="ai_back_op")
        b.button(text="❌ Chiqish", callback_data="ai_exit")
        b.adjust(1)

    elif stage == "delivery":
        for key, dt in DELIVERY_TYPES.items():
            price_text = "Bepul 🎁" if dt["price"] == 0 else f"{dt['price']:,} so'm"
            b.button(
                text=f"{dt['emoji']} {dt['desc']} — {price_text}",
                callback_data=f"ai_del_{key}",
            )
        b.button(text="❌ Chiqish", callback_data="ai_exit")
        b.adjust(1)

    elif stage == "done":
        b.button(text="🔄 Yangi buyurtma", callback_data="ai_restart")
        b.button(text="❌ Chiqish", callback_data="ai_exit")
        b.adjust(1)

    else:  # phone va boshqalar
        b.button(text="❌ Chiqish", callback_data="ai_exit")
        b.adjust(1)

    return b.as_markup()


def _location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyamni yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── AI MASLAHAT (sof matn, tool YO'Q) ──────────────────────────

# Few-shot priming — maslahat stsenariylari bilan (proxy + model uchun)
_PRIMING = [
    {"role": "user", "content": "Salom"},
    {"role": "assistant", "content": (
        "Salom! Men Suxrob — Texnoset SIM karta mutaxassisi 😊 "
        "Qaysi operatorni xohlaysiz: Ucell, Beeline, Mobiuz, Humans yoki Uzmobile?"
    )},
    {"role": "user", "content": "menga eng arzon tarif kerak"},
    {"role": "assistant", "content": (
        "Eng arzon variantlar: Beeline Standart 45 000 so'm (kuniga 1 500 so'm) yoki "
        "Mobiuz Connect M ham 45 000 so'm — ikkalasida 10 GB + TAS-IX internet va 700 daqiqa ☎️ "
        "Pastdagi tugmadan operatorni tanlang 👇"
    )},
    {"role": "user", "content": "ko'p internet kerak, qaysi tarif yaxshi?"},
    {"role": "assistant", "content": (
        "Ko'p internet uchun eng yaxshilari: Mobiuz ORZU 90 — 180 GB (90 000 so'm/oy), "
        "Ucell Bor 90 — 90 GB + hafta oxiri cheksiz (90 000 so'm/oy) 📶 "
        "Bonus: ikkalasiga 🎁 1+1 aksiya — ikkinchi SIM karta BEPUL! "
        "Quyidan operatorni tanlang 👇"
    )},
    {"role": "user", "content": "YouTube ko'p ishlataman"},
    {"role": "assistant", "content": (
        "Humans YouTube+ tarifini qo'ying — 56 000 so'm/oy, YouTube CHEKSIZ + "
        "40 GB asosiy internet + Telegram/Instagram ham bepul 🎬 "
        "Humans tugmasini bosing 👇"
    )},
]


async def _ai_reply(history: list) -> str:
    """AI'дан sof matn javob oladi (tool yo'q + few-shot priming = ishonchli)."""
    client = _get_client()
    resp = await client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        system=_get_system_prompt(), messages=_PRIMING + history,
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


async def _typewriter(answer_to, text: str, reply_markup, existing_msg=None):
    """Matnni 'yozilayotgandek' ko'rsatadi. Qisqa javoblar darhol chiqadi."""
    words = text.split()
    msg = existing_msg

    if len(words) <= 6:
        if msg is not None:
            try:
                await msg.edit_text(text, reply_markup=reply_markup)
                return msg
            except Exception:
                pass
        return await answer_to.answer(text, reply_markup=reply_markup)

    if msg is None:
        msg = await answer_to.answer("✍️")
    steps = 3
    step_size = max(1, len(words) // (steps + 1))
    try:
        for i in range(step_size, len(words), step_size):
            try:
                await msg.edit_text(" ".join(words[:i]) + " ▌", parse_mode=None)
            except Exception:
                pass
            await asyncio.sleep(0.18)
    finally:
        try:
            await msg.edit_text(text, reply_markup=reply_markup)
        except Exception:
            try:
                await msg.edit_text(text, parse_mode=None)
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

async def _place_order(data: dict, user_id: int, bot) -> int:
    """Tanlangan ma'lumotlar asosida buyurtma yaratadi (AI'siz, to'liq kod)."""
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
    total = tariff_price + delivery_price

    order_num = await save_order({
        "name": customer_name,
        "user_id": user_id,
        "contact_phone": customer_phone,
        "operator_name": operator["name"],
        "tariff_name": tariff_name,
        "sim_number": "pending",
        "region": region,
        "delivery_price": delivery_price,
        "delivery_type_name": delivery_name,
        "tariff_price": tariff_price,
    })
    if order_num is None:
        order_num = random.randint(1000, 9999)

    promo_line = ""
    if tariff_price >= PROMO_1PLUS1_MIN_PRICE:
        promo_line = "🎁 <b>1+1 AKSIYA:</b> 2 ta SIM karta tayyorlang!\n"

    admin_text = (
        f"🆕 <b>Yangi buyurtma #{order_num}</b> 🤖 AI orqali\n\n"
        f"👤 <b>Mijoz:</b> {customer_name}\n"
        f"📞 <b>Tel:</b> <code>{customer_phone}</code>\n"
        f"📡 <b>Operator:</b> {operator['name']}\n"
        f"📦 <b>Tarif:</b> {tariff_name} — {tariff_price:,} so'm/oy\n"
        f"{promo_line}"
        f"📱 <b>Raqam:</b> kuryer kelganida tanlanadi\n"
        f"📍 <b>Hudud:</b> {region}\n"
        f"🚀 <b>Yetkazish:</b> {delivery_name} — {delivery_price:,} so'm\n"
        f"💰 <b>Jami:</b> {total:,} so'm"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            pass

    return order_num


# ─── START AI CHAT ───────────────────────────────────────────────

async def start_ai_chat(target, state: FSMContext):
    await state.clear()
    await state.set_state(AIState.chatting)
    user_name = target.from_user.first_name or "Mehmon"
    await state.update_data(ai_history=[], user_name=user_name, ai_stage="operator")

    text = (
        "Salom! 👋 Men Suxrob — Texnoset SIM mutaxassisi.\n\n"
        "📱 Bir necha soniyada sizga eng zo'r tarifni tanlab beraman.\n\n"
        "Boshladik — qaysi operatorni xohlaysiz? 👇"
    )
    keyboard = _stage_keyboard("operator")
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)
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


# ─── ERKIN MATN HANDLERI ────────────────────────────────────────

@router.message(AIState.chatting, F.text & ~F.text.startswith("/"))
async def handle_ai_message(message: Message, state: FSMContext):
    data = await state.get_data()
    stage: str = data.get("ai_stage", "operator")

    # Telefon bosqichi — AI EMAS, to'g'ridan-to'g'ri kod
    if stage == "phone":
        if not _looks_like_phone(message.text):
            await message.answer(
                "📞 Iltimos, to'g'ri telefon raqam kiriting.\n<i>Masalan: +998901234567</i>",
                reply_markup=_stage_keyboard("phone"),
            )
            return
        await state.update_data(customer_phone=message.text.strip(), ai_stage="location")
        await message.answer(
            "✅ Raqam qabul qilindi!\n\n"
            "📍 Endi joylashuvingizni yuboring — yetkazib berish hududini tekshiramiz 👇",
            reply_markup=_location_keyboard(),
        )
        return

    if _is_injection(message.text):
        await message.answer(
            "Men faqat SIM karta bo'yicha yordam beraman 😊",
            reply_markup=_stage_keyboard(stage),
        )
        return

    # Operator nomini yozsa — darhol tarifga (AI'siz, tez)
    op_id = _detect_operator(message.text)
    if op_id and (stage == "operator" or stage.startswith("tariff:")):
        op = OPERATORS[op_id]
        await state.update_data(ai_stage=f"tariff:{op_id}", sel_operator=op_id)
        await message.answer(
            f"✅ {op['emoji']} <b>{op['name']}</b> tanlandi!\n\nQaysi tarifni xohlaysiz? 👇",
            reply_markup=_stage_keyboard(f"tariff:{op_id}"),
        )
        return

    # Operator/tarif/delivery bosqichlari — AI maslahat (sof matn)
    history: list = data.get("ai_history", [])
    history.append({"role": "user", "content": message.text})

    thinking = await message.answer("💭 Bir lahza...")
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        ai_text = await _ai_reply(history)
        if not ai_text:
            ai_text = _fallback_text(stage)
        history.append({"role": "assistant", "content": ai_text})
        if len(history) > 12:
            history = history[-12:]
        await state.update_data(ai_history=history)
        await _typewriter(message, ai_text, _stage_keyboard(stage), existing_msg=thinking)
    except anthropic.AuthenticationError:
        await thinking.edit_text("⚠️ AI kalit xato. Admin bilan bog'laning.")
    except anthropic.RateLimitError:
        await thinking.edit_text("⚠️ AI band. Bir oz kutib qayta urinib ko'ring.")
    except Exception:
        try:
            await thinking.edit_text(_fallback_text(stage), reply_markup=_stage_keyboard(stage))
        except Exception:
            await message.answer(_fallback_text(stage), reply_markup=_stage_keyboard(stage))


# ─── GPS LOKATSIYA HANDLERI ──────────────────────────────────────

@router.message(AIState.chatting, F.location)
async def handle_location(message: Message, state: FSMContext):
    data = await state.get_data()
    lat = message.location.latitude
    lon = message.location.longitude
    zone = _check_zone(lat, lon)

    if not zone:
        office = settings_store.get_office()
        distance = _haversine(lat, lon, office["lat"], office["lon"])
        await message.answer(
            f"📍 Joylashuvingiz yetkazish hududidan biroz uzoqroqda "
            f"(taxminan {distance:.0f} km).\n\n"
            f"Lekin buyurtmangizni shaxsan ko'rib chiqamiz! 🤝\n"
            f"👨‍💼 Admin tez orada bog'lanadi: {ADMIN_CONTACT}",
            reply_markup=ReplyKeyboardRemove(),
        )
        name = data.get("user_name", message.from_user.first_name or "Mijoz")
        phone = data.get("customer_phone", "—")
        op_id = data.get("sel_operator", "")
        operator = OPERATORS.get(op_id, {}).get("name", "—")
        username = message.from_user.username
        uname = f"@{username}" if username else f"ID: {message.from_user.id}"
        maps = f"https://maps.google.com/?q={lat},{lon}"
        admin_text = (
            "🟠 <b>HUDUD TASHQARISIDAGI BUYURTMA</b> 🤖 AI\n\n"
            f"👤 Mijoz: {name} ({uname})\n"
            f"📞 Tel: {phone}\n"
            f"📡 Operator: {operator}\n"
            f"📍 Masofa: ~{distance:.1f} km (ruxsat {office['radius_km']:.0f} km)\n"
            f"🗺 Lokatsiya: {maps}\n\n"
            "Mijoz bilan bog'lanib, qo'lda kelishishingiz mumkin."
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(admin_id, admin_text)
                await message.bot.send_location(admin_id, latitude=lat, longitude=lon)
            except Exception:
                pass
        await state.update_data(ai_stage="done")
        return

    await state.update_data(region=zone)
    await message.answer(f"✅ Joylashuv tasdiqlandi: <b>{zone}</b>", reply_markup=ReplyKeyboardRemove())

    # Buyurtmani KOD orqali rasmiylashtiramiz (AI'siz, ishonchli)
    data = await state.get_data()
    try:
        order_num = await _place_order(data, message.from_user.id, message.bot)
        tariff = next((t for t in TARIFFS.get(data.get("sel_operator", ""), [])
                       if t["id"] == data.get("sel_tariff", "")), None)
        dtype = DELIVERY_TYPES.get(data.get("sel_delivery", "ish_vaqti"), {})
        tariff_name = tariff["name"] if tariff else "—"
        await state.update_data(ai_stage="done")
        await message.answer(
            f"🎉 <b>Buyurtmangiz qabul qilindi! #{order_num}</b>\n\n"
            f"📦 Tarif: <b>{tariff_name}</b>\n"
            f"🚀 Yetkazish: <b>{dtype.get('desc', '—')}</b>\n"
            f"📍 Hudud: <b>{zone}</b>\n"
            f"📱 SIM raqam: kuryer kelganda tanlaysiz\n\n"
            "⏱ Kuryer tez orada bog'lanadi. Rahmat! 🙏",
            reply_markup=_stage_keyboard("done"),
        )
    except Exception:
        await message.answer("⚠️ Buyurtmani saqlashda xatolik. /start bosib qayta urinib ko'ring.")


# ─── TUGMA CALLBACK HANDLERLARI ─────────────────────────────────

@router.callback_query(AIState.chatting, F.data.startswith("ai_op_"))
async def ai_pick_operator(callback: CallbackQuery, state: FSMContext):
    op_id = callback.data.replace("ai_op_", "")
    op = OPERATORS.get(op_id)
    if not op:
        return await callback.answer("Xatolik.", show_alert=True)

    await state.update_data(ai_stage=f"tariff:{op_id}", sel_operator=op_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(f"{op['emoji']} Tanlandi!")
    await callback.message.answer(
        f"✅ {op['emoji']} <b>{op['name']}</b> tanlandi!\n\nQaysi tarifni xohlaysiz? 👇",
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

    await state.update_data(ai_stage="delivery", sel_tariff=tariff_id, sel_operator=op_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("📦 Tanlandi!")
    promo_line = ""
    if tariff["price"] >= PROMO_1PLUS1_MIN_PRICE:
        promo_line = f"{PROMO_1PLUS1_TEXT}\n\n"
    await callback.message.answer(
        f"✅ <b>{tariff['name']}</b> — {tariff['price']:,} so'm/oy\n\n"
        f"{promo_line}"
        "Yetkazib berish turini tanlang 👇",
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
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(f"{dtype['emoji']} Tanlandi!")
    await callback.message.answer(
        f"✅ {dtype['emoji']} <b>{dtype['name']}</b> ({dtype['desc']}) — {price_text}\n\n"
        "📞 Telefon raqamingizni yozing:\n<i>Masalan: +998901234567</i>",
        reply_markup=_stage_keyboard("phone"),
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


# ─── UMUMIY CALLBACK HANDLERLARI ────────────────────────────────

@router.callback_query(F.data == "open_ai_chat")
async def open_ai_chat(callback: CallbackQuery, state: FSMContext):
    if not ANTHROPIC_API_KEY:
        await callback.answer("AI xizmati hozircha mavjud emas.", show_alert=True)
        return
    await start_ai_chat(callback, state)


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
