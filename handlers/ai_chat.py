import math
import random
import anthropic
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatAction

from states import AIState
from data import OPERATORS, TARIFFS
from config import ANTHROPIC_API_KEY, ADMIN_IDS, DELIVERY_PRICES, DEFAULT_DELIVERY_PRICE, DELIVERY_TYPES
from sheets_handler import save_order
import numbers_db

router = Router()

# ─── YETKAZIB BERISH HUDUDLARI ──────────────────────────────────
# (lat, lon, radius_km) — aniq koordinatalarni yangilang
DELIVERY_ZONES = [
    ("Qo'vchin shaharcha", 41.2800, 69.5500, 5.0),
    ("Shirkent shaharcha", 41.3500, 69.9800, 5.0),
]

_ai_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url="https://aiprimetech.io",
        )
    return _ai_client


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _check_zone(lat: float, lon: float) -> str | None:
    for name, zlat, zlon, radius in DELIVERY_ZONES:
        if _haversine(lat, lon, zlat, zlon) <= radius:
            return name
    return None


def _build_system_prompt() -> str:
    tariff_lines = []
    for op_id, op in OPERATORS.items():
        for t in TARIFFS.get(op_id, []):
            items = [x.strip() for x in t["desc"].split("•") if x.strip()]
            tariff_lines.append(
                f"{op['emoji']} {op['name']} | id:{t['id']} | {t['name']} | "
                f"{t['price']:,} so'm/oy | " + " | ".join(items)
            )
    zones = " va ".join(z[0] for z in DELIVERY_ZONES)
    return (
        'Sen "Texnoset" SIM karta xizmatining eng professional savdo-konsultantisan. Ismingiz Suxrob.\n\n'
        "MAQSAD: Har bir mijozni SIM karta buyurtma berishga undash — issiq, professional, natijali.\n\n"
        "SAVDO USLUBI:\n"
        "- Do'stona o'zbek tilida, emoji qo'sh ✅\n"
        "- 2-3 jumladan oshirma\n"
        "- Bir vaqtda 1 ta savol\n"
        "- Ehtiyojga qarab 1-2 tarifni tavsiya qil\n"
        "- Narxni rag'batlantirib ko'rsat: 'Oyiga 70,000 — kuniga atiga 2,300 so'm!'\n"
        "- E'tirozga: afzalliklarni ta'kidla\n"
        "- Shoshiltir: 'Bu raqamlar kam qoldi, hozir band qilib qo'ying!'\n\n"
        "BUYURTMA KETMA-KETLIGI:\n"
        "1. Salom + darhol ehtiyojini so'ra (ism so'rama)\n"
        "2. Mos tarifni tavsiya qil, roziligini ol\n"
        "3. Telefon raqamini so'ra\n"
        "4. Yetkazish tezligini so'ra va tushuntir (quyida)\n"
        "5. request_location chaqir (GPS lokatsiya tekshirish uchun)\n"
        "6. Hamma ma'lumotni qisqacha takrorla va tasdiqlat\n"
        "7. place_order chaqir\n"
        "SIM raqam tanlash kuryer yetib kelganida bo'ladi — hozir so'rama.\n\n"
        "YETKAZIB BERISH TARIFLARI (yumshoq, chiroyli tushuntir):\n"
        "⚡ tezkor — '1 soat ichida eshigingizga yetkazamiz, shoshilinch bo'lsa ideal!' — 10 000 so'm\n"
        "🚗 standart — '2 soat ichida qulay narxda' — 5 000 so'm\n"
        "🕐 ish_vaqti — 'Bugun ish vaqtida (12 soat ichida) — mutlaqo BEPUL! 🎁' — 0 so'm\n"
        "Mijozga 3 variantni iliq tushuntir. Tejamkor bo'lsa ish_vaqti ni, shoshilsa tezkor ni tavsiya qil.\n\n"
        "MUHIM: Yetkazib berish FAQAT " + zones + " da amalga oshiriladi.\n"
        "Boshqa hudud so'rasa: 'Kechirasiz, hozircha faqat " + zones + " ga yetkazamiz' de.\n\n"
        "MAVJUD TARIFLAR:\n"
        + "\n".join(tariff_lines)
        + "\n\n"
        "Faqat SIM karta va buyurtma haqida gaplash."
    )


SYSTEM_PROMPT = _build_system_prompt()

TOOLS = [
    {
        "name": "request_location",
        "description": (
            "Mijozdan GPS lokatsiya so'rash. "
            "Yetkazib berish hududi tekshiriladi. "
            "Manzil yig'ish bosqichida chaqirish kerak."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "place_order",
        "description": "Barcha ma'lumotlar tasdiqlangandan keyin buyurtma yaratish",
        "input_schema": {
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "tariff_id": {"type": "string"},
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
                "region": {"type": "string", "description": "GPS orqali tasdiqlangan hudud nomi"},
                "delivery_type": {
                    "type": "string",
                    "enum": ["tezkor", "standart", "ish_vaqti"],
                    "description": "Yetkazish tezligi: tezkor (1 soat, 10000), standart (2 soat, 5000), ish_vaqti (12 soat, bepul)",
                },
            },
            "required": ["operator_id", "tariff_id", "customer_phone", "region", "delivery_type"],
        },
    },
]


def _serialize_content(blocks) -> list:
    result = []
    for b in blocks:
        if b.type == "text":
            result.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            result.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return result


async def _execute_tool(name: str, inputs: dict, user_id: int, bot, ctx: dict) -> str:
    if name == "get_available_numbers":
        op_id = inputs.get("operator_id", "")
        numbers = numbers_db.get_available(op_id)
        if not numbers:
            return "Bu operator uchun hozircha mavjud raqam yo'q."
        return OPERATORS[op_id]["name"] + " uchun mavjud raqamlar: " + ", ".join(numbers)

    if name == "request_location":
        ctx["waiting_for_location"] = True
        return "Mijozdan GPS lokatsiya kutilmoqda."

    if name == "place_order":
        op_id = inputs.get("operator_id", "")
        tariff_id = inputs.get("tariff_id", "")
        sim_number = "pending"
        customer_name = inputs.get("customer_name", "") or ctx.get("user_name", "Mehmon")
        customer_phone = inputs.get("customer_phone", "")
        region = inputs.get("region", "")
        dtype_key = inputs.get("delivery_type", "ish_vaqti")

        tariff = next((t for t in TARIFFS.get(op_id, []) if t["id"] == tariff_id), None)
        if not tariff:
            tariff = next(
                (t for t in TARIFFS.get(op_id, []) if tariff_id.lower() in t["name"].lower()),
                (TARIFFS.get(op_id) or [{}])[0],
            )

        operator = OPERATORS.get(op_id, {"name": op_id})
        dtype = DELIVERY_TYPES.get(dtype_key, DELIVERY_TYPES["ish_vaqti"])
        delivery_type_price = dtype["price"]
        delivery_type_name = f"{dtype['emoji']} {dtype['name']} ({dtype['desc']})"
        tariff_price = tariff.get("price", 0) if tariff else 0
        tariff_name = tariff.get("name", tariff_id) if tariff else tariff_id
        total = tariff_price + delivery_type_price

        order_num = await save_order({
            "name": customer_name,
            "user_id": user_id,
            "contact_phone": customer_phone,
            "operator_name": operator["name"],
            "tariff_name": tariff_name,
            "sim_number": sim_number,
            "region": region,
            "delivery_price": delivery_type_price,
            "delivery_type_name": delivery_type_name,
            "tariff_price": tariff_price,
        })
        if order_num is None:
            order_num = random.randint(1000, 9999)

        ctx["order_placed"] = True

        admin_text = (
            f"🆕 <b>Yangi buyurtma #{order_num}</b> 🤖 AI orqali\n\n"
            f"👤 <b>Mijoz:</b> {customer_name}\n"
            f"📞 <b>Tel:</b> <code>{customer_phone}</code>\n"
            f"📡 <b>Operator:</b> {operator['name']}\n"
            f"📦 <b>Tarif:</b> {tariff_name} — {tariff_price:,} so'm/oy\n"
            f"📱 <b>Raqam:</b> kuryer kelganida tanlanadi\n"
            f"📍 <b>Hudud:</b> {region}\n"
            f"🚀 <b>Yetkazish:</b> {delivery_type_name} — {delivery_type_price:,} so'm\n"
            f"💰 <b>Jami:</b> {total:,} so'm"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception:
                pass

        return f"BUYURTMA_OK|{order_num}|{sim_number}"

    return "Noma'lum amal."


async def _run_ai_loop(history: list, user_id: int, bot, ctx: dict) -> tuple[str, list]:
    client = _get_client()
    for _ in range(8):
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=history,
            tools=TOOLS,
        )
        history.append({"role": "assistant", "content": _serialize_content(resp.content)})

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    result = await _execute_tool(block.name, block.input, user_id, bot, ctx)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                    if ctx.get("waiting_for_location"):
                        # Lokatsiya kutilmoqda — loop to'xtaydi, foydalanuvchi yuborgunicha
                        ai_text = next((b.text for b in resp.content if b.type == "text"), "")
                        history.append({"role": "user", "content": tool_results})
                        return ai_text, history
            history.append({"role": "user", "content": tool_results})
        else:
            ai_text = next((b.text for b in resp.content if b.type == "text"), "")
            return ai_text, history

    return "Qayta urinib ko'ring.", history


def _location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyamni yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _inline_keyboard(order_placed: bool = False):
    b = InlineKeyboardBuilder()
    if order_placed:
        b.button(text="🔄 Yangi buyurtma", callback_data="ai_restart")
    b.button(text="❌ Chiqish", callback_data="ai_exit")
    b.adjust(1)
    return b.as_markup()


async def start_ai_chat(target, state: FSMContext):
    await state.clear()
    await state.set_state(AIState.chatting)

    if isinstance(target, Message):
        user_name = target.from_user.first_name or "Mehmon"
    else:
        user_name = target.from_user.first_name or "Mehmon"

    await state.update_data(ai_history=[], waiting_for_location=False, user_name=user_name)
    text = (
        f"Assalomu alaykum! 👋 Men Suxrob — \"Texnoset\" SIM karta xizmatidan.\n\n"
        "Sizga eng mos SIM karta va tarif topishda yordam beraman 📱\n\n"
        "Qanday tarif kerak — ko'proq internet, arzon, yoki cheksiz qo'ng'iroqmi? 😊"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=_inline_keyboard())
    else:
        await target.message.edit_text(text, reply_markup=_inline_keyboard())
        await target.answer()


# ─── ASOSIY XABAR HANDLERI ──────────────────────────────────────

@router.message(AIState.chatting, F.text)
async def handle_ai_message(message: Message, state: FSMContext):
    data = await state.get_data()
    history: list = data.get("ai_history", [])
    user_name: str = data.get("user_name", message.from_user.first_name or "Mehmon")
    history.append({"role": "user", "content": message.text})

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    ctx = {"waiting_for_location": False, "order_placed": False, "user_name": user_name}

    try:
        ai_text, history = await _run_ai_loop(history, message.from_user.id, message.bot, ctx)
        if not ai_text:
            ai_text = "Uzr, tushunmadim. Boshqacha yozing."

        if len(history) > 24:
            history = history[-24:]

        await state.update_data(
            ai_history=history,
            waiting_for_location=ctx["waiting_for_location"],
        )

        if ctx["waiting_for_location"]:
            await message.answer(ai_text, reply_markup=_location_keyboard())
        else:
            await message.answer(ai_text, reply_markup=_inline_keyboard(ctx["order_placed"]))

    except anthropic.AuthenticationError:
        await message.answer("⚠️ AI kalit xato. Admin bilan bog'laning.")
    except anthropic.RateLimitError:
        await message.answer("⚠️ AI band. Bir oz kutib qayta urinib ko'ring.")
    except Exception:
        await message.answer("⚠️ Xatolik. /start bosib qayta boshlang.")


# ─── GPS LOKATSIYA HANDLERI ──────────────────────────────────────

@router.message(AIState.chatting, F.location)
async def handle_location(message: Message, state: FSMContext):
    data = await state.get_data()
    lat = message.location.latitude
    lon = message.location.longitude
    zone = _check_zone(lat, lon)

    if not zone:
        zones_str = " va ".join(z[0] for z in DELIVERY_ZONES)
        await message.answer(
            f"❌ Kechirasiz, hozircha yetkazib berish faqat <b>{zones_str}</b> da amalga oshiriladi.\n\n"
            "Siz shu hududlarda yashamaysizmi? Agar xato bo'lsa, qayta urinib ko'ring.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer(f"✅ Joylashuv tasdiqlandi: <b>{zone}</b>", reply_markup=ReplyKeyboardRemove())

    history: list = data.get("ai_history", [])
    history.append({"role": "user", "content": f"Mening hududim tasdiqlandi: {zone}"})

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    ctx = {"waiting_for_location": False, "order_placed": False, "user_name": data.get("user_name", message.from_user.first_name or "Mehmon")}

    try:
        ai_text, history = await _run_ai_loop(history, message.from_user.id, message.bot, ctx)
        if not ai_text:
            ai_text = "Zo'r! Davom etamiz."

        if len(history) > 24:
            history = history[-24:]

        await state.update_data(ai_history=history, waiting_for_location=False)
        await message.answer(ai_text, reply_markup=_inline_keyboard(ctx["order_placed"]))

    except Exception:
        await message.answer("⚠️ Xatolik. /start bosib qayta boshlang.")


# ─── CALLBACK HANDLERLAR ────────────────────────────────────────

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
