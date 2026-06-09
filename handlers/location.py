from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import confirm_keyboard, remove_keyboard, delivery_type_keyboard
from utils import detect_region, get_delivery_price, build_order_summary
from sheets_handler import save_order
from config import DELIVERY_TYPES, ADMIN_IDS, ADMIN_CONTACT
import settings_store
import math

router = Router()


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


async def _redirect_to_admin(message: Message, state: FSMContext, lat: float, lon: float, distance: float):
    """Mijoz hudud tashqarisida — adminga xabar beradi va mijozni yo'naltiradi."""
    data = await state.get_data()
    office = settings_store.get_office()

    await message.answer(
        f"📍 Sizning joylashuvingiz yetkazish hududidan biroz uzoqroqda "
        f"(taxminan {distance:.0f} km, hudud {office['radius_km']:.0f} km).\n\n"
        f"Lekin xavotir olmang — buyurtmangizni shaxsan ko'rib chiqamiz! 🤝\n"
        f"👨‍💼 Admin tez orada siz bilan bog'lanadi: {ADMIN_CONTACT}",
        reply_markup=remove_keyboard(),
    )

    # Adminlarga xabar — mijoz ma'lumotlari bilan
    name = data.get("name", message.from_user.first_name or "Mijoz")
    phone = data.get("contact_phone", "—")
    operator = data.get("operator_name", "—")
    tariff = data.get("tariff_name", "—")
    username = message.from_user.username
    uname = f"@{username}" if username else f"ID: {message.from_user.id}"
    maps = f"https://maps.google.com/?q={lat},{lon}"

    admin_text = (
        "🟠 <b>HUDUD TASHQARISIDAGI BUYURTMA</b>\n\n"
        f"👤 Mijoz: {name} ({uname})\n"
        f"📞 Tel: {phone}\n"
        f"📡 Operator: {operator}\n"
        f"📦 Tarif: {tariff}\n"
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

    await state.clear()


@router.message(OrderState.sharing_location, F.location)
async def receive_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude

    office = settings_store.get_office()
    distance = _haversine(lat, lon, office["lat"], office["lon"])
    if distance > office["radius_km"]:
        await _redirect_to_admin(message, state, lat, lon, distance)
        return

    region = office["zone_name"]
    delivery_price = 0

    await state.update_data(
        region=region,
        delivery_price=delivery_price,
        latitude=lat,
        longitude=lon,
    )
    await state.set_state(OrderState.choosing_delivery_type)

    await message.answer(
        f"✅ <b>Joylashuv tasdiqlandi:</b> {region}\n\n"
        "🚀 <b>Yetkazib berish tezligini tanlang:</b>\n\n"
        "⚡ <b>Tezkor</b> — 1 soat ichida — <b>10 000 so'm</b>\n"
        "🚗 <b>Standart</b> — 2 soat ichida — <b>5 000 so'm</b>\n"
        "🕐 <b>Ish vaqtida</b> — 12 soat ichida — <b>Bepul</b> 🎁\n\n"
        "💡 <i>Ish vaqti: 09:00 – 18:00, dushanba–shanba</i>",
        reply_markup=delivery_type_keyboard(),
    )


@router.callback_query(OrderState.choosing_delivery_type, F.data.startswith("dtype_"))
async def choose_delivery_type(callback: CallbackQuery, state: FSMContext):
    dtype_key = callback.data.replace("dtype_", "")
    dtype = DELIVERY_TYPES.get(dtype_key)
    if not dtype:
        return await callback.answer("Xatolik.", show_alert=True)

    data = await state.get_data()
    base_delivery = data.get("delivery_price", 0)
    delivery_type_price = dtype["price"]
    total_delivery = base_delivery + delivery_type_price

    await state.update_data(
        delivery_type_key=dtype_key,
        delivery_type_name=f"{dtype['emoji']} {dtype['name']} ({dtype['desc']})",
        delivery_type_price=delivery_type_price,
        delivery_price=total_delivery,
    )
    await state.set_state(OrderState.confirming_order)

    user_data = await state.get_data()
    summary = build_order_summary(user_data)

    await callback.message.edit_text(
        f"✅ <b>Yetkazish turi tanlandi:</b> {dtype['emoji']} {dtype['desc']}\n\n"
        f"{summary}\n\n"
        "Buyurtmani tasdiqlaysizmi?",
        reply_markup=confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(OrderState.confirming_order, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    from config import ADMIN_IDS

    user_data = await state.get_data()
    user_data["user_id"] = callback.from_user.id

    saved = await save_order(user_data)

    dtype_name = user_data.get("delivery_type_name", "—")
    await callback.message.edit_text(
        "🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"📍 Hudud: <b>{user_data.get('region')}</b>\n"
        f"🚀 Yetkazish: <b>{dtype_name}</b>\n"
        f"📱 Raqam: kuryer kelganida tanlanadi\n\n"
        "⏱ Kuryer siz bilan tez orada bog'lanadi.\n"
        "📞 Savollar uchun: /start → Aloqa\n\n"
        "✅ Rahmat! Xaridingiz uchun minnatdormiz 🙏"
    )

    try:
        bot = callback.bot
        summary = build_order_summary(user_data)
        username = callback.from_user.username or "Noma'lum"
        admin_text = (
            f"🔔 <b>YANGI BUYURTMA!</b>\n\n"
            f"👤 Foydalanuvchi: @{username} "
            f"(ID: {callback.from_user.id})\n\n"
            f"{summary}"
        )
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, admin_text)
    except Exception:
        pass

    await state.clear()
    await callback.answer("✅ Buyurtma qabul qilindi!")


@router.callback_query(OrderState.confirming_order, F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Buyurtma bekor qilindi.\n\n"
        "Qaytadan boshlash uchun /start bosing."
    )
    await callback.answer("Bekor qilindi")


@router.callback_query(OrderState.choosing_delivery_type, F.data == "cancel_order")
async def cancel_delivery_type(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Buyurtma bekor qilindi.\n\n"
        "Qaytadan boshlash uchun /start bosing."
    )
    await callback.answer("Bekor qilindi")
