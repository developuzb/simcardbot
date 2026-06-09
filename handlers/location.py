from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import confirm_keyboard, remove_keyboard, delivery_type_keyboard
from utils import detect_region, get_delivery_price, build_order_summary
from sheets_handler import save_order
from config import DELIVERY_TYPES

router = Router()


@router.message(OrderState.sharing_location, F.location)
async def receive_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude

    region = detect_region(lat, lon)
    delivery_price = get_delivery_price(region)

    await state.update_data(
        region=region,
        delivery_price=delivery_price,
        latitude=lat,
        longitude=lon,
    )
    await state.set_state(OrderState.choosing_delivery_type)

    await message.answer("Klaviatura o'chirildi.", reply_markup=remove_keyboard())
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
